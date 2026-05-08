from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qs, urlparse

import requests


class FeishuError(RuntimeError):
    def __init__(self, code: str, message: str, *, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.code = code
        self.details = details or {}


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
            raise FeishuError("feishu_api_error", payload.get("msg") or "飞书接口调用失败", details=payload)
        return payload.get("data") or {}

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
        data = self._get(
            f"/sheets/v2/spreadsheets/{spreadsheet_token}/values/{sheet_id}!1:1",
        )
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
            raise FeishuError("feishu_api_error", payload.get("msg") or "多维表格写入失败", details=payload)
        return payload.get("data") or {}

    def append_sheet_records(
        self,
        spreadsheet_token: str,
        sheet_id: str,
        fields: list[dict[str, Any]],
        rows: list[dict[str, Any]],
    ) -> dict[str, Any]:
        ordered_names = [field["field_name"] for field in sorted(fields, key=lambda item: item["column_index"])]
        values = [[row.get(name, "") for name in ordered_names] for row in rows]
        response = self.session.post(
            f"{self.base_url}/sheets/v2/spreadsheets/{spreadsheet_token}/values_append",
            headers=self._headers(),
            json={
                "valueRange": {
                    "range": f"{sheet_id}!A:A",
                    "values": values,
                }
            },
            timeout=30,
        )
        payload = response.json()
        if payload.get("code") != 0:
            raise FeishuError("feishu_api_error", payload.get("msg") or "电子表格写入失败", details=payload)
        return payload.get("data") or {}


def choose_table(tables: list[dict[str, Any]], selected_id: str | None) -> dict[str, Any]:
    if selected_id:
        for table in tables:
            if selected_id in {table.get("table_id"), table.get("sheet_id"), table.get("id")}:
                return table
        raise FeishuError("table_not_found", "链接中指定的子表不存在", details={"selected_id": selected_id})
    if len(tables) == 1:
        return tables[0]
    raise FeishuError("ambiguous_table_id", "当前链接包含多个子表，请选择一个子表", details={"available_tables": tables})
