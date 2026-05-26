import csv
import json
import threading
import time
import uuid

from rpa_mcp_sync.creator_store import connect

from rpa_mcp_sync.creator_store import (
    bulk_upsert_creators,
    cleanup_project_creator_duplicates,
    change_creator_stage,
    creator_pool,
    creator_pool_detail,
    detail_completion_actionable_missing_fields,
    detail_completion_actionable_needs,
    export_creator_pool_csv,
    generate_test_creators,
    get_creator,
    needs_detail_completion,
    quality_feishu_rows,
    review_creator,
    score_creator,
    score_project,
    score_values,
    score_values_batch_with_llm,
    save_project,
    standard_feishu_rows,
    update_creator_metrics,
    upsert_creator,
    _threshold_from_text,
)
from rpa_mcp_sync.config_store import ROOT
from rpa_mcp_sync.feishu_field_agent import analyze_field_mapping, apply_field_mapping
from rpa_mcp_sync.pgy_browser import (
    _annotate_note_cases_with_traffic_reference,
    _collect_audience_profile_chart_metrics,
    _extract_note_cases,
    _extract_performance_state,
    _merge_note_case_assets,
    _visible_text_lines,
)


def _sample_pool_fixture_rows():
    rows = []
    samples = [
        ("sample-001", "北京升学答疑赵老师", "https://pgy.xiaohongshu.com/solar/pre-trade/blogger-detail/sample-001", "教育垂类/卖货型", "教师人设/升学规划/初中学习", "北京", "12800", "预算内", "2026-05-20", "132000", "稳定", "低风险", "1.38", "8.4", "", "62%", "", "初三", "", "升学规划、错题答疑和学习工具推荐", "", "", "", "", "", "是", "", "待审核", "答疑种草", ""),
        ("sample-002", "上海精英妈妈Lisa", "https://pgy.xiaohongshu.com/solar/pre-trade/blogger-detail/sample-002", "曝光型", "高知家庭/中产家庭/亲子大孩", "上海", "17600", "预算内", "2026-05-20", "215000", "稳定", "低风险", "1.72", "11.2", "", "54%", "", "初一", "女", "国际学校转轨、家庭学习陪伴和答疑场景", "", "", "", "", "", "是", "", "待审核", "家长陪读", ""),
        ("sample-003", "海淀初中陪跑爸爸", "https://pgy.xiaohongshu.com/solar/pre-trade/blogger-detail/sample-003", "曝光型", "普通有娃家庭/初高中学习陪伴", "北京", "9800", "预算内", "2026-05-20", "88000", "稳定", "低风险", "1.61", "9.6", "", "51%", "", "初三", "男", "中考冲刺、家长陪跑和即时答疑需求", "", "", "", "", "", "是", "", "待审核", "答疑种草", ""),
        ("sample-004", "沪上物理陈老师", "https://pgy.xiaohongshu.com/solar/pre-trade/blogger-detail/sample-004", "教育垂类/卖货型", "教师人设/高知教育达人", "上海", "14200", "预算内", "2026-05-20", "156000", "稳定", "低风险", "1.44", "8.9", "", "58%", "", "高一", "", "理科学习方法、题目讲解和答疑工具", "", "", "", "", "", "是", "", "待审核", "老师讲解", ""),
        ("sample-005", "北京胡同陪读妈妈", "https://pgy.xiaohongshu.com/solar/pre-trade/blogger-detail/sample-005", "曝光型", "普通有娃家庭/话题型亲子", "北京", "11800", "预算内", "2026-05-20", "103000", "稳定", "低风险", "1.83", "12.8", "", "49%", "", "小升初", "女", "胡同家庭、小升初焦虑和学习效率", "", "", "", "", "", "是", "", "待审核", "家长陪读", ""),
        ("sample-006", "教辅测评林小北", "https://pgy.xiaohongshu.com/solar/pre-trade/blogger-detail/sample-006", "教育垂类/卖货型", "学习用品测评/教育卖货型", "杭州", "7600", "预算内", "2026-05-20", "64000", "稳定", "低风险", "1.29", "7.6", "", "44%", "", "初二", "女", "教辅工具横评、学习用品转化复盘", "", "", "", "", "", "是", "", "待审核", "测评对比", ""),
        ("sample-007", "博士妈妈讲学习", "https://pgy.xiaohongshu.com/solar/pre-trade/blogger-detail/sample-007", "教育垂类/卖货型", "高知家庭/博士父母/教育达人", "北京", "18800", "预算内", "2026-05-20", "245000", "稳定", "低风险", "1.68", "10.7", "", "57%", "", "高二", "男", "理工科家庭、学习规划和答疑工具深度种草", "", "", "", "", "", "是", "", "待审核", "学习规划", ""),
        ("sample-008", "上海中考政策观察", "https://pgy.xiaohongshu.com/solar/pre-trade/blogger-detail/sample-008", "教育垂类/卖货型", "教育政策解读/高知教育达人", "上海", "16900", "预算内", "2026-05-20", "174000", "稳定", "低风险", "1.55", "9.9", "", "60%", "", "初三", "", "中考政策、升学路径和家长决策", "", "", "", "", "", "是", "", "待审核", "升学规划", ""),
        ("sample-009", "高中数学陪练王老师", "https://pgy.xiaohongshu.com/solar/pre-trade/blogger-detail/sample-009", "教育垂类/卖货型", "教师人设/高中学习陪伴", "武汉", "10500", "预算内", "2026-05-20", "92000", "稳定", "低风险", "1.47", "8.2", "", "56%", "", "高二", "", "高中数学错题、刷题节奏和答疑效率", "", "", "", "", "", "是", "", "待审核", "老师讲解", ""),
        ("sample-010", "沪漂学区房妈妈", "https://pgy.xiaohongshu.com/solar/pre-trade/blogger-detail/sample-010", "曝光型", "普通有娃家庭/学区房话题", "上海", "13800", "预算内", "2026-05-20", "121000", "稳定", "低风险", "1.86", "14.1", "", "46%", "", "小升初", "女", "学区房蜗居、家庭教育投入和学习工具", "", "", "", "", "", "是", "", "待审核", "家长陪读", ""),
    ]
    headers = [
        "达人ID", "达人昵称", "蒲公英链接", "达人类型", "人设标签", "IP城市", "报价", "预算状态", "预计发布时间", "粉丝数",
        "近30天流量稳定性", "限流风险判断", "合作笔记自然CPC", "合作笔记自然CPE", "搜索+推荐占比", "35岁以上粉丝占比", "孩子年龄", "孩子年级",
        "孩子性别", "家庭/教育话题点", "30天外溢进店成本", "90天外溢进店成本", "评分总分", "评分等级", "推荐等级", "硬性条件通过", "达人池分组", "当前状态",
        "合作方向", "备注",
    ]
    for sample in samples:
        rows.append(dict(zip(headers, sample)))
    return rows


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
    scored = score_creator(project_id, second["creator_id"], use_llm=False)
    assert scored["hard_filter_passed"] == 1
    assert scored["total_score"] >= 70
    assert scored["budget_score"] is not None
    assert scored["fans_score"] is not None
    assert scored["cpe_score"] is not None
    assert scored["traffic_score"] is not None
    assert scored["persona_score"] is not None
    assert scored["content_score"] is not None


def test_bulk_upsert_creators_writes_history_only_on_metric_change():
    project_id = f"pytest_bulk_history_{uuid.uuid4().hex[:8]}"
    first = bulk_upsert_creators(
        project_id,
        [
            {
                "creator_id": f"{project_id}-001",
                "nickname": "批量历史达人",
                "pgy_url": f"https://pgy.xiaohongshu.com/creator/{project_id}-001",
                "quote_price": 1200,
                "followers_count": 10000,
            }
        ],
    )
    second = bulk_upsert_creators(
        project_id,
        [
            {
                "creator_id": f"{project_id}-repeat",
                "nickname": "批量历史达人",
                "pgy_url": f"https://pgy.xiaohongshu.com/creator/{project_id}-001",
                "quote_price": 1200,
                "followers_count": 10000,
            }
        ],
    )
    third = bulk_upsert_creators(
        project_id,
        [
            {
                "creator_id": f"{project_id}-repeat",
                "nickname": "批量历史达人",
                "pgy_url": f"https://pgy.xiaohongshu.com/creator/{project_id}-001",
                "quote_price": 1300,
                "followers_count": 10000,
            }
        ],
    )

    assert first[0]["creator_id"] == second[0]["creator_id"] == third[0]["creator_id"]
    with connect() as conn:
        history_count = conn.execute(
            "SELECT COUNT(*) AS count FROM creator_metrics_history WHERE project_id=? AND creator_id=?",
            (project_id, first[0]["creator_id"]),
        ).fetchone()["count"]
        log_count = conn.execute(
            "SELECT COUNT(*) AS count FROM operation_logs WHERE project_id=? AND action='批量入库达人'",
            (project_id,),
        ).fetchone()["count"]
    assert history_count == 2
    assert log_count == 3


