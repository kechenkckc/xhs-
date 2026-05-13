import json

from fastapi.testclient import TestClient

from rpa_mcp_sync.creator_store import connect
from rpa_mcp_sync.config_store import AI_PROVIDER_PATH, feishu_connection_path
from rpa_mcp_sync.pgy_browser import build_collection_plan
from rpa_mcp_sync.web import app, _filter_creators_by_hard_filters, _scheme_plan


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


def test_pgy_collect_batch_stops_after_first_collectable_scheme(monkeypatch):
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
                "actual_recommend_count": 120,
                "actual_count_text": "推荐 120 位博主",
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
    assert [item["scheme_id"] for item in payload["scheme_results"]] == ["education_core"]
    assert calls == [
        {"scheme": "education_core", "reset": True},
        {"scheme": "education_core", "reset": False},
    ]
    assert payload["batch"]["total_count"] == 2
    assert payload["batch"]["success_count"] == 2
    assert {creator["creator_id"] for creator in payload["creators"]} == {"education-creator", "shared-creator"}
    assert payload["export_result"]["status"] == "multi_scheme"
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
    counts = [5000, 800]
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
        {"preflight": True, "reset": False, "fields": ["博主类目", "粉丝量", "粉丝年龄", "合作报价", "预估阅读单价"]},
        {"preflight": False, "reset": False, "fields": ["博主类目", "粉丝量", "粉丝年龄", "合作报价", "预估阅读单价"]},
    ]
    preflight = payload["scheme_results"][0]["preflight"]
    assert [step["actual_recommend_count"] for step in preflight["steps"]] == [5000, 800]
    assert [item["field"] for item in preflight["active_additional_filters"]] == ["预估阅读单价"]
    client.delete(f"/api/projects/{project_id}")


def test_scheme_plan_uses_required_filters_and_manual_only_user_filters():
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
    assert [item["field"] for item in pgy_plan["filters"]] == ["博主类目", "粉丝量", "粉丝年龄", "合作报价", "职业身份"]


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

    creators = client.get(f"/api/projects/{project_id}/creators").json()["creators"]
    assert {creator["nickname"] for creator in creators} == {"精准入库达人", "超预算达人", "粉丝年龄不符达人"}
    flagged = next(creator for creator in creators if creator["nickname"] == "超预算达人")
    assert "collection_hard_filter_issues" in json.loads(flagged["raw_payload"])
    client.delete(f"/api/projects/{project_id}")


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
    assert collection_plan["filters"][2]["min"] == 1000


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


def test_pgy_row_parser_ignores_empty_state_as_creator():
    from rpa_mcp_sync.pgy_browser import _parse_row_text

    assert _parse_row_text("暂无数据\n暂未发现相关博主\n放宽条件才能找到更多的博主", "https://pgy.xiaohongshu.com/solar/pre-trade/note/kol") is None


def test_collection_only_marketing_goal_does_not_block_creator_gate():
    creators = [{"creator_id": "c1", "nickname": "教育学硕士妈妈", "source": "pgy", "raw_payload": {"collection_page": 1}}]
    hard_filters = [{"field": "营销目标", "condition": "包含", "value": "种草", "required": True, "pgyField": "营销目标"}]

    accepted, rejected = _filter_creators_by_hard_filters("pytest_collection_only_goal", creators, hard_filters)

    assert accepted == creators
    assert rejected == []


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


def test_llm_test_reuses_saved_inline_key(monkeypatch):
    original = AI_PROVIDER_PATH.read_text(encoding="utf-8") if AI_PROVIDER_PATH.exists() else None

    class Response:
        status_code = 200

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
    assert payload["screeningPlan"]["hardFilters"][1]["feishuField"] == "35岁以上粉丝占比"
    assert payload["screeningPlan"]["scoringCriteria"]["purpose"]
    assert len(payload["screeningPlan"]["pgyCollectionPlan"]["schemes"]) >= 3
    first_scheme = payload["screeningPlan"]["pgyCollectionPlan"]["schemes"][0]
    assert first_scheme["target_count_range"]
    assert first_scheme["narrow_if_too_many"]
    project = client.get(f"/api/projects/{project_id}").json()["project"]
    assert project["screening_plan"]
    assert "35岁以上粉丝占比" in project["screening_plan"]
    assert "scoringCriteria" in project["screening_plan"]
    with connect() as conn:
        conn.execute("DELETE FROM projects WHERE project_id=?", (project_id,))
    if original is None:
        if AI_PROVIDER_PATH.exists():
            AI_PROVIDER_PATH.unlink()
    else:
        AI_PROVIDER_PATH.write_text(original, encoding="utf-8")


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


def test_relaxed_collection_plan_keeps_broad_filters_when_empty():
    from rpa_mcp_sync.pgy_browser import _relaxed_collection_plan

    plan = {
        "filters": [
            {"field": "营销目标", "value": "种草"},
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
