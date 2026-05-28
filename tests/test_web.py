import json

from fastapi.testclient import TestClient

from rpa_mcp_sync.creator_store import connect
from rpa_mcp_sync.config_store import AI_PROVIDER_PATH, feishu_connection_path
from rpa_mcp_sync.pgy_browser import build_collection_plan
from rpa_mcp_sync.web import (
    app,
    _clear_sheet_audience_profile_image_values,
    _filter_creators_by_hard_filters,
    _find_sheet_audience_profile_image_field,
    _scheme_collect_limit,
    _scheme_plan,
)
from rpa_mcp_sync.creator_store import _project_hard_filter_issues


client = TestClient(app)


def test_projects_hide_pytest_records_by_default():
    project_id = "pytest_hidden_from_list"
    with connect() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO projects(project_id, project_name, target_qualified_creator_count, period_start, period_end, brief, screening_plan, created_at, updated_at)
            VALUES (?, ?, 10, '2026-05-07', '2026-05-19', '', '{}', '2026-05-09 12:00:00', '2026-05-09 12:00:00')
            """,
            (project_id, project_id),
        )

    response = client.get("/api/projects")
    assert response.status_code == 200
    project_ids = [project["project_id"] for project in response.json()["projects"]]
    assert project_id not in project_ids

    response = client.get("/api/projects?include_test_projects=true")
    assert response.status_code == 200
    project_ids = [project["project_id"] for project in response.json()["projects"]]
    assert project_id in project_ids

    with connect() as conn:
        conn.execute("DELETE FROM projects WHERE project_id=?", (project_id,))


def test_project_archive_restore_and_delete():
    project_id = "manage_project_case"
    with connect() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO projects(project_id, project_name, target_qualified_creator_count, period_start, period_end, brief, screening_plan, created_at, updated_at)
            VALUES (?, '管理测试项目', 10, '2026-05-07', '2026-05-19', '', '{}', '2026-05-09 13:00:00', '2026-05-09 13:00:00')
            """,
            (project_id,),
        )

    archive = client.post(f"/api/projects/{project_id}/archive")
    assert archive.status_code == 200
    assert archive.json()["project"]["archived_at"]

    default_ids = [project["project_id"] for project in client.get("/api/projects").json()["projects"]]
    assert project_id not in default_ids
    all_ids = [project["project_id"] for project in client.get("/api/projects?include_archived=true").json()["projects"]]
    assert project_id in all_ids

    restore = client.post(f"/api/projects/{project_id}/restore")
    assert restore.status_code == 200
    assert restore.json()["project"]["archived_at"] is None
    default_ids = [project["project_id"] for project in client.get("/api/projects").json()["projects"]]
    assert project_id in default_ids

    delete = client.delete(f"/api/projects/{project_id}")
    assert delete.status_code == 200
    assert delete.json()["deleted"] is True
    assert client.get(f"/api/projects/{project_id}").status_code == 404


def test_creators_endpoint_omits_raw_payload_by_default_but_can_include_it():
    project_id = "pytest_creator_light_payload"
    creator_id = "pytest-light-creator"
    raw_payload = {"recent_notes": [{"title": "学习工具测评", "content": "孩子作业答疑场景"}]}
    with connect() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO projects(project_id, project_name, target_qualified_creator_count, period_start, period_end, brief, screening_plan, created_at, updated_at)
            VALUES (?, ?, 10, '2026-05-07', '2026-05-19', '', '{}', '2026-05-09 12:00:00', '2026-05-09 12:00:00')
            """,
            (project_id, project_id),
        )
        conn.execute(
            """
            INSERT OR REPLACE INTO creators_global(
                creator_id, source, pgy_url, nickname, creator_type, persona_tags, ip_city, raw_payload, created_at, updated_at
            )
            VALUES (?, 'pgy', 'https://pgy.xiaohongshu.com/creator/light', '轻量达人', 'KOL', '教育', '北京', ?, '2026-05-09 12:00:00', '2026-05-09 12:00:00')
            """,
            (creator_id, json.dumps(raw_payload, ensure_ascii=False)),
        )
        conn.execute(
            """
            INSERT OR REPLACE INTO project_creators(project_id, creator_id, review_status, created_at, updated_at)
            VALUES (?, ?, '待审核', '2026-05-09 12:00:00', '2026-05-09 12:00:00')
            """,
            (project_id, creator_id),
        )

    light = client.get(f"/api/projects/{project_id}/creators")
    assert light.status_code == 200
    light_creator = light.json()["creators"][0]
    assert light_creator["raw_payload"] == "{}"

    full = client.get(f"/api/projects/{project_id}/creators?include_raw=true")
    assert full.status_code == 200
    full_creator = full.json()["creators"][0]
    assert json.loads(full_creator["raw_payload"])["recent_notes"][0]["title"] == "学习工具测评"

    detail = client.get(f"/api/projects/{project_id}/creators/{creator_id}")
    assert detail.status_code == 200
    assert json.loads(detail.json()["creator"]["raw_payload"])["recent_notes"][0]["title"] == "学习工具测评"

    client.delete(f"/api/projects/{project_id}")


def test_creators_endpoint_normalizes_display_tier_for_filtering():
    project_id = "pytest_creator_tier_normalize"
    creator_id = "pytest-tier-b-display"
    with connect() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO projects(project_id, project_name, target_qualified_creator_count, period_start, period_end, brief, screening_plan, created_at, updated_at)
            VALUES (?, ?, 10, '2026-05-07', '2026-05-19', '', '{}', '2026-05-09 12:00:00', '2026-05-09 12:00:00')
            """,
            (project_id, project_id),
        )
        conn.execute(
            """
            INSERT OR REPLACE INTO creators_global(
                creator_id, source, pgy_url, nickname, creator_type, persona_tags, ip_city, raw_payload, created_at, updated_at
            )
            VALUES (?, 'pgy', 'https://pgy.xiaohongshu.com/creator/tier-b', 'B档达人', 'KOC', '教育', '上海', '{}', '2026-05-09 12:00:00', '2026-05-09 12:00:00')
            """,
            (creator_id,),
        )
        conn.execute(
            """
            INSERT OR REPLACE INTO project_creators(project_id, creator_id, review_status, total_score, tier, created_at, updated_at)
            VALUES (?, ?, '待审核', 72, 'B档', '2026-05-09 12:00:00', '2026-05-09 12:00:00')
            """,
            (project_id, creator_id),
        )

    light = client.get(f"/api/projects/{project_id}/creators")
    assert light.status_code == 200
    assert light.json()["creators"][0]["initial_tier"] == "B"

    stats = client.get(f"/api/projects/{project_id}/creators/stats")
    assert stats.status_code == 200
    assert stats.json()["tiers"]["B"] == 1

    client.delete(f"/api/projects/{project_id}")