def test_creator_upsert_derives_effective_cost_and_manual_search_review():
    project_id = f"pytest_effective_cost_{uuid.uuid4().hex[:8]}"
    creator = upsert_creator(
        project_id,
        {
            "creator_id": f"{project_id}-001",
            "nickname": "成本口径达人",
            "pgy_url": "https://pgy.xiaohongshu.com/solar/pre-trade/blogger-detail/effective-cost",
            "quote_price": 3600,
            "image_read_unit_price": "0.66",
            "image_interaction_unit_price": "8.8",
            "fans_35_44_ratio": "41%",
            "fans_44_plus_ratio": "12%",
        },
        score=False,
    )

    assert creator["effective_cpc"] == 0.66
    assert creator["effective_cpc_source"] == "image_read_unit_price"
    assert creator["effective_cpe"] == 8.8
    assert creator["effective_cpe_source"] == "image_interaction_unit_price"
    assert creator["fans_35_plus_ratio"] == 0.53
    assert creator["fans_35_plus_ratio_source"] == "derived_35_44_plus_44_plus"
    assert creator["search_recommend_review_status"] == "待复核"
    assert "人工" in creator["search_recommend_review_note"]


def test_creator_upsert_extracts_child_grade_and_risk_reason_from_detail_payload():
    project_id = f"pytest_grade_risk_{uuid.uuid4().hex[:8]}"
    creator = upsert_creator(
        project_id,
        {
            "creator_id": f"{project_id}-001",
            "nickname": "学段抽取达人",
            "pgy_url": "https://pgy.xiaohongshu.com/solar/pre-trade/blogger-detail/grade-risk",
            "quote_price": 4200,
            "daily_read_median": 10000,
            "daily_interaction_median": 800,
            "cooperation_read_median": 3200,
            "cooperation_interaction_median": 260,
            "raw_payload": {
                "recent_notes": [
                    {"title": "初二孩子写作业总拖拉，怎么补效率", "content": "结合错题讲解和作业辅导去解决"},
                    {"title": "答疑笔和学习机怎么选", "content": "实测对比，适合家长辅导减负"},
                ]
            },
        },
        score=False,
    )

    assert creator["child_grade"] in {"初二", "初中"}
    assert creator["child_grade_confidence"] in {"high", "medium"}
    assert "初二" in creator["child_grade_evidence"]
    assert "作业答疑" in creator["content_scene_tags"] or "家长辅导" in creator["content_scene_tags"]
    assert creator["presentation_style_tags"]
    assert creator["rate_limit_risk"] in {"中风险", "高风险"}
    assert "合作阅读" in creator["rate_limit_risk_reason"] or "合作互动" in creator["rate_limit_risk_reason"]


def test_needs_detail_completion_only_counts_actionable_detail_fields():
    creator = {
        "creator_id": "pytest-detail-actionable",
        "nickname": "详情字段达人",
        "pgy_url": "https://pgy.xiaohongshu.com/solar/pre-trade/blogger-detail/test-detail-actionable",
        "total_score": 96,
        "hard_filter_passed": 1,
        "detail_collection_priority": "高优先级",
        "daily_read_median": None,
        "daily_interaction_median": None,
        "fans_35_plus_ratio": 0.56,
        "topic_point": "学习规划",
        "raw_payload": {"detail_collection_summary": {"module_count": 3}, "recent_notes": [{"title": "学习"}]},
    }

    assert detail_completion_actionable_missing_fields(creator) == []
    assert detail_completion_actionable_needs(creator) == []
    assert needs_detail_completion(creator) is False


def test_needs_detail_completion_skips_creators_without_detail_link():
    creator = {
        "creator_id": "pgy:list:no-link:beijing",
        "nickname": "无链接达人",
        "pgy_url": "",
        "total_score": 82,
        "hard_filter_passed": 1,
        "detail_collection_priority": "高优先级",
        "fans_35_plus_ratio": None,
        "topic_point": "",
        "raw_payload": {},
    }

    assert detail_completion_actionable_missing_fields(creator) == [
        "education_context",
        "note_cases",
        "detail_page_evidence",
    ]
    assert needs_detail_completion(creator) is False


