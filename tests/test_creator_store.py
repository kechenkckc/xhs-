import csv
import json
import uuid

from rpa_mcp_sync.creator_store import (
    change_creator_stage,
    creator_pool,
    creator_pool_detail,
    export_creator_pool_csv,
    generate_test_creators,
    get_creator,
    quality_feishu_rows,
    review_creator,
    score_creator,
    score_project,
    score_values,
    score_values_batch_with_llm,
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


def test_test_stage_scores_sample_creator_pool():
    project_id = "pytest_sample_pool"
    imported = 0
    with (ROOT / "有道答疑笔5-6月合作_测试项目" / "03_达人池实体表.csv").open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
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
    assert len(rows) >= 10
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

    assert row["主页链接"].endswith("/RinaGuGu")
    assert row["赞藏数/w"] == 162.5
    assert row["图文执行价（含平台服务费）"] == 6600
    assert row["视频执行价（含平台服务费）"] == 13200
    assert row["粉丝女性用户占比"] == "94.8%"
    assert row["粉丝年龄25-34占比"] == "37.7%"
    assert row["粉丝年龄25-44占比"] == "87.1%"
    assert row["粉丝年龄34岁以上占比"] == "56.9%"


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
                }
                for item in payload["creators"]
            ]
        }

    monkeypatch.setattr("rpa_mcp_sync.creator_store.chat_json", fake_chat_json)
    scores = score_values_batch_with_llm(project_id, creators)

    assert captured["creator_count"] == 2
    assert "scoringCriteria" in captured["project"]
    assert "screening_plan" not in captured["project"]
    assert set(scores) == {creator["creator_id"] for creator in creators}
    assert all(score["cooperation_direction"] == "答疑笔场景种草" for score in scores.values())
