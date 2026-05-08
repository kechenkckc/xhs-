import pytest

from rpa_mcp_sync.feishu import FeishuError, choose_table, parse_feishu_url


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