def test_creator_stats_use_final_score_tier_not_rule_group_score():
    project_id = "pytest_creator_stats_final_tier"
    creator_id = "pytest-tier-final-bplus"
    with connect() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO projects(project_id, project_name, target_qualified_creator_count, period_start, period_end, brief, screening_plan, created_at, updated_at)
            VALUES (?, ?, 10, '2026-05-07', '2026-05-19', '', '{}', '2026-05-09 12:00:00', '2026-05-09 12:00:00')
            """,
            (project_id, project_id),
        )
        conn.execute(
            """
            INSERT OR REPLACE INTO creators_global(
                creator_id, source, pgy_url, nickname, creator_type, persona_tags, ip_city, raw_payload, created_at, updated_at
            )
            VALUES (?, 'pgy', 'https://pgy.xiaohongshu.com/creator/final-bplus', '最终B+达人', 'KOC', '教育', '上海', '{}', '2026-05-09 12:00:00', '2026-05-09 12:00:00')
            """,
            (creator_id,),
        )
        conn.execute(
            """
            INSERT OR REPLACE INTO project_creators(project_id, creator_id, review_status, total_score, tier, created_at, updated_at)
            VALUES (?, ?, '待审核', 78, 'B+', '2026-05-09 12:00:00', '2026-05-09 12:00:00')
            """,
            (project_id, creator_id),
        )
        conn.execute(
            """
            INSERT OR REPLACE INTO creator_scores(creator_id, total_score, rule_group_score, initial_tier, scored_at)
            VALUES (?, 78, 98, 'S', '2026-05-09 12:00:00')
            """,
            (creator_id,),
        )

    light = client.get(f"/api/projects/{project_id}/creators")
    assert light.status_code == 200
    assert light.json()["creators"][0]["initial_tier"] == "B+"

    stats = client.get(f"/api/projects/{project_id}/creators/stats")
    assert stats.status_code == 200
    assert stats.json()["tiers"]["S"] == 0
    assert stats.json()["tiers"]["B+"] == 1

    client.delete(f"/api/projects/{project_id}")


def test_default_project_delete_does_not_recreate():
    project_id = "youdao_001"
    with connect() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO projects(project_id, project_name, target_qualified_creator_count, period_start, period_end, brief, screening_plan, created_at, updated_at)
            VALUES (?, '有道答疑笔5-6月合作', 10, '2026-05-07', '2026-05-19', '', '{}', '2026-05-09 13:00:00', '2026-05-09 13:00:00')
            """,
            (project_id,),
        )

    delete = client.delete(f"/api/projects/{project_id}")
    assert delete.status_code == 200
    assert client.get(f"/api/projects/{project_id}").status_code == 404
    project_ids = [project["project_id"] for project in client.get("/api/projects?include_archived=true").json()["projects"]]
    assert project_id not in project_ids

    with connect() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO projects(project_id, project_name, target_qualified_creator_count, period_start, period_end, brief, screening_plan, created_at, updated_at)
            VALUES (?, '有道答疑笔5-6月合作', 10, '2026-05-07', '2026-05-19', '', '{}', '2026-05-09 13:01:00', '2026-05-09 13:01:00')
            """,
            (project_id,),
        )


def test_pgy_collect_batch_persists_strategy_snapshot(monkeypatch):
    project_id = "pytest_collect_snapshot"
    plan = {
        "pgyCollectionPlan": {
            "filters": [{"field": "博主类目", "value": "教育", "reason": "测试"}],
            "display_metrics": ["粉丝数"],
        }
    }
    response = client.post(
        f"/api/projects/{project_id}",
        json={
            "project_name": project_id,
            "brief": "教育达人，优先北京上海",
            "screening_plan": plan,
        },
    )
    assert response.status_code == 200

    def fake_collect_visible_list(**kwargs):
        assert kwargs["include_details"] is False
        assert kwargs["export_metrics"] is True
        return {
            "ok": True,
            "creators": [
                {
                    "creator_id": "snapshot-creator-001",
                    "source": "pgy",
                    "nickname": "策略快照测试达人",
                    "pgy_url": "https://pgy.xiaohongshu.com/creator/snapshot-001",
                    "followers_count": 10000,
                    "quote_price": 12000,
                }
            ],
            "collection_plan": kwargs["screening_plan"]["pgyCollectionPlan"],
            "applied_filters": [{"field": "博主类目", "value": "教育", "message": "已点击页面筛选项"}],
            "skipped_filters": [{"field": "地域", "value": "北京/上海优先", "message": "该条件需要下拉/区间细分，已保留在采集计划中"}],
            "selected_metrics": [{"metric": "粉丝数", "message": "已选中"}],
            "skipped_metrics": [{"metric": "互动中位数（日常）", "message": "弹窗内未找到该指标"}],
            "detail_collection": "planned",
            "export_result": {
                "status": "success",
                "path": "runtime/exports/pgy/test.csv",
                "parsed": {
                    "status": "parsed",
                    "creators": [
                        {
                            "source": "pgy",
                            "nickname": "策略快照测试达人",
                            "cooperation_read_median": "22,000",
                            "cooperation_interaction_median": "880",
                            "overflow_store_unit_price": "1.6",
                            "raw_payload": {"export_row": {"阅读中位数（合作）": "22,000"}},
                        }
                    ],
                },
            },
        }

    monkeypatch.setattr("rpa_mcp_sync.web.collect_visible_list", fake_collect_visible_list)
    monkeypatch.setattr("rpa_mcp_sync.web.score_project", lambda project_id, **kwargs: {"scored": len(kwargs.get("creator_ids") or [])})

    collect = client.post(
        "/api/pgy/collect/batch",
        json={
            "project_id": project_id,
            "screening_plan": plan,
            "apply_filters": True,
            "include_details": False,
            "export_metrics": True,
            "limit": 20,
        },
    )
    assert collect.status_code == 200
    payload = collect.json()
    assert payload["ok"] is True
    batch = payload["batch"]
    assert batch["collection_plan"]["filters"][0]["value"] == "教育"
    assert batch["applied_filters"][0]["message"] == "已点击页面筛选项"
    assert batch["skipped_filters"][0]["value"] == "北京/上海优先"
    assert batch["selected_metrics"][0]["metric"] == "粉丝数"
    assert batch["skipped_metrics"][0]["metric"] == "互动中位数（日常）"
    assert batch["detail_collection"] == "planned"
    assert payload["export_result"]["status"] == "success"
    assert payload["creators"][0]["cooperation_read_median"] == "22,000"

    batches = client.get(f"/api/projects/{project_id}/batches")
    assert batches.status_code == 200
    latest = batches.json()["batches"][0]
    assert latest["batch_id"] == batch["batch_id"]
    assert latest["collection_plan"] == batch["collection_plan"]
    assert latest["applied_filters"] == batch["applied_filters"]

    client.delete(f"/api/projects/{project_id}")


def test_pgy_collect_batch_continues_collectable_schemes_until_limit(monkeypatch):
    project_id = "pytest_collect_multi_scheme"
    plan = {
        "pgyCollectionPlan": {
            "schemes": [
                {
                    "scheme_id": "education_core",
                    "name": "教育核心池",
                    "filters": [{"field": "博主类目", "value": "教育", "reason": "教育场景"}],
                },
                {
                    "scheme_id": "parent_family",
                    "name": "亲子家庭池",
                    "filters": [{"field": "博主类目", "value": "母婴", "reason": "亲子场景"}],
                },
            ],
            "display_metrics": ["全部非直播指标"],
        }
    }
    client.post(
        f"/api/projects/{project_id}",
        json={"project_name": project_id, "brief": "有道答疑笔教育亲子达人", "screening_plan": plan},
    )
    calls = []

    def fake_collect_visible_list(**kwargs):
        pgy_plan = kwargs["screening_plan"]["pgyCollectionPlan"]
        calls.append({"scheme": pgy_plan["active_scheme_id"], "reset": kwargs.get("reset_filters")})
        if kwargs.get("preflight_only"):
            return {
                "ok": True,
                "collection_plan": kwargs["screening_plan"]["pgyCollectionPlan"],
                "applied_filters": [{"field": "博主类目", "value": pgy_plan["filters"][0]["value"], "message": "已点击页面筛选项"}],
                "skipped_filters": [],
                "selected_metrics": [],
                "skipped_metrics": [],
                "actual_recommend_count": 2,
                "actual_count_text": "推荐 2 位博主",
                "export_result": {"status": "skipped"},
            }
        creator_id = "shared-creator" if pgy_plan["active_scheme_id"] == "parent_family" else "education-creator"
        return {
            "ok": True,
            "creators": [
                {
                    "creator_id": creator_id,
                    "source": "pgy",
                    "nickname": f"{pgy_plan['active_scheme_name']}达人",
                    "pgy_url": f"https://pgy.xiaohongshu.com/creator/{creator_id}",
                    "quote_price": 12000,
                },
                {
                    "creator_id": "shared-creator",
                    "source": "pgy",
                    "nickname": "重复达人",
                    "pgy_url": "https://pgy.xiaohongshu.com/creator/shared",
                    "quote_price": 9000,
                },
            ],
            "collection_plan": kwargs["screening_plan"]["pgyCollectionPlan"],
            "applied_filters": [{"field": "博主类目", "value": pgy_plan["filters"][0]["value"], "message": "已点击页面筛选项"}],
            "skipped_filters": [],
            "selected_metrics": [],
            "skipped_metrics": [],
            "export_result": {"status": "success", "path": f"runtime/exports/pgy/{pgy_plan['active_scheme_id']}.csv"},
        }

    monkeypatch.setattr("rpa_mcp_sync.web.collect_visible_list", fake_collect_visible_list)
    monkeypatch.setattr("rpa_mcp_sync.web.score_project", lambda project_id, **kwargs: {"scored": len(kwargs.get("creator_ids") or [])})

    response = client.post(
        "/api/pgy/collect/batch",
        json={"project_id": project_id, "screening_plan": plan, "limit": 20},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert [item["scheme_id"] for item in payload["scheme_results"]] == ["education_core", "parent_family"]
    assert calls == [
        {"scheme": "education_core", "reset": True},
        {"scheme": "education_core", "reset": False},
        {"scheme": "parent_family", "reset": True},
        {"scheme": "parent_family", "reset": False},
    ]
    assert payload["batch"]["total_count"] == 2
    assert payload["batch"]["success_count"] == 2
    assert payload["scheme_results"][0]["estimated_count"] == 2
    assert payload["scheme_results"][0]["estimated_count_text"] == "推荐 2 位博主"
    assert payload["scheme_results"][0]["ingested_count"] == 2
    assert payload["scheme_results"][1]["ingested_count"] == 0
    assert payload["batch"]["collection_plan"]["schemes"][0]["ingested_count"] == 2
    assert {creator["creator_id"] for creator in payload["creators"]} == {"education-creator", "shared-creator"}
    assert payload["export_result"]["status"] == "multi_scheme"
    client.delete(f"/api/projects/{project_id}")


def test_pgy_collect_batch_ingests_each_scheme_before_next_preflight(monkeypatch):
    project_id = "pytest_collect_scheme_ingest_loop"
    plan = {
        "pgyCollectionPlan": {
            "schemes": [
                {"scheme_id": "first", "name": "第一方案", "filters": [{"field": "博主类目", "value": "教育"}]},
                {"scheme_id": "second", "name": "第二方案", "filters": [{"field": "博主类目", "value": "母婴"}]},
            ],
        }
    }
    client.post(f"/api/projects/{project_id}", json={"project_name": project_id, "brief": "教育亲子达人", "screening_plan": plan})
    events = []

    def fake_collect_visible_list(**kwargs):
        pgy_plan = kwargs["screening_plan"]["pgyCollectionPlan"]
        scheme_id = pgy_plan["active_scheme_id"]
        events.append(f"{'preflight' if kwargs.get('preflight_only') else 'collect'}:{scheme_id}")
        if kwargs.get("preflight_only"):
            return {
                "ok": True,
                "collection_plan": pgy_plan,
                "applied_filters": [],
                "skipped_filters": [],
                "selected_metrics": [],
                "skipped_metrics": [],
                "actual_recommend_count": 1,
                "actual_count_text": "推荐 1 位博主",
                "export_result": {"status": "skipped"},
            }
        return {
            "ok": True,
            "creators": [{"creator_id": f"{scheme_id}-creator", "source": "pgy", "nickname": f"{scheme_id}达人"}],
            "collection_plan": pgy_plan,
            "applied_filters": [],
            "skipped_filters": [],
            "selected_metrics": [],
            "skipped_metrics": [],
            "export_result": {"status": "skipped"},
        }

    def fake_bulk_upsert_creators(project_id_arg, creators, score=False):
        ids = [creator["creator_id"] for creator in creators]
        events.append(f"bulk:{','.join(ids)}:score={score}")
        return [{"creator_id": creator_id, "action": "新增达人"} for creator_id in ids]

    def fake_queue_collect_scoring(project_id_arg, creator_ids, batch_id):
        events.append("score:" + ",".join(creator_ids))
        return {"async": True, "queued": len(creator_ids)}

    monkeypatch.setattr("rpa_mcp_sync.web.collect_visible_list", fake_collect_visible_list)
    monkeypatch.setattr("rpa_mcp_sync.web.bulk_upsert_creators", fake_bulk_upsert_creators)
    monkeypatch.setattr("rpa_mcp_sync.web._queue_collect_scoring", fake_queue_collect_scoring)

    response = client.post("/api/pgy/collect/batch", json={"project_id": project_id, "screening_plan": plan, "limit": 10})

    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert events == [
        "preflight:first",
        "collect:first",
        "bulk:first-creator:score=True",
        "preflight:second",
        "collect:second",
        "bulk:second-creator:score=True",
    ]
    client.delete(f"/api/projects/{project_id}")


def test_pgy_collect_batch_uses_saved_enabled_scheme_ids(monkeypatch):
    project_id = "pytest_collect_saved_enabled_scheme"
    plan = {
        "pgyCollectionPlan": {
            "enabled_scheme_ids": ["parent_family"],
            "schemes": [
                {"scheme_id": "education_core", "name": "教育核心池", "filters": [{"field": "博主类目", "value": "教育"}]},
                {"scheme_id": "parent_family", "name": "亲子家庭池", "filters": [{"field": "博主类目", "value": "母婴"}]},
            ],
        }
    }
    client.post(
        f"/api/projects/{project_id}",
        json={"project_name": project_id, "brief": "亲子达人", "screening_plan": plan},
    )
    calls = []

    def fake_collect_visible_list(**kwargs):
        pgy_plan = kwargs["screening_plan"]["pgyCollectionPlan"]
        calls.append(pgy_plan["active_scheme_id"])
        if kwargs.get("preflight_only"):
            return {
                "ok": True,
                "collection_plan": pgy_plan,
                "applied_filters": [],
                "skipped_filters": [],
                "selected_metrics": [],
                "skipped_metrics": [],
                "actual_recommend_count": 1,
                "actual_count_text": "推荐 1 位博主",
            }
        return {
            "ok": True,
            "creators": [{"creator_id": "parent-creator", "source": "pgy", "nickname": "亲子方案达人"}],
            "collection_plan": pgy_plan,
            "applied_filters": [],
            "skipped_filters": [],
            "selected_metrics": [],
            "skipped_metrics": [],
            "export_result": {"status": "skipped"},
        }

    monkeypatch.setattr("rpa_mcp_sync.web.collect_visible_list", fake_collect_visible_list)
    monkeypatch.setattr("rpa_mcp_sync.web.score_project", lambda project_id, **kwargs: {"scored": len(kwargs.get("creator_ids") or [])})

    response = client.post("/api/pgy/collect/batch", json={"project_id": project_id, "screening_plan": plan, "limit": 10})

    assert response.status_code == 200
    payload = response.json()
    assert [item["scheme_id"] for item in payload["scheme_results"]] == ["parent_family"]
    assert calls == ["parent_family", "parent_family"]
    assert payload["scheme_results"][0]["estimated_count_text"] == "推荐 1 位博主"
    assert payload["scheme_results"][0]["ingested_count"] == 1
    client.delete(f"/api/projects/{project_id}")


def test_pgy_collect_batch_reads_saved_scheme_config_when_payload_plan_empty(monkeypatch):
    project_id = "pytest_collect_saved_scheme_config"
    plan = {
        "pgyCollectionPlan": {
            "enabled_scheme_ids": ["parent_family"],
            "schemes": [
                {
                    "scheme_id": "education_core",
                    "name": "教育核心池",
                    "required_filters": [{"field": "博主类目", "value": "教育"}],
                },
                {
                    "scheme_id": "parent_family",
                    "name": "亲子家庭池",
                    "required_filters": [
                        {"field": "博主类目", "value": "母婴"},
                        {"field": "粉丝量", "value": "1万-10万"},
                    ],
                    "enabled_additional_filters": [{"field": "地域", "value": "上海"}],
                    "additional_filters": [{"field": "地域", "value": "上海"}],
                },
            ],
        }
    }
    client.post(
        f"/api/projects/{project_id}",
        json={"project_name": project_id, "brief": "上海亲子达人", "screening_plan": plan},
    )
    seen_plans = []

    def fake_collect_visible_list(**kwargs):
        pgy_plan = kwargs["screening_plan"]["pgyCollectionPlan"]
        seen_plans.append(
            {
                "scheme_id": pgy_plan.get("active_scheme_id"),
                "filters": pgy_plan.get("filters") or [],
            }
        )
        if kwargs.get("preflight_only"):
            return {
                "ok": True,
                "collection_plan": pgy_plan,
                "applied_filters": pgy_plan.get("filters") or [],
                "skipped_filters": [],
                "selected_metrics": [],
                "skipped_metrics": [],
                "actual_recommend_count": 1,
                "actual_count_text": "推荐 1 位博主",
            }
        return {
            "ok": True,
            "creators": [{"creator_id": "parent-shanghai-creator", "source": "pgy", "nickname": "上海亲子达人"}],
            "collection_plan": pgy_plan,
            "applied_filters": pgy_plan.get("filters") or [],
            "skipped_filters": [],
            "selected_metrics": [],
            "skipped_metrics": [],
            "export_result": {"status": "skipped"},
        }

    monkeypatch.setattr("rpa_mcp_sync.web.collect_visible_list", fake_collect_visible_list)
    monkeypatch.setattr("rpa_mcp_sync.web.score_project", lambda project_id, **kwargs: {"scored": len(kwargs.get("creator_ids") or [])})

    response = client.post("/api/pgy/collect/batch", json={"project_id": project_id, "limit": 10})

    assert response.status_code == 200
    payload = response.json()
    assert [item["scheme_id"] for item in payload["scheme_results"]] == ["parent_family"]
    assert [item["scheme_id"] for item in seen_plans] == ["parent_family", "parent_family"]
    assert any(item["field"] == "博主类目" and item["value"] == "母婴" for item in seen_plans[-1]["filters"])
    follower_filter = next(item for item in seen_plans[-1]["filters"] if item["field"] == "粉丝量")
    assert follower_filter["value"] == "1万以上"
    assert follower_filter["min"] == 10000
    assert follower_filter["max"] == ""
    assert follower_filter["range_policy"] == "min_only"
    assert any(item.get("field") == "地域" and item.get("value") == "上海" for item in seen_plans[-1]["filters"])
    assert payload["scheme_results"][0]["ingested_count"] == 1
    client.delete(f"/api/projects/{project_id}")


def test_pgy_collect_batch_skips_scheme_when_preflight_count_too_many(monkeypatch):
    project_id = "pytest_collect_preflight_too_many"
    plan = {
        "pgyCollectionPlan": {
            "target_count_range": "50-300",
            "schemes": [
                {
                    "scheme_id": "broad",
                    "name": "过宽方案",
                    "target_count_range": "50-300",
                    "filters": [{"field": "博主类目", "value": "教育", "reason": "教育场景"}],
                }
            ],
        }
    }
    client.post(f"/api/projects/{project_id}", json={"project_name": project_id, "brief": "有道答疑笔", "screening_plan": plan})
    calls = []

    def fake_collect_visible_list(**kwargs):
        calls.append(bool(kwargs.get("preflight_only")))
        return {
            "ok": True,
            "collection_plan": kwargs["screening_plan"]["pgyCollectionPlan"],
            "applied_filters": [],
            "skipped_filters": [],
            "selected_metrics": [],
            "skipped_metrics": [],
            "actual_recommend_count": 5000,
            "actual_count_text": "推荐 5000+ 位博主",
            "actual_count_is_lower_bound": True,
            "creators": [] if kwargs.get("preflight_only") else [{"creator_id": "should-not-run"}],
            "export_result": {"status": "skipped"},
        }

    monkeypatch.setattr("rpa_mcp_sync.web.collect_visible_list", fake_collect_visible_list)
    monkeypatch.setattr("rpa_mcp_sync.web.score_project", lambda project_id, **kwargs: {"scored": len(kwargs.get("creator_ids") or [])})

    response = client.post("/api/pgy/collect/batch", json={"project_id": project_id, "screening_plan": plan})

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is False
    assert calls == [True]
    preflight = payload["scheme_results"][0]["preflight"]
    assert preflight["actual_recommend_count"] == 5000
    assert preflight["evaluation"]["status"] == "too_many"
    assert preflight["collected_after_preflight"] is False
    assert payload["batch"]["error_message"]
    client.delete(f"/api/projects/{project_id}")


def test_pgy_collect_batch_adds_additional_filters_in_order_until_count_ok(monkeypatch):
    project_id = "pytest_collect_additional_order"
    plan = {
        "pgyCollectionPlan": {
            "target_count_range": "50-2000",
            "schemes": [
                {
                    "scheme_id": "ordered",
                    "name": "顺序附加方案",
                    "target_count_range": "50-2000",
                    "required_filters": [
                        {"field": "博主类目", "value": "教育"},
                        {"field": "粉丝量", "value": "1万～10万"},
                        {"field": "粉丝年龄", "value": "35～44 占比高"},
                        {"field": "合作报价", "value": "图文笔记：0.1万～2万"},
                    ],
                    "additional_filters": [
                        {"field": "预估阅读单价", "value": "图文笔记阅读单价≤2"},
                        {"field": "预估互动单价", "value": "图文笔记互动单价≤20"},
                    ],
                }
            ],
        }
    }
    client.post(f"/api/projects/{project_id}", json={"project_name": project_id, "brief": "有道答疑笔", "screening_plan": plan})
    counts = [5000, 1]
    calls = []

    def fake_collect_visible_list(**kwargs):
        pgy_plan = kwargs["screening_plan"]["pgyCollectionPlan"]
        fields = [item["field"] for item in pgy_plan["filters"]]
        calls.append({"preflight": bool(kwargs.get("preflight_only")), "reset": kwargs.get("reset_filters"), "fields": fields})
        if kwargs.get("preflight_only"):
            count = counts.pop(0)
            return {
                "ok": True,
                "collection_plan": pgy_plan,
                "applied_filters": [{"field": field, "value": field} for field in fields],
                "skipped_filters": [],
                "selected_metrics": [],
                "skipped_metrics": [],
                "actual_recommend_count": count,
                "actual_count_text": f"推荐 {count} 位博主",
                "export_result": {"status": "skipped"},
            }
        return {
            "ok": True,
            "creators": [{"creator_id": "ordered-creator", "nickname": "顺序达人", "pgy_url": "https://pgy.xiaohongshu.com/creator/ordered"}],
            "collection_plan": pgy_plan,
            "applied_filters": [{"field": field, "value": field} for field in fields],
            "skipped_filters": [],
            "selected_metrics": [],
            "skipped_metrics": [],
            "export_result": {"status": "skipped"},
        }

    monkeypatch.setattr("rpa_mcp_sync.web.collect_visible_list", fake_collect_visible_list)
    monkeypatch.setattr("rpa_mcp_sync.web.score_project", lambda project_id, **kwargs: {"scored": len(kwargs.get("creator_ids") or [])})

    response = client.post("/api/pgy/collect/batch", json={"project_id": project_id, "screening_plan": plan})

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert calls == [
        {"preflight": True, "reset": True, "fields": ["博主类目", "粉丝量", "粉丝年龄", "合作报价"]},
        {"preflight": True, "reset": False, "fields": ["博主类目", "粉丝量", "粉丝年龄", "合作报价", "预估互动单价"]},
        {"preflight": False, "reset": False, "fields": ["博主类目", "粉丝量", "粉丝年龄", "合作报价", "预估互动单价"]},
    ]
    preflight = payload["scheme_results"][0]["preflight"]
    assert [step["actual_recommend_count"] for step in preflight["steps"]] == [5000, 1]
    assert [item["field"] for item in preflight["active_additional_filters"]] == ["预估互动单价"]
    client.delete(f"/api/projects/{project_id}")


def test_pgy_collect_batch_adjusts_additional_filter_parameter_before_next_filter(monkeypatch):
    project_id = "pytest_collect_adaptive_additional_parameter"
    plan = {
        "pgyCollectionPlan": {
            "target_count_range": "80-800",
            "schemes": [
                {
                    "scheme_id": "adaptive",
                    "name": "自适应附加方案",
                    "target_count_range": "80-800",
                    "required_filters": [{"field": "博主类目", "value": "教育"}],
                    "additional_filters": [
                        {
                            "field": "预估互动单价",
                            "value": "图文笔记互动单价≤20",
                            "sub_field": "图文笔记互动单价",
                            "max": 20,
                            "control_type": "subfield_preset_or_number_range",
                            "adaptive_direction": "max",
                            "adaptive_values": [20, 15, 10],
                        },
                    ],
                }
            ],
        }
    }
    client.post(f"/api/projects/{project_id}", json={"project_name": project_id, "brief": "有道留学听课宝", "screening_plan": plan})
    counts = [5000, 2500, 2600, 2700, 2800, 2900, 1800]
    calls = []

    def fake_collect_visible_list(**kwargs):
        pgy_plan = kwargs["screening_plan"]["pgyCollectionPlan"]
        filters = pgy_plan["filters"]
        calls.append(
            {
                "preflight": bool(kwargs.get("preflight_only")),
                "filters": [(item["field"], item["value"]) for item in filters],
            }
        )
        if kwargs.get("preflight_only"):
            count = counts.pop(0)
            return {
                "ok": True,
                "collection_plan": pgy_plan,
                "applied_filters": filters,
                "skipped_filters": [],
                "selected_metrics": [],
                "skipped_metrics": [],
                "actual_recommend_count": count,
                "actual_count_text": f"推荐 {count} 位博主",
                "export_result": {"status": "skipped"},
            }
        return {
            "ok": True,
            "creators": [{"creator_id": "adaptive-creator", "nickname": "自适应达人", "pgy_url": "https://pgy.xiaohongshu.com/creator/adaptive"}],
            "collection_plan": pgy_plan,
            "applied_filters": filters,
            "skipped_filters": [],
            "selected_metrics": [],
            "skipped_metrics": [],
            "export_result": {"status": "skipped"},
        }

    monkeypatch.setattr("rpa_mcp_sync.web.collect_visible_list", fake_collect_visible_list)
    monkeypatch.setattr("rpa_mcp_sync.web.score_project", lambda project_id, **kwargs: {"scored": len(kwargs.get("creator_ids") or [])})

    response = client.post("/api/pgy/collect/batch", json={"project_id": project_id, "screening_plan": plan})

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    steps = payload["scheme_results"][0]["preflight"]["steps"]
    assert [step["actual_recommend_count"] for step in steps] == [5000, 2500, 2600, 2700, 2800, 2900, 1800]
    active_filters = payload["scheme_results"][0]["preflight"]["active_additional_filters"]
    active_pairs = [(item["field"], item["value"]) for item in active_filters]
    assert ("预估互动单价", "图文笔记互动单价/视频笔记互动单价≤30") in active_pairs
    assert ("曝光中位数", "0.1万以上") in active_pairs
    assert ("阅读中位数", "500以上") in active_pairs
    assert ("互动中位数", "50以上") in active_pairs
    assert ("预估阅读单价", "图文笔记阅读单价/视频笔记阅读单价≤3") in active_pairs
    assert payload["scheme_results"][0]["preflight"]["steps"][-1]["stage"] == "additional_adjustment"
    client.delete(f"/api/projects/{project_id}")


def test_pgy_collect_batch_uses_preflight_count_as_scheme_limit(monkeypatch):
    project_id = "pytest_collect_preflight_count_limit"
    plan = {
        "pgyCollectionPlan": {
            "target_count_range": "50-2000",
            "schemes": [
                {
                    "scheme_id": "wide",
                    "name": "宽方案",
                    "target_count_range": "50-2000",
                    "target_quota": 12,
                    "max_quota": 18,
                    "required_filters": [{"field": "博主类目", "value": "教育"}],
                }
            ],
        }
    }
    client.post(f"/api/projects/{project_id}", json={"project_name": project_id, "brief": "有道答疑笔", "screening_plan": plan})
    seen_limits = []

    def fake_collect_visible_list(**kwargs):
        seen_limits.append({"preflight": bool(kwargs.get("preflight_only")), "limit": kwargs.get("limit")})
        pgy_plan = kwargs["screening_plan"]["pgyCollectionPlan"]
        if kwargs.get("preflight_only"):
            return {
                "ok": True,
                "collection_plan": pgy_plan,
                "applied_filters": [],
                "skipped_filters": [],
                "selected_metrics": [],
                "skipped_metrics": [],
                "actual_recommend_count": 3,
                "actual_count_text": "推荐 3 位博主",
                "export_result": {"status": "skipped"},
            }
        return {
            "ok": True,
            "creators": [
                {"creator_id": f"wide-creator-{index}", "nickname": f"宽方案达人{index}"}
                for index in range(3)
            ],
            "collection_plan": pgy_plan,
            "applied_filters": [],
            "skipped_filters": [],
            "selected_metrics": [],
            "skipped_metrics": [],
            "export_result": {"status": "skipped"},
        }

    monkeypatch.setattr("rpa_mcp_sync.web.collect_visible_list", fake_collect_visible_list)
    monkeypatch.setattr("rpa_mcp_sync.web.score_project", lambda project_id, **kwargs: {"scored": len(kwargs.get("creator_ids") or [])})

    response = client.post("/api/pgy/collect/batch", json={"project_id": project_id, "screening_plan": plan, "limit": 1000})

    assert response.status_code == 200
    assert seen_limits == [
        {"preflight": True, "limit": 1000},
        {"preflight": False, "limit": 3},
    ]
    client.delete(f"/api/projects/{project_id}")


def test_pgy_collect_batch_stops_before_next_scheme_when_collection_shortfall(monkeypatch):
    project_id = "pytest_collect_shortfall_stops"
    plan = {
        "pgyCollectionPlan": {
            "target_count_range": "50-2000",
            "schemes": [
                {
                    "scheme_id": "short",
                    "name": "少采方案",
                    "target_count_range": "50-2000",
                    "required_filters": [{"field": "博主类目", "value": "教育"}],
                },
                {
                    "scheme_id": "next",
                    "name": "下一方案",
                    "target_count_range": "50-2000",
                    "required_filters": [{"field": "博主类目", "value": "母婴"}],
                },
            ],
        }
    }
    client.post(f"/api/projects/{project_id}", json={"project_name": project_id, "brief": "有道答疑笔", "screening_plan": plan})
    calls = []

    def fake_collect_visible_list(**kwargs):
        pgy_plan = kwargs["screening_plan"]["pgyCollectionPlan"]
        calls.append({"scheme": pgy_plan["active_scheme_id"], "preflight": bool(kwargs.get("preflight_only"))})
        if kwargs.get("preflight_only"):
            return {
                "ok": True,
                "collection_plan": pgy_plan,
                "applied_filters": [],
                "skipped_filters": [],
                "selected_metrics": [],
                "skipped_metrics": [],
                "actual_recommend_count": 5,
                "actual_count_text": "推荐 5 位博主",
                "export_result": {"status": "skipped"},
            }
        return {
            "ok": True,
            "creators": [{"creator_id": "only-one", "nickname": "只采到一个"}],
            "collection_plan": pgy_plan,
            "applied_filters": [],
            "skipped_filters": [],
            "selected_metrics": [],
            "skipped_metrics": [],
            "export_result": {"status": "skipped"},
        }

    monkeypatch.setattr("rpa_mcp_sync.web.collect_visible_list", fake_collect_visible_list)
    monkeypatch.setattr("rpa_mcp_sync.web.score_project", lambda project_id, **kwargs: {"scored": len(kwargs.get("creator_ids") or [])})

    response = client.post("/api/pgy/collect/batch", json={"project_id": project_id, "screening_plan": plan, "limit": 20})

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is False
    assert calls == [
        {"scheme": "short", "preflight": True},
        {"scheme": "short", "preflight": False},
    ]
    assert [item["scheme_id"] for item in payload["scheme_results"]] == ["short"]
    shortfall = payload["scheme_results"][0]["collection_shortfall"]
    assert shortfall["expected_count"] == 5
    assert shortfall["collected_count"] == 1
    assert "避免未采完就应用下一套筛选条件" in payload["message"]
    client.delete(f"/api/projects/{project_id}")


def test_pgy_collect_batch_accepts_partial_shortfall_on_last_scheme(monkeypatch):
    project_id = "pytest_collect_last_shortfall_accepts"
    plan = {
        "pgyCollectionPlan": {
            "target_count_range": "50-2000",
            "schemes": [
                {
                    "scheme_id": "last",
                    "name": "最后方案",
                    "target_count_range": "50-2000",
                    "required_filters": [{"field": "博主类目", "value": "教育"}],
                },
            ],
        }
    }
    client.post(f"/api/projects/{project_id}", json={"project_name": project_id, "brief": "有道留学听课宝", "screening_plan": plan})

    def fake_collect_visible_list(**kwargs):
        pgy_plan = kwargs["screening_plan"]["pgyCollectionPlan"]
        if kwargs.get("preflight_only"):
            return {
                "ok": True,
                "collection_plan": pgy_plan,
                "applied_filters": [],
                "skipped_filters": [],
                "selected_metrics": [],
                "skipped_metrics": [],
                "actual_recommend_count": 20,
                "actual_count_text": "推荐 20 位博主",
                "export_result": {"status": "skipped"},
            }
        return {
            "ok": True,
            "creators": [
                {"creator_id": f"last-{index}", "nickname": f"最后方案达人{index}", "pgy_url": f"https://pgy.xiaohongshu.com/creator/last-{index}"}
                for index in range(16)
            ],
            "collection_plan": pgy_plan,
            "applied_filters": [],
            "skipped_filters": [],
            "selected_metrics": [],
            "skipped_metrics": [],
            "export_result": {"status": "skipped"},
        }

    monkeypatch.setattr("rpa_mcp_sync.web.collect_visible_list", fake_collect_visible_list)
    monkeypatch.setattr("rpa_mcp_sync.web.score_project", lambda project_id, **kwargs: {"scored": len(kwargs.get("creator_ids") or [])})

    response = client.post("/api/pgy/collect/batch", json={"project_id": project_id, "screening_plan": plan, "limit": 20})

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert len(payload["creators"]) == 16
    shortfall = payload["scheme_results"][0]["collection_shortfall"]
    assert shortfall["warning"] is True
    assert shortfall["expected_count"] == 20
    assert shortfall["collected_count"] == 16
    assert "继续入库" in shortfall["message"]
    assert payload["scheme_results"][0]["ingested_count"] == 16
    client.delete(f"/api/projects/{project_id}")


def test_scheme_plan_uses_required_filters_profile_extra_and_manual_only_user_filters():
    screening_plan = {
        "pgyCollectionPlan": {
            "filters": [
                {"field": "特色背景", "value": "备考经验"},
                {"field": "职业身份", "value": "教育科研", "manual": True, "source": "frontend"},
            ]
        }
    }
    scheme = {
        "scheme_id": "clean",
        "required_filters": [
            {"field": "博主类目", "value": "教育"},
            {"field": "粉丝量", "value": "1万～10万"},
            {"field": "粉丝年龄", "value": "35～44 占比高"},
            {"field": "合作报价", "value": "图文笔记：0.1万～2万"},
        ],
        "additional_filters": [{"field": "预估互动单价", "value": "图文笔记互动单价≤20"}],
    }

    plan = _scheme_plan(screening_plan, scheme)
    pgy_plan = plan["pgyCollectionPlan"]

    assert [item["field"] for item in pgy_plan["required_filters"]] == ["博主类目", "粉丝量", "粉丝年龄", "合作报价"]
    assert [item["field"] for item in pgy_plan["additional_filters"]] == ["预估互动单价"]
    assert [item["field"] for item in pgy_plan["filters"]] == ["博主类目", "粉丝量", "粉丝年龄", "合作报价", "特色背景", "职业身份"]
    follower_filter = next(item for item in pgy_plan["required_filters"] if item["field"] == "粉丝量")
    assert follower_filter["value"] == "1万以上"
    assert follower_filter["max"] == ""


def test_pgy_scheme_memory_blends_next_expected_count(monkeypatch):
    project_id = "pytest_collect_memory"
    plan = {
        "pgyCollectionPlan": {
            "target_count_range": "50-300",
            "schemes": [
                {
                    "scheme_id": "memory_scheme",
                    "name": "记忆方案",
                    "target_count_range": "50-300",
                    "filters": [
                        {"field": "营销目标", "value": "种草", "reason": "测试"},
                        {"field": "博主类目", "value": "教育", "reason": "测试"},
                    ],
                }
            ],
        }
    }
    client.post(f"/api/projects/{project_id}", json={"project_name": project_id, "brief": "有道答疑笔", "screening_plan": plan})
    counts = [240, 180]

    def fake_collect_visible_list(**kwargs):
        pgy_plan = kwargs["screening_plan"]["pgyCollectionPlan"]
        if kwargs.get("preflight_only"):
            count = counts.pop(0)
            return {
                "ok": True,
                "collection_plan": pgy_plan,
                "applied_filters": [],
                "skipped_filters": [],
                "selected_metrics": [],
                "skipped_metrics": [],
                "actual_recommend_count": count,
                "actual_count_text": f"推荐 {count} 位博主",
                "creators": [],
                "export_result": {"status": "skipped"},
            }
        return {
            "ok": True,
            "creators": [{"creator_id": f"memory-{len(counts)}", "nickname": "记忆达人", "pgy_url": f"https://pgy.xiaohongshu.com/creator/memory-{len(counts)}"}],
            "collection_plan": pgy_plan,
            "applied_filters": [],
            "skipped_filters": [],
            "selected_metrics": [],
            "skipped_metrics": [],
            "export_result": {"status": "skipped"},
        }

    monkeypatch.setattr("rpa_mcp_sync.web.collect_visible_list", fake_collect_visible_list)
    monkeypatch.setattr("rpa_mcp_sync.web.score_project", lambda project_id, **kwargs: {"scored": len(kwargs.get("creator_ids") or [])})

    first = client.post("/api/pgy/collect/batch", json={"project_id": project_id, "screening_plan": plan})
    assert first.status_code == 200
    assert first.json()["scheme_results"][0]["preflight"]["expected"]["predicted_source"] == "formula"

    second = client.post("/api/pgy/collect/batch", json={"project_id": project_id, "screening_plan": plan})
    assert second.status_code == 200
    preflight = second.json()["scheme_results"][0]["preflight"]
    assert preflight["expected"]["predicted_source"] == "history_blended"
    assert preflight["memory"]["sample_size"] >= 1

    memory = client.get(f"/api/projects/{project_id}/pgy/scheme-memory?scheme_id=memory_scheme").json()["memory"]
    assert len(memory) >= 2
    assert memory[0]["scheme_id"] == "memory_scheme"
    client.delete(f"/api/projects/{project_id}")


def test_pgy_collect_uses_hard_filters_as_collection_gate(monkeypatch):
    project_id = "pytest_collect_hard_gate"
    plan = {
        "hardFilters": [
            {"field": "平台报价", "condition": "<=", "value": "20000", "required": True},
            {"field": "粉丝年龄34岁以上占比", "condition": ">=", "value": "40%", "required": True},
            {"field": "孩子年级", "condition": "包含", "value": "小升初/初中/高中", "required": True},
        ],
        "pgyCollectionPlan": {
            "filters": [{"field": "博主类目", "value": "教育", "reason": "测试"}],
            "display_metrics": ["粉丝数"],
        },
    }
    client.post(
        f"/api/projects/{project_id}",
        json={"project_name": project_id, "brief": "教育大孩家庭，报价2万以下，34岁以上占比40%", "screening_plan": plan},
    )

    captured = {}

    def fake_collect_visible_list(**kwargs):
        captured["screening_plan"] = kwargs["screening_plan"]
        return {
            "ok": True,
            "creators": [
                {
                    "creator_id": "hard-gate-good",
                    "source": "pgy",
                    "nickname": "精准入库达人",
                    "pgy_url": "https://pgy.xiaohongshu.com/creator/good",
                    "quote_price": 18000,
                    "fans_35_plus_ratio": 0.45,
                    "child_grade": "初二",
                },
                {
                    "creator_id": "hard-gate-expensive",
                    "source": "pgy",
                    "nickname": "超预算达人",
                    "pgy_url": "https://pgy.xiaohongshu.com/creator/bad",
                    "quote_price": 26000,
                    "fans_35_plus_ratio": 0.48,
                    "child_grade": "初一",
                },
                {
                    "creator_id": "hard-gate-young",
                    "source": "pgy",
                    "nickname": "粉丝年龄不符达人",
                    "pgy_url": "https://pgy.xiaohongshu.com/creator/young",
                    "quote_price": 12000,
                    "fans_35_plus_ratio": 0.2,
                    "child_grade": "初三",
                },
            ],
            "collection_plan": {
                "filters": [
                    {"field": "报价", "value": "报价≤20000", "reason": "硬性条件：平台报价<=20000"},
                    {"field": "粉丝年龄", "value": "35岁以上≥40%", "reason": "硬性条件：粉丝年龄34岁以上占比>=40%"},
                    {"field": "内容场景", "value": "小升初/初中/高中", "reason": "硬性条件：孩子年级包含小升初/初中/高中"},
                    {"field": "博主类目", "value": "教育", "reason": "测试"},
                ]
            },
            "applied_filters": [],
            "skipped_filters": [],
            "selected_metrics": [],
            "skipped_metrics": [],
        }

    monkeypatch.setattr("rpa_mcp_sync.web.collect_visible_list", fake_collect_visible_list)
    monkeypatch.setattr("rpa_mcp_sync.web.score_project", lambda project_id, **kwargs: {"scored": 1})

    response = client.post(
        "/api/pgy/collect/batch",
        json={"project_id": project_id, "screening_plan": plan, "apply_filters": True, "include_details": False, "export_metrics": True, "limit": 20},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["batch"]["total_count"] == 3
    assert payload["batch"]["success_count"] == 3
    assert payload["batch"]["failed_count"] == 0
    assert [creator["nickname"] for creator in payload["creators"]] == ["精准入库达人", "超预算达人", "粉丝年龄不符达人"]
    assert {item["nickname"] for item in payload["rejected_by_hard_filters"]} == {"超预算达人", "粉丝年龄不符达人"}
    assert payload["flagged_by_hard_filters"] == payload["rejected_by_hard_filters"]
    assert any(item["field"] == "筛选工作台标记" for item in payload["skipped_filters"])
    assert captured["screening_plan"]["hardFilters"] == plan["hardFilters"]

    creators = client.get(f"/api/projects/{project_id}/creators?include_raw=true").json()["creators"]
    assert {creator["nickname"] for creator in creators} == {"精准入库达人", "超预算达人", "粉丝年龄不符达人"}
    flagged = next(creator for creator in creators if creator["nickname"] == "超预算达人")
    assert "collection_hard_filter_issues" in json.loads(flagged["raw_payload"])
    client.delete(f"/api/projects/{project_id}")


def test_pgy_collect_flags_no_order_permission_even_without_hard_filters(monkeypatch):
    project_id = "pytest_collect_no_order_permission"
    client.post(
        f"/api/projects/{project_id}",
        json={"project_name": project_id, "brief": "教育达人采集", "screening_plan": {"pgyCollectionPlan": {"filters": []}}},
    )

    def fake_collect_visible_list(**kwargs):
        return {
            "ok": True,
            "creators": [
                {
                    "creator_id": "no-order-permission",
                    "source": "pgy",
                    "nickname": "无接单权限达人",
                    "pgy_url": "https://pgy.xiaohongshu.com/creator/no-order",
                    "raw_payload": {"raw_table": {"全部报价": "无接单权限"}},
                }
            ],
            "collection_plan": {"filters": []},
            "applied_filters": [],
            "skipped_filters": [],
            "selected_metrics": [],
            "skipped_metrics": [],
        }

    monkeypatch.setattr("rpa_mcp_sync.web.collect_visible_list", fake_collect_visible_list)
    monkeypatch.setattr("rpa_mcp_sync.web.score_project", lambda project_id, **kwargs: {"scored": 1})

    response = client.post(
        "/api/pgy/collect/batch",
        json={"project_id": project_id, "screening_plan": {"pgyCollectionPlan": {"filters": []}}, "apply_filters": True, "include_details": False, "limit": 5},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["rejected_by_hard_filters"][0]["nickname"] == "无接单权限达人"
    assert "无接单权限" in "；".join(payload["rejected_by_hard_filters"][0]["issues"])

    creators = client.get(f"/api/projects/{project_id}/creators?include_raw=true").json()["creators"]
    raw_payload = json.loads(creators[0]["raw_payload"])
    assert raw_payload["collection_hard_filter_passed"] is False
    assert "无接单权限" in "；".join(raw_payload["collection_hard_filter_issues"])
    client.delete(f"/api/projects/{project_id}")


def test_blogger_category_hard_filters_match_any_selected_subcategory():
    hard_filters = [
        {"field": "博主类目", "condition": "包含", "value": "教育", "sub_value": "家庭教育", "required": True},
        {"field": "博主类目", "condition": "包含", "value": "教育", "sub_value": "k12教育", "required": True},
        {"field": "博主类目", "condition": "包含", "value": "母婴", "sub_value": "育儿经验", "required": True},
    ]
    creators = [
        {
            "creator_id": "edu-family",
            "nickname": "教育家庭达人",
            "raw_payload": {
                "list_api_kol": {
                    "name": "教育家庭达人",
                    "tradeType": "教育培训",
                    "contentTags": [{"taxonomy1Tag": "教育", "taxonomy2Tags": ["家庭教育"]}],
                }
            },
        },
        {
            "creator_id": "mum-parent",
            "nickname": "亲子达人",
            "raw_payload": {
                "list_api_kol": {
                    "name": "亲子达人",
                    "tradeType": "母婴",
                    "contentTags": [{"taxonomy1Tag": "母婴", "taxonomy2Tags": ["育儿经验"]}],
                }
            },
        },
        {
            "creator_id": "other",
            "nickname": "路人达人",
            "raw_payload": {"list_api_kol": {"name": "路人达人", "tradeType": "家居家装"}},
        },
    ]

    accepted, rejected = _filter_creators_by_hard_filters("pytest_category_or", creators, hard_filters)
    assert [item["creator_id"] for item in accepted] == ["edu-family", "mum-parent"]
    assert len(rejected) == 1
    assert rejected[0]["creator_id"] == "other"
    assert rejected[0]["issues"] == ["博主类目：未命中 教育-家庭教育 / 教育-k12教育 / 母婴-育儿经验"]


def test_project_hard_filter_issues_match_any_selected_subcategory():
    project_id = "pytest_category_or_score"
    screening_plan = {
        "hardFilters": [
            {"field": "博主类目", "condition": "包含", "value": "教育", "sub_value": "家庭教育", "required": True},
            {"field": "博主类目", "condition": "包含", "value": "教育", "sub_value": "k12教育", "required": True},
            {"field": "博主类目", "condition": "包含", "value": "母婴", "sub_value": "育儿经验", "required": True},
        ]
    }
    with connect() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO projects(project_id, project_name, target_qualified_creator_count, period_start, period_end, brief, screening_plan, created_at, updated_at)
            VALUES (?, '类别OR测试', 10, '2026-05-07', '2026-05-19', '', ?, '2026-05-09 14:00:00', '2026-05-09 14:00:00')
            """,
            (project_id, json.dumps(screening_plan, ensure_ascii=False)),
        )

    pass_creator = {
        "creator_id": "edu-family",
        "nickname": "教育家庭达人",
        "raw_payload": {
            "list_api_kol": {
                "name": "教育家庭达人",
                "tradeType": "教育培训",
                "contentTags": [{"taxonomy1Tag": "教育", "taxonomy2Tags": ["家庭教育"]}],
            }
        },
    }
    other_creator = {
        "creator_id": "other",
        "nickname": "路人达人",
        "raw_payload": {"list_api_kol": {"name": "路人达人", "tradeType": "家居家装"}},
    }

    assert _project_hard_filter_issues(project_id, pass_creator) == []
    issues = _project_hard_filter_issues(project_id, other_creator)
    assert issues == ["博主类目：未命中 教育-家庭教育 / 教育-k12教育 / 母婴-育儿经验"]

    with connect() as conn:
        conn.execute("DELETE FROM projects WHERE project_id=?", (project_id,))


