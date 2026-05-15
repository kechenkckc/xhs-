from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import requests

URL_PATTERN = re.compile(r"https?://[^\s\"'<>）)]+")
FEISHU_PERMISSION_HOSTS = {"open.feishu.cn", "open.larksuite.com"}


def _is_feishu_permission_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme in {"http", "https"} and parsed.netloc in FEISHU_PERMISSION_HOSTS


class FeishuError(RuntimeError):
    def __init__(self, code: str, message: str, *, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.code = code
        self.details = details or {}


def _collect_permission_urls(value: Any) -> list[str]:
    urls: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if key in {"console_url", "permission_url", "auth_url", "open_url"} and isinstance(item, str) and item:
                urls.append(item)
            urls.extend(_collect_permission_urls(item))
    elif isinstance(value, list):
        for item in value:
            urls.extend(_collect_permission_urls(item))
    elif isinstance(value, str):
        urls.extend(URL_PATTERN.findall(value))
    return [url for url in dict.fromkeys(urls) if _is_feishu_permission_url(url)]


def _collect_permission_violations(value: Any) -> list[Any]:
    violations: list[Any] = []
    if isinstance(value, dict):
        nested = value.get("permission_violations")
        if isinstance(nested, list):
            violations.extend(nested)
        for item in value.values():
            violations.extend(_collect_permission_violations(item))
    elif isinstance(value, list):
        for item in value:
            violations.extend(_collect_permission_violations(item))
    return violations


def permission_details(payload: dict[str, Any], *, required_scope: str | None = None) -> dict[str, Any]:
    details = dict(payload)
    urls = _collect_permission_urls(payload)
    if urls:
        details["permission_urls"] = urls
        details["console_url"] = urls[0]
    violations = _collect_permission_violations(payload)
    if violations:
        details["permission_violations"] = violations
    if required_scope:
        details["required_scope"] = required_scope
    return details


def column_name(index: int) -> str:
    if index < 1:
        raise ValueError("column index is 1-based")
    name = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        name = chr(65 + remainder) + name
    return name


@dataclass(frozen=True)
class FeishuTarget:
    resource_type: str
    token: str
    table_id: str | None = None
    source: str = "direct"

    def as_dict(self) -> dict[str, Any]:
        return {
            "resource_type": self.resource_type,
            "token": self.token,
            "table_id": self.table_id,
            "source": self.source,
        }


def parse_feishu_url(url: str) -> FeishuTarget:
    parsed = urlparse(url.strip())
    parts = [p for p in parsed.path.split("/") if p]
    query = parse_qs(parsed.query)

    if not parsed.netloc.endswith(("feishu.cn", "larksuite.com")):
        raise FeishuError("invalid_feishu_url", "请输入飞书或 Lark 链接")

    def q(name: str) -> str | None:
        value = query.get(name)
        return value[0] if value else None

    if "base" in parts:
        index = parts.index("base")
        token = parts[index + 1] if len(parts) > index + 1 else ""
        return FeishuTarget("bitable", token, q("table") or q("table_id"), "base_url")

    if "sheets" in parts or "sheet" in parts:
        marker = "sheets" if "sheets" in parts else "sheet"
        index = parts.index(marker)
        token = parts[index + 1] if len(parts) > index + 1 else ""
        return FeishuTarget("sheet", token, q("sheet") or q("sheet_id"), "sheet_url")

    if "wiki" in parts:
        index = parts.index("wiki")
        token = parts[index + 1] if len(parts) > index + 1 else ""
        table_id = q("table") or q("table_id") or q("sheet") or q("sheet_id")
        hinted = "sheet" if q("sheet") or q("sheet_id") else "wiki"
        return FeishuTarget(hinted, token, table_id, "wiki_url")

    match = re.search(r"/([A-Za-z0-9]{8,})", parsed.path)
    if match:
        return FeishuTarget("unknown", match.group(1), q("table") or q("sheet"), "unknown_url")

    raise FeishuError("unsupported_feishu_url", "无法识别飞书链接中的资源标识")


class FeishuClient:
    def __init__(self, app_id: str, app_secret: str, *, session: requests.Session | None = None):
        self.app_id = app_id
        self.app_secret = app_secret
        self.session = session or requests.Session()
        self.base_url = "https://open.feishu.cn/open-apis"
        self._tenant_access_token: str | None = None

    def tenant_access_token(self) -> str:
        if self._tenant_access_token:
            return self._tenant_access_token
        response = self.session.post(
            f"{self.base_url}/auth/v3/tenant_access_token/internal",
            json={"app_id": self.app_id, "app_secret": self.app_secret},
            timeout=20,
        )
        payload = response.json()
        if payload.get("code") != 0:
            raise FeishuError("auth_failed", payload.get("msg") or "飞书鉴权失败", details=payload)
        self._tenant_access_token = payload["tenant_access_token"]
        return self._tenant_access_token

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.tenant_access_token()}"}

    def _get(self, path: str, **params: Any) -> dict[str, Any]:
        response = self.session.get(
            f"{self.base_url}{path}",
            headers=self._headers(),
            params={k: v for k, v in params.items() if v is not None},
            timeout=30,
        )
        payload = response.json()
        if payload.get("code") != 0:
            raise FeishuError("feishu_api_error", payload.get("msg") or "飞书接口调用失败", details=permission_details(payload))
        return payload.get("data") or {}

    def _translate_sheet_error(self, payload: dict[str, Any], fallback: str) -> str:
        message = str(payload.get("msg") or fallback)
        if payload.get("code") == 91403 or "Forbidden" in message:
            return "飞书表格写入权限不足：请确认当前应用已开通 Sheets 写入权限，并已被添加为该表格的可编辑协作者"
        if "RangeVal" in message or "range" in message.lower():
            return "读取飞书电子表格表头失败，请确认链接中的子表存在，且第 1 行是字段表头"
        return message

    def _sheet_write_permission_details(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            **permission_details(payload, required_scope="sheets:spreadsheet:write_only"),
            "write_ok": False,
            "fix_actions": [
                "在飞书开放平台为当前应用开通 Sheets 写入权限 sheets:spreadsheet:write_only，并发布/生效。",
                "在目标电子表格中把当前应用添加为可编辑协作者，或把应用加入该表所在知识库的可编辑成员范围。",
                "完成授权后重新点击写回飞书验证。",
            ],
        }

    def resolve_wiki_target(self, target: FeishuTarget) -> FeishuTarget:
        if target.source != "wiki_url":
            return target
        data = self._get(f"/wiki/v2/spaces/get_node", token=target.token)
        node = data.get("node") or data
        obj_type = node.get("obj_type") or target.resource_type
        obj_token = node.get("obj_token") or target.token
        if obj_type in {"bitable", "base"}:
            return FeishuTarget("bitable", obj_token, target.table_id, "wiki_node")
        if obj_type in {"sheet", "spreadsheet"}:
            return FeishuTarget("sheet", obj_token, target.table_id, "wiki_node")
        raise FeishuError("unsupported_wiki_object", f"暂不支持该飞书 Wiki 对象：{obj_type}", details=node)

    def list_bitable_tables(self, app_token: str) -> list[dict[str, Any]]:
        data = self._get(f"/bitable/v1/apps/{app_token}/tables", page_size=100)
        return data.get("items") or []

    def list_bitable_fields(self, app_token: str, table_id: str) -> list[dict[str, Any]]:
        data = self._get(f"/bitable/v1/apps/{app_token}/tables/{table_id}/fields", page_size=100)
        return data.get("items") or []

    def list_sheet_tabs(self, spreadsheet_token: str) -> list[dict[str, Any]]:
        data = self._get(f"/sheets/v3/spreadsheets/{spreadsheet_token}/sheets/query")
        return data.get("sheets") or []

    def list_sheet_fields(self, spreadsheet_token: str, sheet_id: str) -> list[dict[str, Any]]:
        # Reads the first row as field names. This method is intentionally simple:
        # callers can map returned field names to columns A, B, C...
        if not sheet_id:
            raise FeishuError("missing_sheet_id", "未找到电子表格子表 ID，无法读取字段")
        response = self.session.get(
            f"{self.base_url}/sheets/v2/spreadsheets/{spreadsheet_token}/values/{sheet_id}!A1:ZZ1",
            headers=self._headers(),
            timeout=30,
        )
        payload = response.json()
        if payload.get("code") != 0:
            raise FeishuError("feishu_api_error", self._translate_sheet_error(payload, "电子表格表头读取失败"), details=permission_details(payload))
        data = payload.get("data") or {}
        rows = (data.get("valueRange") or {}).get("values") or []
        headers = rows[0] if rows else []
        return [{"field_name": str(name), "column_index": index} for index, name in enumerate(headers) if name]

    def create_bitable_records(self, app_token: str, table_id: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
        response = self.session.post(
            f"{self.base_url}/bitable/v1/apps/{app_token}/tables/{table_id}/records/batch_create",
            headers=self._headers(),
            json={"records": [{"fields": row} for row in rows]},
            timeout=30,
        )
        payload = response.json()
        if payload.get("code") != 0:
            raise FeishuError("feishu_api_error", payload.get("msg") or "多维表格写入失败", details=permission_details(payload, required_scope="bitable:record:write"))
        return payload.get("data") or {}

    def list_bitable_records(self, app_token: str, table_id: str) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        page_token: str | None = None
        while True:
            data = self._get(
                f"/bitable/v1/apps/{app_token}/tables/{table_id}/records",
                page_size=500,
                page_token=page_token,
            )
            items.extend(data.get("items") or [])
            if not data.get("has_more"):
                break
            page_token = data.get("page_token")
        return items

    def update_bitable_record(self, app_token: str, table_id: str, record_id: str, row: dict[str, Any]) -> dict[str, Any]:
        response = self.session.put(
            f"{self.base_url}/bitable/v1/apps/{app_token}/tables/{table_id}/records/{record_id}",
            headers=self._headers(),
            json={"fields": row},
            timeout=30,
        )
        payload = response.json()
        if payload.get("code") != 0:
            raise FeishuError("feishu_api_error", payload.get("msg") or "多维表格更新失败", details=permission_details(payload, required_scope="bitable:record:write"))
        return payload.get("data") or {}

    def upsert_bitable_records(
        self,
        app_token: str,
        table_id: str,
        rows: list[dict[str, Any]],
        known_record_ids: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        known_record_ids = known_record_ids or {}
        existing = self.list_bitable_records(app_token, table_id)
        index: dict[str, str] = {}
        for item in existing:
            record_id = item.get("record_id")
            fields = item.get("fields") or {}
            if not record_id:
                continue
            for key in ("达人ID", "蒲公英链接", "达人昵称"):
                value = fields.get(key)
                if value:
                    index[f"{key}:{value}"] = record_id
        created: list[dict[str, Any]] = []
        updated: list[dict[str, Any]] = []
        for row in rows:
            creator_id = str(row.get("达人ID") or "")
            record_id = known_record_ids.get(creator_id)
            if not record_id:
                for key in ("达人ID", "蒲公英链接", "达人昵称"):
                    value = row.get(key)
                    if value and f"{key}:{value}" in index:
                        record_id = index[f"{key}:{value}"]
                        break
            if record_id:
                updated.append({"record_id": record_id, "result": self.update_bitable_record(app_token, table_id, record_id, row)})
            else:
                result = self.create_bitable_records(app_token, table_id, [row])
                new_items = result.get("records") or result.get("items") or []
                new_record_id = (new_items[0] or {}).get("record_id") if new_items else None
                created.append({"record_id": new_record_id, "result": result})
        return {"created": created, "updated": updated}

    def append_sheet_records(
        self,
        spreadsheet_token: str,
        sheet_id: str,
        fields: list[dict[str, Any]],
        rows: list[dict[str, Any]],
    ) -> dict[str, Any]:
        if not sheet_id:
            raise FeishuError("missing_sheet_id", "未找到电子表格子表 ID，无法写入记录")
        ordered_names = [field["field_name"] for field in sorted(fields, key=lambda item: item["column_index"])]
        values = [[row.get(name, "") for name in ordered_names] for row in rows]
        end_column = column_name(max(len(ordered_names), 1))
        end_row = max(len(values), 1)
        response = self.session.post(
            f"{self.base_url}/sheets/v2/spreadsheets/{spreadsheet_token}/values_append",
            headers=self._headers(),
            json={
                "valueRange": {
                    "range": f"{sheet_id}!A1:{end_column}{end_row}",
                    "values": values,
                }
            },
            timeout=30,
        )
        payload = response.json()
        if payload.get("code") != 0:
            message = self._translate_sheet_error(payload, "电子表格写入失败")
            if payload.get("code") == 91403 or "Forbidden" in str(payload.get("msg") or ""):
                raise FeishuError(
                    "sheet_write_permission_denied",
                    message,
                    details=self._sheet_write_permission_details(payload),
                )
            raise FeishuError("feishu_api_error", message, details=permission_details(payload))
        return payload.get("data") or {}

    def ensure_sheet_field(
        self,
        spreadsheet_token: str,
        sheet_id: str,
        fields: list[dict[str, Any]],
        field_name: str,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        existing = next((field for field in fields if field.get("field_name") == field_name), None)
        if existing:
            return fields, {"created": False, "field": existing}
        column_index = max([int(field.get("column_index", -1)) for field in fields] or [-1]) + 1
        column = column_name(column_index + 1)
        response = self.session.put(
            f"{self.base_url}/sheets/v2/spreadsheets/{spreadsheet_token}/values",
            headers=self._headers(),
            json={"valueRange": {"range": f"{sheet_id}!{column}1:{column}1", "values": [[field_name]]}},
            timeout=30,
        )
        payload = response.json()
        if payload.get("code") != 0:
            raise FeishuError(
                "feishu_api_error",
                self._translate_sheet_error(payload, f"电子表格追加字段失败：{field_name}"),
                details=permission_details(payload, required_scope="sheets:spreadsheet:write_only"),
            )
        field = {"field_name": field_name, "column_index": column_index}
        return [*fields, field], {"created": True, "field": field, "result": payload.get("data") or {}}

    def write_sheet_image(
        self,
        spreadsheet_token: str,
        sheet_id: str,
        cell: str,
        image_path: str,
        *,
        name: str | None = None,
    ) -> dict[str, Any]:
        path = Path(image_path)
        if not path.exists() or not path.is_file():
            raise FeishuError("image_not_found", f"粉丝画像截图文件不存在：{image_path}")
        response = self.session.post(
            f"{self.base_url}/sheets/v2/spreadsheets/{spreadsheet_token}/values_image",
            headers=self._headers(),
            json={
                "range": f"{sheet_id}!{cell}:{cell}",
                "image": list(path.read_bytes()),
                "name": name or path.name,
            },
            timeout=60,
        )
        payload = response.json()
        if payload.get("code") != 0:
            raise FeishuError(
                "feishu_api_error",
                self._translate_sheet_error(payload, "粉丝画像截图写入电子表格失败"),
                details=permission_details(payload, required_scope="sheets:spreadsheet:write_only"),
            )
        return payload.get("data") or {}

    def list_sheet_records(self, spreadsheet_token: str, sheet_id: str, fields: list[dict[str, Any]], max_rows: int = 2000) -> list[dict[str, Any]]:
        ordered = sorted(fields, key=lambda item: item["column_index"])
        if not ordered:
            return []
        end_column = column_name(len(ordered))
        response = self.session.get(
            f"{self.base_url}/sheets/v2/spreadsheets/{spreadsheet_token}/values/{sheet_id}!A2:{end_column}{max_rows}",
            headers=self._headers(),
            timeout=30,
        )
        payload = response.json()
        if payload.get("code") != 0:
            raise FeishuError("feishu_api_error", self._translate_sheet_error(payload, "电子表格记录读取失败"), details=permission_details(payload))
        data = payload.get("data") or {}
        values = (data.get("valueRange") or {}).get("values") or []
        names = [field["field_name"] for field in ordered]
        return [
            {"_row_number": index + 2, **{name: row[col_index] if col_index < len(row) else "" for col_index, name in enumerate(names)}}
            for index, row in enumerate(values)
        ]

    def update_sheet_record(
        self,
        spreadsheet_token: str,
        sheet_id: str,
        fields: list[dict[str, Any]],
        row_number: int,
        row: dict[str, Any],
    ) -> dict[str, Any]:
        ordered_names = [field["field_name"] for field in sorted(fields, key=lambda item: item["column_index"])]
        values = [[row.get(name, "") for name in ordered_names]]
        end_column = column_name(max(len(ordered_names), 1))
        response = self.session.put(
            f"{self.base_url}/sheets/v2/spreadsheets/{spreadsheet_token}/values",
            headers=self._headers(),
            json={"valueRange": {"range": f"{sheet_id}!A{row_number}:{end_column}{row_number}", "values": values}},
            timeout=30,
        )
        payload = response.json()
        if payload.get("code") != 0:
            raise FeishuError("feishu_api_error", self._translate_sheet_error(payload, "电子表格记录更新失败"), details=permission_details(payload, required_scope="sheets:spreadsheet:write_only"))
        return payload.get("data") or {}

    def upsert_sheet_records(
        self,
        spreadsheet_token: str,
        sheet_id: str,
        fields: list[dict[str, Any]],
        rows: list[dict[str, Any]],
        known_record_ids: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        known_record_ids = known_record_ids or {}
        existing = self.list_sheet_records(spreadsheet_token, sheet_id, fields)
        index: dict[str, int] = {}
        for item in existing:
            for key in ("达人ID", "蒲公英链接", "达人昵称"):
                value = item.get(key)
                if value:
                    index[f"{key}:{value}"] = int(item["_row_number"])
        created = []
        updated = []
        append_rows = []
        for row in rows:
            creator_id = str(row.get("达人ID") or "")
            record_id = known_record_ids.get(creator_id)
            row_number = int(record_id) if record_id and str(record_id).isdigit() else None
            if not row_number:
                for key in ("达人ID", "蒲公英链接", "达人昵称"):
                    value = row.get(key)
                    if value and f"{key}:{value}" in index:
                        row_number = index[f"{key}:{value}"]
                        break
            if row_number:
                updated.append({"record_id": str(row_number), "result": self.update_sheet_record(spreadsheet_token, sheet_id, fields, row_number, row), "row": row})
            else:
                append_rows.append(row)
        if append_rows:
            append_result = self.append_sheet_records(spreadsheet_token, sheet_id, fields, append_rows)
            updated_range = (
                (append_result.get("updates") or {}).get("updatedRange")
                or append_result.get("tableRange")
                or ""
            )
            match = re.search(r"![A-Z]+(\d+):", updated_range)
            first_row = int(match.group(1)) if match else None
            for offset, row in enumerate(append_rows):
                row_number = first_row + offset if first_row else None
                created.append({"record_id": str(row_number) if row_number else None, "result": append_result, "row": row})
        return {"created": created, "updated": updated}


def choose_table(tables: list[dict[str, Any]], selected_id: str | None) -> dict[str, Any]:
    if selected_id:
        for table in tables:
            if selected_id in {table.get("table_id"), table.get("sheet_id"), table.get("id")}:
                return table
        raise FeishuError("table_not_found", "链接中指定的子表不存在", details={"selected_id": selected_id})
    if len(tables) == 1:
        return tables[0]
    raise FeishuError("ambiguous_table_id", "当前链接包含多个子表，请选择一个子表", details={"available_tables": tables})
