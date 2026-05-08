from rpa_mcp_sync.creator_store import (
    get_creator,
    review_creator,
    score_creator,
    standard_feishu_rows,
    upsert_creator,
)


def test_creator_upsert_deduplicates_and_scores():
    project_id = "pytest_creators"
    first = upsert_creator(
        project_id,
        {
            "creator_id": "pytest-kol-001",
            "nickname": "测试教育达人",
            "pgy_url": "https://pgy.xiaohongshu.com/creator/test-001",
            "quote_price": 12000,
            "fans_35_plus_ratio": 0.45,
            "search_recommend_ratio": 0.55,
            "natural_cpc": 1.5,
            "natural_cpe": 9,
            "persona_tags": "高知家庭/小升初",
            "ip_city": "北京",
        },
    )
    second = upsert_creator(
        project_id,
        {
            "creator_id": "pytest-kol-duplicate",
            "nickname": "测试教育达人更新",
            "pgy_url": "https://pgy.xiaohongshu.com/creator/test-001",
            "quote_price": 11000,
            "fans_35_plus_ratio": 0.46,
        },
    )
    assert first["creator_id"] == second["creator_id"]
    scored = score_creator(project_id, second["creator_id"])
    assert scored["hard_filter_passed"] == 1
    assert scored["total_score"] >= 75


def test_review_flow_and_writeback_rows():
    project_id = "pytest_review"
    creator = upsert_creator(
        project_id,
        {
            "creator_id": "pytest-kol-002",
            "nickname": "待写回达人",
            "pgy_url": "https://pgy.xiaohongshu.com/creator/test-002",
            "quote_price": 9000,
            "fans_35_plus_ratio": 0.5,
        },
    )
    reviewed = review_creator(project_id, creator["creator_id"], "已通过", "测试通过", "pytest")
    assert reviewed["status"] == "已通过"
    rows = standard_feishu_rows(project_id, ["已通过"])
    assert any(row["达人昵称"] == "待写回达人" for row in rows)
    assert get_creator(project_id, creator["creator_id"])["reviewer"] == "pytest"
