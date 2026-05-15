import pytest

from rpa_mcp_sync.feishu import FeishuClient, FeishuError, choose_table, parse_feishu_url, permission_details


def test_parse_wiki_sheet_url():
    target = parse_feishu_url(
        "https://example.feishu.cn/wiki/wikiToken123?renamingWikiNode=false&sheet=sheet123"
    )
    assert target.resource_type == "sheet"
    assert target.token == "wikiToken123"
    assert target.table_id == "sheet123"
    assert target.source == "wiki_url"


def test_parse_bitable_url():
    target = parse_feishu_url("https://example.feishu.cn/base/abc123?table=tbl456")
    assert target.resource_type == "bitable"
    assert target.token == "abc123"
    assert target.table_id == "tbl456"


def test_choose_table_requires_selection_when_many():
    with pytest.raises(FeishuError) as exc:
        choose_table([{"sheet_id": "a"}, {"sheet_id": "b"}], None)
    assert exc.value.code == "ambiguous_table_id"
    assert exc.value.details["available_tables"]


class DummyResponse:
    def __init__(self, payload):
        self.payload = payload

    def json(self):
        return self.payload


class DummySession:
    def __init__(self, payload):
        self.payload = payload
        self.last_get_url = ""
        self.last_post_url = ""
        self.last_post_json = None

    def get(self, url, **kwargs):
        self.last_get_url = url
        return DummyResponse(self.payload)

    def post(self, url, **kwargs):
        self.last_post_url = url
        self.last_post_json = kwargs.get("json")
        return DummyResponse(self.payload)


def test_list_sheet_fields_reads_header_with_a1_range():
    session = DummySession({"code": 0, "data": {"valueRange": {"values": [["达人昵称", "粉丝数"]]}}})
    client = FeishuClient("cli_test", "secret", session=session)
    client._tenant_access_token = "token"

    fields = client.list_sheet_fields("spreadsheetToken", "sheet123")

    assert session.last_get_url.endswith("/sheets/v2/spreadsheets/spreadsheetToken/values/sheet123!A1:ZZ1")
    assert fields == [
        {"field_name": "达人昵称", "column_index": 0},
        {"field_name": "粉丝数", "column_index": 1},
    ]


def test_list_sheet_fields_translates_range_error():
    session = DummySession({"code": 99991663, "msg": "validate RangeVal fail"})
    client = FeishuClient("cli_test", "secret", session=session)
    client._tenant_access_token = "token"

    with pytest.raises(FeishuError) as exc:
        client.list_sheet_fields("spreadsheetToken", "sheet123")

    assert exc.value.code == "feishu_api_error"
    assert "读取飞书电子表格表头失败" in str(exc.value)


def test_append_sheet_records_classifies_write_permission_error():
    session = DummySession({"code": 91403, "msg": "Forbidden", "data": {}})
    client = FeishuClient("cli_test", "secret", session=session)
    client._tenant_access_token = "token"

    with pytest.raises(FeishuError) as exc:
        client.append_sheet_records(
            "spreadsheetToken",
            "sheet123",
            [{"field_name": "达人昵称", "column_index": 0}],
            [{"达人昵称": "测试达人"}],
        )

    assert exc.value.code == "sheet_write_permission_denied"
    assert "写入权限不足" in str(exc.value)
    assert exc.value.details["required_scope"] == "sheets:spreadsheet:write_only"
    assert exc.value.details["write_ok"] is False


def test_append_sheet_records_uses_explicit_a1_range():
    session = DummySession({"code": 0, "data": {"updates": {"updatedRows": 1}}})
    client = FeishuClient("cli_test", "secret", session=session)
    client._tenant_access_token = "token"

    client.append_sheet_records(
        "spreadsheetToken",
        "sheet123",
        [
            {"field_name": "序号", "column_index": 0},
            {"field_name": "达人昵称", "column_index": 1},
            {"field_name": "推荐理由", "column_index": 2},
        ],
        [{"序号": 1, "达人昵称": "测试达人", "推荐理由": "连接测试"}],
    )

    assert session.last_post_json["valueRange"]["range"] == "sheet123!A1:C1"


def test_upsert_bitable_records_updates_existing_by_creator_id():
    class BitableSession:
        def __init__(self):
            self.put_calls = []
            self.post_calls = []

        def get(self, url, **kwargs):
            if url.endswith("/records"):
                return DummyResponse({"code": 0, "data": {"items": [{"record_id": "rec1", "fields": {"达人ID": "kol-1"}}]}})
            return DummyResponse({"code": 0, "data": {}})

        def put(self, url, **kwargs):
            self.put_calls.append((url, kwargs.get("json")))
            return DummyResponse({"code": 0, "data": {"record": {"record_id": "rec1"}}})

        def post(self, url, **kwargs):
            self.post_calls.append((url, kwargs.get("json")))
            return DummyResponse({"code": 0, "data": {"records": [{"record_id": "rec2"}]}})

    session = BitableSession()
    client = FeishuClient("cli_test", "secret", session=session)
    client._tenant_access_token = "token"

    result = client.upsert_bitable_records(
        "appToken",
        "tbl1",
        [{"达人ID": "kol-1", "达人昵称": "已存在"}, {"达人ID": "kol-2", "达人昵称": "新达人"}],
    )

    assert len(result["updated"]) == 1
    assert len(result["created"]) == 1
    assert session.put_calls[0][0].endswith("/records/rec1")