def test_scheme_collect_limit_respects_target_count_range_floor():
    scheme = {
        "role": "primary",
        "precision_level": "high",
        "target_count_range": "50-2000",
        "target_quota": 12,
        "max_quota": 18,
    }
    assert _scheme_collect_limit(scheme, 1000) == 50
    assert _scheme_collect_limit(scheme, 40) == 40


def test_scheme_collect_limit_uses_actual_recommend_count_when_available():
    scheme = {
        "role": "primary",
        "precision_level": "high",
        "target_count_range": "50-2000",
        "target_quota": 12,
        "max_quota": 18,
    }
    assert _scheme_collect_limit(scheme, 1000, 869) == 869
    assert _scheme_collect_limit(scheme, 300, 869) == 300


def test_pgy_collect_hard_filters_parse_loose_multi_value_rules(monkeypatch):
    project_id = "pytest_collect_loose_rules"
    plan = {
        "hardFilters": [
            {"field": "达人预算", "condition": "<=", "value": "单个达人 ¥20,000；总预算暂定 ¥120,000", "required": True},
            {"field": "达人粉丝画像", "condition": ">", "value": "35岁以上占比 40%，不符合直接 pass", "required": True},
            {"field": "自然流量效率", "condition": "<", "value": "CPC 2；CPE 20，优先 CPE 10 以下", "required": True},
        ],
        "pgyCollectionPlan": {"filters": [{"field": "博主类目", "value": "教育", "reason": "测试"}]},
    }

    captured = {}

    def fake_collect_visible_list(**kwargs):
        captured["collection_plan"] = build_collection_plan("教育达人", kwargs["screening_plan"])
        return {
            "ok": True,
            "creators": [
                {
                    "creator_id": "loose-pass",
                    "nickname": "宽松写法通过达人",
                    "pgy_url": "https://pgy.xiaohongshu.com/creator/loose-pass",
                    "quote_price": 18000,
                    "fans_35_plus_ratio": 0.45,
                    "natural_cpc": 1.8,
                    "natural_cpe": 18,
                    "child_grade": "初二",
                },
                {
                    "creator_id": "loose-fail",
                    "nickname": "宽松写法失败达人",
                    "pgy_url": "https://pgy.xiaohongshu.com/creator/loose-fail",
                    "quote_price": 26000,
                    "fans_35_plus_ratio": 0.35,
                    "natural_cpc": 2.5,
                    "natural_cpe": 25,
                    "child_grade": "初二",
                },
            ],
            "collection_plan": captured["collection_plan"],
            "applied_filters": [],
            "skipped_filters": [],
            "selected_metrics": [],
            "skipped_metrics": [],
        }

    monkeypatch.setattr("rpa_mcp_sync.web.collect_visible_list", fake_collect_visible_list)
    monkeypatch.setattr("rpa_mcp_sync.web.score_project", lambda project_id, **kwargs: {"scored": len(kwargs.get("creator_ids") or [])})

    response = client.post("/api/pgy/collect/batch", json={"project_id": project_id, "screening_plan": plan, "limit": 20})
    assert response.status_code == 200
    payload = response.json()
    assert [creator["creator_id"] for creator in payload["creators"]] == ["loose-pass", "loose-fail"]
    assert payload["rejected_by_hard_filters"][0]["creator_id"] == "loose-fail"
    pgy_filters = captured["collection_plan"]["filters"]
    assert next(item for item in pgy_filters if item["field"] == "合作报价")["max"] == 20000
    assert next(item for item in pgy_filters if item["field"] == "预估阅读单价")["max"] == 2
    assert next(item for item in pgy_filters if item["field"] == "预估互动单价")["max"] == 20
    client.delete(f"/api/projects/{project_id}")


def test_structured_hard_filters_map_directly_to_pgy_filters():
    plan = {
        "hardFilters": [
            {
                "field": "粉丝年龄",
                "condition": "匹配",
                "value": "35～44 占比高、>44 占比高",
                "required": True,
                "pgyField": "粉丝年龄",
                "valueControl": "multi",
            },
            {
                "field": "合作报价",
                "condition": "<=",
                "value": "图文笔记：1万～2万",
                "required": True,
                "pgyField": "合作报价",
                "valueControl": "range",
                "subField": "图文笔记",
            },
        ],
        "pgyCollectionPlan": {"filters": []},
    }
    collection_plan = build_collection_plan("教育达人", plan)
    assert collection_plan["filters"][0]["field"] == "粉丝年龄"
    assert collection_plan["filters"][0]["value"] == "35～44 占比高"
    assert collection_plan["filters"][1]["field"] == "粉丝年龄"
    assert collection_plan["filters"][1]["value"] == ">44 占比高"
    assert collection_plan["filters"][2]["field"] == "合作报价"
    assert collection_plan["filters"][2]["sub_field"] == "图文笔记"
    assert collection_plan["filters"][2]["max"] == 20000
    assert collection_plan["filters"][2]["min"] == 10000


def test_structured_image_and_video_quote_filters_are_preserved():
    plan = {
        "collectionHardFilters": [
            {
                "field": "合作报价",
                "condition": "<=",
                "value": "图文笔记：0.1万～0.5万",
                "required": True,
                "pgyField": "合作报价",
                "valueControl": "range",
                "subField": "图文笔记",
            },
            {
                "field": "合作报价",
                "condition": "<=",
                "value": "视频笔记：0.5万～1万",
                "required": True,
                "pgyField": "合作报价",
                "valueControl": "range",
                "subField": "视频笔记",
            },
        ],
        "pgyCollectionPlan": {"filters": []},
    }

    collection_plan = build_collection_plan("教育达人", plan)
    quote_filters = [item for item in collection_plan["filters"] if item["field"] == "合作报价"]

    assert [item["sub_field"] for item in quote_filters] == ["图文笔记", "视频笔记"]
    assert [item["value"] for item in quote_filters] == ["图文笔记：0.1万～0.5万", "视频笔记：0.5万～1万"]
    assert [item["max"] for item in quote_filters] == [5000, 10000]


def test_project_save_preserves_image_and_video_quote_filters():
    project_id = "pytest_quote_subfields_save"
    plan = {
        "briefType": "complex",
        "pgyCollectionPlan": {
            "filters": [
                {
                    "field": "合作报价",
                    "value": "图文笔记：0.1万～0.5万",
                    "control_type": "subfield_preset_or_number_range",
                    "sub_field": "图文笔记",
                    "manual": True,
                    "source": "frontend",
                },
                {
                    "field": "合作报价",
                    "value": "视频笔记：0.5万～1万",
                    "control_type": "subfield_preset_or_number_range",
                    "sub_field": "视频笔记",
                    "manual": True,
                    "source": "frontend",
                },
            ]
        },
    }

    response = client.post(f"/api/projects/{project_id}", json={"project_name": project_id, "brief": "教育达人", "screening_plan": plan})
    assert response.status_code == 200
    saved_plan = json.loads(response.json()["project"]["screening_plan"])
    quote_filters = [item for item in saved_plan["collectionHardFilters"] if item["pgyField"] == "合作报价"]

    assert [item["subField"] for item in quote_filters] == ["图文笔记", "视频笔记"]
    assert [item["value"] for item in quote_filters] == ["图文笔记：0.1万～0.5万", "视频笔记：0.5万～1万"]
    client.delete(f"/api/projects/{project_id}")


