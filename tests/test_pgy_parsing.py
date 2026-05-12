from rpa_mcp_sync.creator_store import normalize_creator, parse_number
from rpa_mcp_sync.pgy_browser import _number_from_text, _parse_row_text


def test_parse_number_handles_pgy_follower_formats():
    assert parse_number("1.2 万") == 12000
    assert parse_number("3,456+") == 3456
    assert parse_number("8.4w") == 84000
    assert parse_number("--") is None
    assert _number_from_text("粉丝数 2.6 万+") == 26000


def test_parse_row_text_prefers_table_follower_value_over_position_guess():
    text = "\n".join(
        [
            "表头映射达人",
            "北京",
            "教育",
            "42%",
            "1688",
            "98",
            "¥",
            "3500",
        ]
    )

    creator = _parse_row_text(
        text,
        "https://pgy.xiaohongshu.com/solar/pre-trade/note/kol",
        table_payload={
            "raw_table": {"博主名称": "表头映射达人", "粉丝数": "2.3 万", "阅读中位数（日常）": "1688"},
            "nickname": "表头映射达人",
            "followers_count": "2.3 万",
            "daily_read_median": "1688",
        },
    )

    assert creator is not None
    assert creator["followers_count"] == 23000
    assert creator["daily_read_median"] == "1688"
    assert creator["raw_payload"]["raw_table"]["粉丝数"] == "2.3 万"


def test_normalize_creator_keeps_correct_table_follower_count():
    creator = normalize_creator(
        {
            "nickname": "入库粉丝数达人",
            "followers_count": "2.3 万",
            "quote_price": "¥3,500",
        },
        "pytest_pgy_parse",
    )

    assert creator["followers_count"] == 23000
    assert creator["quote_price"] == 3500