def test_cleanup_project_creator_duplicates_prefers_api_record():
    project_id = f"pytest_cleanup_dup_{uuid.uuid4().hex[:8]}"
    upsert_creator(
        project_id,
        {
            "creator_id": "pgy-api:dup-001",
            "nickname": "重复达人",
            "pgy_url": "https://pgy.xiaohongshu.com/solar/pre-trade/blogger-detail/dup-001",
            "xiaohongshu_id": "dup-xhs-001",
            "quote_price": 5000,
            "followers_count": 30000,
            "fans_35_plus_ratio": 0.52,
        },
        score=False,
    )
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO creators(
                creator_id, project_id, source, xiaohongshu_id, pgy_blogger_id, pgy_url, nickname,
                creator_type, persona_tags, ip_city, profile_url, avatar_url, status, raw_payload, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
            """,
            (
                "pgy:list:重复达人:北京",
                project_id,
                "pgy",
                "dup-xhs-001",
                "",
                "",
                "重复达人",
                "",
                "",
                "北京",
                "",
                "",
                "待补数据",
                "{}",
            ),
        )
        conn.execute(
            """
            INSERT INTO project_creators(project_id, creator_id, pool_stage, review_status, created_at, updated_at)
            VALUES (?, ?, '待建联达人', '待补数据', datetime('now'), datetime('now'))
            """,
            (project_id, "pgy:list:重复达人:北京"),
        )

    result = cleanup_project_creator_duplicates(project_id)
    rows = [
        item
        for item in [
            get_creator(project_id, "pgy-api:dup-001"),
            get_creator(project_id, "pgy:list:重复达人:北京"),
        ]
        if item
    ]

    assert result["deleted_count"] == 1
    assert result["merged_pairs"][0]["canonical_creator_id"] == "pgy-api:dup-001"
    assert len(rows) == 1
    assert rows[0]["creator_id"] == "pgy-api:dup-001"


def test_hard_filter_threshold_parser_handles_mixed_descriptions():
    assert _threshold_from_text("单个达人 ¥20,000；总预算暂定 ¥120,000", "quote") == 20000
    assert _threshold_from_text("图文笔记：0.1万～0.5万", "quote") == 5000
    assert _threshold_from_text("图文笔记：1万～2万", "quote") == 20000
    assert _threshold_from_text("35岁以上占比 40%，不符合直接 pass", "fans35") == 0.4
    assert _threshold_from_text("CPC 2；CPE 20，优先 CPE 10 以下", "cpc") == 2
    assert _threshold_from_text("CPC 2；CPE 20，优先 CPE 10 以下", "cpe") == 20
    assert _threshold_from_text("图文笔记阅读单价 0.5～1.0", "cpc") == 1.0
    assert _threshold_from_text("图文笔记互动单价 10～20", "cpe") == 20


def test_scoring_caps_low_recent_reads_even_when_profile_and_quote_match():
    score = score_values(
        {
            "creator_id": "pytest-low-read-profile",
            "nickname": "低阅读教育妈妈",
            "pgy_url": "https://pgy.xiaohongshu.com/creator/low-read",
            "followers_count": 2000,
            "quote_price": 280,
            "fans_35_plus_ratio": 0.5,
            "creator_type": "教育/vlog/沉浸式/开箱",
            "persona_tags": "12岁以上、妈妈、学生、小升初",
            "raw_payload": {
                "recent_notes": [
                    {"title": "期中总结", "read_count": 79, "like_count": 4, "save_count": 2},
                    {"title": "晚间学习", "read_count": 195, "like_count": 12, "save_count": 2},
                    {"title": "学习方法", "read_count": 294, "like_count": 17, "save_count": 5},
                    {"title": "刷题", "read_count": 158, "like_count": 6, "save_count": 2},
                ]
            },
        }
    )
    assert score["total_score"] <= 79
    assert score["initial_tier"] == "B"
    assert "近期笔记阅读未达较好数据" in score["score_reason"]


def test_scoring_uses_cpm_to_accept_higher_quote_when_exposure_is_good():
    efficient = score_values(
        {
            "creator_id": "pytest-good-cpm",
            "nickname": "高曝光小粉",
            "pgy_url": "https://pgy.xiaohongshu.com/creator/good-cpm",
            "followers_count": 2000,
            "quote_price": 1000,
            "daily_exposure_median": 20000,
            "daily_read_median": 1500,
            "fans_35_plus_ratio": 0.5,
            "creator_type": "教育/测评",
            "persona_tags": "妈妈、家长、学习工具、小升初",
            "raw_payload": {"recent_notes": [{"title": "学习工具测评", "read_count": 1500, "like_count": 100, "save_count": 60}]},
        }
    )
    inefficient = score_values(
        {
            "creator_id": "pytest-bad-cpm",
            "nickname": "低曝光小粉",
            "pgy_url": "https://pgy.xiaohongshu.com/creator/bad-cpm",
            "followers_count": 2000,
            "quote_price": 1000,
            "daily_exposure_median": 3000,
            "daily_read_median": 1500,
            "fans_35_plus_ratio": 0.5,
            "creator_type": "教育/测评",
            "persona_tags": "妈妈、家长、学习工具、小升初",
            "raw_payload": {"recent_notes": [{"title": "学习工具测评", "read_count": 1500, "like_count": 100, "save_count": 60}]},
        }
    )
    assert "CPM 50.0 达标" in efficient["score_reason"]
    assert "CPM 333.3 偏高" in inefficient["score_reason"]
    assert inefficient["total_score"] <= 84
    assert efficient["total_score"] > inefficient["total_score"]


def _overseas_listening_special_scoring_config():
    return {
        "enabled": True,
        "label": "听课宝",
        "identity": {
            "name": "留学/留学生背景",
            "points": 35,
            "fields": ["nickname", "creator_type", "persona_tags", "ip_city", "topic_point"],
            "keywords": ["留学", "留学生", "海外", "美国", "英国", "study abroad", "overseas"],
            "evidence_keywords": ["留学", "留学生", "海外课堂", "assignment", "lecture"],
        },
        "scene": {
            "name": "Brief学习/听课场景",
            "max_points": 30,
            "base_points": 12,
            "points_per_hit": 4,
            "max_keyword_hits": 4,
            "direction_bonus": {"strong": 4, "medium": 2},
            "keywords": ["学习", "听课", "课堂", "笔记", "复盘", "assignment", "lecture", "考试"],
        },
        "data": {
            "max_points": 20,
            "good_points": 15,
            "excellent_points": 20,
            "read_ratio_points": [{"min": 0.75, "points": 10}, {"min": 0.5, "points": 6}],
            "interaction_bonus": [{"min": 120, "points": 4}, {"min": 60, "points": 2}],
        },
        "efficiency": {"max_points": 15, "good_points": 10, "excellent_points": 15, "fallback_points": 5},
        "tier_rules": {
            "s_min_priority_score": 85,
            "s_score": 95,
            "s_high_priority_score": 92,
            "s_high_score": 97,
            "a_min_priority_score": 72,
            "a_score": 88,
            "b_plus_min_priority_score": 55,
            "b_plus_score": 80,
            "b_min_priority_score": 40,
            "b_score": 75,
            "require_identity_for_s": True,
            "require_scene_for_s": True,
            "require_good_data_for_s": True,
            "require_good_efficiency_for_s": True,
            "no_identity_cap": 89,
            "identity_only_s_cap": 94,
        },
        "negative": {"keywords": ["纯vlog", "旅行", "穿搭"], "cap_without_scene": 84},
        "ignore_hard_filter_keywords": ["35", "34", "粉丝年龄", "宝妈", "家长"],
    }


def test_project_special_scoring_promotes_configured_overseas_student_to_s_tier():
    project_id = f"pytest_special_scoring_{uuid.uuid4().hex[:8]}"
    save_project(
        project_id,
        {
            "project_name": "配置型听课宝项目",
            "brief": "优先留学背景/留学生，学习、听课、课堂、复盘场景。",
            "screening_plan": {"projectSpecialScoring": _overseas_listening_special_scoring_config()},
        },
    )
    score = score_values(
        {
            "creator_id": "pytest-overseas-student-s-tier",
            "nickname": "海外留学生学习博主",
            "pgy_url": "https://pgy.xiaohongshu.com/creator/overseas-student",
            "followers_count": 5200,
            "quote_price": 800,
            "daily_read_median": 5000,
            "daily_interaction_median": 420,
            "image_read_unit_price": 0.16,
            "image_interaction_unit_price": 1.9,
            "creator_type": "教育/留学教育/学习日常",
            "persona_tags": "海外留学生、美国大学、课堂复盘",
            "raw_payload": {
                "recent_notes": [
                    {"title": "留学生课堂笔记复盘", "content": "海外上课和assignment整理方法", "read_count": 5200, "like_count": 180, "save_count": 120},
                    {"title": "lecture听课复盘", "content": "final备考和课堂录音整理", "read_count": 4800, "like_count": 170, "save_count": 100},
                ]
            },
        },
        project_id=project_id,
    )

    assert score["initial_tier"] == "S"
    assert score["detail_collection_priority"] == "最高优先级"
    assert "听课宝S档依据：身份、Brief场景、数据效率累计达标" in score["score_reason"]


def test_overseas_student_background_is_not_code_level_s_tier_without_project_config():
    score = score_values(
        {
            "creator_id": "pytest-overseas-student-without-special-config",
            "nickname": "海外留学生学习博主",
            "pgy_url": "https://pgy.xiaohongshu.com/creator/overseas-student",
            "followers_count": 5200,
            "quote_price": 800,
            "creator_type": "教育/留学教育/学习日常",
            "persona_tags": "海外留学生、美国大学、课堂复盘",
            "raw_payload": {
                "recent_notes": [
                    {"title": "留学生课堂笔记复盘", "content": "海外上课和assignment整理方法", "read_count": 800, "like_count": 50},
                ]
            },
        }
    )

    assert score["initial_tier"] != "S"
    assert "听课宝S档依据" not in score["score_reason"]


def test_low_reply_rate_caps_high_scoring_creator():
    project_id = f"pytest_low_reply_special_{uuid.uuid4().hex[:8]}"
    save_project(
        project_id,
        {
            "project_name": "低回复率配置项目",
            "brief": "优先留学背景/留学生，学习、听课、课堂、复盘场景。",
            "screening_plan": {"projectSpecialScoring": _overseas_listening_special_scoring_config()},
        },
    )
    score = score_values(
        {
            "creator_id": "pytest-low-reply-rate-cap",
            "nickname": "海外留学生高数据学习博主",
            "pgy_url": "https://pgy.xiaohongshu.com/creator/low-reply-rate",
            "followers_count": 5200,
            "quote_price": 800,
            "reply_rate_48h": 0.49,
            "daily_read_median": 5000,
            "daily_interaction_median": 420,
            "image_read_unit_price": 0.16,
            "image_interaction_unit_price": 1.9,
            "creator_type": "教育/留学教育/学习日常",
            "persona_tags": "海外留学生、美国大学、课堂复盘",
            "raw_payload": {
                "recent_notes": [
                    {"title": "留学生课堂笔记复盘", "content": "海外上课和assignment整理方法", "read_count": 5200, "like_count": 180, "save_count": 120},
                    {"title": "lecture听课复盘", "content": "final备考和课堂录音整理", "read_count": 4800, "like_count": 170, "save_count": 100},
                ]
            },
        },
        project_id=project_id,
    )

    assert score["total_score"] <= 84
    assert score["initial_tier"] != "S"
    assert "48h回复率低于50%" in score["score_reason"]


def test_missing_reply_rate_is_not_treated_as_low_reply_rate():
    score = score_values(
        {
            "creator_id": "pytest-missing-reply-rate",
            "nickname": "教育测评博主",
            "pgy_url": "https://pgy.xiaohongshu.com/creator/missing-reply-rate",
            "followers_count": 3000,
            "quote_price": 500,
            "daily_read_median": 1800,
            "daily_interaction_median": 120,
            "image_read_unit_price": 0.28,
            "image_interaction_unit_price": 4.2,
            "creator_type": "教育/测评",
            "persona_tags": "学习工具、课堂复盘",
            "raw_payload": {"recent_notes": [{"title": "学习工具测评", "read_count": 1800, "like_count": 80, "save_count": 45}]},
        }
    )

    assert "48h回复率未进入本轮数据" in score["score_reason"]
    assert "48h回复率低于50%" not in score["score_reason"]


def test_rule_scoring_uses_project_weights_and_hard_filters():
    project_id = f"pytest_project_weighted_scoring_{uuid.uuid4().hex[:8]}"
    save_project(
        project_id,
        {
            "project_name": "高端家居项目",
            "brief": "寻找高端家居、收纳、装修生活方式达人，重视内容场景，不要求35岁以上粉丝占比。",
            "screening_plan": {
                "scoringWeights": {"budget": 5, "fans": 5, "cpe": 10, "engagement": 10, "persona": 50, "content": 20},
                "scoringHardFilters": [
                    {"field": "平台报价", "condition": "<=", "value": "5000", "required": True},
                    {"field": "博主类目", "condition": "包含", "value": "家居", "required": True},
                ],
                "scoringCriteria": {
                    "hard_rules": [
                        {"field": "平台报价", "condition": "<=", "value": "5000", "required": True},
                        {"field": "博主类目", "condition": "包含", "value": "家居", "required": True},
                    ]
                },
                "projectFitConfig": {
                    "preferred_content_scenes": ["家居", "收纳", "装修"],
                    "evidence_rules": {"require_scene_evidence_for_a_tier": True},
                },
            },
        }
    )
    creator = {
        "creator_id": f"{project_id}-creator",
        "nickname": "家居收纳达人",
        "pgy_url": "https://pgy.xiaohongshu.com/creator/home",
        "followers_count": 50000,
        "quote_price": 4500,
        "fans_35_plus_ratio": 0.2,
        "daily_read_median": 12000,
        "daily_interaction_median": 800,
        "image_read_unit_price": 0.7,
        "image_interaction_unit_price": 7,
        "creator_type": "家居家装/生活方式",
        "persona_tags": "家居、收纳、装修、生活方式",
        "raw_payload": {"recent_notes": [{"title": "小户型收纳装修复盘", "content": "家居收纳和装修动线", "read_count": 12000, "like_count": 300, "save_count": 120}]},
    }

    project_score = score_values(creator, project_id=project_id)
    generic_score = score_values(creator)

    assert project_score["hard_filter_passed"] == 1
    assert "35岁以上粉丝占比低于40%" not in project_score["score_reason"]
    assert project_score["persona_score"] > generic_score["persona_score"]
    assert project_score["total_score"] > generic_score["total_score"]


def test_rule_scoring_rejects_no_order_permission_from_raw_payload():
    project_id = f"pytest_no_order_permission_scoring_{uuid.uuid4().hex[:8]}"
    save_project(
        project_id,
        {
            "project_name": "无接单权限测试",
            "brief": "教育达人采集",
            "screening_plan": {"scoringHardFilters": []},
        },
    )

    score = score_values(
        {
            "creator_id": f"{project_id}-creator",
            "nickname": "无接单权限达人",
            "pgy_url": "https://pgy.xiaohongshu.com/creator/no-order",
            "followers_count": 12000,
            "daily_read_median": 3000,
            "daily_interaction_median": 240,
            "creator_type": "教育",
            "raw_payload": {"raw_table": {"全部报价": "无接单权限"}},
        },
        project_id=project_id,
    )

    assert score["hard_filter_passed"] == 0
    assert "无接单权限" in score["score_reason"]


def test_default_scoring_does_not_use_35_plus_as_hard_audience_condition():
    score = score_values(
        {
            "creator_id": "pytest-no-default-fans35-hard-condition",
            "nickname": "低35占比但高数据家居达人",
            "pgy_url": "https://pgy.xiaohongshu.com/creator/no-default-fans35",
            "followers_count": 50000,
            "quote_price": 1200,
            "fans_35_plus_ratio": 0.2,
            "daily_read_median": 12000,
            "daily_interaction_median": 800,
            "image_read_unit_price": 0.1,
            "image_interaction_unit_price": 1.5,
            "creator_type": "家居家装/生活方式",
            "persona_tags": "家居、收纳、装修、生活方式",
            "raw_payload": {"recent_notes": [{"title": "小户型收纳装修复盘", "content": "家居收纳和装修动线", "read_count": 12000, "like_count": 300, "save_count": 120}]},
        }
    )

    assert score["total_score"] > 69
    assert "项目粉丝年龄硬条件未达标" not in score["score_reason"]
    assert "粉丝年龄画像未进入本轮数据判断" not in score["score_reason"]


def test_initial_scoring_caps_weak_direction_without_detail_evidence():
    score = score_values(
        {
            "creator_id": "pytest-lifestyle-weak-direction",
            "nickname": "生活方式谭十七",
            "pgy_url": "https://pgy.xiaohongshu.com/creator/lifestyle-weak",
            "followers_count": 80000,
            "quote_price": 6000,
            "fans_35_plus_ratio": 0.55,
            "daily_read_median": 18000,
            "daily_interaction_median": 900,
            "image_read_unit_price": 0.8,
            "image_interaction_unit_price": 6,
            "creator_type": "家居家装/生活记录",
            "persona_tags": "极简主义",
            "raw_payload": {"cooperation_hint": "期待与「3C及电器」行业合作"},
        }
    )
    assert score["total_score"] <= 89
    assert score["initial_tier"] in {"B", "B+"}
    assert "方向弱证据：weak" in score["score_reason"]


def test_project_fit_config_caps_creator_without_product_scene_evidence():
    project_id = f"pytest_project_fit_cap_{uuid.uuid4().hex[:8]}"
    save_project(
        project_id,
        {
            "project_name": project_id,
            "brief": "有道答疑笔，找初中家长和老师达人",
            "screening_plan": {
                "projectFitConfig": {
                    "product_name": "有道答疑笔",
                    "preferred_content_scenes": ["作业答疑", "错题讲解", "家长辅导"],
                    "preferred_presentation_styles": ["老师讲解型", "测评对比型"],
                    "target_grade_keywords": ["初中", "初一", "初二", "初三"],
                    "parent_decision_keywords": ["家长", "妈妈", "爸爸", "陪学"],
                    "discouraged_keywords": ["纯生活方式"],
                    "evidence_rules": {
                        "minimum_recent_note_count_for_high_score": 2,
                        "require_scene_evidence_for_a_tier": True,
                        "require_grade_or_parent_evidence_for_s_tier": True,
                        "insufficient_evidence_max_score": 84,
                        "weak_scene_match_max_score": 79,
                        "negative_hit_max_score": 74,
                    },
                }
            },
        },
    )
    creator = upsert_creator(
        project_id,
        {
            "creator_id": f"{project_id}-001",
            "nickname": "高数据但场景偏生活",
            "pgy_url": "https://pgy.xiaohongshu.com/creator/project-fit-cap",
            "quote_price": 6500,
            "followers_count": 120000,
            "fans_35_plus_ratio": 0.55,
            "daily_read_median": 26000,
            "daily_interaction_median": 1300,
            "image_read_unit_price": 0.8,
            "image_interaction_unit_price": 6,
            "creator_type": "生活记录/家居",
            "persona_tags": "极简生活/收纳",
            "raw_payload": {
                "recent_notes": [
                    {"title": "小家收纳清单", "content": "分享今天的家务动线"},
                    {"title": "周末生活vlog", "content": "记录一日三餐和家里布置"},
                ]
            },
        },
        score=False,
    )

    score_project(project_id, creator_ids=[creator["creator_id"]], use_llm=False, trigger_source="manual")
    scored = get_creator(project_id, creator["creator_id"])

    assert scored["total_score"] <= 79
    assert scored["initial_tier"] in {"A", "B+"}
    assert scored["detail_collection_priority"] in {"高优先级", "中高优先级"}
    assert "规则初筛分组" in scored["score_reason"]
    assert "缺少与当前产品场景直接匹配的内容证据" in scored["score_reason"]


def test_project_fit_config_rewards_creator_with_scene_and_grade_evidence():
    project_id = f"pytest_project_fit_match_{uuid.uuid4().hex[:8]}"
    save_project(
        project_id,
        {
            "project_name": project_id,
            "brief": "有道答疑笔，找初中家长和老师达人",
            "screening_plan": {
                "projectFitConfig": {
                    "product_name": "有道答疑笔",
                    "preferred_content_scenes": ["作业答疑", "错题讲解", "家长辅导"],
                    "preferred_presentation_styles": ["老师讲解型", "测评对比型"],
                    "target_grade_keywords": ["初中", "初一", "初二", "初三"],
                    "parent_decision_keywords": ["家长", "妈妈", "爸爸", "陪学"],
                    "discouraged_keywords": ["纯生活方式"],
                    "evidence_rules": {
                        "minimum_recent_note_count_for_high_score": 2,
                        "require_scene_evidence_for_a_tier": True,
                        "require_grade_or_parent_evidence_for_s_tier": True,
                        "insufficient_evidence_max_score": 84,
                        "weak_scene_match_max_score": 79,
                        "negative_hit_max_score": 74,
                    },
                }
            },
        },
    )
    creator = upsert_creator(
        project_id,
        {
            "creator_id": f"{project_id}-001",
            "nickname": "初二答疑老师",
            "pgy_url": "https://pgy.xiaohongshu.com/creator/project-fit-match",
            "quote_price": 7200,
            "followers_count": 98000,
            "fans_35_plus_ratio": 0.58,
            "daily_read_median": 22000,
            "daily_interaction_median": 1100,
            "image_read_unit_price": 0.76,
            "image_interaction_unit_price": 5.8,
            "creator_type": "教育/老师讲题",
            "persona_tags": "老师/家长辅导/初中",
            "child_grade": "初二",
            "content_scene_tags": "作业答疑、错题讲解、家长辅导",
            "presentation_style_tags": "老师讲解型、测评对比型",
            "raw_payload": {
                "recent_notes": [
                    {"title": "初二数学作业答疑，这题孩子为什么总卡住", "content": "结合错题讲解和家长辅导步骤拆解"},
                    {"title": "答疑笔和传统搜题的差别", "content": "演示孩子自主学习和家长减负过程"},
                ]
            },
        },
        score=False,
    )

    score_project(project_id, creator_ids=[creator["creator_id"]], use_llm=False, trigger_source="manual")
    scored = get_creator(project_id, creator["creator_id"])

    assert scored["total_score"] >= 80
    assert "项目场景匹配" in scored["score_reason"]
    assert "内容呈现匹配" in scored["score_reason"]


def test_creator_upsert_persists_full_collection_metrics():
    project_id = "pytest_full_metrics"
    creator = upsert_creator(
        project_id,
        {
            "creator_id": "pytest-full-metrics-001",
            "nickname": "完整指标达人",
            "pgy_url": "https://pgy.xiaohongshu.com/creator/full-metrics-001",
            "粉丝数": "8.8万",
            "全部报价": "¥12,000",
            "阅读中位数（日常）": "33,000",
            "互动中位数（日常）": "1,200",
            "曝光中位数（合作）": "80,000",
            "阅读中位数（合作）": "20,000",
            "互动中位数（合作）": "900",
            "外溢进店单价": "1.8",
            "图文预估阅读单价": "1.2",
            "图文预估互动单价": "8.5",
            "视频预估阅读单价": "1.6",
            "视频预估互动单价": "11",
            "活跃粉丝占比": "18.8%",
            "互动粉丝占比": "4.2%",
            "邀约48h回复率": "97.0%",
            "粉丝画像截图": "runtime/pgy_detail_screenshots/test-fans-profile.png",
        },
        score=False,
    )
    assert creator["followers_count"] == 88000
    assert creator["daily_read_median"] == 33000
    assert creator["cooperation_read_median"] == 20000
    assert creator["overflow_store_unit_price"] == 1.8
    assert creator["image_read_unit_price"] == 1.2
    assert creator["video_interaction_unit_price"] == 11
    assert creator["active_fans_ratio"] == 0.188
    assert creator["reply_rate_48h"] == 0.97
    assert creator["audience_profile_screenshot"].endswith("test-fans-profile.png")


def test_pgy_detail_performance_parser_handles_cooperation_cost_and_scale():
    scale = """数据表现
合作笔记
核心指标
按规模
按成本
曝光中位数
60,068
阅读中位数
10,624
互动中位数
920
外溢进店中位数
1
其他指标
互动率
7.4%
视频完播率
31.4%
百赞笔记比例
100.0%
粉丝分析"""
    cost = """数据表现
合作笔记
核心指标
按规模
按成本
预估CPM
37.40
元/千次曝光
预估阅读单价
0.19
元/阅读
预估互动单价
2.58
元/互动
预估外溢进店单价(视频)
4.08
元/进店
外溢进店单价
4.08
元/进店
其他指标
互动率
7.4%
粉丝分析"""
    scale_metrics = _extract_performance_state(scale)["metrics"]
    cost_metrics = _extract_performance_state(cost)["metrics"]
    assert scale_metrics["曝光中位数"] == "60,068"
    assert scale_metrics["阅读中位数"] == "10,624"
    assert scale_metrics["互动中位数"] == "920"
    assert scale_metrics["外溢进店中位数"] == "1"
    assert scale_metrics["百赞笔记比例"] == "100.0%"
    assert cost_metrics["预估CPM"] == "37.40元/千次曝光"
    assert cost_metrics["预估阅读单价"] == "0.19元/阅读"
    assert cost_metrics["预估互动单价"] == "2.58元/互动"
    assert cost_metrics["预估外溢进店单价(视频)"] == "4.08元/进店"
    assert cost_metrics["外溢进店单价"] == "4.08元/进店"


def test_pgy_detail_note_case_parser_keeps_cooperation_brand():
    text = """笔记案例
全部类型
合作笔记
仅展示跨域合作笔记
作业帮智能教育
破防了，原来告别低效抄错题这么简单啊！
阅读
9,760
点赞
456
收藏
294
发布时间
2026-05-07
八九间BAJOJAN
孩子写作业爱晃悠？换这把学习椅直接坐得住！
含推广流量
阅读
10,419
点赞
383
收藏
159
发布时间
2026-05-06
前往TA的小红书APP主页"""
    cases = _extract_note_cases(_visible_text_lines(text))
    assert len(cases) == 2
    assert cases[0]["brand"] == "作业帮智能教育"
    assert cases[0]["read_count"] == 9760
    assert cases[1]["brand"] == "八九间BAJOJAN"
    assert cases[1]["has_promoted_traffic"] is True


def test_pgy_detail_note_cases_keep_cover_link_and_median_contrast():
    cases = [
        {"brand": "作业帮智能教育", "title": "破防了，原来告别低效抄错题这么简单啊！", "read_count": 9760, "like_count": 456, "save_count": 294, "published_at": "2026-05-07"},
        {"brand": "八九间BAJOJAN", "title": "孩子写作业爱晃悠？换这把学习椅直接坐得住！", "read_count": 10419, "like_count": 383, "save_count": 159, "published_at": "2026-05-06"},
    ]
    assets = [
        {"title": "破防了，原来告别低效抄错题这么简单啊！", "cover_url": "https://img.example/cover-1.jpg", "note_url": "https://www.xiaohongshu.com/explore/note-1"},
        {"title": "孩子写作业爱晃悠？换这把学习椅直接坐得住！", "cover_url": "https://img.example/cover-2.jpg", "note_url": "https://www.xiaohongshu.com/explore/note-2"},
    ]
    merged = _merge_note_case_assets(cases, assets, "https://pgy.xiaohongshu.com/solar/pre-trade/blogger-detail/abc")
    detail = _annotate_note_cases_with_traffic_reference(
        {
            "cooperation_read_median": 6000,
            "cooperation_interaction_median": 300,
            "raw_payload": {"cooperation_note_cases": merged},
        }
    )
    note = detail["raw_payload"]["cooperation_note_cases"][0]
    assert note["cover_url"].endswith("cover-1.jpg")
    assert note["note_url"].endswith("note-1")
    assert note["read_vs_median"] == 1.627
    assert note["interaction_vs_median"] == 2.5
    assert note["has_clear_median_contrast"] is True
    assert note["traffic_median_reference"]["source"] == "cooperation"


def test_audience_profile_chart_metrics_extracts_full_age_distribution():
    class FakePage:
        def evaluate(self, script):
            return {
                "female_fans_ratio": 0.911,
                "male_fans_ratio": 0.089,
                "fans_under_18_ratio": 0.057,
                "fans_25_34_ratio": 0.274,
                "fans_35_44_ratio": 0.448,
                "fans_44_plus_ratio": 0.052,
                "audience_age_dominant": {"label": "25-34", "ratio": 0.274},
                "audience_gender_dominant": {"label": "女性", "ratio": 0.911},
                "sources": [
                    {"key": "fans_25_34_ratio", "name": "25-34", "value": 0.274, "source": "echarts_option"},
                ],
            }

    metrics = _collect_audience_profile_chart_metrics(FakePage())

    assert metrics["female_fans_ratio"] == 0.911
    assert metrics["male_fans_ratio"] == 0.089
    assert metrics["fans_under_18_ratio"] == 0.057
    assert metrics["fans_25_34_ratio"] == 0.274
    assert metrics["fans_35_44_ratio"] == 0.448
    assert metrics["fans_44_plus_ratio"] == 0.052
    assert metrics["audience_age_distribution"]["segments"][0]["label"] == "<18"
    assert metrics["audience_age_distribution"]["dominant"]["label"] == "25-34"
    assert metrics["audience_gender_distribution"]["segments"][0]["label"] == "女性"
    assert metrics["raw_payload"]["audience_profile_chart_metrics"]["sources"][0]["source"] == "echarts_option"


def test_audience_profile_distribution_is_stored_and_derives_flat_metrics():
    project_id = f"pytest_audience_distribution_{uuid.uuid4().hex[:8]}"
    creator = upsert_creator(
        project_id,
        {
            "creator_id": f"{project_id}-001",
            "nickname": "粉丝画像结构化达人",
            "audience_age_distribution": {
                "segments": [
                    {"label": "<18", "key": "fans_under_18_ratio", "ratio": 0.057},
                    {"label": "18-24", "key": "fans_18_24_ratio", "ratio": 0.096},
                    {"label": "25-34", "key": "fans_25_34_ratio", "ratio": 0.348},
                    {"label": "35-44", "key": "fans_35_44_ratio", "ratio": 0.337},
                    {"label": ">44", "key": "fans_44_plus_ratio", "ratio": 0.161},
                ],
                "dominant": {"label": "25-34", "ratio": 0.348},
                "source": "dom_echarts",
            },
            "audience_gender_distribution": {
                "segments": [
                    {"label": "女性", "key": "female_fans_ratio", "ratio": 0.902},
                    {"label": "男性", "key": "male_fans_ratio", "ratio": 0.098},
                ],
                "dominant": {"label": "女性", "ratio": 0.902},
                "source": "dom_echarts",
            },
        },
        score=False,
    )

    stored_age = json.loads(creator["audience_age_distribution"])
    stored_gender = json.loads(creator["audience_gender_distribution"])

    assert creator["fans_under_18_ratio"] == 0.057
    assert creator["fans_25_34_ratio"] == 0.348
    assert creator["fans_35_44_ratio"] == 0.337
    assert creator["female_fans_ratio"] == 0.902
    assert stored_age["segments"][2]["label"] == "25-34"
    assert stored_gender["dominant"]["label"] == "女性"


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


def test_creator_pool_stage_history_and_csv_export():
    project_id = f"pytest_pool_{uuid.uuid4().hex[:8]}"
    creator = upsert_creator(
        project_id,
        {
            "creator_id": f"{project_id}-001",
            "nickname": "池化测试达人",
            "pgy_url": "https://pgy.xiaohongshu.com/creator/pool-001",
            "quote_price": 8800,
            "fans_35_plus_ratio": 0.52,
            "followers_count": 80000,
        },
    )
    review_creator(project_id, creator["creator_id"], "已通过", "进入达人池", "pytest")
    pool = creator_pool(project_id)
    assert any(item["creator_id"] == creator["creator_id"] for item in pool["groups"]["合格达人待合作"])

    changed = change_creator_stage(project_id, creator["creator_id"], "已合作跟进中", "确认合作", "pytest")
    assert changed["pool_stage"] == "已合作跟进中"
    updated = update_creator_metrics(project_id, creator["creator_id"], {"followers_count": 81200}, "pytest")
    assert updated["followers_count"] == 81200
    detail = creator_pool_detail(project_id, creator["creator_id"])
    assert detail["history"]
    assert detail["stage_logs"]

    csv_path = export_creator_pool_csv(project_id)
    assert csv_path.exists()
    assert "池化测试达人" in csv_path.read_text(encoding="utf-8-sig")


def test_scored_collected_creators_stay_in_screening_until_reviewed():
    project_id = f"pytest_screening_gate_{uuid.uuid4().hex[:8]}"
    creator = upsert_creator(
        project_id,
        {
            "creator_id": f"{project_id}-001",
            "nickname": "待筛选候选达人",
            "pgy_url": "https://pgy.xiaohongshu.com/creator/screening-gate-001",
            "quote_price": 6800,
            "fans_35_plus_ratio": 0.48,
            "followers_count": 86000,
            "source": "pgy",
        },
        score=False,
    )

    scored = score_project(project_id, creator_ids=[creator["creator_id"]], use_llm=False, trigger_source="pgy_collect")
    assert scored["scored"] == 1
    pool = creator_pool(project_id)
    assert any(item["creator_id"] == creator["creator_id"] for item in pool["groups"]["筛选工作台"])
    assert not any(item["creator_id"] == creator["creator_id"] for item in pool["groups"]["待建联达人"])
    assert not any(item["creator_id"] == creator["creator_id"] for item in pool["groups"]["合格达人待合作"])

    review_creator(project_id, creator["creator_id"], "已通过", "人工确认入池", "pytest")
    reviewed_pool = creator_pool(project_id)
    assert any(item["creator_id"] == creator["creator_id"] for item in reviewed_pool["groups"]["合格达人待合作"])


def test_test_stage_scores_sample_creator_pool():
    project_id = "pytest_sample_pool"
    imported = 0
    fixture_rows = []
    with (ROOT / "有道答疑笔5-6月合作_测试项目" / "03_达人池实体表.csv").open("r", encoding="utf-8-sig", newline="") as handle:
        fixture_rows = list(csv.DictReader(handle))
    if not fixture_rows:
        fixture_rows = _sample_pool_fixture_rows()
    for row in fixture_rows:
        row["达人ID"] = f"{project_id}-{row['达人ID']}"
        upsert_creator(project_id, row, score=False)
        imported += 1
    scored = score_project(project_id, use_llm=False)
    rows = standard_feishu_rows(project_id, ["待审核", "初筛通过", "备选"])

    assert imported >= 10
    assert scored["source"] in {"rule", "generated", "llm"}
    assert scored["scored"] >= 10
    assert all(not str(row["达人ID"]).startswith("pytest_sample_pool-pytest_") for row in rows)
    assert any(str(row["备注"]) for row in rows)


def test_generate_more_creators_and_quality_rows():
    project_id = f"pytest_more_creators_{uuid.uuid4().hex[:8]}"
    generated = generate_test_creators(project_id, desired_count=18)
    scored = score_project(project_id, use_llm=False)
    rows = quality_feishu_rows(project_id, limit=10, include_test_creators=True)

    assert generated["total"] >= 18
    assert scored["source"] in {"rule", "generated", "llm"}
    assert scored["scored"] >= 18
    assert len(rows) >= min(8, generated["total"])
    assert rows[0]["达人昵称"]
    assert rows[0]["品牌反馈"] == "优质候选"


def test_feishu_rows_include_semantic_and_computed_fields():
    project_id = f"pytest_semantic_rows_{uuid.uuid4().hex[:8]}"
    creator = upsert_creator(
        project_id,
        {
            "creator_id": f"{project_id}-001",
            "nickname": "语义映射达人",
            "xiaohongshu_id": "RinaGuGu",
            "pgy_url": "https://pgy.xiaohongshu.com/solar/pre-trade/blogger-detail/abc",
            "creator_type": "母婴/vlog",
            "persona_tags": "妈妈/6-12岁",
            "followers_count": 186000,
            "liked_collected_count": 1625000,
            "quote_price": 6000,
            "video_quote_price": 12000,
            "daily_read_median": 22859,
            "daily_interaction_median": 1634,
            "cooperation_interaction_median": 1200,
            "image_interaction_unit_price": 2,
            "image_cpm": 149.9,
            "video_completion_rate": "49.4%",
            "active_fans_ratio": "90.2%",
            "female_fans_ratio": "94.76%",
            "fans_25_34_ratio": "37.7%",
            "fans_35_44_ratio": "49.4%",
            "fans_44_plus_ratio": "7.5%",
            "fans_35_plus_ratio": "56.9%",
        },
        score=False,
    )
    review_creator(project_id, creator["creator_id"], "已通过", "测试通过", "pytest")

    row = standard_feishu_rows(project_id, ["已通过"])[0]

    assert row["主页链接"].endswith("/abc")
    assert row["赞藏数/w"] == 162.5
    assert row["图文执行价（含平台服务费）"] == 6600
    assert row["视频执行价（含平台服务费）"] == 13200
    assert row["粉丝女性用户占比"] == "94.8%"
    assert row["粉丝年龄25-34占比"] == "37.7%"
    assert row["粉丝年龄25-44占比"] == "87.1%"
    assert row["粉丝年龄34岁以上占比"] == "56.9%"


def test_feishu_homepage_uses_pgy_blogger_id_before_numeric_red_id():
    project_id = f"pytest_homepage_user_id_{uuid.uuid4().hex[:8]}"
    creator = upsert_creator(
        project_id,
        {
            "creator_id": f"{project_id}-001",
            "nickname": "主页链接达人",
            "xiaohongshu_id": "95292130186",
            "pgy_blogger_id": "664886190000000003033e00",
            "pgy_url": "https://pgy.xiaohongshu.com/solar/pre-trade/blogger-detail/664886190000000003033e00",
            "quote_price": 6000,
        },
        score=False,
    )
    review_creator(project_id, creator["creator_id"], "已通过", "测试通过", "pytest")

    row = standard_feishu_rows(project_id, ["已通过"])[0]

    assert row["小红书号"] == "95292130186"
    assert row["主页链接"] == "https://www.xiaohongshu.com/user/profile/664886190000000003033e00"


def test_feishu_homepage_uses_real_profile_url_when_collected():
    project_id = f"pytest_homepage_profile_url_{uuid.uuid4().hex[:8]}"
    creator = upsert_creator(
        project_id,
        {
            "creator_id": f"{project_id}-001",
            "nickname": "真实主页达人",
            "xiaohongshu_id": "95292130186",
            "profile_url": "https://www.xiaohongshu.com/user/profile/69c0fe76000000003201af1b",
            "pgy_url": "https://pgy.xiaohongshu.com/solar/pre-trade/blogger-detail/664886190000000003033e00",
            "quote_price": 6000,
        },
        score=False,
    )
    review_creator(project_id, creator["creator_id"], "已通过", "测试通过", "pytest")

    row = standard_feishu_rows(project_id, ["已通过"])[0]

    assert row["主页链接"] == "https://www.xiaohongshu.com/user/profile/69c0fe76000000003201af1b"


def test_normalize_creator_converts_pgy_profile_url_to_xhs_profile_url():
    creator = upsert_creator(
        f"pytest_profile_normalize_{uuid.uuid4().hex[:8]}",
        {
            "creator_id": "profile-normalize-001",
            "nickname": "清理主页达人",
            "xiaohongshu_id": "95292130186",
            "profile_url": "https://pgy.xiaohongshu.com/solar/pre-trade/blogger-detail/67e3aefa000000000d008d1b",
            "pgy_url": "https://pgy.xiaohongshu.com/solar/pre-trade/blogger-detail/67e3aefa000000000d008d1b",
        },
        score=False,
    )

    assert creator["profile_url"] == "https://www.xiaohongshu.com/user/profile/67e3aefa000000000d008d1b"


def test_fans_34_plus_is_derived_from_35_44_and_44_plus():
    project_id = f"pytest_fans_age_sum_{uuid.uuid4().hex[:8]}"
    creator = upsert_creator(
        project_id,
        {
            "creator_id": f"{project_id}-001",
            "nickname": "年龄分布达人",
            "pgy_url": "https://pgy.xiaohongshu.com/creator/age-sum",
            "followers_count": 80000,
            "quote_price": 5000,
            "fans_35_44_ratio": "49.4%",
            "fans_44_plus_ratio": "7.5%",
            "fans_35_plus_ratio": "49.4%",
        },
        score=False,
    )
    review_creator(project_id, creator["creator_id"], "已通过", "测试通过", "pytest")

    row = standard_feishu_rows(project_id, ["已通过"])[0]

    assert row["粉丝年龄35-44占比"] == "49.4%"
    assert row["粉丝年龄44岁以上占比"] == "7.5%"
    assert row["粉丝年龄34岁以上占比"] == "56.9%"
    assert row["粉丝年龄34岁以上占比（35-44+44岁以上）"] == "56.9%"


def test_field_mapping_agent_maps_varied_sheet_headers_without_llm():
    rows = [
        {
            "达人昵称": "语义映射达人",
            "粉丝量（w）": 18.6,
            "赞藏量（w）": 162.5,
            "25-44岁粉丝占比（25-34+35-44）": "87.1%",
            "粉丝年龄34岁以上占比（35-44+44岁以上）": "56.9%",
            "粉丝年龄35-44占比": "49.4%",
            "图文报备价": 6000,
            "图文执行价（含平台服务费）": 6600,
            "视频报备裸价": 12000,
            "视频执行价（含平台服务费）": 13200,
            "预估cpe": 2,
            "视频完播率": "49.4%",
        }
    ]
    fields = [
        {"field_name": "达人昵称", "column_index": 0},
        {"field_name": "粉丝量\n（w）", "column_index": 1},
        {"field_name": "赞藏量\n（w）", "column_index": 2},
        {"field_name": "25~44岁粉丝占比", "column_index": 3},
        {"field_name": "粉丝年龄34岁以上占比", "column_index": 4},
        {"field_name": "图文报备价", "column_index": 5},
        {"field_name": "图文执行价\n（含平台服务费）", "column_index": 6},
        {"field_name": "视频报备裸价", "column_index": 7},
        {"field_name": "预估cpe", "column_index": 8},
        {"field_name": "视频完播率", "column_index": 9},
    ]

    mapped_rows, plan = apply_field_mapping(rows, fields, use_llm=False)

    assert mapped_rows[0]["粉丝量\n（w）"] == 18.6
    assert mapped_rows[0]["赞藏量\n（w）"] == 162.5
    assert mapped_rows[0]["25~44岁粉丝占比"] == "87.1%"
    assert mapped_rows[0]["粉丝年龄34岁以上占比"] == "56.9%"
    assert mapped_rows[0]["图文执行价\n（含平台服务费）"] == 6600
    assert mapped_rows[0]["视频报备裸价"] == 12000
    assert mapped_rows[0]["预估cpe"] == 2
    assert not any(item["target_field"] == "达人昵称" for item in plan["unmatched"])


def test_quality_feishu_rows_include_project_promotion_reason():
    project_id = f"pytest_promo_reason_{uuid.uuid4().hex[:8]}"
    save_project(
        project_id,
        {
            "name": "答疑笔推广",
            "brief": "推广答疑笔，需要能讲清初中学习、作业答疑和家长决策场景的达人",
            "target_qualified_creator_count": 5,
            "screening_plan": {
                "projectFitConfig": {
                    "preferred_content_scenes": ["作业答疑", "初中学习"],
                    "preferred_presentation_styles": ["老师讲解型"],
                    "target_grade_keywords": ["初二", "初中"],
                    "parent_decision_keywords": ["家长"],
                    "evidence_rules": {"minimum_recent_note_count_for_high_score": 1},
                }
            },
        }
    )
    creator = upsert_creator(
        project_id,
        {
            "creator_id": f"{project_id}-1",
            "nickname": "项目契合达人",
            "pgy_url": "https://pgy.xiaohongshu.com/solar/pre-trade/blogger-detail/project-fit",
            "quote_price": 9000,
            "followers_count": 86000,
            "daily_read_median": 14000,
            "daily_interaction_median": 800,
            "content_scene_tags": "作业答疑、初中学习",
            "presentation_style_tags": "老师讲解型",
            "topic_point": "初中作业答疑和家长陪伴学习",
            "child_grade": "初二",
            "fans_35_plus_ratio": 0.56,
        },
        score=False,
    )
    score_creator(project_id, creator["creator_id"], use_llm=False)

    row = quality_feishu_rows(project_id, rescore=False)[0]

    assert "推荐理由：" in row["推荐理由"]
    assert "内容场景契合项目推广" in row["推荐理由"]
    assert "作业答疑" in row["达人契合该项目推广的地方"]
    assert row["项目推广契合点"] == row["达人契合该项目推广的地方"]


def test_field_mapping_agent_maps_project_fit_reason_header_without_llm():
    rows = [
        {
            "达人昵称": "契合达人",
            "达人契合该项目推广的地方": "内容场景契合项目推广：命中作业答疑",
        }
    ]
    fields = [
        {"field_name": "达人昵称", "column_index": 0},
        {"field_name": "达人契合该项目推广的地方", "column_index": 1},
    ]

    mapped_rows, plan = apply_field_mapping(rows, fields, use_llm=False)

    assert mapped_rows[0]["达人契合该项目推广的地方"] == "内容场景契合项目推广：命中作业答疑"
    assert any(item["target_field"] == "达人契合该项目推广的地方" for item in plan["mappings"])


def test_field_mapping_agent_maps_25_to_44_age_ratio_with_llm(monkeypatch):
    captured = {}

    def fake_chat_json(messages, config=None):
        captured["prompt"] = messages[-1]["content"]
        return {
            "mappings": [
                {
                    "target_field": "粉丝年龄25~44占比",
                    "source_field": "25-44岁粉丝占比（25-34+35-44）",
                    "confidence": 0.95,
                    "reason": "25-44 是 25-34 与 35-44 合计",
                }
            ],
            "unmatched": [],
        }

    monkeypatch.setattr("rpa_mcp_sync.feishu_field_agent.chat_json", fake_chat_json)
    rows = [{"25-44岁粉丝占比（25-34+35-44）": "87.1%", "粉丝年龄25-34占比": "37.7%", "粉丝年龄35-44占比": "49.4%"}]

    plan = analyze_field_mapping(["粉丝年龄25~44占比"], rows, use_llm=True)

    assert plan["source"] == "llm"
    assert plan["mappings"][0]["source_field"] == "25-44岁粉丝占比（25-34+35-44）"
    assert "25-44岁占比" in captured["prompt"]


def test_batch_llm_scores_multiple_creators_in_one_request(monkeypatch):
    project_id = f"pytest_batch_llm_{uuid.uuid4().hex[:8]}"
    creators = [
        upsert_creator(project_id, {"creator_id": f"{project_id}-1", "nickname": "批量达人A", "pgy_url": "https://pgy.xiaohongshu.com/creator/a", "quote_price": 9000}, score=False),
        upsert_creator(project_id, {"creator_id": f"{project_id}-2", "nickname": "批量达人B", "pgy_url": "https://pgy.xiaohongshu.com/creator/b", "quote_price": 12000}, score=False),
    ]
    captured = {}

    def fake_chat_json(messages, config=None):
        payload = json.loads(messages[-1]["content"].split("\n", 1)[1])
        captured["creator_count"] = len(payload["creators"])
        captured["project"] = payload["project"]
        return {
            "results": [
                {
                    "creator_id": item["creator_id"],
                    "totalScore": 86,
                    "dimensionScores": {"budget": 90, "fans": 80, "cpe": 80, "engagement": 80, "persona": 90, "content": 85},
                    "hardFilterPassed": True,
                    "recommendLevel": "推荐",
                    "reason": f"{item['nickname']}适合教育场景",
                    "cooperationDirection": "答疑笔场景种草",
                    "manualReviewItems": ["搜索+推荐占比需人工确认"],
                    "evidenceQuotes": ["近期笔记出现作业答疑场景"],
                    "confidence": 0.86,
                    "promptVersion": "creator-score-v2-20260519",
                    "schemaVersion": "creator-score-structured-v2",
                }
                for item in payload["creators"]
            ]
        }

    monkeypatch.setattr("rpa_mcp_sync.creator_store.chat_json", fake_chat_json)
    scores = score_values_batch_with_llm(project_id, creators)

    assert captured["creator_count"] == 2
    assert "scoringCriteria" in captured["project"]
    assert "projectFitConfig" in captured["project"]
    assert "screening_plan" not in captured["project"]
    assert set(scores) == {creator["creator_id"] for creator in creators}
    assert all(score["cooperation_direction"] == "答疑笔场景种草" for score in scores.values())
    assert all(score["manual_review_items"] == ["搜索+推荐占比需人工确认"] for score in scores.values())
    assert all(score["evidence_quotes"] == ["近期笔记出现作业答疑场景"] for score in scores.values())
    assert all(score["llm_confidence"] == 0.86 for score in scores.values())


def test_rule_scoring_persists_system_defects_from_batch_benchmarks():
    project_id = f"pytest_system_defects_{uuid.uuid4().hex[:8]}"
    save_project(
        project_id,
        {
            "project_name": project_id,
            "brief": "教育答疑笔推广，需要教育、学习、作业答疑方向达人",
            "screening_plan": {
                "projectFitConfig": {
                    "preferred_content_scenes": ["作业答疑", "学习工具"],
                    "target_grade_keywords": ["初中"],
                }
            },
        },
    )
    good_ids = []
    for index in range(6):
        creator = upsert_creator(
            project_id,
            {
                "creator_id": f"{project_id}-good-{index}",
                "nickname": f"基准教育达人{index}",
                "pgy_url": f"https://pgy.xiaohongshu.com/creator/good-{index}",
                "followers_count": 80000,
                "quote_price": 4000,
                "daily_read_median": 12000 + index * 100,
                "daily_interaction_median": 900 + index * 10,
                "image_cpm": 80,
                "image_interaction_unit_price": 8,
                "reply_rate_48h": 0.8,
                "creator_type": "教育达人",
                "persona_tags": "初中学习/作业答疑/学习工具",
            },
            score=False,
        )
        good_ids.append(creator["creator_id"])
    bad = upsert_creator(
        project_id,
        {
            "creator_id": f"{project_id}-bad",
            "nickname": "硬缺陷达人",
            "pgy_url": "https://pgy.xiaohongshu.com/creator/bad",
            "followers_count": 80000,
            "quote_price": 4000,
            "daily_read_median": 2000,
            "daily_interaction_median": 100,
            "image_cpm": 200,
            "image_interaction_unit_price": 20,
            "reply_rate_48h": 0.42,
            "creator_type": "娱乐生活",
            "persona_tags": "穿搭/美妆/旅游",
        },
        score=False,
    )

    result = score_project(project_id, use_llm=False, creator_ids=[*good_ids, bad["creator_id"]], trigger_source="pytest_rule")

    assert result["scored"] == 7
    assert result["defects"]["creators_with_hard_defects"] >= 1
    scored_bad = get_creator(project_id, bad["creator_id"])
    defects = json.loads(scored_bad["hard_defects"])
    codes = {item["code"] for item in defects}
    assert {"LOW_48H_REPLY_RATE", "LOW_READ_MEDIAN", "LOW_INTERACTION_MEDIAN", "HIGH_CPM", "HIGH_CPE", "PROJECT_TAG_DIRECTION_MISMATCH"} <= codes
    assert scored_bad["hard_filter_passed"] == 0


def test_rule_scoring_handles_large_batch_without_llm(monkeypatch):
    project_id = f"pytest_fast_batch_{uuid.uuid4().hex[:8]}"
    creators = [
        {
            "creator_id": f"{project_id}-{index}",
            "nickname": f"批量达人{index}",
            "pgy_url": f"https://pgy.xiaohongshu.com/creator/{index}",
            "followers_count": 20000 + index,
            "quote_price": 1000,
            "daily_read_median": 3000,
            "daily_interaction_median": 200,
            "image_cpm": 90,
            "image_interaction_unit_price": 10,
            "reply_rate_48h": 0.8,
            "creator_type": "教育达人",
            "persona_tags": "学习/作业答疑",
        }
        for index in range(2005)
    ]
    bulk_upsert_creators(project_id, creators, score=False)

    def fail_llm(*args, **kwargs):
        raise AssertionError("rule batch scoring should not call LLM")

    monkeypatch.setattr("rpa_mcp_sync.creator_store.score_values_batch_with_llm", fail_llm)
    result = score_project(project_id, use_llm=False, trigger_source="pytest_large_rule")

    assert result["scored"] == 2005
    assert result["source"] == "rule"
    assert result["sources"]["rule"] == 2005


def test_llm_structured_output_persists_to_creator_scores(monkeypatch):
    project_id = f"pytest_llm_structured_{uuid.uuid4().hex[:8]}"
    creator = upsert_creator(
        project_id,
        {
            "creator_id": f"{project_id}-1",
            "nickname": "结构化LLM达人",
            "pgy_url": "https://pgy.xiaohongshu.com/creator/llm-structured",
            "quote_price": 8800,
            "fans_35_plus_ratio": 0.56,
            "daily_read_median": 12000,
            "daily_interaction_median": 900,
            "content_scene_tags": "作业答疑、错题讲解",
            "presentation_style_tags": "老师讲解型",
            "child_grade": "初二",
        },
        score=False,
    )

    def fake_chat_json(messages, config=None):
        return {
            "results": [
                {
                    "creator_id": creator["creator_id"],
                    "totalScore": 88,
                    "dimensionScores": {"budget": 80, "fans": 90, "cpe": 88, "engagement": 85, "persona": 92, "content": 90},
                    "hardFilterPassed": True,
                    "recommendLevel": "推荐",
                    "reason": "作业答疑和错题讲解证据较强",
                    "cooperationDirection": "答疑笔讲题场景",
                    "manualReviewItems": ["复核搜索+推荐占比", "确认老师身份"],
                    "evidenceQuotes": ["初二数学作业答疑", "错题讲解步骤拆解"],
                    "confidence": 0.91,
                    "promptVersion": "creator-score-v2-20260519",
                    "schemaVersion": "creator-score-structured-v2",
                }
            ]
        }

    monkeypatch.setattr("rpa_mcp_sync.creator_store.chat_json", fake_chat_json)
    result = score_project(project_id, use_llm=True, creator_ids=[creator["creator_id"]], trigger_source="manual")

    assert result["sources"]["llm"] == 1
    with connect() as conn:
        row = conn.execute(
            "SELECT manual_review_items, evidence_quotes, llm_confidence, llm_prompt_version, llm_schema_version FROM creator_scores WHERE creator_id=?",
            (creator["creator_id"],),
        ).fetchone()
    assert json.loads(row["manual_review_items"]) == ["复核搜索+推荐占比", "确认老师身份"]
    assert json.loads(row["evidence_quotes"]) == ["初二数学作业答疑", "错题讲解步骤拆解"]
    assert row["llm_confidence"] == 0.91
    assert row["llm_prompt_version"] == "creator-score-v2-20260519"
    assert row["llm_schema_version"] == "creator-score-structured-v2"

    fetched = get_creator(project_id, creator["creator_id"])
    assert json.loads(fetched["manual_review_items"]) == ["复核搜索+推荐占比", "确认老师身份"]


def test_score_project_runs_llm_chunks_in_parallel(monkeypatch):
    project_id = f"pytest_parallel_llm_{uuid.uuid4().hex[:8]}"
    creators = [
        upsert_creator(
            project_id,
            {
                "creator_id": f"{project_id}-{index}",
                "nickname": f"并发达人{index}",
                "pgy_url": f"https://pgy.xiaohongshu.com/creator/parallel-{index}",
                "quote_price": 8000 + index,
                "fans_35_plus_ratio": 0.5,
                "daily_read_median": 5000,
                "daily_interaction_median": 300,
            },
            score=False,
        )
        for index in range(8)
    ]
    lock = threading.Lock()
    active = 0
    max_active = 0
    chunk_sizes: list[int] = []

    def fake_score_values_batch_with_llm(project_id_arg, chunk):
        nonlocal active, max_active
        assert project_id_arg == project_id
        with lock:
            active += 1
            max_active = max(max_active, active)
            chunk_sizes.append(len(chunk))
        time.sleep(0.2)
        try:
            return {
                str(creator["creator_id"]): {
                    **score_values(creator),
                    "score_reason": f"【大模型分析】{creator['nickname']}并发评分完成",
                }
                for creator in chunk
            }
        finally:
            with lock:
                active -= 1

    monkeypatch.setattr("rpa_mcp_sync.creator_store.score_values_batch_with_llm", fake_score_values_batch_with_llm)

    result = score_project(project_id, use_llm=True, creator_ids=[creator["creator_id"] for creator in creators], trigger_source="manual")

    assert result["sources"]["llm"] == 8
    assert len(chunk_sizes) >= 2
    assert set(chunk_sizes) == {1}
    assert max_active >= 2


def test_manual_llm_score_retries_single_creator_once(monkeypatch):
    project_id = f"pytest_llm_retry_{uuid.uuid4().hex[:8]}"
    creator = upsert_creator(
        project_id,
        {
            "creator_id": f"{project_id}-1",
            "nickname": "重试达人",
            "pgy_url": "https://pgy.xiaohongshu.com/creator/retry",
            "quote_price": 800,
            "daily_read_median": 5000,
            "daily_interaction_median": 300,
        },
        score=False,
    )
    calls = 0

    def flaky_score_values_batch_with_llm(project_id_arg, chunk):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("temporary llm error")
        return {
            str(chunk[0]["creator_id"]): {
                **score_values(chunk[0], project_id=project_id_arg),
                "score_reason": "【大模型分析】重试后成功",
            }
        }

    monkeypatch.setattr("rpa_mcp_sync.creator_store.score_values_batch_with_llm", flaky_score_values_batch_with_llm)

    result = score_project(
        project_id,
        use_llm=True,
        creator_ids=[creator["creator_id"]],
        trigger_source="manual_ai",
        fallback_on_llm_error=False,
    )

    assert calls == 2
    assert result["sources"]["llm"] == 1


def test_manual_llm_score_raises_after_retry_without_rule_fallback(monkeypatch):
    project_id = f"pytest_llm_fail_{uuid.uuid4().hex[:8]}"
    creator = upsert_creator(
        project_id,
        {
            "creator_id": f"{project_id}-1",
            "nickname": "失败达人",
            "pgy_url": "https://pgy.xiaohongshu.com/creator/fail",
            "quote_price": 800,
        },
        score=False,
    )
    calls = 0

    def failing_score_values_batch_with_llm(project_id_arg, chunk):
        nonlocal calls
        calls += 1
        raise RuntimeError("bad llm config")

    monkeypatch.setattr("rpa_mcp_sync.creator_store.score_values_batch_with_llm", failing_score_values_batch_with_llm)

    try:
        score_project(
            project_id,
            use_llm=True,
            creator_ids=[creator["creator_id"]],
            trigger_source="manual_ai",
            fallback_on_llm_error=False,
        )
    except RuntimeError as error:
        assert "大模型评分失败" in str(error)
        assert creator["creator_id"] in str(error)
    else:
        raise AssertionError("manual AI scoring should surface LLM failures")
    assert calls == 2