def test_pgy_quote_range_text_parses_to_yuan_values():
    from rpa_mcp_sync.pgy_browser import _normalize_pgy_filters, _range_numbers_from_text

    assert _range_numbers_from_text("图文笔记：0.1万～2万") == (1000, 20000)
    assert _range_numbers_from_text("图文笔记阅读单价≤2") == (None, 2)
    normalized = _normalize_pgy_filters([
        {"field": "合作报价", "value": "图文笔记：0.1万～2万"},
        {"field": "粉丝年龄", "value": "35～44 占比高"},
        {"field": "粉丝量", "value": "1万～10万"},
    ])
    assert normalized[0]["min"] == 1000
    assert normalized[0]["max"] == 20000
    assert normalized[0]["sub_fields"] == ["图文笔记"]
    assert normalized[1]["control_type"] == "dropdown"
    assert normalized[2]["control_type"] == "preset_or_number_range"
    ambiguous = _normalize_pgy_filters([{"field": "合作报价", "value": "0.1万～2万"}])[0]
    assert ambiguous["sub_fields"] == ["图文笔记", "视频笔记"]
    video = _normalize_pgy_filters([{"field": "合作报价", "value": "视频笔记：0.1万～2万"}])[0]
    assert video["sub_fields"] == ["视频笔记"]


def test_pgy_range_policy_keeps_scale_fields_min_only_and_quote_bounded():
    from rpa_mcp_sync.pgy_browser import _normalize_pgy_filters, _range_for_subfield

    normalized = _normalize_pgy_filters(
        [
            {"field": "粉丝量", "value": "1万～10万"},
            {"field": "曝光中位数", "value": "1万～5万"},
            {"field": "阅读中位数", "value": "0.5万～1万"},
            {"field": "互动中位数", "value": "500～1000"},
            {"field": "合作订单数", "value": "3～10"},
            {"field": "合作报价", "value": "图文笔记：0.1万～2万"},
            {"field": "预估阅读单价", "value": "图文笔记阅读单价≤2", "sub_field": "图文笔记阅读单价"},
            {"field": "传播规模", "value": "曝光中位数：1万～5万", "sub_field": "曝光中位数"},
            {"field": "合作信用度", "value": "邀约48h回复率：60～100", "sub_field": "邀约48h回复率"},
        ]
    )
    by_field = {item["field"]: item for item in normalized}

    assert by_field["粉丝量"]["min"] == 10000
    assert by_field["粉丝量"]["max"] == ""
    assert by_field["曝光中位数"]["min"] == 10000
    assert by_field["曝光中位数"]["max"] == ""
    assert by_field["阅读中位数"]["min"] == 5000
    assert by_field["阅读中位数"]["max"] == ""
    assert by_field["互动中位数"]["min"] == 500
    assert by_field["互动中位数"]["max"] == ""
    assert by_field["合作订单数"]["min"] == 3
    assert by_field["合作订单数"]["max"] == ""
    assert by_field["合作报价"]["min"] == 1000
    assert by_field["合作报价"]["max"] == 20000
    assert by_field["预估阅读单价"]["max"] == 2
    assert _range_for_subfield(by_field["传播规模"], "曝光中位数") == (10000.0, "")
    assert _range_for_subfield(by_field["合作信用度"], "邀约48h回复率") == (60.0, "")


def test_saved_scheme_filters_rewrite_min_only_ranges_for_display():
    from rpa_mcp_sync.web import _scheme_plan

    screening_plan = {"pgyCollectionPlan": {"filters": []}}
    scheme = {
        "required_filters": [
            {"field": "博主类目", "value": "教育"},
            {"field": "粉丝量", "value": "1万～10万"},
            {"field": "粉丝年龄", "value": "35～44 占比高"},
            {"field": "合作报价", "value": "图文笔记：0.1万～2万"},
        ],
        "additional_filters": [
            {"field": "曝光中位数", "value": "1万～5万"},
            {"field": "阅读中位数", "value": "0.5万～1万"},
            {"field": "互动中位数", "value": "500～1000"},
            {"field": "合作订单数", "value": "3～10"},
            {"field": "传播规模", "value": "曝光中位数：1万～5万", "sub_field": "曝光中位数"},
            {"field": "合作信用度", "value": "邀约48h回复率：60～100", "sub_field": "邀约48h回复率"},
        ],
        "enabled_additional_filters": [
            {"field": "曝光中位数", "value": "1万以上"},
            {"field": "阅读中位数", "value": "0.5万以上"},
            {"field": "互动中位数", "value": "500以上"},
            {"field": "合作订单数", "value": "3以上"},
            {"field": "传播规模", "value": "曝光中位数：1万以上", "sub_field": "曝光中位数"},
            {"field": "合作信用度", "value": "邀约48h回复率：60%以上", "sub_field": "邀约48h回复率"},
        ],
    }

    plan = _scheme_plan(screening_plan, scheme)
    pgy_plan = plan["pgyCollectionPlan"]
    by_field = {
        (item["field"], item.get("sub_field") or ""): item
        for item in [*pgy_plan["required_filters"], *pgy_plan["additional_filters"]]
    }

    assert by_field[("粉丝量", "")]["value"] == "1万以上"
    assert by_field[("曝光中位数", "")]["value"] == "1万以上"
    assert by_field[("阅读中位数", "")]["value"] == "0.5万以上"
    assert by_field[("互动中位数", "")]["value"] == "500以上"
    assert by_field[("合作订单数", "")]["value"] == "3以上"
    assert by_field[("传播规模", "曝光中位数")]["value"] == "曝光中位数：1万以上"
    assert by_field[("合作信用度", "邀约48h回复率")]["value"] == "邀约48h回复率：60%以上"
    min_only_fields = {"粉丝量", "曝光中位数", "阅读中位数", "互动中位数", "合作订单数", "传播规模", "合作信用度"}
    assert all(item.get("max") == "" for item in by_field.values() if item["field"] in min_only_fields)
    assert all(item.get("range_policy") == "min_only" for item in by_field.values() if item["field"] in min_only_fields)


def test_pgy_row_parser_ignores_empty_state_as_creator():
    from rpa_mcp_sync.pgy_browser import _parse_row_text

    assert _parse_row_text("暂无数据\n暂未发现相关博主\n放宽条件才能找到更多的博主", "https://pgy.xiaohongshu.com/solar/pre-trade/note/kol") is None


def test_collection_only_marketing_goal_does_not_block_creator_gate():
    creators = [{"creator_id": "c1", "nickname": "教育学硕士妈妈", "source": "pgy", "raw_payload": {"collection_page": 1}}]
    hard_filters = [{"field": "营销目标", "condition": "包含", "value": "种草", "required": True, "pgyField": "营销目标"}]

    accepted, rejected = _filter_creators_by_hard_filters("pytest_collection_only_goal", creators, hard_filters)

    assert accepted == creators
    assert rejected == []


def test_build_collection_plan_uses_marketing_goal_metric_shape_and_strict_region():
    weak = build_collection_plan("上海教育品牌想找母婴和教育达人做种草内容", {})
    weak_filters = weak["filters"]

    goal = next(item for item in weak_filters if item["field"] == "营销目标")
    assert goal["value"] == "互动表现"
    assert goal["goal"] == "种草"
    assert goal["control_type"] == "marketing_goal_metric"
    assert [item["value"] for item in weak_filters if item["field"] == "博主类目"] == ["教育", "母婴"]
    assert "地域" not in [item["field"] for item in weak_filters]

    strict = build_collection_plan("地域要求：北京、上海 IP 优先，教育达人", {})
    region_filters = [item for item in strict["filters"] if item["field"] == "地域"]
    assert [item["value"] for item in region_filters] == ["北京", "上海"]
    assert [item["country"] for item in region_filters] == ["中国", "中国"]
    assert region_filters[0]["control_type"] == "three_level_cascade_checkbox_popover"


def test_build_collection_plan_uses_blogger_subcategories_from_taxonomy():
    plan = build_collection_plan("有道答疑笔，找教育、家庭教育、k12、学习日常、大孩亲子家长育儿达人", {})
    category_filters = [item for item in plan["filters"] if item["field"] == "博主类目"]

    assert category_filters[0]["field"] == "博主类目"
    assert category_filters[0]["value"] == "教育"
    assert category_filters[0]["sub_value"] == "家庭教育"
    assert ("教育", "k12教育") in [(item["value"], item.get("sub_value")) for item in category_filters]
    assert ("教育", "学习日常") in [(item["value"], item.get("sub_value")) for item in category_filters]
    assert ("母婴", "育儿经验") in [(item["value"], item.get("sub_value")) for item in category_filters]
    assert all(item["control_type"] == "tag_select_with_hover_subcategory" for item in category_filters)


def test_region_targets_parse_china_and_foreign_values():
    from rpa_mcp_sync.pgy_browser import _normalize_pgy_filters, _region_targets_from_item

    assert _region_targets_from_item({"field": "地域", "value": "北京/上海优先"}) == ["北京", "上海"]
    assert _region_targets_from_item({"field": "地域", "value": "地域要求：中国、美国、日本"}) == ["美国", "日本"]
    assert _region_targets_from_item({"field": "地域", "value": "北上广深"}) == ["北京", "上海", "广州", "深圳"]
    normalized = _normalize_pgy_filters([{"field": "地域", "value": "北京/上海优先"}])
    assert [(item["country"], item["value"]) for item in normalized] == [("中国", "北京"), ("中国", "上海")]


def test_scheme_plan_preserves_multiple_category_filters():
    from rpa_mcp_sync.web import _scheme_plan

    screening_plan = {"pgyCollectionPlan": {"filters": []}}
    scheme = {
        "filters": [
            {"field": "博主类目", "value": "教育"},
            {"field": "博主类目", "value": "母婴"},
            {"field": "粉丝量", "value": "1万～10万"},
            {"field": "粉丝年龄", "value": "35～44 占比高"},
            {"field": "合作报价", "value": "图文笔记：0.1万～2万"},
        ],
    }

    plan = _scheme_plan(screening_plan, scheme)
    required = plan["pgyCollectionPlan"]["required_filters"]

    assert [item["value"] for item in required if item["field"] == "博主类目"] == ["教育", "母婴"]
    assert [item["sub_value"] for item in required if item["field"] == "博主类目"] == ["家庭教育", "育儿经验"]


def test_scheme_plan_preserves_valid_blogger_subcategory_and_drops_invalid():
    from rpa_mcp_sync.web import _scheme_plan

    screening_plan = {"pgyCollectionPlan": {"filters": []}}
    scheme = {
        "required_filters": [
            {"field": "博主类目", "value": "教育", "sub_value": "家庭教育"},
            {"field": "博主类目", "value": "母婴", "sub_value": "家庭教育"},
            {"field": "粉丝量", "value": "1万～10万"},
            {"field": "粉丝年龄", "value": "35～44 占比高"},
            {"field": "合作报价", "value": "图文笔记：0.1万～2万"},
        ],
    }

    plan = _scheme_plan(screening_plan, scheme)
    required = plan["pgyCollectionPlan"]["required_filters"]
    categories = [item for item in required if item["field"] == "博主类目"]

    assert categories[0]["value"] == "教育"
    assert categories[0]["sub_value"] == "家庭教育"
    assert categories[0]["control_type"] == "tag_select_with_hover_subcategory"
    assert categories[1]["value"] == "母婴"
    assert categories[1]["sub_value"] == "育儿经验"


def test_scheme_plan_preserves_multiple_subcategories_across_blogger_categories():
    from rpa_mcp_sync.web import _scheme_plan

    screening_plan = {"pgyCollectionPlan": {"filters": []}}
    scheme = {
        "required_filters": [
            {"field": "博主类目", "value": "教育", "sub_value": "家庭教育"},
            {"field": "博主类目", "value": "教育", "sub_value": "k12教育"},
            {"field": "博主类目", "value": "教育", "sub_value": "学习日常"},
            {"field": "博主类目", "value": "母婴", "sub_value": "育儿经验"},
            {"field": "博主类目", "value": "母婴", "sub_value": "早教"},
            {"field": "粉丝量", "value": "1万以上"},
            {"field": "粉丝年龄", "value": "35～44 占比高"},
            {"field": "合作报价", "value": "图文笔记：0.1万～2万"},
        ],
    }

    plan = _scheme_plan(screening_plan, scheme)
    required = plan["pgyCollectionPlan"]["required_filters"]
    categories = [item for item in required if item["field"] == "博主类目"]

    assert [(item["value"], item["sub_value"]) for item in categories] == [
        ("教育", "家庭教育"),
        ("教育", "k12教育"),
        ("教育", "学习日常"),
        ("母婴", "育儿经验"),
        ("母婴", "早教"),
    ]


def test_normalize_screening_standard_backfills_cross_category_subcategory_multiselect():
    from rpa_mcp_sync.web import ScreeningStandardPayload, _normalize_screening_standard

    payload = ScreeningStandardPayload(
        brief="有道答疑笔，找教育、家庭教育、学习日常、母婴、育儿经验、大孩亲子家长达人",
        project={},
        feishu_fields=[],
    )
    result = {
        "briefType": "complex",
        "scoringWeights": {"budget": 15, "fans": 5, "cpe": 20, "engagement": 30, "persona": 20, "content": 10},
        "pgyCollectionPlan": {
            "schemes": [
                {
                    "scheme_id": "education_family",
                    "name": "教育家庭池",
                    "required_filters": [
                        {"field": "博主类目", "value": "教育", "sub_value": "家庭教育"},
                        {"field": "粉丝量", "value": "1万以上"},
                        {"field": "粉丝年龄", "value": "35～44 占比高"},
                        {"field": "合作报价", "value": "图文笔记：0.1万～2万"},
                    ],
                },
                {
                    "scheme_id": "parenting",
                    "name": "母婴亲子补量",
                    "required_filters": [
                        {"field": "博主类目", "value": "母婴", "sub_value": "育儿经验"},
                        {"field": "粉丝量", "value": "1万以上"},
                        {"field": "粉丝年龄", "value": "35～44 占比高"},
                        {"field": "合作报价", "value": "图文笔记：0.1万～2万"},
                    ],
                },
            ],
        },
    }

    plan = _normalize_screening_standard(result, payload)
    schemes = plan["pgyCollectionPlan"]["schemes"]
    first_categories = [(item["value"], item.get("sub_value")) for item in schemes[0]["required_filters"] if item["field"] == "博主类目"]
    second_categories = [(item["value"], item.get("sub_value")) for item in schemes[1]["required_filters"] if item["field"] == "博主类目"]

    assert ("教育", "家庭教育") in first_categories
    assert ("教育", "学习日常") in first_categories
    assert ("母婴", "育儿经验") in second_categories


def test_normalize_screening_standard_enforces_distinct_study_abroad_video_schemes():
    from rpa_mcp_sync.web import ScreeningStandardPayload, _normalize_screening_standard

    payload = ScreeningStandardPayload(
        brief=(
            "有道留学听课宝，图文和视频都可，最好是视频；"
            "单达人预算1000以下KOC；留学背景/海外留学生，内容需要50%以上学习类，"
            "不要全都是vlog的达人。"
        ),
        project={},
        feishu_fields=[],
    )
    result = {
        "briefType": "complex",
        "scoringWeights": {"budget": 15, "fans": 5, "cpe": 20, "engagement": 30, "persona": 20, "content": 10},
        "pgyCollectionPlan": {
            "filters": [
                {"field": "地域", "value": "美国", "manual": False, "reason": "模型误放的默认全局条件"},
            ],
            "schemes": [
                {
                    "scheme_id": "study_main",
                    "name": "方案一：留学学习主池",
                    "required_filters": [
                        {"field": "博主类目", "value": "教育", "sub_value": "学习日常"},
                        {"field": "粉丝量", "value": "0.1万以上"},
                        {"field": "合作报价", "value": "图文笔记：0-1000；视频笔记：0-1000"},
                    ],
                },
                {
                    "scheme_id": "video_focus",
                    "name": "方案二：视频优先学习池",
                    "required_filters": [
                        {"field": "博主类目", "value": "教育", "sub_value": "留学教育"},
                        {"field": "博主类目", "value": "教育", "sub_value": "学习日常"},
                        {"field": "粉丝量", "value": "0.1万以上"},
                        {"field": "合作报价", "value": "图文笔记：0-1000；视频笔记：0-1000"},
                    ],
                },
                {
                    "scheme_id": "overseas_proxy",
                    "name": "方案三：海外生活补量池",
                    "required_filters": [
                        {"field": "博主类目", "value": "生活记录", "sub_value": "中外生活"},
                        {"field": "博主类目", "value": "教育", "sub_value": "学习日常"},
                        {"field": "粉丝量", "value": "0.1万以上"},
                        {"field": "合作报价", "value": "图文笔记：0-1000；视频笔记：0-1000"},
                    ],
                },
                {
                    "scheme_id": "edu_broad_proxy",
                    "name": "方案四：广教育补量池",
                    "required_filters": [
                        {"field": "博主类目", "value": "教育", "sub_value": "语言教育"},
                        {"field": "博主类目", "value": "教育", "sub_value": "教育其他"},
                        {"field": "博主类目", "value": "教育", "sub_value": "学习日常"},
                        {"field": "粉丝量", "value": "0.1万以上"},
                        {"field": "合作报价", "value": "图文笔记：0-1000；视频笔记：0-1000"},
                    ],
                },
            ],
        },
    }

    plan = _normalize_screening_standard(result, payload)
    pgy_plan = plan["pgyCollectionPlan"]
    schemes = pgy_plan["schemes"]
    video_enabled = schemes[1]["enabled_additional_filters"]
    video_additional_fields = [item["field"] for item in schemes[1]["additional_filters"]]
    first_narrow_text = " ".join(schemes[0]["narrow_if_too_many"])
    overseas_categories = [(item["value"], item.get("sub_value")) for item in schemes[2]["required_filters"] if item["field"] == "博主类目"]
    broad_categories = [(item["value"], item.get("sub_value")) for item in schemes[3]["required_filters"] if item["field"] == "博主类目"]

    assert pgy_plan["filters"] == []
    assert any(item["field"] == "笔记类型" and item["value"] == "视频笔记为主" for item in video_enabled)
    assert video_additional_fields == ["笔记类型", "预估互动单价", "曝光中位数", "阅读中位数", "互动中位数", "预估阅读单价"]
    assert "预估CPM" not in video_additional_fields
    first_additional_by_field = {item["field"]: item for item in schemes[0]["additional_filters"]}
    assert first_additional_by_field["预估互动单价"]["sub_fields"] == ["图文笔记互动单价", "视频笔记互动单价"]
    assert first_additional_by_field["预估阅读单价"]["sub_fields"] == ["图文笔记阅读单价", "视频笔记阅读单价"]
    video_additional_by_field = {item["field"]: item for item in schemes[1]["additional_filters"]}
    assert video_additional_by_field["预估互动单价"]["sub_fields"] == ["视频笔记互动单价"]
    assert video_additional_by_field["预估阅读单价"]["sub_fields"] == ["视频笔记阅读单价"]
    assert video_additional_by_field["预估互动单价"]["max"] == 20
    assert video_additional_by_field["曝光中位数"]["min"] == 500
    assert video_additional_by_field["阅读中位数"]["min"] == 300
    assert video_additional_by_field["互动中位数"]["min"] == 30
    assert video_additional_by_field["预估阅读单价"]["max"] == 3
    assert "常规剔除" not in video_additional_fields
    assert "地域" not in video_additional_fields
    assert "预估CPM" not in first_narrow_text
    assert "预估互动单价" in first_narrow_text
    assert "曝光中位数" in first_narrow_text
    assert "阅读中位数" in first_narrow_text
    assert "互动中位数" in first_narrow_text
    assert "常规剔除" not in first_narrow_text
    assert "地域" not in first_narrow_text
    assert ("教育", "留学教育") in [(item["value"], item.get("sub_value")) for item in schemes[0]["required_filters"] if item["field"] == "博主类目"]
    assert ("教育", "学习日常") not in overseas_categories
    assert ("教育", "留学教育") not in overseas_categories
    assert ("教育", "大学教育") not in overseas_categories
    assert ("生活记录", "中外生活") in overseas_categories
    assert ("教育", "学习日常") not in broad_categories
    assert ("教育", "留学教育") not in broad_categories
    assert ("教育", "大学教育") not in broad_categories
    assert not any(value == "生活记录" for value, _ in broad_categories)
    assert int(schemes[2]["max_quota"]) <= 20
    assert int(schemes[3]["max_quota"]) <= 25