def test_upsert_sheet_records_updates_existing_row_by_pgy_url():
    class SheetSession:
        def __init__(self):
            self.put_calls = []
            self.post_calls = []

        def get(self, url, **kwargs):
            if "!A2:" in url:
                return DummyResponse({"code": 0, "data": {"valueRange": {"values": [["kol-1", "https://pgy/1", "旧昵称"]]}}})
            return DummyResponse({"code": 0, "data": {}})

        def put(self, url, **kwargs):
            self.put_calls.append((url, kwargs.get("json")))
            return DummyResponse({"code": 0, "data": {"updatedRows": 1}})

        def post(self, url, **kwargs):
            self.post_calls.append((url, kwargs.get("json")))
            return DummyResponse({"code": 0, "data": {"updates": {"updatedRows": 1}}})

    session = SheetSession()
    client = FeishuClient("cli_test", "secret", session=session)
    client._tenant_access_token = "token"

    result = client.upsert_sheet_records(
        "spreadsheetToken",
        "sheet123",
        [
            {"field_name": "达人ID", "column_index": 0},
            {"field_name": "蒲公英链接", "column_index": 1},
            {"field_name": "达人昵称", "column_index": 2},
        ],
        [{"达人ID": "", "蒲公英链接": "https://pgy/1", "达人昵称": "更新昵称"}],
    )

    assert len(result["updated"]) == 1
    assert session.put_calls[0][1]["valueRange"]["range"] == "sheet123!A2:C2"


def test_ensure_sheet_field_reuses_existing_column():
    session = DummySession({"code": 0, "data": {}})
    client = FeishuClient("cli_test", "secret", session=session)
    client._tenant_access_token = "token"
    fields = [{"field_name": "达人昵称", "column_index": 0}, {"field_name": "粉丝画像截图", "column_index": 1}]

    next_fields, result = client.ensure_sheet_field("spreadsheetToken", "sheet123", fields, "粉丝画像截图")

    assert next_fields == fields
    assert result["created"] is False
    assert session.last_post_json is None


def test_ensure_sheet_field_appends_missing_column():
    class SheetSession:
        def __init__(self):
            self.put_calls = []

        def put(self, url, **kwargs):
            self.put_calls.append((url, kwargs.get("json")))
            return DummyResponse({"code": 0, "data": {"updatedRows": 1}})

        def post(self, url, **kwargs):
            return DummyResponse({"code": 0, "tenant_access_token": "token"})

    session = SheetSession()
    client = FeishuClient("cli_test", "secret", session=session)
    client._tenant_access_token = "token"

    fields, result = client.ensure_sheet_field(
        "spreadsheetToken",
        "sheet123",
        [{"field_name": "达人昵称", "column_index": 0}, {"field_name": "粉丝数", "column_index": 1}],
        "粉丝画像截图",
    )

    assert result["created"] is True
    assert fields[-1] == {"field_name": "粉丝画像截图", "column_index": 2}
    assert session.put_calls[0][1]["valueRange"]["range"] == "sheet123!C1:C1"


def test_permission_details_extracts_console_url():
    payload = {
        "code": 99991672,
        "msg": "Permission denied",
        "error": {
            "permission_violations": [{"scope": "sheets:spreadsheet:write_only"}],
            "console_url": "https://open.feishu.cn/app/cli_test/auth",
        },
    }

    details = permission_details(payload, required_scope="sheets:spreadsheet:write_only")

    assert details["console_url"] == "https://open.feishu.cn/app/cli_test/auth"
    assert details["permission_urls"] == ["https://open.feishu.cn/app/cli_test/auth"]
    assert details["permission_violations"] == [{"scope": "sheets:spreadsheet:write_only"}]
    assert details["required_scope"] == "sheets:spreadsheet:write_only"


def test_permission_details_extracts_permission_url_from_message():
    payload = {
        "code": 99991672,
        "msg": "Permission denied. open https://open.feishu.cn/app/cli_test/auth to enable scope.",
    }

    details = permission_details(payload)

    assert details["console_url"] == "https://open.feishu.cn/app/cli_test/auth"


def test_permission_details_ignores_non_feishu_permission_urls():
    payload = {
        "code": 99991672,
        "msg": "Permission denied. open http://127.0.0.1:5173/login",
        "error": {
            "console_url": "/login",
            "permission_url": "https://example.com/auth",
        },
    }

    details = permission_details(payload)

    assert "console_url" not in details
    assert "permission_urls" not in details