def test_pgy_filter_field_guide_exposes_real_options_and_usage_groups():
    from rpa_mcp_sync.web import _pgy_filter_field_guide

    guide = _pgy_filter_field_guide()
    fields = {item["field"]: item for item in guide["fields"]}
    blogger_category = fields["博主类目"]

    assert guide["source"] == "pgy_scraped_filter_catalog"
    assert "博主类目" in guide["required_filters_allowed_fields"]
    assert "笔记类型" in guide["additional_filters_allowed_fields"]
    assert "家庭身份" in guide["additional_filters_allowed_fields"]
    assert "职业身份" in guide["additional_filters_allowed_fields"]
    assert "特色背景" in guide["additional_filters_allowed_fields"]
    assert "母婴阶段" in guide["additional_filters_allowed_fields"]
    assert "近期合作品牌" in guide["manual_only_fields"]
    assert fields["家庭身份"]["usage_group"] == "additional_filters_allowed"
    assert blogger_category["usage_group"] == "required_filters_allowed"
    assert blogger_category["control_type"] == "tag_select_with_hover_subcategory"
    assert any(group["label"] == "教育" and "留学教育" in group["options"] for group in blogger_category["option_groups"])
    assert "高知家庭" in guide["unavailable_as_frontend_filters"]


def test_normalize_scheme_filters_preserves_wan_units_and_splits_quote_subfields():
    from rpa_mcp_sync.web import _normalize_scheme_filter_structure

    plan = {
        "schemes": [
            {
                "required_filters": [
                    {"field": "粉丝量", "value": "0.1万以上", "min": 0.1},
                    {"field": "合作报价", "value": "图文笔记：0-1000；视频笔记：0-1000"},
                ]
            }
        ]
    }

    scheme = _normalize_scheme_filter_structure(plan)["schemes"][0]
    followers = next(item for item in scheme["required_filters"] if item["field"] == "粉丝量")
    quotes = [item for item in scheme["required_filters"] if item["field"] == "合作报价"]

    assert followers["value"] == "0.1万以上"
    assert followers["min"] == 1000
    assert [(item["sub_field"], item["max"]) for item in quotes] == [("图文笔记", 1000), ("视频笔记", 1000)]
    assert scheme["expected_request_constraints"]["notePriceUpper"] == 1000
    assert scheme["expected_request_constraints"]["videoPriceUpper"] == 1000
    assert scheme["application_validation"]["on_mismatch"] == "repair_then_validate"
    assert scheme["application_validation"]["stop_on_repair_failed"] is True


def test_normalize_scheme_filters_parses_separate_video_quote_subfield():
    from rpa_mcp_sync.web import _normalize_scheme_filter_structure

    plan = {
        "schemes": [
            {
                "required_filters": [
                    {"field": "合作报价", "value": "图文笔记：0-1000", "sub_field": "图文笔记"},
                    {"field": "合作报价", "value": "视频笔记：0-1000", "sub_field": "视频笔记"},
                ]
            }
        ]
    }

    scheme = _normalize_scheme_filter_structure(plan)["schemes"][0]
    quotes = [item for item in scheme["required_filters"] if item["field"] == "合作报价"]

    assert [(item["sub_field"], item["min"], item["max"]) for item in quotes] == [("图文笔记", 0.0, 1000.0), ("视频笔记", 0.0, 1000.0)]
    assert scheme["expected_request_constraints"]["notePriceUpper"] == 1000
    assert scheme["expected_request_constraints"]["videoPriceUpper"] == 1000


def test_scheme_plan_exposes_expected_request_constraints():
    from rpa_mcp_sync.web import _scheme_plan

    screening_plan = {"pgyCollectionPlan": {"filters": []}}
    scheme = {
        "required_filters": [
            {"field": "博主类目", "value": "教育", "sub_value": "留学教育"},
            {"field": "合作报价", "value": "图文笔记：0-1000；视频笔记：0-1000"},
        ],
        "enabled_additional_filters": [
            {"field": "笔记类型", "value": "视频笔记为主"},
            {"field": "阅读中位数", "value": "1000以上", "min": 1000},
            {"field": "互动中位数", "value": "100以上", "min": 100},
        ],
    }

    plan = _scheme_plan(screening_plan, scheme)
    constraints = plan["pgyCollectionPlan"]["expected_request_constraints"]

    assert constraints["contentTag"] == ["留学教育"]
    assert constraints["notePriceUpper"] == 1000
    assert constraints["videoPriceUpper"] == 1000
    assert constraints["noteType"] == 2
    assert constraints["readMidNor30_min"] == 1000
    assert constraints["interMidNor30_min"] == 100


def test_study_abroad_primary_schemes_enable_profile_filters():
    from rpa_mcp_sync.web import ScreeningStandardPayload, _normalize_screening_standard

    payload = ScreeningStandardPayload(
        brief="有道留学听课宝，图文和视频都可，最好是视频，单达人预算1000以下koc；留学背景/海外留学生，内容需要50%以上学习类。",
        fields=[],
        samples=[],
    )
    result = {
        "pgyCollectionPlan": {
            "filters": [],
            "schemes": [
                {
                    "scheme_id": "study_main",
                    "name": "方案一：留学学习主池",
                    "role": "primary",
                    "required_filters": [
                        {"field": "博主类目", "value": "教育", "sub_value": "留学教育"},
                        {"field": "粉丝量", "value": "0.1万以上"},
                        {"field": "合作报价", "value": "图文笔记：0-1000；视频笔记：0-1000"},
                    ],
                },
                {
                    "scheme_id": "video_focus",
                    "name": "方案二：视频优先池",
                    "role": "primary",
                    "required_filters": [
                        {"field": "博主类目", "value": "教育", "sub_value": "留学教育"},
                        {"field": "粉丝量", "value": "0.1万以上"},
                        {"field": "合作报价", "value": "图文笔记：0-1000；视频笔记：0-1000"},
                    ],
                },
                {"scheme_id": "overseas_proxy", "name": "方案三：海外生活补量池", "required_filters": [{"field": "博主类目", "value": "生活记录", "sub_value": "中外生活"}]},
                {"scheme_id": "edu_broad_proxy", "name": "方案四：广教育补量池", "required_filters": [{"field": "博主类目", "value": "教育", "sub_value": "语言教育"}]},
            ],
        }
    }

    plan = _normalize_screening_standard(result, payload)
    schemes = plan["pgyCollectionPlan"]["schemes"]
    main_enabled = {(item["field"], item["value"]) for item in schemes[0]["enabled_additional_filters"]}
    video_enabled = {(item["field"], item["value"]) for item in schemes[1]["enabled_additional_filters"]}

    assert ("职业身份", "学生") in main_enabled
    assert ("特色背景", "留学背景") in main_enabled
    assert ("职业身份", "学生") in video_enabled
    assert ("特色背景", "留学背景") in video_enabled
    assert schemes[0]["expected_request_constraints"]["personalTags"] == ["学生", "留学背景"]
    assert schemes[1]["expected_request_constraints"]["noteType"] == 2


def test_scheme_plan_does_not_treat_note_category_as_blogger_category():
    from rpa_mcp_sync.web import _scheme_plan

    screening_plan = {"pgyCollectionPlan": {"filters": []}}
    scheme = {
        "filters": [
            {"field": "博主类目", "value": "教育"},
            {"field": "笔记类目", "value": "母婴"},
            {"field": "内容题材", "value": "婴童洗护"},
            {"field": "粉丝量", "value": "1万～10万"},
            {"field": "粉丝年龄", "value": "35～44 占比高"},
            {"field": "合作报价", "value": "图文笔记：0.1万～2万"},
        ],
    }

    plan = _scheme_plan(screening_plan, scheme)
    filters = plan["pgyCollectionPlan"]["filters"]

    assert [item["value"] for item in filters if item["field"] == "博主类目"] == ["教育"]
    assert "笔记类目" not in [item["field"] for item in filters]
    assert "内容题材" not in [item["field"] for item in filters]


def test_hard_filters_parse_multi_choice_text_rules(monkeypatch):
    project_id = "pytest_collect_multi_text_rules"
    plan = {
        "hardFilters": [
            {"field": "地域优先级", "condition": "匹配", "value": "北京、上海 IP 或中产家庭叙事", "required": True},
        ],
        "pgyCollectionPlan": {"filters": []},
    }

    def fake_collect_visible_list(**kwargs):
        return {
            "ok": True,
            "creators": [
                {"creator_id": "text-pass", "nickname": "北京教育达人", "ip_city": "北京", "pgy_url": "https://pgy.xiaohongshu.com/creator/text-pass"},
                {"creator_id": "text-fail", "nickname": "普通教育达人", "ip_city": "成都", "pgy_url": "https://pgy.xiaohongshu.com/creator/text-fail"},
            ],
            "collection_plan": build_collection_plan("教育达人", kwargs["screening_plan"]),
            "applied_filters": [],
            "skipped_filters": [],
            "selected_metrics": [],
            "skipped_metrics": [],
        }

    monkeypatch.setattr("rpa_mcp_sync.web.collect_visible_list", fake_collect_visible_list)
    monkeypatch.setattr("rpa_mcp_sync.web.score_project", lambda project_id, **kwargs: {"scored": len(kwargs.get("creator_ids") or [])})

    response = client.post("/api/pgy/collect/batch", json={"project_id": project_id, "screening_plan": plan, "limit": 20})
    assert response.status_code == 200
    payload = response.json()
    assert [creator["creator_id"] for creator in payload["creators"]] == ["text-pass", "text-fail"]
    assert payload["rejected_by_hard_filters"][0]["creator_id"] == "text-fail"
    client.delete(f"/api/projects/{project_id}")


def test_pgy_detail_collect_only_updates_passed_creators(monkeypatch):
    project_id = "pytest_detail_collect"
    good = {
        "creator_id": "detail-good",
        "nickname": "详情补全通过达人",
        "pgy_url": "https://pgy.xiaohongshu.com/solar/pre-trade/blogger-detail/detail-good",
        "quote_price": 12000,
        "fans_35_plus_ratio": 0.6,
        "child_grade": "初二",
    }
    bad = {
        "creator_id": "detail-low",
        "nickname": "详情补全未通过达人",
        "pgy_url": "https://pgy.xiaohongshu.com/solar/pre-trade/blogger-detail/detail-low",
        "quote_price": 22000,
        "fans_35_plus_ratio": 0.2,
    }
    client.post(f"/api/projects/{project_id}/creators", json={"data": good})
    client.post(f"/api/projects/{project_id}/creators", json={"data": bad})
    with connect() as conn:
        conn.execute(
            "UPDATE creator_scores SET total_score=82, hard_filter_passed=1 WHERE creator_id=?",
            ("detail-good",),
        )
        conn.execute(
            "UPDATE creator_scores SET total_score=55, hard_filter_passed=0 WHERE creator_id=?",
            ("detail-low",),
        )

    captured = {}

    def fake_collect_details_for_targets(targets, limit=20):
        captured["targets"] = targets
        return {
            "ok": True,
            "creators": [{"creator_id": "detail-good", "nickname": "详情补全通过达人", "xiaohongshu_id": "xhs-good", "topic_point": "初中学习"}],
            "failed": [],
        }

    monkeypatch.setattr("rpa_mcp_sync.web.collect_details_for_targets", fake_collect_details_for_targets)
    monkeypatch.setattr("rpa_mcp_sync.web.score_project", lambda project_id, **kwargs: {"scored": 1})

    response = client.post("/api/pgy/collect/detail", json={"project_id": project_id, "limit": 20})
    assert response.status_code == 200
    payload = response.json()
    assert payload["updated"][0]["xiaohongshu_id"] == "xhs-good"
    assert [item["creator_id"] for item in captured["targets"]] == ["detail-good"]
    client.delete(f"/api/projects/{project_id}")


def test_pgy_detail_collect_honors_explicit_creator_ids(monkeypatch):
    project_id = "pytest_detail_collect_segment"
    selected = {
        "creator_id": "detail-selected-low",
        "nickname": "分段补全达人",
        "pgy_url": "https://pgy.xiaohongshu.com/solar/pre-trade/blogger-detail/detail-selected-low",
        "quote_price": 22000,
        "fans_35_plus_ratio": 0.2,
    }
    skipped = {
        "creator_id": "detail-skipped-high",
        "nickname": "未选中达人",
        "pgy_url": "https://pgy.xiaohongshu.com/solar/pre-trade/blogger-detail/detail-skipped-high",
        "quote_price": 12000,
        "fans_35_plus_ratio": 0.6,
        "child_grade": "初二",
    }
    client.post(f"/api/projects/{project_id}/creators", json={"data": selected})
    client.post(f"/api/projects/{project_id}/creators", json={"data": skipped})
    with connect() as conn:
        conn.execute(
            "UPDATE creator_scores SET total_score=55, hard_filter_passed=0, detail_collection_priority='不补采' WHERE creator_id=?",
            ("detail-selected-low",),
        )
        conn.execute(
            "UPDATE creator_scores SET total_score=96, hard_filter_passed=1, detail_collection_priority='优先补采' WHERE creator_id=?",
            ("detail-skipped-high",),
        )

    captured = {}

    def fake_collect_details_for_targets(targets, limit=20):
        captured["targets"] = targets
        captured["limit"] = limit
        return {
            "ok": True,
            "creators": [{"creator_id": "detail-selected-low", "nickname": "分段补全达人", "topic_point": "补全分段详情"}],
            "failed": [],
        }

    monkeypatch.setattr("rpa_mcp_sync.web.collect_details_for_targets", fake_collect_details_for_targets)
    monkeypatch.setattr("rpa_mcp_sync.web.score_project", lambda project_id, **kwargs: {"scored": 1})

    response = client.post(
        "/api/pgy/collect/detail",
        json={"project_id": project_id, "creator_ids": ["detail-selected-low"], "segment": "C", "manual": True, "limit": 1},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["updated"][0]["topic_point"] == "补全分段详情"
    assert [item["creator_id"] for item in captured["targets"]] == ["detail-selected-low"]
    assert captured["limit"] == 1
    client.delete(f"/api/projects/{project_id}")


def test_pgy_detail_collect_manual_selection_uses_all_selected_ids_by_default(monkeypatch):
    project_id = "pytest_detail_collect_all_selected"
    selected_ids = [f"detail-selected-{index:03d}" for index in range(98)]
    for creator_id in selected_ids:
        client.post(
            f"/api/projects/{project_id}/creators",
            json={
                "data": {
                    "creator_id": creator_id,
                    "nickname": creator_id,
                    "pgy_url": f"https://pgy.xiaohongshu.com/solar/pre-trade/blogger-detail/{creator_id}",
                }
            },
        )

    captured = {}

    def fake_collect_details_for_targets(targets, limit=20, progress_callback=None):
        captured["target_count"] = len(targets)
        captured["limit"] = limit
        return {
            "ok": True,
            "creators": [{"creator_id": creator["creator_id"], "nickname": creator["nickname"]} for creator in targets],
            "failed": [],
        }

    monkeypatch.setattr("rpa_mcp_sync.web.collect_details_for_targets", fake_collect_details_for_targets)
    monkeypatch.setattr("rpa_mcp_sync.web.score_project", lambda project_id, **kwargs: {"scored": len(kwargs.get("creator_ids") or [])})

    response = client.post(
        "/api/pgy/collect/detail",
        json={"project_id": project_id, "creator_ids": selected_ids, "segment": "S", "manual": True},
    )

    assert response.status_code == 200
    payload = response.json()
    assert captured["target_count"] == 98
    assert captured["limit"] == 98
    assert len(payload["updated"]) == 98
    client.delete(f"/api/projects/{project_id}")


def test_pgy_detail_collect_targets_high_potential_missing_evidence(monkeypatch):
    project_id = "pytest_detail_missing_evidence"
    high_potential = {
        "creator_id": "detail-missing-evidence",
        "nickname": "高潜缺证据达人",
        "pgy_url": "https://pgy.xiaohongshu.com/solar/pre-trade/blogger-detail/detail-missing-evidence",
        "quote_price": 5000,
        "followers_count": 50000,
        "daily_read_median": 12000,
        "creator_type": "教育/k12教育",
    }
    enough_evidence = {
        "creator_id": "detail-enough-evidence",
        "nickname": "证据充分达人",
        "pgy_url": "https://pgy.xiaohongshu.com/solar/pre-trade/blogger-detail/detail-enough-evidence",
        "quote_price": 5000,
        "followers_count": 50000,
        "fans_35_plus_ratio": 0.55,
        "daily_read_median": 12000,
        "daily_interaction_median": 900,
        "image_cpm": 80,
        "child_grade": "初中",
        "topic_point": "学习规划",
        "raw_payload": {
            "recent_notes": [{"title": "学习规划", "read_count": 12000, "like_count": 100}],
            "detail_collection_summary": {"module_count": 5},
        },
        "creator_type": "教育/k12教育",
    }
    client.post(f"/api/projects/{project_id}/creators", json={"data": high_potential})
    client.post(f"/api/projects/{project_id}/creators", json={"data": enough_evidence})
    with connect() as conn:
        conn.execute(
            "UPDATE creator_scores SET total_score=78, hard_filter_passed=1, detail_collection_priority='中高优先级' WHERE creator_id=?",
            ("detail-missing-evidence",),
        )
        conn.execute(
            "UPDATE creator_scores SET total_score=83, hard_filter_passed=1, detail_collection_priority='高优先级' WHERE creator_id=?",
            ("detail-enough-evidence",),
        )

    captured = {}

    def fake_collect_details_for_targets(targets, limit=20):
        captured["targets"] = targets
        return {
            "ok": True,
            "creators": [{"creator_id": "detail-missing-evidence", "nickname": "高潜缺证据达人", "fans_35_plus_ratio": 0.58}],
            "failed": [],
        }

    monkeypatch.setattr("rpa_mcp_sync.web.collect_details_for_targets", fake_collect_details_for_targets)
    monkeypatch.setattr("rpa_mcp_sync.web.score_project", lambda project_id, **kwargs: {"scored": 1})

    response = client.post("/api/pgy/collect/detail", json={"project_id": project_id, "limit": 20})

    assert response.status_code == 200
    payload = response.json()
    assert [item["creator_id"] for item in captured["targets"]] == ["detail-missing-evidence"]
    assert payload["target_needs"][0]["needs"]
    client.delete(f"/api/projects/{project_id}")


def test_writeback_quality_only_does_not_generate_test_creators(monkeypatch):
    project_id = "pytest_no_fake_writeback"
    calls = {"quality": None}

    def fake_quality_rows(project_id, limit=None, min_score=90, creator_ids=None, include_test_creators=False, rescore=True):
        calls["quality"] = {
            "project_id": project_id,
            "creator_ids": creator_ids,
            "include_test_creators": include_test_creators,
            "rescore": rescore,
        }
        return []

    def fail_generate(*args, **kwargs):
        raise AssertionError("写回不应生成测试达人")

    monkeypatch.setattr("rpa_mcp_sync.web.quality_feishu_rows", fake_quality_rows)
    monkeypatch.setattr("rpa_mcp_sync.creator_store.generate_test_creators", fail_generate)

    response = client.post("/api/projects/feishu/writeback", json={"project_id": project_id, "quality_only": True})

    assert response.status_code == 400
    assert "没有要写入的记录" in response.json()["detail"]["message"]
    assert calls["quality"] == {
        "project_id": project_id,
        "creator_ids": None,
        "include_test_creators": False,
        "rescore": False,
    }
    client.delete(f"/api/projects/{project_id}")


def test_sheet_writeback_keeps_audience_profile_path_out_of_normal_cells():
    fields = [
        {"field_name": "达人昵称", "column_index": 0},
        {"field_name": "粉丝画像", "column_index": 1},
        {"field_name": "粉丝画像截图", "column_index": 2},
    ]
    rows = [
        {
            "达人昵称": "截图达人",
            "粉丝画像": "D:/第三事业部/runtime/pgy_detail_screenshots/fans-profile.png",
            "粉丝画像截图": "D:/第三事业部/runtime/pgy_detail_screenshots/fans-profile.png",
        }
    ]

    cleaned = _clear_sheet_audience_profile_image_values(rows, fields)

    assert cleaned[0]["达人昵称"] == "截图达人"
    assert cleaned[0]["粉丝画像"] == ""
    assert cleaned[0]["粉丝画像截图"] == ""
    assert rows[0]["粉丝画像"]


def test_sheet_image_writeback_prefers_existing_fans_profile_column():
    fields = [
        {"field_name": "达人昵称", "column_index": 0},
        {"field_name": "粉丝画像", "column_index": 7},
        {"field_name": "粉丝画像截图", "column_index": 8},
    ]

    field = _find_sheet_audience_profile_image_field(fields)

    assert field["field_name"] == "粉丝画像"
    assert field["column_index"] == 7


def test_auto_writeback_runs_after_detail_when_enabled(monkeypatch):
    project_id = "pytest_detail_auto_writeback"
    creator = {
        "creator_id": "auto-detail-good",
        "nickname": "自动写回达人",
        "pgy_url": "https://pgy.xiaohongshu.com/solar/pre-trade/blogger-detail/auto-detail-good",
        "quote_price": 12000,
        "fans_35_plus_ratio": 0.6,
        "child_grade": "初二",
    }
    client.post(f"/api/projects/{project_id}/creators", json={"data": creator})
    with connect() as conn:
        conn.execute(
            """
            UPDATE creator_scores
            SET total_score=96, hard_filter_passed=1, recommend_level='推荐', detail_collection_priority='优先补采'
            WHERE creator_id=?
            """,
            ("auto-detail-good",),
        )
    client.post(
        "/api/projects/feishu/writeback-settings",
        json={"project_id": project_id, "auto_writeback_enabled": True},
    )

    captured = {}

    def fake_collect_details_for_targets(targets, limit=20):
        return {
            "ok": True,
            "creators": [{"creator_id": "auto-detail-good", "nickname": "自动写回达人", "topic_point": "初中学习"}],
            "failed": [],
        }

    def fake_create_feishu_records(payload):
        captured["payload"] = payload
        return {"ok": True, "written_count": 1, "sync_status": {"success": 1, "failed": 0}}

    monkeypatch.setattr("rpa_mcp_sync.web.collect_details_for_targets", fake_collect_details_for_targets)
    monkeypatch.setattr("rpa_mcp_sync.web.score_project", lambda project_id, **kwargs: {"scored": 1})
    monkeypatch.setattr("rpa_mcp_sync.web.create_feishu_records", fake_create_feishu_records)

    response = client.post("/api/pgy/collect/detail", json={"project_id": project_id, "limit": 20})

    assert response.status_code == 200
    payload = response.json()
    assert payload["auto_writeback"]["enabled"] is True
    assert payload["auto_writeback"]["written_count"] == 1
    assert captured["payload"].quality_only is True
    assert captured["payload"].creator_ids == ["auto-detail-good"]
    client.delete(f"/api/projects/{project_id}")


def test_overview_hides_connection_files():
    response = client.get("/api/overview")
    assert response.status_code == 200
    projects = response.json()["projects"]
    assert projects[0]["project_id"] == "youdao_001"
    assert "feishu.connection" not in str(projects)


def test_save_feishu_connection_masks_secret(tmp_path, monkeypatch):
    project_id = "pytest_mask"
    path = feishu_connection_path(project_id)
    if path.exists():
        path.unlink()
    response = client.post(
        "/api/projects/feishu/connection",
        json={
            "project_id": project_id,
            "feishu_url": "https://example.feishu.cn/wiki/wikiToken123?sheet=sheet123",
            "app_id": "cli_test",
            "app_secret": "secret",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["config"]["app_secret_configured"] is True
    assert "app_secret" not in payload["config"]
    if path.exists():
        path.unlink()


def test_save_feishu_connection_precomputes_hidden_field_mapping(monkeypatch):
    project_id = "pytest_precompute_mapping"
    path = feishu_connection_path(project_id)
    if path.exists():
        path.unlink()

    def fake_refresh(target_project_id):
        config = json.loads(path.read_text(encoding="utf-8"))
        config["field_mapping_cache"] = {
            "sheet:sheet123": {
                "source": "fallback",
                "mappings": [{"target_field": "达人昵称", "source_field": "达人昵称"}],
            }
        }
        path.write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")
        return config

    monkeypatch.setattr("rpa_mcp_sync.web._refresh_feishu_field_mapping_cache", fake_refresh)

    response = client.post(
        "/api/projects/feishu/connection",
        json={
            "project_id": project_id,
            "feishu_url": "https://example.feishu.cn/wiki/wikiToken123?sheet=sheet123",
            "app_id": "cli_test",
            "app_secret": "secret",
        },
    )

    assert response.status_code == 200
    assert "field_mapping_cache" not in response.json()["config"]
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["field_mapping_cache"]["sheet:sheet123"]["mappings"][0]["source_field"] == "达人昵称"
    if path.exists():
        path.unlink()


def test_feishu_fields_uses_rule_mapping_by_default(monkeypatch):
    from rpa_mcp_sync.feishu import FeishuTarget

    project_id = "pytest_feishu_fields_rule_mapping"
    path = feishu_connection_path(project_id)
    if path.exists():
        path.unlink()

    class FakeFeishuClient:
        def list_sheet_tabs(self, token):
            return [{"sheet_id": "sheet123", "title": "达人表"}]

        def list_sheet_fields(self, token, sheet_id):
            return [{"field_name": "达人昵称", "column_index": 1}]

    def fake_load_feishu_client(target_project_id):
        assert target_project_id == project_id
        return (
            {"project_id": project_id, "feishu_url": "https://example.feishu.cn/sheets/token?sheet=sheet123", "field_mapping_cache": {}},
            FakeFeishuClient(),
            FeishuTarget("sheet", "token", "sheet123", "sheet_url"),
        )

    def fail_chat_json(*args, **kwargs):
        raise AssertionError("field mapping should not call LLM unless use_ai_mapping=true")

    monkeypatch.setattr("rpa_mcp_sync.web._load_feishu_client", fake_load_feishu_client)
    monkeypatch.setattr("rpa_mcp_sync.feishu_field_agent.chat_json", fail_chat_json)

    response = client.get(f"/api/projects/feishu/fields?project_id={project_id}&table_id=sheet123")

    assert response.status_code == 200
    payload = response.json()
    assert payload["field_mapping"]["source"] == "fallback"
    assert payload["field_mapping"]["llm_count"] == 0
    assert "本地规则" in payload["message"]
    if path.exists():
        path.unlink()


def test_feishu_fields_ai_mapping_requires_explicit_query_and_refreshes_cache(monkeypatch):
    from rpa_mcp_sync.feishu import FeishuTarget

    project_id = "pytest_feishu_fields_ai_mapping"
    path = feishu_connection_path(project_id)
    if path.exists():
        path.unlink()

    fields = [{"field_name": "粉丝年龄25~44占比", "column_index": 1}]

    class FakeFeishuClient:
        def list_sheet_tabs(self, token):
            return [{"sheet_id": "sheet123", "title": "达人表"}]

        def list_sheet_fields(self, token, sheet_id):
            return fields

    def fake_load_feishu_client(target_project_id):
        assert target_project_id == project_id
        return (
            {
                "project_id": project_id,
                "feishu_url": "https://example.feishu.cn/sheets/token?sheet=sheet123",
                "field_mapping_cache": {
                    "sheet:sheet123": {
                        "source": "fallback",
                        "field_signature": ["粉丝年龄25~44占比"],
                        "mappings": [],
                        "unmatched": [{"target_field": "粉丝年龄25~44占比", "reason": "old cache"}],
                    }
                },
            },
            FakeFeishuClient(),
            FeishuTarget("sheet", "token", "sheet123", "sheet_url"),
        )

    calls = {"chat_json": 0}

    def fake_chat_json(*args, **kwargs):
        calls["chat_json"] += 1
        return {
            "mappings": [
                {
                    "target_field": "粉丝年龄25~44占比",
                    "source_field": "粉丝年龄25-44占比",
                    "confidence": 0.95,
                    "reason": "explicit AI mapping",
                }
            ],
            "unmatched": [],
        }

    monkeypatch.setattr("rpa_mcp_sync.web._load_feishu_client", fake_load_feishu_client)
    monkeypatch.setattr("rpa_mcp_sync.feishu_field_agent.chat_json", fake_chat_json)

    response = client.get(f"/api/projects/feishu/fields?project_id={project_id}&table_id=sheet123&use_ai_mapping=true")

    assert response.status_code == 200
    payload = response.json()
    assert calls["chat_json"] == 1
    assert payload["field_mapping"]["source"] == "llm"
    assert payload["field_mapping"]["mappings"][0]["source_field"] == "粉丝年龄25-44占比"
    assert "大模型" in payload["message"]
    if path.exists():
        path.unlink()


def test_feishu_test_requires_secret_for_full_check():
    project_id = "pytest_missing_secret"
    path = feishu_connection_path(project_id)
    if path.exists():
        path.unlink()
    response = client.post(
        "/api/projects/feishu/test",
        json={
            "project_id": project_id,
            "feishu_url": "https://example.feishu.cn/wiki/wikiToken123?sheet=sheet123",
            "app_id": "cli_test",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is False
    assert payload["failed_step"] == "auth"
    assert "无法完整测试" in payload["message"]
    if path.exists():
        path.unlink()


def test_feishu_test_reuses_saved_app_secret(monkeypatch):
    project_id = "pytest_feishu_saved_secret"
    path = feishu_connection_path(project_id)
    if path.exists():
        path.unlink()

    client.post(
        "/api/projects/feishu/connection",
        json={
            "project_id": project_id,
            "feishu_url": "https://example.feishu.cn/wiki/wikiToken123?sheet=sheet123",
            "app_id": "cli_saved",
            "app_secret": "saved-secret",
        },
    )

    captured = {}

    def fake_full_test(feishu_url, app_id, app_secret, *, table_id=None):
        captured.update({"feishu_url": feishu_url, "app_id": app_id, "app_secret": app_secret, "table_id": table_id})
        return {
            "ok": True,
            "fields": [],
            "steps": [],
            "message": "飞书连接完整测试通过：字段读取和测试写入均正常",
        }

    monkeypatch.setattr("rpa_mcp_sync.web._run_feishu_full_test", fake_full_test)

    response = client.post(
        "/api/projects/feishu/test",
        json={
            "project_id": project_id,
            "feishu_url": "https://example.feishu.cn/wiki/wikiToken123?sheet=sheet123",
            "app_id": "cli_saved",
            "app_secret": "",
        },
    )

    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert captured["app_secret"] == "saved-secret"

    if path.exists():
        path.unlink()


def test_llm_config_roundtrip():
    original = AI_PROVIDER_PATH.read_text(encoding="utf-8") if AI_PROVIDER_PATH.exists() else None
    response = client.post(
        "/api/llm/config",
        json={
            "protocol": "gemini",
            "base_url": "https://generativelanguage.googleapis.com/v1beta",
            "model": "gemini-2.5-flash",
            "api_key_env": "GEMINI_API_KEY",
            "temperature": 0.1,
            "max_tokens": 1000,
            "timeout_seconds": 30,
        },
    )
    assert response.status_code == 200
    assert response.json()["config"]["protocol"] == "gemini"
    if original is None:
        if AI_PROVIDER_PATH.exists():
            AI_PROVIDER_PATH.unlink()
    else:
        AI_PROVIDER_PATH.write_text(original, encoding="utf-8")


def test_llm_config_supports_main_and_secondary_models():
    original = AI_PROVIDER_PATH.read_text(encoding="utf-8") if AI_PROVIDER_PATH.exists() else None
    response = client.post(
        "/api/llm/config",
        json={
            "main_model": {
                "protocol": "openai-compatible",
                "base_url": "https://main.example.com/v1",
                "model": "main-heavy",
                "api_key_env": "MAIN_MODEL_KEY",
                "temperature": 0.2,
                "timeout_seconds": 300,
            },
            "secondary_model": {
                "protocol": "openai-compatible",
                "base_url": "https://secondary.example.com/v1",
                "model": "secondary-batch",
                "api_key_env": "SECONDARY_MODEL_KEY",
                "temperature": 0.1,
                "timeout_seconds": 120,
            },
        },
    )

    assert response.status_code == 200
    config = response.json()["config"]
    assert config["model"] == "main-heavy"
    assert config["main_model"]["model"] == "main-heavy"
    assert config["secondary_model"]["model"] == "secondary-batch"
    assert config["routing"]["brief_parsing"] == "main_model"
    assert config["routing"]["creator_scoring"] == "secondary_model"

    if original is None:
        if AI_PROVIDER_PATH.exists():
            AI_PROVIDER_PATH.unlink()
    else:
        AI_PROVIDER_PATH.write_text(original, encoding="utf-8")


def test_llm_config_does_not_append_v1_to_base_url():
    original = AI_PROVIDER_PATH.read_text(encoding="utf-8") if AI_PROVIDER_PATH.exists() else None

    response = client.post(
        "/api/llm/config",
        json={
            "protocol": "openai-compatible",
            "base_url": "https://vip.123everything.com/",
            "model": "gpt-5.4",
            "api_key_env": "OPENAI_API_KEY",
        },
    )

    assert response.status_code == 200
    assert response.json()["config"]["base_url"] == "https://vip.123everything.com"

    if original is None:
        if AI_PROVIDER_PATH.exists():
            AI_PROVIDER_PATH.unlink()
    else:
        AI_PROVIDER_PATH.write_text(original, encoding="utf-8")


def test_llm_test_reuses_saved_inline_key(monkeypatch):
    original = AI_PROVIDER_PATH.read_text(encoding="utf-8") if AI_PROVIDER_PATH.exists() else None

    class Response:
        status_code = 200

        def json(self):
            return {"data": []}

    captured = {}

    def fake_get(url, headers=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers or {}
        captured["timeout"] = timeout
        return Response()

    monkeypatch.setattr("rpa_mcp_sync.llm_config.requests.get", fake_get)

    client.post(
        "/api/llm/config",
        json={
            "protocol": "openai-compatible",
            "base_url": "https://vip.123everything.com/v1",
            "model": "gpt-5.4",
            "api_key": "saved-secret",
            "api_key_env": "OPENAI_API_KEY",
            "keep_existing_api_key": True,
        },
    )
    response = client.post(
        "/api/llm/test",
        json={
            "protocol": "openai-compatible",
            "base_url": "https://vip.123everything.com/v1",
            "model": "gpt-5.4",
            "api_key": "",
            "api_key_env": "OPENAI_API_KEY",
        },
    )

    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert captured["url"] == "https://vip.123everything.com/v1/models"
    assert captured["headers"]["Authorization"] == "Bearer saved-secret"

    if original is None:
        if AI_PROVIDER_PATH.exists():
            AI_PROVIDER_PATH.unlink()
    else:
        AI_PROVIDER_PATH.write_text(original, encoding="utf-8")


def test_optimize_screening_standard_generates_without_key():
    original = AI_PROVIDER_PATH.read_text(encoding="utf-8") if AI_PROVIDER_PATH.exists() else None
    if AI_PROVIDER_PATH.exists():
        AI_PROVIDER_PATH.unlink()
    project_id = "pytest_screening_standard"
    response = client.post(
        f"/api/projects/{project_id}/screening-standard/optimize",
        json={
            "brief": "需要教育母婴达人，单个达人报价不超过2万元，35岁以上宝妈粉丝占比高，必须有蒲公英链接。",
            "feishu_fields": [
                {"field_name": "达人昵称"},
                {"field_name": "平台报价"},
                {"field_name": "35岁以上粉丝占比"},
                {"field_name": "蒲公英链接"},
            ],
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "generated"
    assert payload["screeningPlan"]["scoringWeights"]["budget"] == 15
    hard_filter_text = json.dumps(payload["screeningPlan"]["hardFilters"], ensure_ascii=False)
    assert "35岁以上粉丝占比" not in hard_filter_text
    assert payload["screeningPlan"]["scoringCriteria"]["purpose"]
    assert payload["screeningPlan"]["projectFitConfig"]["product_name"] == "当前 Brief 产品" or payload["screeningPlan"]["projectFitConfig"]["product_name"]
    assert "preferred_content_scenes" in payload["screeningPlan"]["projectFitConfig"]
    assert payload["screeningPlan"]["promotionStrategy"]["screening_implications"]
    assert payload["screeningPlan"]["promotionStrategy"]["scoring_implications"]
    assert len(payload["screeningPlan"]["pgyCollectionPlan"]["schemes"]) == 4
    first_scheme = payload["screeningPlan"]["pgyCollectionPlan"]["schemes"][0]
    assert first_scheme["target_count_range"]
    assert first_scheme["narrow_if_too_many"]
    project = client.get(f"/api/projects/{project_id}").json()["project"]
    assert project["screening_plan"]
    assert "scoringCriteria" in project["screening_plan"]
    with connect() as conn:
        conn.execute("DELETE FROM projects WHERE project_id=?", (project_id,))
    if original is None:
        if AI_PROVIDER_PATH.exists():
            AI_PROVIDER_PATH.unlink()
    else:
        AI_PROVIDER_PATH.write_text(original, encoding="utf-8")


def test_save_project_auto_fills_project_fit_config_from_brief():
    project_id = "pytest_project_fit_save"
    plan = {"briefType": "complex", "pgyCollectionPlan": {"filters": []}}

    response = client.post(
        f"/api/projects/{project_id}",
        json={"project_name": project_id, "brief": "有道答疑笔，找初中家长达人", "screening_plan": plan},
    )

    assert response.status_code == 200
    saved_plan = json.loads(response.json()["project"]["screening_plan"])
    assert saved_plan["projectFitConfig"]["product_name"] == "有道答疑笔"
    assert "作业答疑" in saved_plan["projectFitConfig"]["preferred_content_scenes"]
    assert saved_plan["projectFitConfig"]["evidence_rules"]["weak_scene_match_max_score"] == 79

    with connect() as conn:
        conn.execute("DELETE FROM projects WHERE project_id=?", (project_id,))


def test_project_response_hydrates_legacy_empty_fit_config():
    project_id = "pytest_project_fit_legacy_empty"
    plan = {
        "briefType": "complex",
        "projectFitConfig": None,
        "promotionStrategy": None,
        "briefDecomposition": {
            "negative_constraints": ["不优先低幼启蒙账号"],
            "manual_review_rules": ["复核是否真实覆盖作业答疑场景"],
        },
        "pgyCollectionPlan": {"filters": []},
    }
    with connect() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO projects(project_id, project_name, target_qualified_creator_count, period_start, period_end, brief, screening_plan, created_at, updated_at)
            VALUES (?, ?, 10, '', '', ?, ?, '2026-05-25 10:00:00', '2026-05-25 10:00:00')
            """,
            (
                project_id,
                "有道答疑笔历史项目",
                "有道答疑笔，找小学高年级和初中家长达人，35岁以上粉丝占比要高。",
                json.dumps(plan, ensure_ascii=False),
            ),
        )

    response = client.get(f"/api/projects/{project_id}")

    assert response.status_code == 200
    saved_plan = json.loads(response.json()["project"]["screening_plan"])
    assert saved_plan["projectFitConfig"]["product_name"] == "有道答疑笔"
    assert "小学高年级学生" in saved_plan["projectFitConfig"]["core_users"]
    assert "作业答疑" in saved_plan["projectFitConfig"]["preferred_content_scenes"]
    assert saved_plan["promotionStrategy"]["decision_makers"] == ["家长"]

    with connect() as conn:
        conn.execute("DELETE FROM projects WHERE project_id=?", (project_id,))


def test_save_project_replaces_stale_generic_fit_config_for_listening_product():
    project_id = "pytest_project_fit_stale_listening"
    plan = {
        "briefType": "complex",
        "projectFitConfig": {
            "product_name": "当前 Brief 产品",
            "core_users": ["目标学生"],
            "core_decision_makers": ["家长"],
            "target_grade_keywords": ["小学", "初中", "高中"],
            "preferred_content_scenes": ["学习规划", "家长辅导", "产品测评"],
        },
        "promotionStrategy": None,
        "pgyCollectionPlan": {"filters": []},
    }

    response = client.post(
        f"/api/projects/{project_id}",
        json={
            "project_name": project_id,
            "brief": "有道留学听课宝，找留学生/海外背景达人，单达人预算1000以内。",
            "screening_plan": plan,
        },
    )

    assert response.status_code == 200
    saved_plan = json.loads(response.json()["project"]["screening_plan"])
    assert saved_plan["projectFitConfig"]["product_name"] == "有道留学听课宝"
    assert saved_plan["projectFitConfig"]["core_decision_makers"] == ["学生本人"]
    assert "海外课堂听课" in saved_plan["projectFitConfig"]["preferred_content_scenes"]
    assert "家长辅导" not in saved_plan["projectFitConfig"]["preferred_content_scenes"]
    assert saved_plan["promotionStrategy"]["decision_makers"] == ["学生本人"]

    with connect() as conn:
        conn.execute("DELETE FROM projects WHERE project_id=?", (project_id,))


def test_save_project_adds_format_budget_policy_and_hard_rules_for_listening_product():
    project_id = "pytest_listening_format_budget_policy"

    response = client.post(
        f"/api/projects/{project_id}",
        json={
            "project_name": project_id,
            "brief": "有道留学听课宝，图文和视频都可，最好是视频，单达人预算1000以下KOC；需要接过商单，回复率低于50%直接pass，近1个月内有更新，内容需要50%以上学习类。",
            "screening_plan": {"briefType": "complex", "pgyCollectionPlan": {"filters": []}},
        },
    )

    assert response.status_code == 200
    saved_plan = json.loads(response.json()["project"]["screening_plan"])
    assert saved_plan["formatBudgetPolicy"]["preferred_format"] == "视频"
    assert saved_plan["formatBudgetPolicy"]["image_quote_cap"] == 1000
    assert saved_plan["formatBudgetPolicy"]["video_quote_cap"] == 1000
    assert saved_plan["formatBudgetPolicy"]["premium_exception_policy"]["data_top_percent"] == 5
    assert saved_plan["formatBudgetPolicy"]["premium_exception_policy"]["max_budget_multiplier"] == 1.5
    assert saved_plan["hardRules"]["must_have_commercial_order"] is True
    assert saved_plan["hardRules"]["reply_rate_min"] == 0.5
    assert saved_plan["hardRules"]["recent_update_days"] == 30
    assert saved_plan["hardRules"]["must_have_study_content_ratio"] == 0.5
    assert saved_plan["scoringCriteria"]["format_budget_policy"]["preferred_format"] == "视频"

    with connect() as conn:
        conn.execute("DELETE FROM projects WHERE project_id=?", (project_id,))


def test_normalize_screening_standard_outputs_koc_scoring_config_for_koc_brief():
    from rpa_mcp_sync.web import ScreeningStandardPayload, _normalize_screening_standard

    plan = _normalize_screening_standard(
        {
            "briefType": "complex",
            "kocScoringConfig": {"stage1_thresholds": {"read_priority_min": 1500}},
            "pgyCollectionPlan": {"schemes": []},
        },
        ScreeningStandardPayload(brief="KOC项目，单达人预算1000以内，优先学习类内容达人。"),
    )

    assert plan["kocScoringConfig"]["enabled"] is True
    assert plan["kocScoringConfig"]["stage1_thresholds"]["read_priority_min"] == 1500
    assert plan["kocScoringConfig"]["stage1_thresholds"]["interaction_strong_min"] == 274
    assert plan["kocScoringConfig"]["detail_stage_rules"]["missing_evidence_status"] == "待人工确认"


def test_optimize_screening_standard_uses_larger_llm_budget_and_reports_fallback(monkeypatch):
    captured = {}

    def fake_chat_json(messages, config=None):
        captured["config"] = config or {}
        raise json.JSONDecodeError("Expecting ',' delimiter", '{"a":', 5)

    monkeypatch.setattr("rpa_mcp_sync.web.chat_json", fake_chat_json)
    project_id = "pytest_screening_standard_llm_budget"
    response = client.post(
        f"/api/projects/{project_id}/screening-standard/optimize",
        json={"brief": "需要教育母婴达人，单个达人报价不超过2万元。"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert captured["config"]["max_tokens"] == 64000
    assert captured["config"]["timeout_seconds"] == 300
    assert payload["source"] == "generated"
    assert "大模型未返回可用 JSON" in payload["message"]
    assert "JSONDecodeError" in payload["message"]

    with connect() as conn:
        conn.execute("DELETE FROM projects WHERE project_id=?", (project_id,))


def test_optimize_screening_standard_prunes_default_age_rule_for_study_abroad(monkeypatch):
    captured = {}

    def fake_chat_json(messages, config=None):
        captured["prompt"] = "\n".join(message["content"] for message in messages)
        return {
            "briefType": "complex",
            "briefDecomposition": {
                "promotion_audience_analysis": {
                    "actual_users": ["留学生"],
                    "decision_makers": ["学生本人"],
                    "content_influenced_audience": ["海外学习人群"],
                    "not_target_audiences": ["默认35-44家长粉丝"],
                    "reasoning": "留学产品不能默认套家长人群",
                },
                "rule_placement_matrix": [
                    {"brief_requirement": "学习类内容占比", "placement": "post_score", "is_one_vote_veto": False},
                ],
                "post_score_rules": [],
            },
            "scoringWeights": {"budget": 15, "fans": 5, "cpe": 20, "engagement": 30, "persona": 20, "content": 10},
            "scoringHardFilters": [
                {"field": "合作报价", "condition": "<=", "value": "1000", "required": True},
                {"field": "内容适配", "condition": "规则", "value": "学习类内容明显不足50%，则不推荐", "required": True},
                {"field": "粉丝年龄", "condition": "匹配", "value": "35-44 占比高", "required": True},
            ],
            "scoringCriteria": {"hard_rules": []},
            "pgyCollectionPlan": {
                "schemes": [
                    {
                        "scheme_id": "study_abroad_core",
                        "name": "留学核心池",
                        "role": "primary",
                        "precision_level": "high",
                        "required_filters": [
                            {"field": "博主类目", "value": "教育", "sub_value": "留学教育"},
                            {"field": "粉丝量", "value": "0.1万以上"},
                            {"field": "合作报价", "value": "图文笔记：0-1000"},
                        ],
                    }
                ],
            },
        }

    monkeypatch.setattr("rpa_mcp_sync.web.chat_json", fake_chat_json)
    project_id = "pytest_preserve_llm_hard_rules"
    response = client.post(
        f"/api/projects/{project_id}/screening-standard/optimize",
        json={"brief": "有道留学听课宝，找留学生/海外背景达人，内容需要50%以上学习类，单达人预算1000以内。"},
    )

    assert response.status_code == 200
    plan = response.json()["screeningPlan"]
    hard_text = json.dumps(plan["scoringHardFilters"], ensure_ascii=False)
    first_required = plan["pgyCollectionPlan"]["schemes"][0]["required_filters"]

    assert "学习类内容" in hard_text
    assert "35-44" not in hard_text
    assert "合作报价" in hard_text
    assert plan["scoringCriteria"]["post_score_rules"] == []
    assert not any(item.get("field") == "粉丝年龄" for item in first_required)
    assert "教育/学习产品不等于家长/宝妈/35-44" not in captured["prompt"]
    assert "留学/大学/职场学习类产品通常应优先判断学生/留学生/备考人群" not in captured["prompt"]
    assert "不要套用固定行业模板" in captured["prompt"]
    assert "蒲公英不能前置，不等于不能成为采后硬性规则" in captured["prompt"]
    assert "不要自行补全行业默认答案" in captured["prompt"]
    assert "evidence_from_brief" in captured["prompt"]
    assert "assumptions" in captured["prompt"]
    assert "unknowns" in captured["prompt"]
    assert "reasoning 只描述当前 Brief 的正向依据和未明确项" in captured["prompt"]
    assert "不要通过反驳某个历史模板、默认人群或固定年龄段来论证" in captured["prompt"]
    assert "inferred_fans_age" in captured["prompt"]
    assert "蒲公英真实字段“粉丝年龄”的真实选项" in captured["prompt"]
    assert "不得为了凑满方案编造 Brief 没有依据的人群" in captured["prompt"]
    assert "真实优质样本校准后的规则" in captured["prompt"]
    assert "kocScoringConfig" in captured["prompt"]
    assert "负向约束，例如不优先孕期/低幼/泛生活方式妈妈等" not in captured["prompt"]

    with connect() as conn:
        conn.execute("DELETE FROM projects WHERE project_id=?", (project_id,))


def test_optimize_screening_standard_saves_project_special_scoring_and_score_uses_it(monkeypatch):
    def fake_chat_json(messages, config=None):
        return {
            "briefType": "complex",
            "briefDecomposition": {
                "brief_facts": [{"category": "persona", "fact": "优先留学生/海外课堂背景"}],
                "promotion_audience_analysis": {
                    "actual_users": ["留学生"],
                    "decision_makers": ["学生本人"],
                    "content_influenced_audience": ["海外学习人群"],
                    "reasoning": "Brief 明确留学生和听课场景",
                },
                "must_have_requirements": ["留学生或海外学习背景"],
                "strong_preferences": ["课堂、听课、复盘内容"],
                "negative_constraints": ["纯旅行穿搭"],
            },
            "promotionStrategy": {
                "product_positioning": "听课宝 / 留学生学习工具",
                "target_users": ["留学生"],
                "decision_makers": ["学生本人"],
                "core_selling_points": ["课堂录音整理", "课后复盘"],
                "conversion_scenes": ["海外课堂", "听课复盘"],
                "content_angles": ["课堂笔记复盘", "学习工具测评"],
                "negative_fit_risks": ["纯旅行穿搭"],
            },
            "projectFitConfig": {
                "product_name": "听课宝",
                "preferred_content_scenes": ["海外课堂", "听课复盘"],
                "preferred_presentation_styles": ["学习工具测评"],
                "discouraged_keywords": ["纯旅行穿搭"],
            },
            "projectSpecialScoring": {
                "enabled": True,
                "label": "听课宝",
                "source": "llm_brief_decomposition",
                "identity": {
                    "name": "留学生/海外学习背景",
                    "points": 35,
                    "fields": ["nickname", "creator_type", "persona_tags", "topic_point"],
                    "keywords": ["留学生", "海外", "美国大学"],
                    "evidence_keywords": ["海外课堂", "assignment", "lecture"],
                },
                "scene": {
                    "name": "听课/课堂/复盘场景",
                    "max_points": 30,
                    "base_points": 12,
                    "points_per_hit": 4,
                    "max_keyword_hits": 4,
                    "direction_bonus": {"strong": 4, "medium": 2},
                    "keywords": ["听课", "课堂", "复盘", "lecture", "assignment"],
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
                "negative": {"keywords": ["纯旅行穿搭"], "cap_without_scene": 84},
                "project_fit_config_patch": {
                    "preferred_content_scenes": ["海外课堂", "听课复盘"],
                    "preferred_presentation_styles": ["学习工具测评"],
                    "discouraged_keywords": ["纯旅行穿搭"],
                },
                "ignore_hard_filter_keywords": ["35", "34", "粉丝年龄", "宝妈", "家长"],
            },
            "scoringWeights": {"budget": 15, "fans": 5, "cpe": 20, "engagement": 30, "persona": 20, "content": 10},
            "scoringHardFilters": [{"field": "合作报价", "condition": "<=", "value": "1000", "required": True}],
            "scoringCriteria": {"hard_rules": [{"field": "合作报价", "condition": "<=", "value": "1000", "required": True}]},
            "pgyCollectionPlan": {"schemes": []},
        }

    monkeypatch.setattr("rpa_mcp_sync.web.chat_json", fake_chat_json)
    project_id = "pytest_special_scoring_saved_from_brief"
    response = client.post(
        f"/api/projects/{project_id}/screening-standard/optimize",
        json={"brief": "有道留学听课宝，找留学生/海外背景达人，课堂听课和课后复盘场景，单达人预算1000以内。"},
    )

    assert response.status_code == 200
    plan = response.json()["screeningPlan"]
    assert plan["projectSpecialScoring"]["label"] == "听课宝"
    assert plan["projectSpecialScoring"]["identity"]["points"] == 35

    with connect() as conn:
        saved = conn.execute("SELECT screening_plan FROM projects WHERE project_id=?", (project_id,)).fetchone()
    saved_plan = json.loads(saved["screening_plan"])
    assert saved_plan["projectSpecialScoring"]["scene"]["keywords"][:2] == ["听课", "课堂"]

    from rpa_mcp_sync.creator_store import score_values

    score = score_values(
        {
            "creator_id": "pytest-special-scoring-from-saved-plan",
            "nickname": "美国大学留学生学习博主",
            "pgy_url": "https://pgy.xiaohongshu.com/creator/special-scoring",
            "followers_count": 5200,
            "quote_price": 800,
            "daily_read_median": 5000,
            "daily_interaction_median": 420,
            "image_read_unit_price": 0.16,
            "image_interaction_unit_price": 1.9,
            "creator_type": "教育/留学教育/学习日常",
            "persona_tags": "留学生、美国大学、课堂复盘",
            "raw_payload": {
                "recent_notes": [
                    {"title": "lecture听课复盘", "content": "海外课堂assignment整理", "read_count": 5200, "like_count": 180, "save_count": 120},
                    {"title": "课堂笔记复盘", "content": "课后复盘和听课工具测评", "read_count": 4800, "like_count": 170, "save_count": 100},
                ]
            },
        },
        project_id=project_id,
    )
    assert score["initial_tier"] == "S"
    assert "听课宝S档依据" in score["score_reason"]

    with connect() as conn:
        conn.execute("DELETE FROM projects WHERE project_id=?", (project_id,))


def test_save_project_prunes_legacy_default_age_rule_for_study_abroad():
    project_id = "pytest_prune_legacy_age_for_study_abroad"
    plan = {
        "briefType": "complex",
        "scoringHardFilters": [
            {"field": "粉丝年龄", "condition": "匹配", "value": "35～44 占比高", "required": True, "pgyField": "粉丝年龄"},
            {"field": "合作报价", "condition": "<=", "value": "1000", "required": True},
        ],
        "scoringCriteria": {
            "hard_rules": [
                {"field": "粉丝年龄", "condition": "匹配", "value": "35～44 占比高", "required": True, "pgyField": "粉丝年龄"},
                {"field": "合作报价", "condition": "<=", "value": "1000", "required": True},
            ]
        },
        "pgyCollectionPlan": {"filters": [], "schemes": []},
    }
    response = client.post(
        f"/api/projects/{project_id}",
        json={"project_name": project_id, "brief": "有道留学听课宝，找留学生/海外背景达人，单达人预算1000以内。", "screening_plan": plan},
    )

    assert response.status_code == 200
    saved_plan = json.loads(response.json()["project"]["screening_plan"])
    hard_text = json.dumps(saved_plan["scoringHardFilters"], ensure_ascii=False)
    assert "粉丝年龄" not in hard_text
    assert "合作报价" in hard_text
    assert saved_plan["scoringCriteria"]["hard_rules"] == saved_plan["scoringHardFilters"]

    with connect() as conn:
        conn.execute("DELETE FROM projects WHERE project_id=?", (project_id,))


def test_save_project_syncs_editable_hard_filters_to_scoring_criteria():
    project_id = "pytest_editable_hard_filters"
    plan = {
        "briefType": "complex",
        "hardFilters": [
            {"field": "平台报价", "condition": "<=", "value": "15000", "required": True, "feishuField": "报价"},
            {"field": "孩子年级", "condition": "包含", "value": "初中", "required": False, "feishuField": "孩子年级"},
        ],
        "scoringWeights": {"budget": 20, "fans": 20, "cpe": 15, "engagement": 15, "persona": 20, "content": 10},
        "scoringCriteria": {"purpose": "旧说明", "hard_rules": []},
        "pgyCollectionPlan": {"filters": []},
    }
    response = client.post(
        f"/api/projects/{project_id}",
        json={"project_name": project_id, "brief": "教育达人", "screening_plan": plan},
    )
    assert response.status_code == 200
    saved_plan = json.loads(response.json()["project"]["screening_plan"])
    assert saved_plan["hardFilters"][0]["value"] == "15000"
    assert saved_plan["scoringCriteria"]["hard_rules"] == saved_plan["hardFilters"]
    assert saved_plan["scoringCriteria"]["dimension_weights"]["budget"] == 20
    with connect() as conn:
        conn.execute("DELETE FROM projects WHERE project_id=?", (project_id,))


def test_save_project_preserves_brief_generated_pgy_filters():
    project_id = "pytest_saved_pgy_filters"
    plan = {
        "briefType": "complex",
        "collectionHardFilters": [
            {"field": "博主类目", "condition": "包含", "value": "教育", "required": True, "pgyField": "博主类目"},
        ],
        "scoringHardFilters": [
            {"field": "平台报价", "condition": "<=", "value": "20000", "required": True, "feishuField": "报价"},
        ],
        "pgyCollectionPlan": {
            "filters": [
                {"field": "博主类目", "value": "教育", "reason": "Brief 命中教育场景"},
                {"field": "粉丝年龄", "value": "35～44 占比高", "reason": "Brief 要求家长粉丝"},
                {"field": "合作报价", "value": "图文笔记：0.1万～2万", "sub_field": "图文笔记", "max": 20000},
            ],
            "display_metrics": ["全部非直播指标"],
        },
    }

    response = client.post(
        f"/api/projects/{project_id}",
        json={"project_name": project_id, "brief": "教育亲子达人，报价不超过2万", "screening_plan": plan},
    )

    assert response.status_code == 200
    saved_plan = json.loads(response.json()["project"]["screening_plan"])
    saved_filters = saved_plan["pgyCollectionPlan"]["filters"]
    assert [item["field"] for item in saved_filters] == ["博主类目", "粉丝年龄", "合作报价"]
    assert saved_plan["pgyCollectionPlan"]["hard_filters"][0]["pgyField"] == "博主类目"
    assert saved_plan["scoringCriteria"]["hard_rules"] == saved_plan["scoringHardFilters"]

    with connect() as conn:
        conn.execute("DELETE FROM projects WHERE project_id=?", (project_id,))


def test_collect_batch_uses_saved_project_screening_plan(monkeypatch):
    project_id = "pytest_collect_saved_plan"
    plan = {
        "pgyCollectionPlan": {
            "filters": [
                {"field": "博主类目", "value": "教育", "reason": "保存的采集条件"},
                {"field": "粉丝年龄", "value": "35～44 占比高", "reason": "保存的采集条件"},
            ],
            "display_metrics": ["全部非直播指标"],
        }
    }
    client.post(
        f"/api/projects/{project_id}",
        json={"project_name": project_id, "brief": "教育亲子达人", "screening_plan": plan},
    )

    captured = {}

    def fake_collect_visible_list(**kwargs):
        captured["screening_plan"] = kwargs["screening_plan"]
        filters = kwargs["screening_plan"]["pgyCollectionPlan"]["filters"]
        return {
            "ok": True,
            "creators": [
                {
                    "creator_id": "saved-plan-creator",
                    "source": "pgy",
                    "nickname": "保存计划采集测试达人",
                    "pgy_url": "https://pgy.xiaohongshu.com/creator/saved-plan",
                    "quote_price": 12000,
                }
            ],
            "collection_plan": kwargs["screening_plan"]["pgyCollectionPlan"],
            "applied_filters": [{"field": item["field"], "value": item["value"], "message": "已应用"} for item in filters],
            "skipped_filters": [],
            "selected_metrics": [],
            "skipped_metrics": [],
            "export_result": {"status": "skipped"},
        }

    monkeypatch.setattr("rpa_mcp_sync.web.collect_visible_list", fake_collect_visible_list)
    monkeypatch.setattr("rpa_mcp_sync.web.score_project", lambda project_id, **kwargs: {"scored": 0})

    response = client.post("/api/pgy/collect/batch", json={"project_id": project_id, "preflight": False})

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    filters = captured["screening_plan"]["pgyCollectionPlan"]["filters"]
    assert [item["field"] for item in filters] == ["博主类目", "粉丝年龄"]
    assert payload["batch"]["applied_filters"][1]["value"] == "35～44 占比高"

    with connect() as conn:
        conn.execute("DELETE FROM projects WHERE project_id=?", (project_id,))


def test_collect_batch_defaults_to_5000_limit(monkeypatch):
    project_id = "pytest_collect_default_limit"
    plan = {"pgyCollectionPlan": {"filters": [{"field": "博主类目", "value": "教育"}]}}
    client.post(f"/api/projects/{project_id}", json={"project_name": project_id, "screening_plan": plan})
    captured = {}

    def fake_collect_visible_list(**kwargs):
        captured["limit"] = kwargs["limit"]
        return {
            "ok": True,
            "creators": [
                {
                    "creator_id": "default-limit-creator",
                    "source": "pgy",
                    "nickname": "默认上限测试达人",
                    "pgy_url": "https://pgy.xiaohongshu.com/creator/default-limit",
                }
            ],
            "collection_plan": kwargs["screening_plan"]["pgyCollectionPlan"],
            "applied_filters": [],
            "skipped_filters": [],
            "selected_metrics": [],
            "skipped_metrics": [],
            "export_result": {"status": "skipped"},
        }

    monkeypatch.setattr("rpa_mcp_sync.web.collect_visible_list", fake_collect_visible_list)
    monkeypatch.setattr("rpa_mcp_sync.web.score_project", lambda project_id, **kwargs: {"scored": 0})

    response = client.post("/api/pgy/collect/batch", json={"project_id": project_id, "preflight": False})

    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert captured["limit"] == 5000

    with connect() as conn:
        conn.execute("DELETE FROM projects WHERE project_id=?", (project_id,))


def test_project_batches_can_filter_running_status():
    from rpa_mcp_sync.creator_store import create_batch, finish_batch

    project_id = "pytest_batch_status_filter"
    with connect() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO projects(project_id, project_name, target_qualified_creator_count, period_start, period_end, brief, screening_plan, created_at, updated_at)
            VALUES (?, ?, 10, '2026-05-07', '2026-05-19', '', '{}', '2026-05-09 12:00:00', '2026-05-09 12:00:00')
            """,
            (project_id, project_id),
        )
    finished_id = create_batch(project_id, "https://example.com/finished")
    finish_batch(finished_id, "success", 1, 1, 0)
    running_id = create_batch(project_id, "https://example.com/running")

    response = client.get(f"/api/projects/{project_id}/batches", params={"status": "running", "limit": 1})

    assert response.status_code == 200
    batches = response.json()["batches"]
    assert [batch["batch_id"] for batch in batches] == [running_id]

    with connect() as conn:
        conn.execute("DELETE FROM collection_batches WHERE project_id=?", (project_id,))
        conn.execute("DELETE FROM projects WHERE project_id=?", (project_id,))


def test_collect_batch_rejects_concurrent_project_run():
    from rpa_mcp_sync.web import _collect_lock

    project_id = "pytest_collect_lock"
    lock = _collect_lock(project_id)
    assert lock.acquire(blocking=False)
    try:
        response = client.post("/api/pgy/collect/batch", json={"project_id": project_id})
    finally:
        lock.release()

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is False
    assert payload["error"] == "collection_already_running"
    assert "已有采集任务" in payload["message"]


def test_collect_detail_rejects_concurrent_project_run():
    from rpa_mcp_sync.web import _detail_collect_lock

    project_id = "pytest_detail_collect_lock"
    lock = _detail_collect_lock(project_id)
    assert lock.acquire(blocking=False)
    try:
        response = client.post(
            "/api/pgy/collect/detail",
            json={"project_id": project_id, "creator_ids": ["creator-001"], "manual": True},
        )
    finally:
        lock.release()

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is False
    assert payload["error"] == "detail_collection_already_running"
    assert "已有达人详情完善任务" in payload["message"]


def test_collect_detail_async_reports_progress_and_result(monkeypatch):
    import time

    project_id = "pytest_detail_collect_async"
    creator_ids = ["async-detail-001", "async-detail-002", "async-detail-003"]
    for creator_id in creator_ids:
        client.post(
            f"/api/projects/{project_id}/creators",
            json={
                "data": {
                    "creator_id": creator_id,
                    "nickname": creator_id,
                    "pgy_url": f"https://pgy.xiaohongshu.com/solar/pre-trade/blogger-detail/{creator_id}",
                }
            },
        )

    def fake_collect_details_for_targets(targets, limit=20, progress_callback=None):
        completed = []
        for index, creator in enumerate(targets, start=1):
            time.sleep(0.02)
            completed.append({"creator_id": creator["creator_id"], "nickname": creator["nickname"]})
            if progress_callback:
                progress_callback({
                    "stage": "collecting",
                    "total_count": len(targets),
                    "completed_count": index,
                    "failed_count": 0,
                    "current_creator_id": creator["creator_id"],
                    "current_nickname": creator["nickname"],
                })
        return {"ok": True, "creators": completed, "failed": [], "finished_at": "2026-05-25 17:00:00"}

    monkeypatch.setattr("rpa_mcp_sync.web.collect_details_for_targets", fake_collect_details_for_targets)
    monkeypatch.setattr("rpa_mcp_sync.web.score_project", lambda project_id, **kwargs: {"scored": len(kwargs.get("creator_ids") or [])})

    response = client.post(
        "/api/pgy/collect/detail",
        json={"project_id": project_id, "creator_ids": creator_ids, "manual": True, "async_collect": True},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["accepted"] is True
    assert payload["task"]["total_count"] == 3
    task_id = payload["task"]["task_id"]

    task = {}
    deadline = time.time() + 3
    while time.time() < deadline:
        task = client.get(f"/api/pgy/collect/detail/tasks/{task_id}").json()["task"]
        if task["status"] != "running":
            break
        time.sleep(0.03)

    assert task["status"] == "success"
    assert task["completed_count"] == 3
    assert task["total_count"] == 3
    assert "3/3" in task["progress_text"]
    assert len(task["result"]["updated"]) == 3
    client.delete(f"/api/projects/{project_id}")


def test_collect_batch_async_returns_running_batch_and_finishes(monkeypatch):
    import time

    project_id = "pytest_collect_async"
    client.post(f"/api/projects/{project_id}", json={"project_name": project_id, "brief": "异步采集测试"})

    def fake_collect_visible_list(**kwargs):
        time.sleep(0.05)
        return {
            "ok": True,
            "creators": [{"creator_id": "async-creator", "source": "pgy", "nickname": "异步达人"}],
            "collection_plan": kwargs["screening_plan"].get("pgyCollectionPlan") or {},
        }

    monkeypatch.setattr("rpa_mcp_sync.web.collect_visible_list", fake_collect_visible_list)
    monkeypatch.setattr("rpa_mcp_sync.web.score_project", lambda project_id, **kwargs: {"scored": len(kwargs.get("creator_ids") or [])})

    response = client.post("/api/pgy/collect/batch", json={"project_id": project_id, "async_collect": True, "preflight": False})
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["accepted"] is True
    assert payload["batch"]["status"] == "running"

    batch_id = payload["batch"]["batch_id"]
    deadline = time.time() + 3
    batch = {}
    while time.time() < deadline:
        batch = client.get(f"/api/pgy/collect/batches/{batch_id}", params={"project_id": project_id}).json()["batch"]
        if batch["status"] != "running":
            break
        time.sleep(0.05)

    assert batch["status"] == "success"
    assert batch["success_count"] == 1


def test_creator_quality_summary_counts_missing_links_and_fallback_rows():
    project_id = "pytest_quality_summary"
    client.post(f"/api/projects/{project_id}", json={"project_name": project_id, "brief": "质量摘要测试"})
    client.post(
        f"/api/projects/{project_id}/creators",
        json={
            "data": {
                "creator_id": "pgy-api-quality-001",
                "source": "pgy",
                "nickname": "有链接达人",
                "pgy_url": "https://pgy.xiaohongshu.com/solar/pre-trade/blogger-detail/quality-001",
                "xiaohongshu_id": "xhs-quality-001",
                "pgy_blogger_id": "quality-001",
            }
        },
    )
    client.post(
        f"/api/projects/{project_id}/creators",
        json={
            "data": {
                "creator_id": "pgy:list:无链接达人:北京",
                "source": "pgy",
                "nickname": "无链接达人",
            }
        },
    )

    response = client.get(f"/api/projects/{project_id}/creators/quality-summary")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 2
    assert payload["pgy_url"]["present"] == 1
    assert payload["pgy_url"]["missing"] == 1
    assert payload["xiaohongshu_id"]["missing"] == 1
    assert payload["pgy_blogger_id"]["missing"] == 1
    assert payload["fallback_rows"]["total"] == 1
    assert payload["fallback_rows"]["missing_pgy_url"] == 1
    assert payload["samples"]["missing_pgy_url"][0]["creator_id"] == "pgy:list:无链接达人:北京"

    client.delete(f"/api/projects/{project_id}")


def test_collection_plan_uses_first_scheme_when_default_filters_missing():
    plan = build_collection_plan(
        "教育达人",
        {
            "hardFilters": [],
            "pgyCollectionPlan": {
                "schemes": [
                    {
                        "scheme_id": "education_core",
                        "name": "教育核心池",
                        "filters": [{"field": "博主类目", "value": "教育", "reason": "教育场景"}],
                    }
                ],
                "display_metrics": ["全部非直播指标"],
            },
        },
    )

    assert plan["filters"][0]["field"] == "博主类目"
    assert plan["filters"][0]["value"] == "教育"
    assert plan["schemes"][0]["scheme_id"] == "education_core"


def test_collection_plan_normalizes_saved_marketing_goal_parent_value():
    plan = build_collection_plan(
        "种草达人",
        {"pgyCollectionPlan": {"filters": [{"field": "营销目标", "value": "种草"}]}},
    )

    assert plan["filters"][0]["value"] == "互动表现"
    assert plan["filters"][0]["goal"] == "种草"
    assert plan["filters"][0]["control_type"] == "marketing_goal_metric"


def test_relaxed_collection_plan_keeps_broad_filters_when_empty():
    from rpa_mcp_sync.pgy_browser import _relaxed_collection_plan

    plan = {
        "filters": [
            {"field": "营销目标", "value": "互动表现", "goal": "种草", "control_type": "marketing_goal_metric"},
            {"field": "博主类目", "value": "教育"},
            {"field": "粉丝年龄", "value": "35～44 占比高"},
            {"field": "预估互动单价", "value": "图文笔记互动单价≤20"},
        ],
        "display_metrics": ["全部非直播指标"],
    }

    relaxed = _relaxed_collection_plan(plan, "broad")

    assert relaxed["auto_relaxed"] is True
    assert [item["field"] for item in relaxed["filters"]] == ["营销目标", "博主类目"]
    assert [item["field"] for item in relaxed["relaxation"]["removed_filters"]] == ["粉丝年龄", "预估互动单价"]


def test_creator_pool_api_and_csv_export():
    project_id = "pytest_web_pool"
    create = client.post(
        f"/api/projects/{project_id}/creators",
        json={
            "data": {
                "creator_id": "pytest-web-pool-001",
                "nickname": "接口达人池测试",
                "pgy_url": "https://pgy.xiaohongshu.com/creator/web-pool-001",
                "quote_price": 7600,
                "fans_35_plus_ratio": 0.5,
            }
        },
    )
    assert create.status_code == 200
    review = client.post(
        f"/api/projects/{project_id}/creators/review",
        json={"creator_ids": ["pytest-web-pool-001"], "review_status": "已通过", "reviewer": "pytest"},
    )
    assert review.status_code == 200

    pool = client.get(f"/api/projects/{project_id}/creator-pool")
    assert pool.status_code == 200
    assert pool.json()["groups"]["合格达人待合作"]

    stage = client.patch(
        f"/api/projects/{project_id}/creator-pool/pytest-web-pool-001/stage",
        json={"pool_stage": "已合作跟进中", "operator": "pytest"},
    )
    assert stage.status_code == 200
    metrics = client.post(
        f"/api/projects/{project_id}/creator-pool/pytest-web-pool-001/update-metrics",
        json={"data": {"followers_count": 66000}, "operator": "pytest"},
    )
    assert metrics.status_code == 200
    export = client.get(f"/api/projects/{project_id}/exports/creator-pool.csv")
    assert export.status_code == 200
    assert "接口达人池测试" in export.text


def test_creator_create_and_update_do_not_score_by_default(monkeypatch):
    project_id = "pytest_web_no_implicit_score"
    creator_id = "pytest-web-no-implicit-score-001"

    def fail_score_creator(*args, **kwargs):
        raise AssertionError("creator create/update should not score unless explicitly requested")

    monkeypatch.setattr("rpa_mcp_sync.creator_store.score_creator", fail_score_creator)

    create = client.post(
        f"/api/projects/{project_id}/creators",
        json={
            "data": {
                "creator_id": creator_id,
                "nickname": "默认不评分达人",
                "pgy_url": "https://pgy.xiaohongshu.com/creator/no-implicit-score-001",
                "quote_price": 7600,
            }
        },
    )
    assert create.status_code == 200

    update = client.patch(
        f"/api/projects/{project_id}/creators/{creator_id}",
        json={"data": {"nickname": "更新也不默认评分", "quote_price": 8200}},
    )
    assert update.status_code == 200
    client.delete(f"/api/projects/{project_id}")


def test_score_api_manual_source_uses_rule_scoring(monkeypatch):
    project_id = "pytest_web_manual_score_rule"
    creator_id = "pytest-web-manual-rule-001"
    client.post(
        f"/api/projects/{project_id}/creators",
        json={
            "data": {
                "creator_id": creator_id,
                "nickname": "手动规则评分达人",
                "pgy_url": "https://pgy.xiaohongshu.com/creator/manual-rule",
                "followers_count": 3000,
                "quote_price": 500,
                "creator_type": "教育",
            }
        },
    )

    def fail_llm(*args, **kwargs):
        raise AssertionError("source=manual 不应调用大模型")

    monkeypatch.setattr("rpa_mcp_sync.creator_store.score_values_batch_with_llm", fail_llm)
    response = client.post(
        f"/api/projects/{project_id}/creators/score",
        json={"creator_ids": [creator_id], "source": "manual"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "rule"
    assert payload["sources"]["llm"] == 0
    client.delete(f"/api/projects/{project_id}")


def test_score_api_manual_ai_requires_explicit_confirmation(monkeypatch):
    project_id = "pytest_web_manual_ai_confirm_required"
    creator_id = "pytest-web-manual-ai-confirm-001"
    client.post(
        f"/api/projects/{project_id}/creators",
        json={
            "data": {
                "creator_id": creator_id,
                "nickname": "AI确认拦截达人",
                "pgy_url": "https://pgy.xiaohongshu.com/creator/manual-ai-confirm",
                "followers_count": 3000,
                "quote_price": 500,
                "creator_type": "教育",
            }
        },
    )

    def fail_llm(*args, **kwargs):
        raise AssertionError("未确认 AI 评分不应调用大模型")

    monkeypatch.setattr("rpa_mcp_sync.creator_store.score_values_batch_with_llm", fail_llm)
    response = client.post(
        f"/api/projects/{project_id}/creators/score",
        json={"creator_ids": [creator_id], "source": "manual_ai"},
    )

    assert response.status_code == 400
    assert response.json()["detail"]["error"] == "llm_score_confirmation_required"
    client.delete(f"/api/projects/{project_id}")


def test_creator_pool_api_keeps_unreviewed_scored_creators_in_screening(monkeypatch):
    project_id = "pytest_web_screening_gate"
    create = client.post(
        f"/api/projects/{project_id}/creators",
        json={
            "data": {
                "creator_id": "pytest-web-screening-001",
                "nickname": "接口筛选候选",
                "pgy_url": "https://pgy.xiaohongshu.com/creator/web-screening-001",
                "quote_price": 7600,
                "fans_35_plus_ratio": 0.5,
            }
        },
    )
    assert create.status_code == 200

    def fake_score_values_batch_with_llm(project_id_arg, chunk):
        from rpa_mcp_sync.creator_store import score_values

        return {
            str(creator["creator_id"]): {
                **score_values(creator, project_id=project_id_arg),
                "score_reason": "【大模型分析】接口筛选候选评分完成",
            }
            for creator in chunk
        }

    monkeypatch.setattr(
        "rpa_mcp_sync.web.read_ai_config",
        lambda: {"api_key_configured": True, "api_key_env": "OPENAI_API_KEY"},
    )
    monkeypatch.setattr("rpa_mcp_sync.creator_store.score_values_batch_with_llm", fake_score_values_batch_with_llm)
    score = client.post(
        f"/api/projects/{project_id}/creators/score",
        json={"creator_ids": ["pytest-web-screening-001"], "source": "manual_ai", "confirm_large_llm_score": True},
    )
    assert score.status_code == 200

    pool = client.get(f"/api/projects/{project_id}/creator-pool")
    assert pool.status_code == 200
    payload = pool.json()
    assert payload["groups"]["筛选工作台"]
    assert payload["groups"]["筛选工作台"][0]["creator_id"] == "pytest-web-screening-001"
    assert not payload["groups"]["待建联达人"]
    client.delete(f"/api/projects/{project_id}")


def test_score_creators_api_returns_readable_llm_failure(monkeypatch):
    project_id = "pytest_web_llm_score_failure"
    create = client.post(
        f"/api/projects/{project_id}/creators",
        json={
            "data": {
                "creator_id": "pytest-web-llm-failure-001",
                "nickname": "接口模型失败达人",
                "pgy_url": "https://pgy.xiaohongshu.com/creator/web-llm-failure-001",
                "quote_price": 7600,
            }
        },
    )
    assert create.status_code == 200

    monkeypatch.setattr(
        "rpa_mcp_sync.web.read_ai_config",
        lambda: {"api_key_configured": True, "api_key_env": "OPENAI_API_KEY"},
    )

    def failing_score_values_batch_with_llm(project_id_arg, chunk):
        raise RuntimeError("bad llm config")

    monkeypatch.setattr("rpa_mcp_sync.creator_store.score_values_batch_with_llm", failing_score_values_batch_with_llm)
    score = client.post(
        f"/api/projects/{project_id}/creators/score",
        json={"creator_ids": ["pytest-web-llm-failure-001"], "source": "manual_ai", "confirm_large_llm_score": True},
    )

    assert score.status_code == 502
    payload = score.json()["detail"]
    assert payload["ok"] is False
    assert payload["error"] == "llm_score_failed"
    assert "大模型评分失败" in payload["message"]
    assert "bad llm config" in payload["message"]
    assert payload["llm_errors"]
    client.delete(f"/api/projects/{project_id}")


def test_score_creators_api_rule_source_skips_llm_config(monkeypatch):
    project_id = "pytest_web_rule_score"
    create = client.post(
        f"/api/projects/{project_id}/creators",
        json={
            "data": {
                "creator_id": "pytest-web-rule-score-001",
                "nickname": "接口规则评分达人",
                "pgy_url": "https://pgy.xiaohongshu.com/creator/web-rule-score-001",
                "quote_price": 7600,
                "daily_read_median": 5000,
                "daily_interaction_median": 300,
            }
        },
    )
    assert create.status_code == 200
    monkeypatch.setattr(
        "rpa_mcp_sync.web.read_ai_config",
        lambda: {"api_key_configured": False, "api_key_env": "OPENAI_API_KEY"},
    )

    score = client.post(
        f"/api/projects/{project_id}/creators/score",
        json={"creator_ids": ["pytest-web-rule-score-001"], "source": "rule"},
    )

    assert score.status_code == 200
    payload = score.json()
    assert payload["source"] == "rule"
    assert payload["sources"]["rule"] == 1
    assert "defects" in payload
    client.delete(f"/api/projects/{project_id}")


def test_score_creators_api_reports_missing_llm_config(monkeypatch):
    project_id = "pytest_web_llm_config_missing"
    create = client.post(
        f"/api/projects/{project_id}/creators",
        json={
            "data": {
                "creator_id": "pytest-web-llm-config-missing-001",
                "nickname": "接口模型未配置达人",
                "pgy_url": "https://pgy.xiaohongshu.com/creator/web-llm-config-missing-001",
                "quote_price": 7600,
            }
        },
    )
    assert create.status_code == 200
    monkeypatch.setattr(
        "rpa_mcp_sync.web.read_ai_config",
        lambda: {"api_key_configured": False, "api_key_env": "OPENAI_API_KEY"},
    )

    score = client.post(
        f"/api/projects/{project_id}/creators/score",
        json={"creator_ids": ["pytest-web-llm-config-missing-001"], "source": "manual_ai", "confirm_large_llm_score": True},
    )

    assert score.status_code == 400
    payload = score.json()["detail"]
    assert payload["ok"] is False
    assert payload["error"] == "llm_config_missing"
    assert "未配置 API Key" in payload["message"]
    assert "高级配置" in payload["suggestion"]
    client.delete(f"/api/projects/{project_id}")


def test_pgy_invite_api_marks_creators_invited():
    project_id = "pytest_pgy_invite"
    create = client.post(
        f"/api/projects/{project_id}/creators",
        json={
            "data": {
                "creator_id": "pytest-pgy-invite-001",
                "nickname": "蒲公英邀约测试",
                "pgy_url": "https://pgy.xiaohongshu.com/creator/invite-001",
                "quote_price": 9000,
            }
        },
    )
    assert create.status_code == 200

    invite = client.post(
        f"/api/projects/{project_id}/creators/invite",
        json={
            "creator_ids": ["pytest-pgy-invite-001"],
            "brand_name": "有道",
            "cooperation_type": "图文笔记一口价",
            "product_name": "答疑笔",
            "expected_start_date": "2026-05-20",
            "expected_end_date": "2026-05-30",
            "content_intro": "围绕家庭学习场景介绍产品。",
            "contact_type": "微信",
            "contact_info": "youdao-test",
            "source": "pytest",
            "operator": "pytest",
            "channel": "pgy",
        },
    )

    assert invite.status_code == 200
    payload = invite.json()
    assert payload["channel"] == "pgy"
    assert payload["invited_count"] == 1
    assert payload["creators"][0]["status"] == "已邀约"
    pool = client.get(f"/api/projects/{project_id}/creator-pool")
    assert pool.status_code == 200
    assert pool.json()["groups"]["待建联达人"][0]["review_status"] == "已邀约"
    client.delete(f"/api/projects/{project_id}")


def test_xhs_note_parse_stub_accepts_note_link():
    response = client.post(
        "/api/xhs/notes/parse",
        json={
            "url": "https://www.xiaohongshu.com/explore/abc123",
            "note": {
                "title": "每天8小时睡眠，你的枕头挑对了吗",
                "cover_url": "https://example.com/cover.jpg",
                "cover_text": "睡眠枕头测评",
                "published_at": "2026-05-11",
                "comments": ["这个枕头真的舒服", {"content": "适合租房卧室"}],
                "metrics": {"read_count": 8402, "like_count": 580},
            },
            "creator": {"id": "creator-001", "name": "奥特迪迪"},
            "project": {"id": "project-001", "name": "家居家装"},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["status"] == "stub"
    assert payload["note_id"] == "abc123"
    assert payload["note"]["title"] == "每天8小时睡眠，你的枕头挑对了吗"
    assert payload["note"]["cover_text"] == "睡眠枕头测评"
    assert payload["note"]["comments"] == ["这个枕头真的舒服", "适合租房卧室"]


def test_xhs_note_parse_stub_rejects_non_xhs_link():
    response = client.post("/api/xhs/notes/parse", json={"url": "https://example.com/post/1"})
    assert response.status_code == 400
