from __future__ import annotations

import copy
import json
import re
from datetime import datetime
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .config_store import (
    ROOT,
    ensure_dirs,
    feishu_connection_path,
    public_feishu_config,
    read_json,
    write_json,
)
from .creator_store import (
    archive_project,
    connect,
    change_creator_stage,
    create_asset,
    create_handoff,
    create_task,
    create_tasks_from_handoff,
    create_batch,
    creator_pool,
    creator_pool_detail,
    export_creator_pool_csv,
    finish_batch,
    get_project,
    delete_project,
    import_csv,
    get_project_writeback_settings,
    init_db,
    list_assets,
    list_batches,
    list_creators,
    list_feishu_sync_state,
    list_handoffs,
    list_logs,
    list_projects,
    list_tasks,
    list_scheme_count_memory,
    log,
    management_overview,
    merge_feishu_rows,
    normalize_creator,
    parse_number,
    ratio,
    _split_rule_values,
    _threshold_from_text,
    _expand_rule_values,
    record_scheme_count_memory,
    record_feishu_sync_state,
    review_creator,
    save_project,
    save_project_writeback_settings,
    scheme_count_memory,
    score_project,
    project_metrics,
    quality_feishu_rows,
    standard_feishu_rows,
    update_creator_metrics,
    update_handoff_status,
    update_task,
    update_creator,
    update_scheme_count_memory,
    upsert_creator,
)
from .feishu import FeishuClient, FeishuError, choose_table, column_name, parse_feishu_url
from .feishu_field_agent import analyze_field_mapping, apply_field_mapping, default_source_rows
from .llm_config import chat_json, read_ai_config, test_ai_config, write_ai_config
from .pgy_browser import PGY_FILTER_CATALOG, browser_status, build_collection_plan, collect_details_for_targets, collect_visible_list, parse_export_file, start_browser


class FeishuConnectionPayload(BaseModel):
    project_id: str = Field(default="youdao_001")
    feishu_url: str
    app_id: str
    app_secret: str | None = None


class LlmConfigPayload(BaseModel):
    protocol: str = "openai-compatible"
    base_url: str = "https://api.openai.com/v1"
    model: str = "gpt-4.1-mini"
    api_key: str | None = None
    api_key_env: str | None = None
    temperature: float = 0.2
    max_tokens: int | None = None
    timeout_seconds: int | None = None
    keep_existing_api_key: bool = True


class FeishuRecordsPayload(BaseModel):
    project_id: str = "youdao_001"
    table_id: str | None = None
    rows: list[dict[str, Any]] = Field(default_factory=list)
    statuses: list[str] = Field(default_factory=lambda: ["已通过", "备选"])
    quality_only: bool = False
    limit: int | None = None
    creator_ids: list[str] = Field(default_factory=list)


class WritebackSettingsPayload(BaseModel):
    project_id: str = "youdao_001"
    auto_writeback_enabled: bool = False


class FeishuPullPayload(BaseModel):
    project_id: str = "youdao_001"
    table_id: str | None = None
    rows: list[dict[str, Any]] = Field(default_factory=list)


class ProjectPayload(BaseModel):
    project_name: str | None = None
    target_qualified_creator_count: int | None = None
    period_start: str | None = None
    period_end: str | None = None
    brief: str | None = None
    screening_plan: dict[str, Any] | None = None


class CreatorPayload(BaseModel):
    data: dict[str, Any] = Field(default_factory=dict)


class CreatorImportPayload(BaseModel):
    csv_path: str | None = None
    rows: list[dict[str, Any]] = Field(default_factory=list)


class ReviewPayload(BaseModel):
    creator_id: str | None = None
    creator_ids: list[str] = Field(default_factory=list)
    review_status: str
    review_reason: str = ""
    reviewer: str = "用户"


class PgyInvitePayload(BaseModel):
    creator_id: str | None = None
    creator_ids: list[str] = Field(default_factory=list)
    brand_name: str = ""
    cooperation_type: str = "图文笔记一口价"
    product_name: str = ""
    expected_start_date: str = ""
    expected_end_date: str = ""
    content_intro: str = ""
    contact_type: str = "微信"
    contact_info: str = ""
    source: str = "批量邀约"
    operator: str = "当前用户"
    channel: str = "pgy"


class StagePayload(BaseModel):
    pool_stage: str
    reason: str = ""
    operator: str = "用户"


class MetricsUpdatePayload(BaseModel):
    data: dict[str, Any] = Field(default_factory=dict)
    operator: str = "用户"
    sync_feishu: bool = False


class HandoffPayload(BaseModel):
    from_role: str = "planner"
    to_role: str = "executor"
    title: str
    summary: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)
    status: str = "pending"
    created_by: str = "用户"


class HandoffActionPayload(BaseModel):
    operator: str = "用户"
    return_reason: str = ""


class ProjectTaskPayload(BaseModel):
    source_handoff_id: str | None = None
    title: str
    description: str = ""
    role: str = "executor"
    owner: str = ""
    status: str = "todo"
    priority: str = "medium"
    due_at: str = ""
    blocked_reason: str = ""
    deliverables: list[dict[str, Any]] = Field(default_factory=list)
    operator: str = "用户"


class ProjectAssetPayload(BaseModel):
    asset_type: str
    title: str
    payload: dict[str, Any] = Field(default_factory=dict)
    created_by: str = "用户"


class AiAssistPayload(BaseModel):
    input_text: str = ""
    mode: str = "draft"
    target_role: str = "executor"
    payload: dict[str, Any] = Field(default_factory=dict)
    persist: bool = False
    operator: str = "AI"


class BatchCollectPayload(BaseModel):
    project_id: str = "youdao_001"
    source_url: str = "https://pgy.xiaohongshu.com/solar/pre-trade/note/kol"
    screening_plan: dict[str, Any] = Field(default_factory=dict)
    apply_filters: bool = True
    include_details: bool = False
    collect_profile_urls: bool = True
    export_metrics: bool = True
    limit: int = 20
    scheme_ids: list[str] = Field(default_factory=list)
    multi_scheme: bool = True
    preflight: bool = True
    collect_out_of_range: bool = False


class DetailCollectPayload(BaseModel):
    project_id: str = "youdao_001"
    creator_ids: list[str] = Field(default_factory=list)
    segment: str | None = None
    manual: bool = False
    limit: int = 20


class ScreeningStandardPayload(BaseModel):
    project_id: str = "youdao_001"
    brief: str
    project: dict[str, Any] = Field(default_factory=dict)
    feishu_fields: list[dict[str, Any]] = Field(default_factory=list)


app = FastAPI(title="第三事业部达人筛选工作台")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

ensure_dirs()
init_db()


@app.get("/")
def index() -> RedirectResponse:
    return RedirectResponse(url="/workbench", status_code=307)


@app.get("/screening-workbench.css")
def screening_css() -> FileResponse:
    return FileResponse(ROOT / "screening-workbench.css")


@app.get("/screening-workbench.js")
def screening_js() -> FileResponse:
    return FileResponse(ROOT / "screening-workbench.js")


if (ROOT / "ad-workbench" / "dist").exists():
    if (ROOT / "ad-workbench" / "dist" / "assets").exists():
        app.mount("/assets", StaticFiles(directory=ROOT / "ad-workbench" / "dist" / "assets"), name="ad-assets")
    app.mount("/ad-workbench", StaticFiles(directory=ROOT / "ad-workbench" / "dist", html=True), name="ad-workbench")


@app.get("/workbench/{path:path}")
def ad_workbench_spa(path: str) -> FileResponse:
    return FileResponse(ROOT / "ad-workbench" / "dist" / "index.html")


@app.get("/workbench")
def ad_workbench_index() -> FileResponse:
    return FileResponse(ROOT / "ad-workbench" / "dist" / "index.html")


@app.get("/api/overview")
def overview(
    include_test_projects: bool = Query(default=False),
    include_archived: bool = Query(default=False),
) -> dict[str, Any]:
    return {"projects": list_projects(include_test_projects=include_test_projects, include_archived=include_archived)}


@app.get("/api/runtime/version")
def runtime_version() -> dict[str, Any]:
    return {"version": "pgy-python-playwright-20260508", "pgy_collector": "python-playwright"}


@app.get("/api/projects")
def api_projects(
    include_test_projects: bool = Query(default=False),
    include_archived: bool = Query(default=False),
) -> dict[str, Any]:
    return {"projects": list_projects(include_test_projects=include_test_projects, include_archived=include_archived)}


@app.get("/api/projects/{project_id}")
def api_project(project_id: str) -> dict[str, Any]:
    project = get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail={"message": "项目不存在"})
    return {"project": project}


@app.post("/api/projects/{project_id}")
def api_save_project(project_id: str, payload: ProjectPayload) -> dict[str, Any]:
    data = payload.model_dump(exclude_none=True)
    if isinstance(data.get("screening_plan"), dict):
        data["screening_plan"] = _sync_screening_plan_criteria(data["screening_plan"])
    return {"project": save_project(project_id, data)}


@app.post("/api/projects/{project_id}/archive")
def api_archive_project(project_id: str) -> dict[str, Any]:
    try:
        return {"project": archive_project(project_id, archived=True)}
    except KeyError:
        raise HTTPException(status_code=404, detail={"message": "项目不存在"})


@app.post("/api/projects/{project_id}/restore")
def api_restore_project(project_id: str) -> dict[str, Any]:
    try:
        return {"project": archive_project(project_id, archived=False)}
    except KeyError:
        raise HTTPException(status_code=404, detail={"message": "项目不存在"})


@app.delete("/api/projects/{project_id}")
def api_delete_project(project_id: str) -> dict[str, Any]:
    try:
        return delete_project(project_id)
    except KeyError:
        raise HTTPException(status_code=404, detail={"message": "项目不存在"})


@app.get("/api/projects/{project_id}/creators")
def api_creators(
    project_id: str,
    status: str | None = Query(default=None),
    q: str | None = Query(default=None),
) -> dict[str, Any]:
    return {"creators": list_creators(project_id, status=status, q=q)}


@app.post("/api/projects/{project_id}/creators")
def api_create_creator(project_id: str, payload: CreatorPayload) -> dict[str, Any]:
    return {"creator": upsert_creator(project_id, payload.data)}


@app.post("/api/projects/{project_id}/creators/import")
def api_import_creators(project_id: str, payload: CreatorImportPayload) -> dict[str, Any]:
    if payload.rows:
        imported = 0
        creator_ids = []
        for row in payload.rows:
            creator = upsert_creator(project_id, row, score=False)
            creator_ids.append(creator["creator_id"])
            imported += 1
        scoring = score_project(project_id, creator_ids=creator_ids, trigger_source="import")
        return {"imported": imported, "scoring": scoring}
    path = ROOT / payload.csv_path if payload.csv_path else None
    result = import_csv(project_id, path)
    return result


@app.patch("/api/projects/{project_id}/creators/{creator_id}")
def api_update_creator(project_id: str, creator_id: str, payload: CreatorPayload) -> dict[str, Any]:
    try:
        return {"creator": update_creator(project_id, creator_id, payload.data)}
    except KeyError:
        raise HTTPException(status_code=404, detail={"message": "达人不存在"})


@app.post("/api/projects/{project_id}/creators/score")
def api_score_creators(project_id: str) -> dict[str, Any]:
    return score_project(project_id, trigger_source="manual")


@app.post("/api/projects/{project_id}/creators/review")
def api_review_creators(project_id: str, payload: ReviewPayload) -> dict[str, Any]:
    ids = payload.creator_ids or ([payload.creator_id] if payload.creator_id else [])
    if not ids:
        raise HTTPException(status_code=400, detail={"message": "请选择要审核的达人"})
    creators = []
    try:
        for creator_id in ids:
            creators.append(review_creator(project_id, creator_id, payload.review_status, payload.review_reason, payload.reviewer))
    except ValueError:
        raise HTTPException(status_code=400, detail={"message": "审核状态不合法"})
    return {"creators": creators}


@app.post("/api/projects/{project_id}/creators/invite")
def api_invite_creators(project_id: str, payload: PgyInvitePayload) -> dict[str, Any]:
    ids = payload.creator_ids or ([payload.creator_id] if payload.creator_id else [])
    ids = [str(item) for item in ids if str(item or "").strip()]
    if not ids:
        raise HTTPException(status_code=400, detail={"message": "请选择要邀约的达人"})
    if payload.channel != "pgy":
        raise HTTPException(status_code=400, detail={"message": "当前仅支持蒲公英邀约通道"})
    required = {
        "品牌名": payload.brand_name,
        "产品名称": payload.product_name,
        "期望开始时间": payload.expected_start_date,
        "期望结束时间": payload.expected_end_date,
        "合作内容介绍": payload.content_intro,
        "联系信息": payload.contact_info,
    }
    missing = [label for label, value in required.items() if not str(value or "").strip()]
    if missing:
        raise HTTPException(status_code=400, detail={"message": f"请补充：{'、'.join(missing)}"})
    reason = (
        f"蒲公英邀约｜品牌：{payload.brand_name}｜产品：{payload.product_name}｜"
        f"合作类型：{payload.cooperation_type}｜发布时间：{payload.expected_start_date} 至 {payload.expected_end_date}｜"
        f"联系方式：{payload.contact_type} {payload.contact_info}｜内容：{payload.content_intro}"
    )
    creators = []
    try:
        for creator_id in ids:
            creators.append(review_creator(project_id, creator_id, "已邀约", reason, payload.operator))
    except ValueError:
        raise HTTPException(status_code=400, detail={"message": "邀约状态不合法"})
    return {
        "ok": True,
        "channel": "pgy",
        "invited_count": len(creators),
        "creators": creators,
        "message": f"已通过蒲公英邀约通道记录 {len(creators)} 位达人",
    }


@app.get("/api/projects/{project_id}/creator-pool")
def api_creator_pool(project_id: str) -> dict[str, Any]:
    try:
        return creator_pool(project_id)
    except KeyError:
        raise HTTPException(status_code=404, detail={"message": "项目不存在"})


@app.get("/api/projects/{project_id}/creator-pool/{creator_id}")
def api_creator_pool_detail(project_id: str, creator_id: str) -> dict[str, Any]:
    detail = creator_pool_detail(project_id, creator_id)
    if not detail:
        raise HTTPException(status_code=404, detail={"message": "达人不存在"})
    return detail


@app.patch("/api/projects/{project_id}/creator-pool/{creator_id}/stage")
def api_change_creator_stage(project_id: str, creator_id: str, payload: StagePayload) -> dict[str, Any]:
    try:
        return {"creator": change_creator_stage(project_id, creator_id, payload.pool_stage, payload.reason, payload.operator)}
    except KeyError:
        raise HTTPException(status_code=404, detail={"message": "达人不存在"})
    except ValueError:
        raise HTTPException(status_code=400, detail={"message": "达人池阶段不合法"})


@app.post("/api/projects/{project_id}/creator-pool/{creator_id}/update-metrics")
def api_update_creator_metrics(project_id: str, creator_id: str, payload: MetricsUpdatePayload) -> dict[str, Any]:
    try:
        creator = update_creator_metrics(project_id, creator_id, payload.data, payload.operator)
        return {"creator": creator, "sync_feishu": payload.sync_feishu, "message": "达人指标已更新并写入历史快照"}
    except KeyError:
        raise HTTPException(status_code=404, detail={"message": "达人不存在"})


@app.get("/api/projects/{project_id}/exports/creator-pool.csv")
def api_export_creator_pool_csv(project_id: str) -> FileResponse:
    try:
        path = export_creator_pool_csv(project_id)
    except KeyError:
        raise HTTPException(status_code=404, detail={"message": "项目不存在"})
    return FileResponse(path, media_type="text/csv", filename=path.name)


@app.get("/api/projects/{project_id}/exports/creator-pool.xlsx")
def api_export_creator_pool_xlsx(project_id: str) -> dict[str, Any]:
    return {
        "ok": False,
        "message": "XLSX 导出接口已预留；当前最小闭环先提供 CSV 快照导出",
        "csv_url": f"/api/projects/{project_id}/exports/creator-pool.csv",
    }


@app.get("/api/projects/{project_id}/batches")
def api_batches(project_id: str) -> dict[str, Any]:
    return {"batches": list_batches(project_id)}


@app.get("/api/projects/{project_id}/logs")
def api_logs(project_id: str) -> dict[str, Any]:
    return {"logs": list_logs(project_id)}


@app.get("/api/projects/{project_id}/handoffs")
def api_handoffs(
    project_id: str,
    to_role: str | None = Query(default=None),
    from_role: str | None = Query(default=None),
) -> dict[str, Any]:
    return {"handoffs": list_handoffs(project_id, to_role=to_role, from_role=from_role)}


@app.post("/api/projects/{project_id}/handoffs")
def api_create_handoff(project_id: str, payload: HandoffPayload) -> dict[str, Any]:
    return {"handoff": create_handoff(project_id, payload.model_dump())}


@app.post("/api/projects/{project_id}/handoffs/{handoff_id}/accept")
def api_accept_handoff(project_id: str, handoff_id: str, payload: HandoffActionPayload) -> dict[str, Any]:
    try:
        return {"handoff": update_handoff_status(project_id, handoff_id, "accepted", operator=payload.operator)}
    except KeyError:
        raise HTTPException(status_code=404, detail={"message": "交接单不存在"})


@app.post("/api/projects/{project_id}/handoffs/{handoff_id}/return")
def api_return_handoff(project_id: str, handoff_id: str, payload: HandoffActionPayload) -> dict[str, Any]:
    try:
        return {
            "handoff": update_handoff_status(
                project_id,
                handoff_id,
                "returned",
                operator=payload.operator,
                return_reason=payload.return_reason,
            )
        }
    except KeyError:
        raise HTTPException(status_code=404, detail={"message": "交接单不存在"})


@app.get("/api/projects/{project_id}/tasks")
def api_tasks(
    project_id: str,
    role: str | None = Query(default=None),
    status: str | None = Query(default=None),
) -> dict[str, Any]:
    return {"tasks": list_tasks(project_id, role=role, status=status)}


@app.post("/api/projects/{project_id}/tasks")
def api_create_task(project_id: str, payload: ProjectTaskPayload) -> dict[str, Any]:
    return {"task": create_task(project_id, payload.model_dump())}


@app.patch("/api/projects/{project_id}/tasks/{task_id}")
def api_update_task(project_id: str, task_id: str, payload: ProjectTaskPayload) -> dict[str, Any]:
    try:
        return {"task": update_task(project_id, task_id, payload.model_dump(exclude_none=True))}
    except KeyError:
        raise HTTPException(status_code=404, detail={"message": "任务不存在"})


@app.post("/api/projects/{project_id}/tasks/from-handoff/{handoff_id}")
def api_tasks_from_handoff(project_id: str, handoff_id: str, payload: HandoffActionPayload) -> dict[str, Any]:
    try:
        return {"tasks": create_tasks_from_handoff(project_id, handoff_id, operator=payload.operator)}
    except KeyError:
        raise HTTPException(status_code=404, detail={"message": "交接单不存在"})


@app.get("/api/projects/{project_id}/assets")
def api_assets(project_id: str, asset_type: str | None = Query(default=None)) -> dict[str, Any]:
    return {"assets": list_assets(project_id, asset_type=asset_type)}


@app.post("/api/projects/{project_id}/assets")
def api_create_asset(project_id: str, payload: ProjectAssetPayload) -> dict[str, Any]:
    return {"asset": create_asset(project_id, payload.model_dump())}


@app.get("/api/projects/{project_id}/metrics")
def api_project_metrics(project_id: str) -> dict[str, Any]:
    try:
        return project_metrics(project_id)
    except KeyError:
        raise HTTPException(status_code=404, detail={"message": "项目不存在"})


@app.get("/api/management/overview")
def api_management_overview() -> dict[str, Any]:
    return management_overview()


def _project_ai_context(project_id: str) -> dict[str, Any]:
    project = get_project(project_id) or {}
    return {
        "project": project,
        "handoffs": list_handoffs(project_id),
        "tasks": list_tasks(project_id),
        "assets": list_assets(project_id),
        "logs": list_logs(project_id)[:30],
        "metrics": project_metrics(project_id) if project else {},
    }


def _fallback_brief(project: dict[str, Any], text: str) -> dict[str, Any]:
    source = text or project.get("brief") or ""
    return {
        "background": source[:500],
        "product": "待补充产品/服务信息",
        "selling_points": ["AI 答疑", "错题整理", "家长减负"] if "答疑" in source or "有道" in source else [],
        "audience": "小升初、初中、高中大孩家庭" if any(key in source for key in ["初中", "高中", "大孩", "有道"]) else "待补充目标人群",
        "goals": "提升目标用户对产品使用场景的认知",
        "kpi": "待补充 KPI",
        "period": f"{project.get('period_start') or '待定'} 至 {project.get('period_end') or '待定'}",
        "budget": "待补充预算范围",
        "risk": ["避免绝对化承诺", "避免夸大效果"],
        "creator_requirements": ["人设与项目场景匹配", "数据真实可追溯"],
        "platform_requirements": ["小红书", "抖音"],
        "deliverables": ["图文/视频内容", "数据回流"],
    }


def _fallback_strategy(brief: dict[str, Any]) -> dict[str, Any]:
    audience = brief.get("audience") or "目标用户"
    return {
        "positioning": f"面向{audience}的场景化内容种草",
        "core_message": brief.get("goals") or "把产品价值翻译成可感知的使用场景",
        "content_angles": ["真实使用前后对比", "高频问题解决", "达人经验分享"],
        "platform_plan": [
            {"platform": "小红书", "role": "深度种草与搜索承接"},
            {"platform": "抖音", "role": "场景短视频扩散"},
        ],
        "creator_requirements": {"persona": brief.get("creator_requirements") or []},
        "execution_notes": ["先确认风险词", "交付物按平台拆分"],
        "risk_notes": brief.get("risk") or ["合规审核前置"],
    }


def _fallback_handoff(brief: dict[str, Any], strategy: dict[str, Any], target_role: str) -> dict[str, Any]:
    if target_role == "screening":
        return {
            "title": "达人筛选标准交接",
            "summary": brief.get("audience") or "达人画像和筛选口径待确认",
            "payload": {
                "creator_requirements": strategy.get("creator_requirements") or {},
                "budget": brief.get("budget") or "",
                "platform_requirements": brief.get("platform_requirements") or [],
                "risk": brief.get("risk") or [],
            },
        }
    return {
        "title": "策划方案交接给执行",
        "summary": strategy.get("core_message") or brief.get("goals") or "执行拆解依据",
        "payload": {
            "brief": brief,
            "strategy": strategy,
            "execution_tasks": [
                {"title": "拆解内容交付物和排期", "description": strategy.get("core_message") or "", "priority": "high"},
                {"title": "确认达人内容审核口径", "description": "整理风险词、禁区和验收标准", "priority": "medium"},
                {"title": "建立数据回流与日报节奏", "description": brief.get("kpi") or "", "priority": "medium"},
            ],
        },
    }


def _fallback_tasks(handoff: dict[str, Any]) -> list[dict[str, Any]]:
    payload = handoff.get("payload") or {}
    tasks = payload.get("execution_tasks") or []
    if tasks:
        return tasks
    return [
        {"title": f"拆解{handoff.get('title') or '交接单'}", "description": handoff.get("summary") or "", "priority": "high", "status": "todo"},
        {"title": "确认负责人和截止时间", "description": "补齐 owner、due_at 和验收口径", "priority": "medium", "status": "todo"},
    ]


def _fallback_management_advice(context: dict[str, Any]) -> dict[str, Any]:
    summary = (context.get("metrics") or {}).get("summary") or {}
    risks = (context.get("metrics") or {}).get("risks") or []
    return {
        "executive_summary": f"当前健康度 {summary.get('health_score', 0)}，待接交接 {summary.get('pending_handoffs', 0)}，阻塞任务 {summary.get('blocked_tasks', 0)}。",
        "risk_priorities": [risk.get("title") for risk in risks[:5]],
        "recommended_actions": [
            "优先处理待接收交接，避免岗位等待",
            "将阻塞任务指派负责人并设置 SLA",
            "补齐 Brief、策略和日报类项目资产",
        ],
        "meeting_agenda": ["项目健康度变化", "交接等待与退回原因", "任务阻塞处置", "下一周期资源需求"],
    }


def _ai_json_or_fallback(system_prompt: str, user_payload: dict[str, Any], fallback: dict[str, Any] | list[dict[str, Any]]) -> tuple[Any, str, str]:
    try:
        result = chat_json(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
            ]
        )
        return result, "llm", "大模型生成完成"
    except Exception as error:
        return fallback, "fallback", f"大模型不可用，已使用规则兜底：{error}"


@app.post("/api/projects/{project_id}/ai/brief")
def api_ai_brief(project_id: str, payload: AiAssistPayload) -> dict[str, Any]:
    context = _project_ai_context(project_id)
    fallback = _fallback_brief(context["project"], payload.input_text)
    result, source, message = _ai_json_or_fallback(
        "你是资深品牌策划。请把客户 Brief/聊天/会议内容拆解为结构化 JSON，只输出字段：background, product, selling_points, audience, goals, kpi, period, budget, risk, creator_requirements, platform_requirements, deliverables。",
        {"context": context, "input": payload.input_text, "mode": payload.mode},
        fallback,
    )
    if payload.persist:
        brief_text = json.dumps(result, ensure_ascii=False, indent=2)
        save_project(project_id, {"brief": brief_text})
        create_asset(project_id, {"asset_type": "brief", "title": "AI Brief 拆解", "payload": result, "created_by": payload.operator})
    with connect() as conn:
        log(conn, project_id, "ai", "Brief AI 拆解", context["project"].get("project_name") or project_id, payload.operator, message, "success")
    return {"ok": True, "source": source, "message": message, "brief": result}


@app.post("/api/projects/{project_id}/ai/strategy")
def api_ai_strategy(project_id: str, payload: AiAssistPayload) -> dict[str, Any]:
    context = _project_ai_context(project_id)
    latest_brief = next((asset.get("payload") for asset in context["assets"] if asset.get("asset_type") == "brief"), None)
    brief = payload.payload.get("brief") or latest_brief or _fallback_brief(context["project"], context["project"].get("brief") or payload.input_text)
    fallback = _fallback_strategy(brief)
    result, source, message = _ai_json_or_fallback(
        "你是广告内容策略负责人。基于项目 Brief、资产、日志和指标生成结构化策略 JSON，只输出：positioning, core_message, content_angles, platform_plan, creator_requirements, execution_notes, risk_notes。",
        {"context": context, "brief": brief, "input": payload.input_text},
        fallback,
    )
    if payload.persist:
        create_asset(project_id, {"asset_type": "strategy", "title": "AI 创意策略", "payload": result, "created_by": payload.operator})
    with connect() as conn:
        log(conn, project_id, "ai", "策略 AI 生成", context["project"].get("project_name") or project_id, payload.operator, message, "success")
    return {"ok": True, "source": source, "message": message, "strategy": result}


@app.post("/api/projects/{project_id}/ai/handoff")
def api_ai_handoff(project_id: str, payload: AiAssistPayload) -> dict[str, Any]:
    context = _project_ai_context(project_id)
    latest_brief = next((asset.get("payload") for asset in context["assets"] if asset.get("asset_type") == "brief"), None)
    latest_strategy = next((asset.get("payload") for asset in context["assets"] if asset.get("asset_type") == "strategy"), None)
    brief = payload.payload.get("brief") or latest_brief or _fallback_brief(context["project"], context["project"].get("brief") or payload.input_text)
    strategy = payload.payload.get("strategy") or latest_strategy or _fallback_strategy(brief)
    fallback = _fallback_handoff(brief, strategy, payload.target_role)
    result, source, message = _ai_json_or_fallback(
        "你是项目协作 PM。请基于 Brief 和策略生成岗位交接单 JSON，只输出：title, summary, payload。payload 内按目标岗位提供 execution_tasks 或 creator_requirements。",
        {"context": context, "brief": brief, "strategy": strategy, "target_role": payload.target_role, "input": payload.input_text},
        fallback,
    )
    handoff = None
    if payload.persist:
        handoff = create_handoff(
            project_id,
            {
                "from_role": "planner",
                "to_role": payload.target_role,
                "title": result.get("title") or fallback["title"],
                "summary": result.get("summary") or fallback["summary"],
                "payload": result.get("payload") or fallback["payload"],
                "created_by": payload.operator,
            },
        )
    with connect() as conn:
        log(conn, project_id, "ai", "交接 AI 生成", context["project"].get("project_name") or project_id, payload.operator, message, "success")
    return {"ok": True, "source": source, "message": message, "handoffDraft": result, "handoff": handoff}


@app.post("/api/projects/{project_id}/ai/tasks")
def api_ai_tasks(project_id: str, payload: AiAssistPayload) -> dict[str, Any]:
    context = _project_ai_context(project_id)
    handoff = payload.payload.get("handoff") or next((item for item in context["handoffs"] if item.get("to_role") == "executor"), {})
    fallback = {"tasks": _fallback_tasks(handoff)}
    result, source, message = _ai_json_or_fallback(
        "你是执行项目经理。请把交接单拆解为执行任务 JSON，只输出：tasks。每个任务包含 title, description, owner, status(todo/doing/review/done/blocked), priority(low/medium/high), due_at, deliverables。",
        {"context": context, "handoff": handoff, "input": payload.input_text},
        fallback,
    )
    tasks = result.get("tasks") if isinstance(result, dict) else fallback["tasks"]
    persisted_tasks = []
    if payload.persist:
        for task in tasks:
            persisted_tasks.append(create_task(project_id, {**task, "role": "executor", "operator": payload.operator, "source_handoff_id": handoff.get("handoff_id") or ""}))
    with connect() as conn:
        log(conn, project_id, "ai", "任务 AI 拆解", context["project"].get("project_name") or project_id, payload.operator, message, "success")
    return {"ok": True, "source": source, "message": message, "tasks": tasks, "persistedTasks": persisted_tasks}


@app.post("/api/projects/{project_id}/ai/management-advice")
def api_ai_management_advice(project_id: str, payload: AiAssistPayload) -> dict[str, Any]:
    context = _project_ai_context(project_id)
    fallback = _fallback_management_advice(context)
    result, source, message = _ai_json_or_fallback(
        "你是经营管理顾问。请基于项目指标、任务、交接、资产和日志生成管理层可执行建议 JSON，只输出：executive_summary, risk_priorities, recommended_actions, meeting_agenda。",
        {"context": context, "input": payload.input_text},
        fallback,
    )
    if payload.persist:
        create_asset(project_id, {"asset_type": "management_advice", "title": "AI 管理建议", "payload": result, "created_by": payload.operator})
    with connect() as conn:
        log(conn, project_id, "ai", "管理 AI 解读", context["project"].get("project_name") or project_id, payload.operator, message, "success")
    return {"ok": True, "source": source, "message": message, "advice": result}


def _fallback_screening_standard(payload: ScreeningStandardPayload) -> dict[str, Any]:
    fields = payload.feishu_fields or []
    names = [str(item.get("field_name") or item.get("name") or item.get("title") or "") for item in fields]

    def match(*keywords: str) -> str | None:
        for name in names:
            if any(keyword in name for keyword in keywords):
                return name
        return None

    def mapping(standard: str, *keywords: str, confidence: float = 0.75) -> dict[str, Any]:
        feishu = match(*keywords)
        return {"standard": standard, "feishu": feishu or "未匹配", "confidence": confidence if feishu else 0.25}

    hard_filters = [
        {"field": "达人预算", "condition": "<=", "value": "单个达人 ¥20,000；总预算暂定 ¥120,000", "required": True, "feishuField": match("平台报价", "报价", "合作价格")},
        {"field": "达人粉丝画像", "condition": ">", "value": "35岁以上占比 40%，不符合直接 pass", "required": True, "feishuField": match("34岁以上", "35岁以上")},
        {"field": "蒲公英链接", "condition": "必须存在", "value": "不需要小红书主页链接", "required": True, "feishuField": match("蒲公英", "链接")},
        {"field": "自然流量效率", "condition": "<", "value": "CPC 2；CPE 20，优先 CPE 10 以下", "required": True, "feishuField": match("cpe", "cpc")},
        {"field": "限流风险", "condition": "规避", "value": "疑似限流、流量异常波动达人", "required": True, "feishuField": match("限流风险", "流量稳定")},
        {"field": "孩子阶段", "condition": "匹配", "value": "小升初、初中、高中大孩家庭", "required": False, "feishuField": match("孩子年级", "孩子年龄")},
        {"field": "达人类型配比", "condition": "约等于", "value": "曝光型 50%；教育垂类或卖货型 50%", "required": False, "feishuField": match("账号类型", "达人量级")},
        {"field": "地域优先级", "condition": "优先", "value": "北京、上海 IP 或中产家庭叙事", "required": False, "feishuField": match("IP", "城市", "地域")},
    ]
    weights = {"budget": 15, "fans": 20, "cpe": 20, "engagement": 15, "persona": 20, "content": 10}
    field_mappings = [
        mapping("达人昵称", "达人昵称", "博主名称", confidence=0.95),
        mapping("蒲公英链接", "蒲公英", "链接", confidence=0.95),
        mapping("粉丝数", "粉丝数", "粉丝数量", confidence=0.9),
        mapping("平台报价", "平台报价", "报价", confidence=0.9),
        mapping("合作价格", "合作价格", "服务费", confidence=0.9),
        mapping("CPE/CPC", "cpe", "cpc", confidence=0.85),
        mapping("35岁以上粉丝占比", "34岁以上", "35岁以上", confidence=0.9),
        mapping("孩子年级", "孩子年级", "孩子年龄", confidence=0.85),
        mapping("孩子性别", "孩子性别", confidence=0.8),
        mapping("达人类型", "账号类型", "达人量级", confidence=0.8),
        mapping("推荐理由", "推荐理由", confidence=0.8),
        mapping("品牌反馈", "品牌反馈", confidence=0.75),
        mapping("达人反馈", "达人反馈", confidence=0.75),
    ]
    pgy_plan = build_collection_plan(
        payload.brief,
        {"hardFilters": hard_filters, "scoringWeights": weights},
    )
    pgy_plan["strategy"] = "每套方案由必备筛选条件和附加筛选条件组成。必备筛选固定围绕类目、粉丝量级、粉丝年龄、合作报价；附加筛选按前端顺序逐个叠加，数量达标后不再继续添加。"
    pgy_plan["target_count_range"] = "50-2000"
    pgy_plan["schemes"] = [
        {
            "scheme_id": "education_core",
            "name": "教育大孩核心池",
            "goal": "优先找到教育/升学场景强匹配达人",
            "target_count_range": "50-2000",
            "required_filters": [
                {"field": "博主类目", "value": "教育", "reason": "必备筛选：教育学习场景强相关"},
                {"field": "粉丝量", "value": "1万～10万", "reason": "必备筛选：优先中腰部达人", "control_type": "preset_or_number_range"},
                {"field": "粉丝年龄", "value": "35～44 占比高", "reason": "必备筛选：家长决策人群优先", "control_type": "dropdown"},
                {"field": "合作报价", "value": "图文笔记：0.1万～2万", "reason": "必备筛选：控制单达人预算", "control_type": "subfield_preset_or_number_range", "sub_field": "图文笔记", "max": 20000},
            ],
            "additional_filters": [
                {"field": "预估阅读单价", "value": "图文笔记阅读单价≤2", "reason": "附加筛选：数量过多时控制阅读成本", "control_type": "subfield_preset_or_number_range", "sub_field": "图文笔记阅读单价", "max": 2},
                {"field": "预估互动单价", "value": "图文笔记互动单价≤20", "reason": "附加筛选：数量过多时控制互动成本", "control_type": "subfield_preset_or_number_range", "sub_field": "图文笔记互动单价", "max": 20},
            ],
            "filters": [],
            "expand_if_too_few": ["放宽粉丝年龄", "放宽合作报价上限但保留评分扣分"],
            "narrow_if_too_many": ["启用预估阅读单价≤2", "启用预估互动单价≤20"],
        },
        {
            "scheme_id": "parent_family",
            "name": "亲子家庭场景池",
            "goal": "补充真实家庭陪伴、亲子教育、家长口吻达人",
            "target_count_range": "50-2000",
            "required_filters": [
                {"field": "博主类目", "value": "母婴", "reason": "覆盖家长和亲子账号"},
                {"field": "粉丝量", "value": "1万～10万", "reason": "必备筛选：优先中腰部达人", "control_type": "preset_or_number_range"},
                {"field": "粉丝年龄", "value": "35～44 占比高", "reason": "必备筛选：家长决策人群优先", "control_type": "dropdown"},
                {"field": "合作报价", "value": "图文笔记：0.1万～2万", "reason": "必备筛选：控制单达人预算", "control_type": "subfield_preset_or_number_range", "sub_field": "图文笔记", "max": 20000},
            ],
            "additional_filters": [
                {"field": "阅读中位数", "value": "0.5万～1万", "reason": "附加筛选：数量过多时提高阅读门槛", "control_type": "preset_or_number_range"},
            ],
            "filters": [],
            "expand_if_too_few": ["放宽粉丝量级", "放宽合作报价上限但保留评分扣分"],
            "narrow_if_too_many": ["启用阅读中位数门槛"],
        },
        {
            "scheme_id": "efficiency_value",
            "name": "性价比转化池",
            "goal": "找到预算友好、数据效率较好的测评/卖货型达人",
            "target_count_range": "50-2000",
            "required_filters": [
                {"field": "博主类目", "value": "教育", "reason": "保持教育场景相关"},
                {"field": "粉丝量", "value": "0.5万～10万", "reason": "必备筛选：扩大低预算中腰部达人", "control_type": "preset_or_number_range"},
                {"field": "粉丝年龄", "value": "35～44 占比高", "reason": "必备筛选：家长决策人群优先", "control_type": "dropdown"},
                {"field": "合作报价", "value": "图文笔记：0.1万～1万", "reason": "必备筛选：强调性价比", "control_type": "subfield_preset_or_number_range", "sub_field": "图文笔记", "max": 10000},
            ],
            "additional_filters": [
                {"field": "预估阅读单价", "value": "图文笔记阅读单价≤2", "reason": "控制阅读成本", "control_type": "subfield_preset_or_number_range", "sub_field": "图文笔记阅读单价", "max": 2},
                {"field": "预估互动单价", "value": "图文笔记互动单价≤20", "reason": "控制互动成本", "control_type": "subfield_preset_or_number_range", "sub_field": "图文笔记互动单价", "max": 20},
            ],
            "filters": [],
            "expand_if_too_few": ["放宽合作报价到2万", "放宽粉丝量级"],
            "narrow_if_too_many": ["启用预估阅读单价≤2", "启用预估互动单价≤20"],
        },
    ]
    scoring_criteria = {
        "purpose": "用于采集后对达人做评分、推荐等级、推荐理由和合作方向生成，不等同于蒲公英筛选条件。",
        "hard_rules": hard_filters,
        "dimension_weights": weights,
        "dimensions": [
            {"key": "budget", "name": "预算/报价匹配", "weight": weights["budget"], "positive": ["报价≤单达人预算", "报价与预估流量效率匹配"], "negative": ["报价明显超预算", "报价高但无稳定流量证据"]},
            {"key": "fans", "name": "粉丝画像与规模匹配", "weight": weights["fans"], "positive": ["35岁以上家长人群占比高", "粉丝量与投放目标匹配"], "negative": ["学生粉或低龄粉过高", "粉丝画像缺失"]},
            {"key": "cpe", "name": "成本效率", "weight": weights["cpe"], "positive": ["CPC/CPE 低于阈值", "搜索+推荐占比高"], "negative": ["CPC/CPE 明显偏高", "缺少可验证数据"]},
            {"key": "engagement", "name": "流量质量与互动质量", "weight": weights["engagement"], "positive": ["阅读/互动中位数稳定", "粉丝互动占比健康"], "negative": ["限流、违规、流量异常波动"]},
            {"key": "persona", "name": "人设与 Brief 匹配", "weight": weights["persona"], "positive": ["教育/亲子/大孩/高知家庭/教师身份匹配"], "negative": ["内容人设与学习场景弱相关"]},
            {"key": "content", "name": "内容风格与合作场景", "weight": weights["content"], "positive": ["适合产品测评、学习规划、陪伴答疑场景"], "negative": ["硬广痕迹重或难以自然植入"]},
        ],
        "recommendation_rules": [
            {"level": "强推荐", "condition": "硬性条件通过且综合分≥85，至少一个核心人设或效率优势明显"},
            {"level": "推荐", "condition": "硬性条件通过且综合分≥75，主要指标匹配"},
            {"level": "备选", "condition": "存在一项短板但可通过价格、内容角度或补数据复核"},
            {"level": "不推荐", "condition": "命中硬性淘汰项、流量风险高或项目场景弱相关"},
        ],
        "evidence_fields": ["报价", "粉丝年龄", "粉丝量", "CPC/CPE", "搜索+推荐占比", "阅读/互动中位数", "达人类型", "人设标签", "内容话题", "限流风险"],
        "reason_requirements": ["说明推荐理由", "指出主要风险", "给出适合的合作方向/内容角度/投放角色"],
    }
    return {
        "briefType": "complex",
        "hardFilters": hard_filters,
        "scoringWeights": weights,
        "scoringCriteria": scoring_criteria,
        "fieldMappings": field_mappings,
        "pgyCollectionPlan": pgy_plan,
        "summary": "已按有道答疑笔 Brief 生成筛选口径：预算、35岁以上粉丝占比、蒲公英链接、CPC/CPE 和限流风险作为核心门槛，人设与教育亲子大孩场景作为高权重评分项。",
    }


def _normalize_screening_standard(result: dict[str, Any], payload: ScreeningStandardPayload) -> dict[str, Any]:
    fallback = _fallback_screening_standard(payload)
    plan = result.get("screeningPlan") if isinstance(result.get("screeningPlan"), dict) else result
    scoring_hard_filters = plan.get("scoringHardFilters") or (plan.get("scoringCriteria") or {}).get("hard_rules") or plan.get("hardFilters") or fallback["hardFilters"]
    collection_hard_filters = plan.get("collectionHardFilters") or ((plan.get("pgyCollectionPlan") or {}).get("hard_filters") if isinstance(plan.get("pgyCollectionPlan"), dict) else None) or [
        item for item in fallback["hardFilters"] if item.get("pgyField") or item.get("field") in {"合作报价", "粉丝年龄", "蒲公英链接", "限流风险"}
    ]
    hard_filters = scoring_hard_filters
    weights = plan.get("scoringWeights") or fallback["scoringWeights"]
    total = sum(float(value or 0) for value in weights.values()) or 100
    if abs(total - 100) > 0.01:
        weights = {key: round(float(value or 0) * 100 / total) for key, value in weights.items()}
    pgy_plan = plan.get("pgyCollectionPlan") or fallback.get("pgyCollectionPlan") or build_collection_plan(payload.brief, {"collectionHardFilters": collection_hard_filters, "hardFilters": hard_filters, "scoringWeights": weights})
    if isinstance(pgy_plan, dict):
        pgy_plan = {
            **pgy_plan,
            "hard_filters": collection_hard_filters,
            "filters": pgy_plan.get("filters") or fallback["pgyCollectionPlan"].get("filters") or [],
            "schemes": pgy_plan.get("schemes") or fallback["pgyCollectionPlan"].get("schemes") or [],
            "target_count_range": pgy_plan.get("target_count_range") or "50-2000",
            "strategy": pgy_plan.get("strategy") or fallback["pgyCollectionPlan"].get("strategy"),
        }
        pgy_plan = _normalize_scheme_filter_structure(pgy_plan)
    scoring_criteria = plan.get("scoringCriteria") or plan.get("matchingCriteria") or fallback["scoringCriteria"]
    if isinstance(scoring_criteria, dict):
        scoring_criteria = {
            **scoring_criteria,
            "dimension_weights": scoring_criteria.get("dimension_weights") or weights,
            "hard_rules": scoring_criteria.get("hard_rules") or hard_filters,
        }
    return {
        "briefType": plan.get("briefType") or fallback["briefType"],
        "collectionHardFilters": collection_hard_filters,
        "scoringHardFilters": scoring_hard_filters,
        "hardFilters": hard_filters,
        "scoringWeights": weights,
        "scoringCriteria": scoring_criteria,
        "fieldMappings": plan.get("fieldMappings") or result.get("fieldMappings") or fallback["fieldMappings"],
        "pgyCollectionPlan": pgy_plan,
        "summary": plan.get("summary") or result.get("summary") or fallback["summary"],
    }


def _sync_screening_plan_criteria(plan: dict[str, Any]) -> dict[str, Any]:
    normalized = copy.deepcopy(plan or {})
    def normalize_hard_filters(items: Any) -> list[dict[str, Any]]:
        return [
            {
                "field": str(item.get("field") or item.get("standard") or "").strip(),
                "condition": str(item.get("condition") or "").strip(),
                "value": str(item.get("value") or "").strip(),
                "required": item.get("required") is not False,
                "feishuField": str(item.get("feishuField") or item.get("evidenceField") or "").strip(),
                "pgyField": str(item.get("pgyField") or "").strip(),
                "valueControl": str(item.get("valueControl") or "").strip(),
                "subField": str(item.get("subField") or "").strip(),
            }
            for item in (items or [])
            if isinstance(item, dict) and (item.get("field") or item.get("standard") or item.get("value"))
        ]

    def hard_filters_from_pgy_filters(items: Any) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        seen: set[tuple[str, str, str]] = set()
        option_by_field = {
            "博主类目": {"condition": "包含", "feishuField": "账号类型", "valueControl": "multi"},
            "粉丝年龄": {"condition": "匹配", "feishuField": "粉丝年龄34岁以上占比", "valueControl": "multi"},
            "合作报价": {"condition": "<=", "feishuField": "平台报价", "valueControl": "range"},
            "粉丝量": {"condition": "匹配", "feishuField": "粉丝数", "valueControl": "multi"},
        }
        for item in items or []:
            if not isinstance(item, dict):
                continue
            field = str(item.get("field") or "").strip()
            value = str(item.get("value") or "").strip()
            if not field or not value:
                continue
            option = option_by_field.get(field, {})
            sub_field = str(item.get("sub_field") or item.get("subField") or "").strip()
            key = (field, sub_field, value)
            if key in seen:
                continue
            seen.add(key)
            result.append(
                {
                    "field": field,
                    "condition": option.get("condition") or "匹配",
                    "value": value,
                    "required": field in PGY_BASE_FILTER_FIELDS,
                    "feishuField": option.get("feishuField") or "",
                    "pgyField": field,
                    "valueControl": option.get("valueControl") or "",
                    "subField": sub_field,
                }
            )
        return result

    legacy_hard_filters = normalized.get("hardFilters") or []
    pgy_plan = normalized.get("pgyCollectionPlan") if isinstance(normalized.get("pgyCollectionPlan"), dict) else {}
    pgy_plan = _normalize_scheme_filter_structure(pgy_plan)
    pgy_filter_hard_filters = hard_filters_from_pgy_filters(pgy_plan.get("filters") or [])
    collection_hard_filters = normalize_hard_filters(
        pgy_filter_hard_filters or normalized.get("collectionHardFilters") or pgy_plan.get("hard_filters") or legacy_hard_filters
    )
    scoring_criteria_source = normalized.get("scoringCriteria") if isinstance(normalized.get("scoringCriteria"), dict) else {}
    scoring_hard_filters = normalize_hard_filters(
        normalized.get("scoringHardFilters") or scoring_criteria_source.get("hard_rules")
    )
    if not scoring_hard_filters:
        scoring_hard_filters = normalize_hard_filters(legacy_hard_filters)
    hard_filters = scoring_hard_filters
    normalized["collectionHardFilters"] = collection_hard_filters
    normalized["scoringHardFilters"] = scoring_hard_filters
    normalized["hardFilters"] = hard_filters
    normalized["pgyCollectionPlan"] = {
        **pgy_plan,
        "hard_filters": collection_hard_filters,
    }
    scoring_criteria = normalized.get("scoringCriteria") if isinstance(normalized.get("scoringCriteria"), dict) else {}
    scoring_criteria = {
        **scoring_criteria,
        "hard_rules": scoring_hard_filters,
        "dimension_weights": scoring_criteria.get("dimension_weights") or normalized.get("scoringWeights") or {},
    }
    normalized["scoringCriteria"] = scoring_criteria
    return normalized


def _creator_hard_filter_issues(project_id: str, creator: dict[str, Any], hard_filters: list[dict[str, Any]]) -> list[str]:
    normalized = normalize_creator(creator, project_id)
    source_raw_payload = creator.get("raw_payload") if isinstance(creator.get("raw_payload"), dict) else {}
    issues: list[str] = []
    text_pool = " ".join(
        str(normalized.get(key) or "")
        for key in ["nickname", "creator_type", "persona_tags", "ip_city", "topic_point", "child_age", "child_grade"]
    )
    for item in hard_filters or []:
        if item.get("required") is False:
            continue
        field = str(item.get("field") or item.get("standard") or "")
        condition = str(item.get("condition") or "")
        value = str(item.get("value") or "")
        pgy_field = str(item.get("pgyField") or "")
        if field in {"营销目标"} or pgy_field in {"营销目标"}:
            continue
        text = f"{field} {condition} {value}".lower()
        label = f"{field}{condition}{value}".strip()
        if "蒲公英" in text and not normalized.get("pgy_url"):
            if not (normalized.get("source") == "pgy" and source_raw_payload.get("collection_page")):
                issues.append(f"{label}：缺少蒲公英链接")
        if any(keyword in text for keyword in ["报价", "预算", "合作价格", "平台价格"]):
            threshold = _threshold_from_text(value, "quote", 20000)
            quote = normalized.get("quote_price")
            if quote is not None and quote > threshold:
                issues.append(f"{label}：报价 {quote:g} 超过 {threshold:g}")
        if any(keyword in text for keyword in ["35", "34", "粉丝年龄", "宝妈", "家长"]):
            threshold = _threshold_from_text(value, "fans35", 0.4)
            fans_ratio = normalized.get("fans_35_plus_ratio")
            if fans_ratio is not None and fans_ratio < threshold:
                issues.append(f"{label}：35岁以上粉丝占比 {fans_ratio:.0%} 低于 {threshold:.0%}")
        if "cpc" in text:
            threshold = _threshold_from_text(value, "cpc", 2)
            cpc = normalized.get("natural_cpc")
            if cpc is not None and cpc >= threshold:
                issues.append(f"{label}：CPC {cpc:g} 未低于 {threshold:g}")
        if "cpe" in text:
            threshold = _threshold_from_text(value, "cpe", 20)
            cpe = normalized.get("natural_cpe")
            if cpe is not None and cpe >= threshold:
                issues.append(f"{label}：CPE {cpe:g} 未低于 {threshold:g}")
        if any(keyword in text for keyword in ["搜索+推荐", "搜索推荐"]):
            threshold = _threshold_from_text(value, "search", 0.4)
            search_ratio = normalized.get("search_recommend_ratio")
            if search_ratio is not None and search_ratio <= threshold:
                issues.append(f"{label}：搜索+推荐占比 {search_ratio:.0%} 未超过 {threshold:.0%}")
        if any(keyword in text for keyword in ["孩子年级", "小升初", "初中", "高中", "大孩"]):
            expected_values = _expand_rule_values(_split_rule_values(value) or ["小升初", "初中", "高中", "初一", "初二", "初三", "高一", "高二", "高三", "大孩"])
            if not any(keyword in text_pool for keyword in expected_values):
                issues.append(f"{label}：未识别到小升初/初中/高中大孩场景")
        if any(keyword in text for keyword in ["限流", "违规", "流量稳定", "异常"]):
            risk_text = f"{normalized.get('rate_limit_risk') or ''} {normalized.get('traffic_stability') or ''}"
            if any(keyword in risk_text for keyword in ["高", "限流", "违规", "异常"]):
                issues.append(f"{label}：存在限流/异常流量风险")
        if condition in {"包含", "匹配", "约等于", "优先"} and value and not any(
            keyword in text for keyword in ["报价", "预算", "合作价格", "平台价格", "35", "34", "粉丝年龄", "宝妈", "家长", "cpc", "cpe", "搜索+推荐", "搜索推荐", "孩子年级", "小升初", "初中", "高中", "大孩", "限流", "违规", "流量稳定", "异常"]
        ):
            expected_values = _expand_rule_values(_split_rule_values(value))
            if expected_values and not any(keyword in text_pool for keyword in expected_values):
                issues.append(f"{label}：未识别到匹配信息")
        if condition in {"不包含", "规避"} and value and not any(keyword in text for keyword in ["限流", "违规", "流量稳定", "异常"]):
            avoided_values = _expand_rule_values(_split_rule_values(value))
            if avoided_values and any(keyword in text_pool for keyword in avoided_values):
                issues.append(f"{label}：命中规避项")
    return issues


def _filter_creators_by_hard_filters(
    project_id: str,
    creators: list[dict[str, Any]],
    hard_filters: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not hard_filters:
        return creators, []
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for creator in creators:
        issues = _creator_hard_filter_issues(project_id, creator, hard_filters)
        if issues:
            rejected.append(
                {
                    "creator_id": creator.get("creator_id"),
                    "nickname": creator.get("nickname") or creator.get("达人昵称"),
                    "issues": issues,
                }
            )
        else:
            accepted.append(creator)
    return accepted, rejected


def _number_or_zero(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0


@app.post("/api/projects/{project_id}/screening-standard/optimize")
def optimize_screening_standard(project_id: str, payload: ScreeningStandardPayload) -> dict[str, Any]:
    payload.project_id = project_id
    project = get_project(project_id) or payload.project
    system_prompt = (
        "你是广告投放达人筛选策略专家。请把客户 Brief 拆成两个互相独立但可协同使用的结果："
        "第一，面向小红书蒲公英找博主页面的多套筛选方案，必须结合真实蒲公英筛选字段，"
        "通过不同条件组合扩展各类符合标准的达人，并控制单套方案的推荐博主数量不要过大；"
        "第二，面向本项目工具的评分、推荐、匹配标准，用于采集达人后的综合评分、推荐等级、推荐理由和合作方向生成。"
        "只输出 JSON。"
    )
    user_payload = {
        "project": project,
        "brief": payload.brief,
        "feishuFields": payload.feishu_fields,
        "requiredSchema": {
            "briefType": "simple|complex",
            "hardFilters": [{"field": "评分/入库硬性标准名", "condition": ">=|<=|必须存在|包含|规避|匹配", "value": "阈值或规则", "required": True, "feishuField": "匹配到的飞书字段名或空"}],
            "scoringWeights": {"budget": 20, "fans": 20, "cpe": 15, "engagement": 15, "persona": 20, "content": 10},
            "scoringCriteria": {
                "purpose": "说明这是采集后评分/推荐/匹配依据，不等同于蒲公英筛选条件",
                "hard_rules": [{"field": "硬性淘汰/必备项", "condition": "规则", "value": "阈值", "evidenceField": "使用哪个达人字段判断"}],
                "dimension_weights": {"budget": 20, "fans": 20, "cpe": 15, "engagement": 15, "persona": 20, "content": 10},
                "dimensions": [
                    {
                        "key": "budget|fans|cpe|engagement|persona|content",
                        "name": "维度名",
                        "weight": 20,
                        "positive": ["加分证据"],
                        "negative": ["扣分/风险证据"],
                        "evidenceFields": ["达人字段名"],
                    }
                ],
                "recommendation_rules": [{"level": "强推荐|推荐|备选|不推荐", "condition": "判定口径"}],
                "evidence_fields": ["评分时必须参考的达人字段"],
                "reason_requirements": ["推荐理由必须包含的要点"],
            },
            "pgyCollectionPlan": {
                "strategy": "说明如何用多套独立蒲公英方案扩展候选达人；每套方案由 required_filters + additional_filters 组成，先用必备筛选条件预检推荐数，数量过多时按顺序叠加附加筛选条件",
                "target_count_range": "50-2000",
                "schemes": [
                    {
                        "scheme_id": "短英文ID",
                        "name": "筛选方案名称",
                        "goal": "覆盖的人群/达人类型",
                        "target_count_range": "50-2000",
                        "required_filters": [
                            {
                                "field": "只能是 博主类目|粉丝量|粉丝年龄|合作报价 之一",
                                "value": "筛选值或待填写内容",
                                "reason": "为什么作为必备筛选条件",
                                "control_type": "必须与 pgyFilterCatalog 对应字段的控件类型一致",
                                "input_values": ["近期合作品牌等可填空内容"],
                                "pending_detail": "如果页面打开后还要继续选择/补充，写清楚",
                            }
                        ],
                        "additional_filters": [
                            {
                                "field": "预估阅读单价|预估互动单价|阅读中位数|互动中位数|曝光中位数|粉丝地域|常规剔除 等可调整提质条件",
                                "value": "筛选值",
                                "reason": "数量过多或质量不足时才启用",
                                "control_type": "必须与 pgyFilterCatalog 对应字段的控件类型一致",
                            }
                        ],
                        "enabled_additional_filters": [],
                        "filters": [],
                        "expand_if_too_few": ["推荐博主数太少时先放宽哪些条件"],
                        "narrow_if_too_many": ["推荐博主数太多时追加哪些真实蒲公英条件"],
                    }
                ],
                "filters": [
                    {
                        "field": "全局手动添加条件；默认留空，不要自动放入人设/特色背景类低频条件",
                        "value": "筛选值或待填写内容",
                        "reason": "为什么由用户手动添加",
                        "control_type": "必须与 pgyFilterCatalog 对应字段的控件类型一致",
                        "input_values": ["近期合作品牌等可填空内容"],
                        "pending_detail": "如果页面打开后还要继续选择/补充，写清楚",
                    }
                ],
                "display_metrics": ["全部非直播指标"],
                "detail_fields": ["基础画像", "粉丝画像", "报价", "合作表现", "内容表现"],
            },
            "fieldMappings": [{"standard": "标准字段", "feishu": "飞书字段", "confidence": 0.0}],
            "summary": "一句话说明优化依据",
        },
        "pgyFilterCatalog": PGY_FILTER_CATALOG,
        "constraints": [
            "scoringWeights 六项总和必须为 100",
            "必须把蒲公英筛选方案和采集后评分标准拆开：pgyCollectionPlan 只服务找博主采集，scoringCriteria 只服务入库后评分/推荐/匹配",
            "hardFilters 是评分/入库硬性规则，不要简单等同于蒲公英页面已勾选条件",
            "蒲公英 schemes 至少输出 3 套，分别覆盖不同达人来源或人群角度；每套 required_filters 必须且只包含：博主类目、粉丝量、粉丝年龄、合作报价",
            "不要在 required_filters 或自动 filters 中加入 家庭身份、职业身份、特色背景、母婴阶段、行业推荐博主、近期合作品牌、按博主粉丝推荐；这些低频项只有用户在前端手动添加时才允许进入 filters",
            "预估阅读单价、预估互动单价、阅读/互动/曝光中位数等提质条件放入 additional_filters，默认非必要；如果必备筛选下博主过多，按 additional_filters 数组顺序逐个叠加，越靠上越先启用，一旦数量达标就不再继续加下面的条件",
            "每套蒲公英方案需要 target_count_range、expand_if_too_few、narrow_if_too_many，用来根据页面推荐数量动态扩缩条件",
            "当蒲公英页面推荐数量类似 5000+ 时，narrow_if_too_many 必须给出可追加的真实蒲公英附加筛选条件；目标是不超过约 2000",
            "评分硬性条件只使用 Brief 明确要求或达人筛选必需字段",
            "飞书字段匹配要使用 feishuFields 中实际存在的字段名",
            "蒲公英筛选条件必须优先使用 pgyFilterCatalog 中的真实字段和控件类型",
            "近期合作品牌是可搜索品牌多选，不是普通标签；若 Brief 提供品牌名要写入 input_values；品牌不足3个时 pending_detail 标注待补足",
            "按博主粉丝推荐不是普通行内筛选项，而是右上角智能推荐博主/合作品牌搜索入口；Brief 中的合作品牌、目标品牌、竞品、对标品牌都可写入 input_values 或 competitor_values",
            "行业推荐博主打开后仍有“我的行业/请选择”下拉，必须标注为 nested_select_popover 和 pending_detail",
            "合作报价、预估阅读单价、预估互动单价是图文/视频子字段，每个子字段还会打开预设档位和自定义区间",
            "粉丝地域是国家/省/城市三级级联；地域是国家/省级联；粉丝量、曝光/阅读/互动中位数、千赞比例、外溢进店单价都有预设档位和自定义区间",
        ],
    }
    try:
        result = chat_json(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"请根据以下 JSON 输出筛选标准：\n{user_payload}"},
            ]
        )
        plan = _sync_screening_plan_criteria(_normalize_screening_standard(result, payload))
        source = "llm"
        status = "success"
        detail = plan.get("summary") or "量化标准已由大模型优化"
    except Exception as error:
        plan = _sync_screening_plan_criteria(_normalize_screening_standard({}, payload))
        source = "generated"
        status = "success"
        detail = "测试阶段已直接生成量化标准；大模型 API 接入入口保留，可在高级配置中测试"
    with connect() as conn:
        log(conn, project_id, "screening", "优化量化标准", project.get("project_name") or project_id, "AI", detail, status)
    save_project(project_id, {"brief": payload.brief, "screening_plan": plan})
    return {"ok": True, "source": source, "screeningPlan": plan, "message": detail}


@app.get("/api/projects/feishu/connection")
def get_feishu_connection(project_id: str = Query(default="youdao_001")) -> dict[str, Any]:
    config = read_json(feishu_connection_path(project_id), {})
    return {"config": public_feishu_config(config) if config else None}


@app.post("/api/projects/feishu/connection")
def save_feishu_connection(payload: FeishuConnectionPayload) -> dict[str, Any]:
    path = feishu_connection_path(payload.project_id)
    existing = read_json(path, {})
    config = {
        "project_id": payload.project_id,
        "feishu_url": payload.feishu_url,
        "app_id": payload.app_id,
        "app_secret": payload.app_secret or existing.get("app_secret") or "",
    }
    try:
        config["target"] = parse_feishu_url(payload.feishu_url).as_dict()
    except FeishuError as error:
        raise _feishu_error_response(error)
    config["field_mapping_cache"] = {}
    write_json(path, config)
    if config.get("app_secret"):
        try:
            config = _refresh_feishu_field_mapping_cache(payload.project_id)
        except FeishuError:
            config = read_json(path, config)
    return {"config": public_feishu_config(config), "message": "飞书配置已保存"}


def _load_feishu_client(project_id: str) -> tuple[dict[str, Any], FeishuClient, Any]:
    config = read_json(feishu_connection_path(project_id), {})
    if not config:
        raise FeishuError("missing_connection", "当前项目还没有保存飞书配置")
    if not config.get("app_secret"):
        raise FeishuError("missing_app_secret", "当前项目未配置 App Secret，无法读取远端表")
    target = parse_feishu_url(config.get("feishu_url") or "")
    client = FeishuClient(config["app_id"], config["app_secret"])
    return config, client, client.resolve_wiki_target(target)


def _feishu_error_response(error: FeishuError, *, extra: dict[str, Any] | None = None) -> HTTPException:
    detail = {"code": error.code, "message": str(error), **error.details}
    if extra:
        detail.update(extra)
    return HTTPException(status_code=400, detail=detail)


def _safe_table_meta(table: dict[str, Any]) -> dict[str, Any]:
    return {key: table.get(key) for key in ("sheet_id", "table_id", "id", "title", "name") if table.get(key)}


def _table_identifier(table: dict[str, Any]) -> str:
    return str(table.get("sheet_id") or table.get("table_id") or table.get("id") or "")


def _field_signature(fields: list[dict[str, Any]]) -> list[str]:
    return [
        str(field.get("field_name") or field.get("name") or field.get("title") or "")
        for field in sorted(fields, key=lambda item: int(item.get("column_index", item.get("index", 0)) or 0))
        if str(field.get("field_name") or field.get("name") or field.get("title") or "")
    ]


def _mapping_cache_key(resource_type: str, table_id: str) -> str:
    return f"{resource_type}:{table_id}"


def _analyze_table_field_mapping(
    target: Any,
    selected: dict[str, Any],
    fields: list[dict[str, Any]],
) -> dict[str, Any]:
    table_id = _table_identifier(selected)
    field_names = _field_signature(fields)
    plan = analyze_field_mapping(field_names, default_source_rows(), use_llm=True)
    return {
        **plan,
        "resource_type": target.resource_type,
        "table_id": table_id,
        "table": _safe_table_meta(selected),
        "field_signature": field_names,
        "analyzed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def _write_feishu_config(project_id: str, config: dict[str, Any]) -> dict[str, Any]:
    write_json(feishu_connection_path(project_id), config)
    return config


def _load_tables_and_fields(client: FeishuClient, target: Any) -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    if target.resource_type == "sheet":
        tables = client.list_sheet_tabs(target.token)
        fields_by_id = {
            _table_identifier(table): client.list_sheet_fields(target.token, _table_identifier(table))
            for table in tables
            if _table_identifier(table)
        }
    elif target.resource_type == "bitable":
        tables = client.list_bitable_tables(target.token)
        fields_by_id = {
            _table_identifier(table): client.list_bitable_fields(target.token, _table_identifier(table))
            for table in tables
            if _table_identifier(table)
        }
    else:
        raise FeishuError("unsupported_resource_type", f"暂不支持该飞书资源：{target.resource_type}")
    return tables, fields_by_id


def _refresh_feishu_field_mapping_cache(project_id: str) -> dict[str, Any]:
    config, client, target = _load_feishu_client(project_id)
    tables, fields_by_id = _load_tables_and_fields(client, target)
    cache: dict[str, Any] = {}
    for table in tables:
        table_id = _table_identifier(table)
        fields = fields_by_id.get(table_id) or []
        if not table_id or not fields:
            continue
        cache[_mapping_cache_key(target.resource_type, table_id)] = _analyze_table_field_mapping(target, table, fields)
    config["target"] = target.as_dict()
    config["field_mapping_cache"] = cache
    return _write_feishu_config(project_id, config)


def _cached_field_mapping_plan(
    config: dict[str, Any],
    target: Any,
    table_id: str,
    fields: list[dict[str, Any]],
) -> dict[str, Any] | None:
    cache = config.get("field_mapping_cache") if isinstance(config.get("field_mapping_cache"), dict) else {}
    plan = cache.get(_mapping_cache_key(target.resource_type, table_id))
    if not isinstance(plan, dict):
        return None
    if plan.get("field_signature") != _field_signature(fields):
        return None
    return plan


def _ensure_field_mapping_plan(
    project_id: str,
    config: dict[str, Any],
    target: Any,
    selected: dict[str, Any],
    fields: list[dict[str, Any]],
) -> dict[str, Any]:
    table_id = _table_identifier(selected)
    cached = _cached_field_mapping_plan(config, target, table_id, fields)
    if cached:
        return cached
    plan = _analyze_table_field_mapping(target, selected, fields)
    cache = config.get("field_mapping_cache") if isinstance(config.get("field_mapping_cache"), dict) else {}
    cache[_mapping_cache_key(target.resource_type, table_id)] = plan
    config["field_mapping_cache"] = cache
    _write_feishu_config(project_id, config)
    return plan


def _write_sheet_audience_profile_images(
    client: FeishuClient,
    spreadsheet_token: str,
    sheet_id: str,
    fields: list[dict[str, Any]],
    rows: list[dict[str, Any]],
    result: dict[str, Any],
) -> dict[str, Any]:
    image_rows = [row for row in rows if row.get("粉丝画像截图")]
    if not image_rows:
        return {"enabled": False, "message": "本次写回没有粉丝画像截图"}
    fields, field_result = client.ensure_sheet_field(spreadsheet_token, sheet_id, fields, "粉丝画像截图")
    profile_field = next(field for field in fields if field.get("field_name") == "粉丝画像截图")
    profile_column = column_name(int(profile_field["column_index"]) + 1)
    row_lookup: dict[str, str] = {}
    result_items = (result.get("created") or []) + (result.get("updated") or [])
    for row, item in zip(rows, result_items):
        record_id = item.get("record_id")
        if record_id:
            for key in ("达人ID", "蒲公英链接", "达人昵称"):
                value = str(row.get(key) or "").strip()
                if value:
                    row_lookup[f"{key}:{value}"] = str(record_id)
    written: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []
    for row in image_rows:
        record_id = ""
        for key in ("达人ID", "蒲公英链接", "达人昵称"):
            value = str(row.get(key) or "").strip()
            if value and f"{key}:{value}" in row_lookup:
                record_id = row_lookup[f"{key}:{value}"]
                break
        if not record_id or not record_id.isdigit():
            failed.append({"row": row.get("达人昵称") or row.get("达人ID") or "", "message": "未定位到写回后的飞书行号"})
            continue
        cell = f"{profile_column}{record_id}"
        image_path = str(row.get("粉丝画像截图") or "")
        try:
            write_result = client.write_sheet_image(
                spreadsheet_token,
                sheet_id,
                cell,
                image_path,
                name=f"{row.get('达人昵称') or row.get('达人ID') or '粉丝画像截图'}.png",
            )
            written.append({"cell": cell, "image_path": image_path, "result": write_result})
        except FeishuError as error:
            failed.append({"cell": cell, "image_path": image_path, "message": str(error), "code": error.code, **error.details})
    return {
        "enabled": True,
        "field": profile_field,
        "field_result": field_result,
        "written": written,
        "failed": failed,
    }


def _error_detail(error: FeishuError) -> dict[str, Any]:
    return {"code": error.code, "message": str(error), **error.details}


def _mark_step(steps: list[dict[str, Any]], key: str, status: str, message: str, **extra: Any) -> None:
    for step in steps:
        if step["key"] == key:
            step.update({"status": status, "message": message, **extra})
            return
    steps.append({"key": key, "label": key, "status": status, "message": message, **extra})


def _build_feishu_test_row(fields: list[dict[str, Any]]) -> tuple[dict[str, Any], str, list[str]]:
    marker = f"系统连接测试-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    row = {field["field_name"]: "" for field in fields}
    marker_fields = []
    for name, value in {
        "达人昵称": marker,
        "推荐理由": "验证飞书字段读取和记录写入",
        "品牌备注": "自动连接测试，可删除",
        "达人反馈": "自动连接测试，可删除",
    }.items():
        if name in row:
            row[name] = value
            marker_fields.append(name)
    if not marker_fields and fields:
        row[fields[0]["field_name"]] = marker
        marker_fields.append(fields[0]["field_name"])
    return row, marker, marker_fields


def _run_feishu_full_test(feishu_url: str, app_id: str, app_secret: str, *, table_id: str | None = None) -> dict[str, Any]:
    steps = [
        {"key": "parse_url", "label": "识别飞书链接", "status": "pending"},
        {"key": "auth", "label": "应用鉴权 / Wiki 解析", "status": "pending"},
        {"key": "list_tables", "label": "读取子表", "status": "pending"},
        {"key": "read_fields", "label": "读取字段", "status": "pending"},
        {"key": "write_test", "label": "测试写入", "status": "pending"},
    ]
    try:
        target = parse_feishu_url(feishu_url)
        _mark_step(steps, "parse_url", "success", "飞书链接格式已识别", target=target.as_dict())
    except FeishuError as error:
        _mark_step(steps, "parse_url", "failed", str(error), error=_error_detail(error))
        return {"ok": False, "failed_step": "parse_url", "steps": steps, "message": str(error), "error": _error_detail(error)}

    try:
        client = FeishuClient(app_id, app_secret)
        resolved = client.resolve_wiki_target(target)
        _mark_step(steps, "auth", "success", "应用鉴权成功，飞书资源已解析", target=resolved.as_dict())
    except FeishuError as error:
        _mark_step(steps, "auth", "failed", str(error), error=_error_detail(error))
        return {"ok": False, "target": target.as_dict(), "failed_step": "auth", "steps": steps, "message": str(error), "error": _error_detail(error)}

    selected_id = table_id or resolved.table_id
    try:
        if resolved.resource_type == "sheet":
            tables = client.list_sheet_tabs(resolved.token)
        elif resolved.resource_type == "bitable":
            tables = client.list_bitable_tables(resolved.token)
        else:
            raise FeishuError("unsupported_resource_type", f"暂不支持该飞书资源：{resolved.resource_type}")
        selected = choose_table(tables, selected_id)
        _mark_step(steps, "list_tables", "success", "子表读取成功", selected_table=_safe_table_meta(selected), table_count=len(tables))
    except FeishuError as error:
        _mark_step(steps, "list_tables", "failed", str(error), error=_error_detail(error))
        return {"ok": False, "target": resolved.as_dict(), "failed_step": "list_tables", "steps": steps, "message": str(error), "error": _error_detail(error)}

    try:
        if resolved.resource_type == "sheet":
            selected_table_id = selected.get("sheet_id") or selected.get("id")
            fields = client.list_sheet_fields(resolved.token, selected_table_id)
        else:
            selected_table_id = selected.get("table_id") or selected.get("id")
            fields = client.list_bitable_fields(resolved.token, selected_table_id)
        if not fields:
            raise FeishuError("empty_fields", "当前子表未读取到字段，请确认第 1 行是表头或多维表格字段已配置")
        _mark_step(steps, "read_fields", "success", f"字段读取成功，共 {len(fields)} 个字段", field_count=len(fields))
    except FeishuError as error:
        _mark_step(steps, "read_fields", "failed", str(error), error=_error_detail(error))
        return {
            "ok": False,
            "target": resolved.as_dict(),
            "selected_table": _safe_table_meta(selected),
            "failed_step": "read_fields",
            "steps": steps,
            "message": str(error),
            "error": _error_detail(error),
        }

    try:
        if resolved.resource_type == "sheet":
            row, marker, marker_fields = _build_feishu_test_row(fields)
            write_result = client.append_sheet_records(resolved.token, selected_table_id, fields, [row])
        else:
            writable_fields = [
                field for field in fields
                if str(field.get("type", "")).lower() not in {"formula", "lookup", "createdtime", "modifiedtime", "autonumber"}
            ]
            row, marker, marker_fields = _build_feishu_test_row(
                [{"field_name": field.get("field_name") or field.get("name"), "column_index": index} for index, field in enumerate(writable_fields) if field.get("field_name") or field.get("name")]
            )
            if not row:
                raise FeishuError("no_writable_fields", "当前多维表格没有可用于测试写入的普通字段")
            write_result = client.create_bitable_records(resolved.token, selected_table_id, [row])
        _mark_step(steps, "write_test", "success", "测试写入成功", marker=marker, marker_fields=marker_fields)
    except FeishuError as error:
        _mark_step(steps, "write_test", "failed", str(error), error=_error_detail(error))
        return {
            "ok": False,
            "target": resolved.as_dict(),
            "selected_table": _safe_table_meta(selected),
            "fields": fields,
            "field_count": len(fields),
            "read_ok": True,
            "write_ok": False,
            "failed_step": "write_test",
            "steps": steps,
            "message": str(error),
            "error": _error_detail(error),
        }

    return {
        "ok": True,
        "target": resolved.as_dict(),
        "selected_table": selected,
        "fields": fields,
        "field_count": len(fields),
        "read_ok": True,
        "write_ok": True,
        "steps": steps,
        "result": write_result,
        "message": "飞书连接完整测试通过：字段读取和测试写入均正常",
    }


@app.post("/api/projects/feishu/test")
def test_feishu_connection(payload: FeishuConnectionPayload) -> dict[str, Any]:
    saved = read_json(feishu_connection_path(payload.project_id), {})
    feishu_url = payload.feishu_url or saved.get("feishu_url") or ""
    app_id = payload.app_id or saved.get("app_id") or ""
    app_secret = payload.app_secret or saved.get("app_secret") or ""
    target = parse_feishu_url(feishu_url)
    if not app_secret:
        return {
            "ok": False,
            "target": target.as_dict(),
            "failed_step": "auth",
            "steps": [
                {"key": "parse_url", "label": "识别飞书链接", "status": "success", "message": "飞书链接格式已识别"},
                {"key": "auth", "label": "应用鉴权 / Wiki 解析", "status": "failed", "message": "未提供 App Secret，无法完整测试字段读取和写入"},
                {"key": "list_tables", "label": "读取子表", "status": "pending"},
                {"key": "read_fields", "label": "读取字段", "status": "pending"},
                {"key": "write_test", "label": "测试写入", "status": "pending"},
            ],
            "message": "未提供 App Secret，无法完整测试字段读取和写入",
        }
    result = _run_feishu_full_test(feishu_url, app_id, app_secret)
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result)
    return result


@app.get("/api/projects/feishu/tables")
def list_feishu_tables(project_id: str = Query(default="youdao_001")) -> dict[str, Any]:
    try:
        config, client, target = _load_feishu_client(project_id)
        if target.resource_type == "sheet":
            tables = client.list_sheet_tabs(target.token)
        elif target.resource_type == "bitable":
            tables = client.list_bitable_tables(target.token)
        else:
            raise FeishuError("unsupported_resource_type", f"暂不支持该飞书资源：{target.resource_type}")
        try:
            _refresh_feishu_field_mapping_cache(project_id)
        except FeishuError:
            pass
        return {"target": target.as_dict(), "tables": tables}
    except FeishuError as error:
        raise _feishu_error_response(error)


@app.get("/api/projects/feishu/fields")
def list_feishu_fields(
    project_id: str = Query(default="youdao_001"),
    table_id: str | None = Query(default=None),
) -> dict[str, Any]:
    try:
        config, client, target = _load_feishu_client(project_id)
        selected_id = table_id or target.table_id
        if target.resource_type == "sheet":
            tables = client.list_sheet_tabs(target.token)
            selected = choose_table(tables, selected_id)
            selected_id = selected.get("sheet_id") or selected.get("id")
            fields = client.list_sheet_fields(target.token, selected_id)
        elif target.resource_type == "bitable":
            tables = client.list_bitable_tables(target.token)
            selected = choose_table(tables, selected_id)
            selected_id = selected.get("table_id") or selected.get("id")
            fields = client.list_bitable_fields(target.token, selected_id)
        else:
            raise FeishuError("unsupported_resource_type", f"暂不支持该飞书资源：{target.resource_type}")
        _ensure_field_mapping_plan(project_id, config, target, selected, fields)
        return {"target": target.as_dict(), "selected_table": selected, "fields": fields}
    except FeishuError as error:
        raise _feishu_error_response(error)


@app.get("/api/projects/feishu/diagnostics")
def diagnose_feishu_connection(
    project_id: str = Query(default="youdao_001"),
    table_id: str | None = Query(default=None),
    test_write: bool = Query(default=False),
) -> dict[str, Any]:
    diagnostics: dict[str, Any] = {
        "ok": False,
        "read_ok": False,
        "write_ok": None,
        "project_id": project_id,
    }
    try:
        _, client, target = _load_feishu_client(project_id)
        diagnostics["target"] = target.as_dict()
        selected_id = table_id or target.table_id
        if target.resource_type == "sheet":
            tables = client.list_sheet_tabs(target.token)
            selected = choose_table(tables, selected_id)
            sheet_id = selected.get("sheet_id") or selected.get("id")
            fields = client.list_sheet_fields(target.token, sheet_id)
            diagnostics.update(
                {
                    "read_ok": True,
                    "selected_table": _safe_table_meta(selected),
                    "field_count": len(fields),
                    "fields": fields,
                    "message": "飞书字段读取正常；未执行测试写入",
                }
            )
            if test_write:
                marker = f"系统读写诊断-{datetime.now().strftime('%Y%m%d%H%M%S')}"
                row = {field["field_name"]: "" for field in fields}
                marker_fields = []
                for name, value in {
                    "达人昵称": marker,
                    "推荐理由": "验证飞书字段读取和记录写入",
                    "品牌备注": "自动连接诊断，可删除",
                    "达人反馈": "自动连接诊断，可删除",
                }.items():
                    if name in row:
                        row[name] = value
                        marker_fields.append(name)
                if not marker_fields and fields:
                    row[fields[0]["field_name"]] = marker
                    marker_fields.append(fields[0]["field_name"])
                try:
                    result = client.append_sheet_records(target.token, sheet_id, fields, [row])
                    diagnostics.update(
                        {
                            "ok": True,
                            "write_ok": True,
                            "write_test_marker": marker,
                            "write_test_fields": marker_fields,
                            "result": result,
                            "message": "飞书字段读取和测试写入均正常",
                        }
                    )
                except FeishuError as write_error:
                    diagnostics.update(
                        {
                            "ok": False,
                            "write_ok": False,
                            "write_error": {"code": write_error.code, "message": str(write_error), **write_error.details},
                            "message": "飞书字段读取正常，但写入权限不足",
                        }
                    )
            else:
                diagnostics["ok"] = True
        elif target.resource_type == "bitable":
            tables = client.list_bitable_tables(target.token)
            selected = choose_table(tables, selected_id)
            selected_id = selected.get("table_id") or selected.get("id")
            fields = client.list_bitable_fields(target.token, selected_id)
            diagnostics.update(
                {
                    "ok": True,
                    "read_ok": True,
                    "write_ok": None,
                    "selected_table": _safe_table_meta(selected),
                    "field_count": len(fields),
                    "fields": fields,
                    "message": "飞书多维表格字段读取正常；未执行测试写入以避免新增业务记录",
                }
            )
        else:
            raise FeishuError("unsupported_resource_type", f"暂不支持该飞书资源：{target.resource_type}")
        return diagnostics
    except FeishuError as error:
        diagnostics.update({"error": {"code": error.code, "message": str(error), **error.details}, "message": str(error)})
        return diagnostics


@app.get("/api/projects/feishu/writeback-settings")
def get_feishu_writeback_settings(project_id: str = Query(default="youdao_001")) -> dict[str, Any]:
    return {"settings": get_project_writeback_settings(project_id)}


@app.post("/api/projects/feishu/writeback-settings")
def save_feishu_writeback_settings(payload: WritebackSettingsPayload) -> dict[str, Any]:
    return {"settings": save_project_writeback_settings(payload.project_id, payload.auto_writeback_enabled)}


@app.post("/api/projects/feishu/records")
def create_feishu_records(payload: FeishuRecordsPayload) -> dict[str, Any]:
    read_context: dict[str, Any] = {}
    try:
        target_ids = {str(creator_id) for creator_id in payload.creator_ids}
        if payload.rows:
            rows = payload.rows
        elif payload.quality_only:
            rows = quality_feishu_rows(
                payload.project_id,
                payload.limit,
                creator_ids=payload.creator_ids or None,
                include_test_creators=False,
                rescore=False,
            )
        else:
            rows = standard_feishu_rows(payload.project_id, payload.statuses)
            if target_ids:
                rows = [row for row in rows if str(row.get("达人ID") or "") in target_ids]
        if not rows:
            raise FeishuError("empty_records", "没有要写入的记录")
        config, client, target = _load_feishu_client(payload.project_id)
        selected_id = payload.table_id or target.table_id
        if target.resource_type == "sheet":
            tables = client.list_sheet_tabs(target.token)
            selected = choose_table(tables, selected_id)
            sheet_id = selected.get("sheet_id") or selected.get("id")
            fields = client.list_sheet_fields(target.token, sheet_id)
            read_context = {
                "read_ok": True,
                "resource_type": "sheet",
                "selected_table": _safe_table_meta(selected),
                "field_count": len(fields),
            }
            sync_states = list_feishu_sync_state(payload.project_id)
            known_record_ids = {
                item["creator_id"]: item["feishu_record_id"]
                for item in sync_states
                if item.get("table_id") == sheet_id and item.get("feishu_record_id")
            }
            fields, image_field_result = client.ensure_sheet_field(target.token, sheet_id, fields, "粉丝画像截图")
            field_mapping = _ensure_field_mapping_plan(payload.project_id, config, target, selected, fields)
            mapped_rows, field_mapping = apply_field_mapping(rows, fields, mapping_plan=field_mapping)
            result = client.upsert_sheet_records(target.token, sheet_id, fields, mapped_rows, known_record_ids)
            image_result = _write_sheet_audience_profile_images(client, target.token, sheet_id, fields, rows, result)
            image_result["field_result"] = image_result.get("field_result") or image_field_result
            sync_table_id = sheet_id
        elif target.resource_type == "bitable":
            tables = client.list_bitable_tables(target.token)
            selected = choose_table(tables, selected_id)
            table_id = selected.get("table_id") or selected.get("id")
            fields = client.list_bitable_fields(target.token, table_id)
            read_context = {
                "read_ok": True,
                "resource_type": "bitable",
                "selected_table": _safe_table_meta(selected),
            }
            sync_states = list_feishu_sync_state(payload.project_id)
            known_record_ids = {
                item["creator_id"]: item["feishu_record_id"]
                for item in sync_states
                if item.get("table_id") == table_id and item.get("feishu_record_id")
            }
            field_mapping = _ensure_field_mapping_plan(payload.project_id, config, target, selected, fields)
            mapped_rows, field_mapping = apply_field_mapping(rows, fields, mapping_plan=field_mapping)
            result = client.upsert_bitable_records(target.token, table_id, mapped_rows, known_record_ids)
            image_result = {"enabled": False, "message": "当前写回目标是多维表格，粉丝画像截图图片写入仅支持电子表格"}
            sync_table_id = table_id
        else:
            raise FeishuError("unsupported_resource_type", f"暂不支持该飞书资源：{target.resource_type}")
        written_names = {row.get("达人昵称") for row in rows if row.get("达人昵称")}
        record_map: dict[str, str | None] = {}
        result_items = (result.get("created") or []) + (result.get("updated") or [])
        for row, item in zip(rows, result_items):
            record_map[str(row.get("达人ID") or "")] = item.get("record_id")
        success_count = 0
        for item in list_creators(payload.project_id):
            if item.get("nickname") in written_names or (not payload.quality_only and item["status"] in payload.statuses):
                review_creator(payload.project_id, item["creator_id"], "已写回飞书", "优质达人写回飞书成功", "系统")
                record_feishu_sync_state(
                    payload.project_id,
                    item["creator_id"],
                    sync_table_id,
                    record_map.get(item["creator_id"]),
                    "push",
                    "success",
                )
                success_count += 1
        with connect() as conn:
            log(conn, payload.project_id, "feishu", "飞书 upsert 写回", sync_table_id, "系统", f"成功同步 {success_count} 条达人记录", "success")
        return {"ok": True, "target": target.as_dict(), "selected_table": selected, "result": result, "field_mapping": field_mapping, "image_result": image_result, "written_count": len(rows), "sync_status": {"success": success_count, "failed": 0}}
    except FeishuError as error:
        table_id = payload.table_id or "unknown"
        for row in payload.rows:
            creator_id = str(row.get("达人ID") or "")
            if creator_id:
                record_feishu_sync_state(payload.project_id, creator_id, table_id, None, "push", "failed", str(error))
        raise _feishu_error_response(error, extra=read_context)


def _auto_writeback_after_detail(project_id: str, creator_ids: list[str]) -> dict[str, Any]:
    settings = get_project_writeback_settings(project_id)
    if not settings.get("auto_writeback_enabled"):
        return {"enabled": False, "written_count": 0, "message": "自动写回已关闭"}
    if not creator_ids:
        return {"enabled": True, "written_count": 0, "message": "没有详情补采成功的达人需要写回"}
    try:
        result = create_feishu_records(
            FeishuRecordsPayload(
                project_id=project_id,
                quality_only=True,
                creator_ids=creator_ids,
                limit=len(creator_ids),
            )
        )
        return {
            "enabled": True,
            "ok": True,
            "written_count": result.get("written_count", 0),
            "sync_status": result.get("sync_status"),
            "message": f"自动写回飞书完成 {result.get('written_count', 0)} 条合格达人",
        }
    except HTTPException as error:
        detail = error.detail if isinstance(error.detail, dict) else {"message": str(error.detail)}
        return {
            "enabled": True,
            "ok": False,
            "written_count": 0,
            "message": detail.get("message") or "自动写回飞书未完成",
            "error": detail,
        }


@app.post("/api/projects/feishu/writeback")
def writeback_feishu_records(payload: FeishuRecordsPayload) -> dict[str, Any]:
    return create_feishu_records(payload)


@app.post("/api/projects/feishu/pull")
def pull_feishu_records(payload: FeishuPullPayload) -> dict[str, Any]:
    read_context: dict[str, Any] = {}
    try:
        if payload.rows:
            result = merge_feishu_rows(payload.project_id, payload.rows, payload.table_id or "manual")
            return {"ok": True, **result}
        _, client, target = _load_feishu_client(payload.project_id)
        selected_id = payload.table_id or target.table_id
        if target.resource_type == "sheet":
            tables = client.list_sheet_tabs(target.token)
            selected = choose_table(tables, selected_id)
            sheet_id = selected.get("sheet_id") or selected.get("id")
            fields = client.list_sheet_fields(target.token, sheet_id)
            rows = client.list_sheet_records(target.token, sheet_id, fields)
            table_id = sheet_id
            read_context = {"resource_type": "sheet", "selected_table": _safe_table_meta(selected)}
        elif target.resource_type == "bitable":
            tables = client.list_bitable_tables(target.token)
            selected = choose_table(tables, selected_id)
            table_id = selected.get("table_id") or selected.get("id")
            records = client.list_bitable_records(target.token, table_id)
            rows = [{"_record_id": item.get("record_id"), **(item.get("fields") or {})} for item in records]
            read_context = {"resource_type": "bitable", "selected_table": _safe_table_meta(selected)}
        else:
            raise FeishuError("unsupported_resource_type", f"暂不支持该飞书资源：{target.resource_type}")
        result = merge_feishu_rows(payload.project_id, rows, table_id)
        return {"ok": True, "target": target.as_dict(), **read_context, **result}
    except FeishuError as error:
        raise _feishu_error_response(error, extra=read_context)


@app.post("/api/pgy/browser/start")
def api_pgy_browser_start() -> dict[str, Any]:
    return start_browser()


@app.get("/api/pgy/browser/status")
def api_pgy_browser_status() -> dict[str, Any]:
    return browser_status()


@app.post("/api/pgy/collect/list")
def api_pgy_collect_list() -> dict[str, Any]:
    return collect_visible_list(include_details=False, export_metrics=True)


@app.post("/api/pgy/collect/detail")
def api_pgy_collect_detail(payload: DetailCollectPayload) -> dict[str, Any]:
    project_id = payload.project_id or "youdao_001"
    creators = list_creators(project_id)
    target_ids = set(payload.creator_ids or [])
    if payload.manual or target_ids:
        targets = [creator for creator in creators if creator["creator_id"] in target_ids]
    else:
        targets = [
            creator
            for creator in creators
            if creator.get("hard_filter_passed")
            and (
                creator.get("detail_collection_priority") in {"必须补采", "优先补采", "高潜补采"}
                or _number_or_zero(creator.get("total_score")) >= 90
            )
        ]
    if not targets:
        message = "当前分段没有可补全详情页的达人" if (payload.manual or target_ids) else "没有达到详情页补采优先级的达人"
        return {"ok": False, "message": message, "creators": [], "failed": []}
    result = collect_details_for_targets(targets, limit=payload.limit)
    if not result.get("ok"):
        return result
    updated = []
    for creator in result.get("creators") or []:
        updated.append(update_creator(project_id, creator["creator_id"], creator, score=False))
    if updated:
        score_project(project_id, creator_ids=[creator["creator_id"] for creator in updated], trigger_source="pgy_detail")
    auto_writeback = _auto_writeback_after_detail(project_id, [creator["creator_id"] for creator in updated])
    return {
        **result,
        "updated": updated,
        "auto_writeback": auto_writeback,
        "message": f"详情页完善完成，已更新 {len(updated)} 个{'当前分段达人' if (payload.manual or target_ids) else '通过初筛达人'}；失败 {len(result.get('failed') or [])} 个",
    }


def _normalize_project_screening_plan(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return copy.deepcopy(value)
    if isinstance(value, str) and value:
        try:
            loaded = json.loads(value)
            return loaded if isinstance(loaded, dict) else {}
        except Exception:
            return {}
    return {}


PGY_DEFAULT_BASE_FILTERS = {
    "category": {"field": "博主类目", "value": "教育", "reason": "必备筛选：内容类目匹配项目场景"},
    "followers": {"field": "粉丝量", "value": "1万～10万", "reason": "必备筛选：先控制达人量级", "control_type": "preset_or_number_range"},
    "age": {"field": "粉丝年龄", "value": "35～44 占比高", "reason": "必备筛选：家长决策人群优先", "control_type": "dropdown"},
    "quote": {"field": "合作报价", "value": "图文笔记：0.1万～2万", "reason": "必备筛选：控制单达人预算", "control_type": "subfield_preset_or_number_range", "sub_field": "图文笔记", "max": 20000},
}

PGY_BASE_FILTER_FIELDS = {"博主类目", "粉丝量", "粉丝年龄", "合作报价"}
PGY_EXTRA_FILTER_FIELDS = {"预估阅读单价", "预估互动单价", "阅读中位数", "互动中位数", "曝光中位数", "常规剔除", "粉丝地域"}
PGY_MANUAL_ONLY_FILTER_FIELDS = {"职业身份", "特色背景", "家庭身份", "母婴阶段", "行业推荐博主", "平台推荐", "近期合作品牌", "按博主粉丝推荐"}
PGY_MANUAL_FLAGS = {"manual", "manual_added", "user_added", "frontend_added"}


def _filter_key(item: dict[str, Any]) -> tuple[str, str, str]:
    return (str(item.get("field") or ""), str(item.get("value") or ""), str(item.get("sub_field") or item.get("subField") or ""))


def _filter_field_sub_key(item: dict[str, Any]) -> tuple[str, str]:
    return (str(item.get("field") or item.get("pgyField") or ""), str(item.get("sub_field") or item.get("subField") or ""))


def _dedupe_filters(filters: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for item in filters or []:
        if not isinstance(item, dict):
            continue
        key = _filter_key(item)
        if not key[0] or not key[1] or key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def _is_manual_pgy_filter(item: dict[str, Any]) -> bool:
    return any(item.get(flag) is True for flag in PGY_MANUAL_FLAGS) or str(item.get("source") or "").lower() in {"manual", "frontend", "user"}


def _clean_scheme_filters(filters: Any, allowed_fields: set[str] | None = None, allow_manual_only: bool = False) -> list[dict[str, Any]]:
    cleaned: list[dict[str, Any]] = []
    for item in filters or []:
        if not isinstance(item, dict):
            continue
        field = str(item.get("field") or "").strip()
        value = str(item.get("value") or "").strip()
        if not field or not value:
            continue
        if allowed_fields is not None and field not in allowed_fields:
            continue
        if field in PGY_MANUAL_ONLY_FILTER_FIELDS and not (allow_manual_only and _is_manual_pgy_filter(item)):
            continue
        cleaned.append(copy.deepcopy(item))
    return _dedupe_filters(cleaned)


def _manual_filters_for_scheme(screening_plan: dict[str, Any]) -> list[dict[str, Any]]:
    pgy_plan = screening_plan.get("pgyCollectionPlan") if isinstance(screening_plan.get("pgyCollectionPlan"), dict) else {}
    return _clean_scheme_filters(
        [item for item in (pgy_plan.get("filters") or []) if isinstance(item, dict) and _is_manual_pgy_filter(item)],
        allowed_fields=None,
        allow_manual_only=True,
    )


def _normalize_scheme_filter_structure(pgy_plan: dict[str, Any]) -> dict[str, Any]:
    plan = copy.deepcopy(pgy_plan or {})
    plan["filters"] = _clean_scheme_filters(plan.get("filters") or [], allowed_fields=None, allow_manual_only=True)
    normalized_schemes = []
    for scheme in plan.get("schemes") or []:
        if not isinstance(scheme, dict):
            continue
        next_scheme = copy.deepcopy(scheme)
        required_filters = _clean_scheme_filters(
            next_scheme.get("required_filters") or next_scheme.get("base_filters") or [item for item in (next_scheme.get("filters") or []) if isinstance(item, dict)],
            allowed_fields=PGY_BASE_FILTER_FIELDS,
        )
        additional_filters = _clean_scheme_filters(
            next_scheme.get("additional_filters") or next_scheme.get("extra_filters") or [item for item in (next_scheme.get("filters") or []) if isinstance(item, dict)],
            allowed_fields=PGY_EXTRA_FILTER_FIELDS,
        )
        enabled_additional_filters = _clean_scheme_filters(
            next_scheme.get("enabled_additional_filters") or next_scheme.get("enabled_extra_filters") or next_scheme.get("active_extra_filters") or next_scheme.get("active_additional_filters") or [],
            allowed_fields=PGY_EXTRA_FILTER_FIELDS,
        )
        next_scheme["required_filters"] = required_filters
        next_scheme["additional_filters"] = additional_filters
        next_scheme["base_filters"] = required_filters
        next_scheme["extra_filters"] = additional_filters
        next_scheme["enabled_additional_filters"] = enabled_additional_filters
        next_scheme["enabled_extra_filters"] = enabled_additional_filters
        next_scheme["filters"] = []
        normalized_schemes.append(next_scheme)
    plan["schemes"] = normalized_schemes
    return plan


def _base_filters_for_scheme(screening_plan: dict[str, Any], scheme: dict[str, Any]) -> list[dict[str, Any]]:
    explicit_base = scheme.get("required_filters") or scheme.get("base_filters")
    if isinstance(explicit_base, list) and explicit_base:
        return _clean_scheme_filters(explicit_base, allowed_fields=PGY_BASE_FILTER_FIELDS)
    filters = [item for item in (scheme.get("filters") or []) if isinstance(item, dict)]
    by_key = {_filter_field_sub_key(item): item for item in filters if str(item.get("field") or "") in PGY_BASE_FILTER_FIELDS}
    pgy_plan = screening_plan.get("pgyCollectionPlan") if isinstance(screening_plan.get("pgyCollectionPlan"), dict) else {}
    plan_filters = [item for item in (pgy_plan.get("filters") or []) if isinstance(item, dict)]
    for item in plan_filters:
        field = str(item.get("field") or "")
        key = _filter_field_sub_key(item)
        if field in PGY_BASE_FILTER_FIELDS and key not in by_key:
            by_key[key] = item
    category_filters = [item for key, item in by_key.items() if key[0] == "博主类目"] or [{**PGY_DEFAULT_BASE_FILTERS["category"]}]
    follower_filters = [item for key, item in by_key.items() if key[0] == "粉丝量"] or [{**PGY_DEFAULT_BASE_FILTERS["followers"]}]
    age_filters = [item for key, item in by_key.items() if key[0] == "粉丝年龄"] or [{**PGY_DEFAULT_BASE_FILTERS["age"]}]
    quote_filters = [item for key, item in by_key.items() if key[0] == "合作报价"] or [{**PGY_DEFAULT_BASE_FILTERS["quote"]}]
    return _dedupe_filters([*category_filters, *follower_filters, *age_filters, *quote_filters])


def _extra_filters_for_scheme(scheme: dict[str, Any]) -> list[dict[str, Any]]:
    explicit_extra = scheme.get("additional_filters") or scheme.get("extra_filters")
    if isinstance(explicit_extra, list):
        return _clean_scheme_filters(explicit_extra, allowed_fields=PGY_EXTRA_FILTER_FIELDS)
    filters = [item for item in (scheme.get("filters") or []) if isinstance(item, dict)]
    return _clean_scheme_filters([item for item in filters if str(item.get("field") or "") in PGY_EXTRA_FILTER_FIELDS], allowed_fields=PGY_EXTRA_FILTER_FIELDS)


def _scheme_plan(screening_plan: dict[str, Any], scheme: dict[str, Any], active_additional_filters: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    plan = copy.deepcopy(screening_plan)
    pgy_plan = copy.deepcopy(plan.get("pgyCollectionPlan") or {})
    base_filters = _base_filters_for_scheme(screening_plan, scheme)
    extra_filters = _extra_filters_for_scheme(scheme)
    if active_additional_filters is None:
        active_additional_filters = scheme.get("enabled_additional_filters") or scheme.get("active_additional_filters") or scheme.get("enabled_extra_filters") or scheme.get("active_extra_filters") or []
    enabled_extra_keys = {_filter_key(item) for item in active_additional_filters if isinstance(item, dict)}
    enabled_extra_filters = [item for item in extra_filters if _filter_key(item) in enabled_extra_keys]
    manual_filters = _manual_filters_for_scheme(screening_plan)
    pgy_plan["active_scheme_id"] = scheme.get("scheme_id") or scheme.get("id") or scheme.get("name") or "scheme"
    pgy_plan["active_scheme_name"] = scheme.get("name") or pgy_plan["active_scheme_id"]
    pgy_plan["active_scheme_goal"] = scheme.get("goal") or ""
    pgy_plan["required_filters"] = base_filters
    pgy_plan["additional_filters"] = extra_filters
    pgy_plan["enabled_additional_filters"] = enabled_extra_filters
    pgy_plan["base_filters"] = base_filters
    pgy_plan["extra_filters"] = extra_filters
    pgy_plan["enabled_extra_filters"] = enabled_extra_filters
    pgy_plan["manual_filters"] = manual_filters
    pgy_plan["filters"] = _dedupe_filters([*base_filters, *enabled_extra_filters, *manual_filters])
    pgy_plan["target_count_range"] = scheme.get("target_count_range") or pgy_plan.get("target_count_range") or ""
    pgy_plan["expand_if_too_few"] = scheme.get("expand_if_too_few") or []
    pgy_plan["narrow_if_too_many"] = scheme.get("narrow_if_too_many") or []
    plan["pgyCollectionPlan"] = pgy_plan
    return plan


def _creator_dedupe_key(creator: dict[str, Any]) -> str:
    for key in ("creator_id", "pgy_blogger_id", "pgy_url", "xiaohongshu_id", "nickname"):
        value = str(creator.get(key) or "").strip()
        if value:
            return f"{key}:{value}"
    return str(id(creator))


def _merge_raw_payload(*payloads: Any) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for payload in payloads:
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except Exception:
                payload = {"text": payload}
        if isinstance(payload, dict):
            merged.update(payload)
    return merged


def _merge_creator_records(base: dict[str, Any], extra: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in extra.items():
        if key == "raw_payload":
            continue
        if value not in (None, ""):
            merged[key] = value
    raw_payload = _merge_raw_payload(base.get("raw_payload"), extra.get("raw_payload"))
    if raw_payload:
        merged["raw_payload"] = raw_payload
    return merged


def _export_result_items(export_result: Any) -> list[dict[str, Any]]:
    if not isinstance(export_result, dict):
        return []
    if isinstance(export_result.get("items"), list):
        return [item for item in export_result["items"] if isinstance(item, dict)]
    return [export_result]


def _creators_from_export_result(export_result: Any) -> list[dict[str, Any]]:
    creators: list[dict[str, Any]] = []
    for item in _export_result_items(export_result):
        parsed = item.get("parsed")
        if not parsed and item.get("path"):
            parsed = parse_export_file(item["path"])
            item["parsed"] = parsed
        if isinstance(parsed, dict):
            creators.extend(parsed.get("creators") or [])
    return creators


def _merge_export_creators(collected_creators: list[dict[str, Any]], export_result: Any) -> list[dict[str, Any]]:
    export_creators = _creators_from_export_result(export_result)
    if not export_creators:
        return collected_creators
    by_key: dict[str, dict[str, Any]] = {}
    for creator in collected_creators:
        by_key[_creator_dedupe_key(creator)] = creator
    nickname_index = {
        str(creator.get("nickname") or "").strip(): key
        for key, creator in by_key.items()
        if creator.get("nickname")
    }
    for export_creator in export_creators:
        key = _creator_dedupe_key(export_creator)
        existing_key = key if key in by_key else nickname_index.get(str(export_creator.get("nickname") or "").strip())
        if existing_key:
            by_key[existing_key] = _merge_creator_records(by_key[existing_key], export_creator)
        else:
            by_key[key] = export_creator
    return list(by_key.values())


def _parse_count_range(value: Any, default: tuple[int, int] = (50, 500)) -> tuple[int, int]:
    text = str(value or "")
    numbers = [int(item) for item in re.findall(r"\d+", text)]
    if len(numbers) >= 2:
        return min(numbers[0], numbers[1]), max(numbers[0], numbers[1])
    if len(numbers) == 1:
        number = numbers[0]
        return max(1, int(number * 0.5)), max(number, int(number * 1.5))
    return default


def _scheme_expected_count(scheme: dict[str, Any], base_target: Any = None, history: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    target_min, target_max = _parse_count_range(scheme.get("target_count_range") or base_target)
    filters = scheme.get("filters") or scheme.get("required_filters") or scheme.get("base_filters") or []
    enabled_additional = scheme.get("enabled_additional_filters") or scheme.get("enabled_extra_filters") or []
    if enabled_additional:
        filters = [*filters, *enabled_additional]
    strong_fields = {"合作报价", "预估阅读单价", "预估互动单价", "合作订单数", "外溢进店单价", "近期合作品牌", "按博主粉丝推荐"}
    medium_fields = {"粉丝年龄", "粉丝地域", "地域", "家庭身份", "职业身份", "特色背景", "母婴阶段", "平台推荐", "行业推荐博主"}
    broad_fields = {"营销目标", "博主类目"}
    strong = sum(1 for item in filters if item.get("field") in strong_fields)
    medium = sum(1 for item in filters if item.get("field") in medium_fields)
    broad = sum(1 for item in filters if item.get("field") in broad_fields)
    other = max(0, len(filters) - strong - medium - broad)
    precision = 1 + strong * 0.28 + medium * 0.16 + other * 0.08 - max(0, broad - 1) * 0.05
    center = (target_min + target_max) / 2
    expected_center = int(max(20, min(800, center / max(0.65, precision))))
    tolerance = 0.45 if len(filters) >= 4 else 0.6
    expected_min = max(10, int(expected_center * (1 - tolerance)))
    expected_max = min(1200, max(expected_min + 10, int(expected_center * (1 + tolerance))))
    expected = {
        "expected_min": expected_min,
        "expected_max": expected_max,
        "expected_center": expected_center,
        "predicted_source": "formula",
        "target_min": target_min,
        "target_max": target_max,
        "basis": {
            "filter_count": len(filters),
            "strong_filter_count": strong,
            "medium_filter_count": medium,
            "broad_filter_count": broad,
            "precision_factor": round(precision, 2),
            "tolerance": tolerance,
        },
    }
    history_counts = [
        int(item["actual_recommend_count"])
        for item in (history or [])
        if item.get("actual_recommend_count") is not None and not item.get("actual_count_is_lower_bound")
    ]
    if history_counts:
        recent = history_counts[:8]
        sorted_counts = sorted(recent)
        median = sorted_counts[len(sorted_counts) // 2]
        average = sum(recent) / len(recent)
        learned_center = int((median * 0.65) + (average * 0.35))
        blended_center = int(expected_center * 0.35 + learned_center * 0.65)
        expected["expected_center"] = max(10, min(1200, blended_center))
        expected["expected_min"] = max(10, int(expected["expected_center"] * (1 - tolerance)))
        expected["expected_max"] = min(1200, max(expected["expected_min"] + 10, int(expected["expected_center"] * (1 + tolerance))))
        expected["predicted_source"] = "history_blended"
        expected["history"] = {
            "sample_size": len(recent),
            "recent_actual_counts": recent,
            "median": median,
            "average": round(average, 2),
            "learned_center": learned_center,
        }
    return expected


def _evaluate_scheme_count(expected: dict[str, Any], actual: Any, lower_bound: bool = False) -> dict[str, Any]:
    if actual is None:
        return {"status": "unknown", "should_collect": True, "message": "未读取到蒲公英推荐博主数，允许继续采集但标记为待复核"}
    actual_count = int(actual)
    expected_min = int(expected["expected_min"])
    expected_max = int(expected["expected_max"])
    target_max = int(expected.get("target_max") or expected_max)
    allowed_max = max(expected_max, target_max)
    if actual_count <= 0:
        return {"status": "too_few", "should_collect": False, "message": f"实际推荐 {actual_count}，当前方案无可采集达人，切换下一套方案"}
    if actual_count < expected_min:
        return {"status": "too_few", "should_collect": True, "message": f"实际推荐 {actual_count}，低于预期 {expected_min}-{expected_max}，先采集少量结果；若页面无结果则自动放宽条件重试"}
    if actual_count > allowed_max or (lower_bound and actual_count >= allowed_max):
        return {"status": "too_many", "should_collect": False, "message": f"实际推荐 {actual_count}{'+' if lower_bound else ''}，高于可采集上限 {allowed_max}，切换收紧后的下一套方案"}
    return {"status": "ok", "should_collect": True, "message": f"实际推荐 {actual_count}，不超过可采集上限 {allowed_max}，可进入采集"}


@app.post("/api/pgy/collect/batch")
def api_pgy_collect_batch(payload: BatchCollectPayload) -> dict[str, Any]:
    project_id = payload.project_id or "youdao_001"
    project = get_project(project_id) or {}
    brief = project.get("brief") or ""
    screening_plan = payload.screening_plan or _normalize_project_screening_plan(project.get("screening_plan")) or {}
    pgy_plan = screening_plan.get("pgyCollectionPlan") if isinstance(screening_plan, dict) else {}
    if isinstance(pgy_plan, dict):
        pgy_plan = _normalize_scheme_filter_structure(pgy_plan)
        screening_plan = {**screening_plan, "pgyCollectionPlan": pgy_plan}
    all_schemes = pgy_plan.get("schemes") if isinstance(pgy_plan, dict) else []
    selected_ids = {str(item) for item in payload.scheme_ids or []}
    schemes = [
        scheme
        for scheme in (all_schemes or [])
        if isinstance(scheme, dict) and (not selected_ids or str(scheme.get("scheme_id") or scheme.get("id") or scheme.get("name")) in selected_ids)
    ]
    use_multi_scheme = bool(payload.multi_scheme and payload.apply_filters and schemes)
    batch_id = create_batch(project_id, payload.source_url)
    scheme_results: list[dict[str, Any]] = []
    raw_creators_by_key: dict[str, dict[str, Any]] = {}
    memory_ids_by_scheme: dict[str, str] = {}
    applied_filters: list[dict[str, Any]] = []
    skipped_filters_base: list[dict[str, Any]] = []
    selected_metrics: list[dict[str, Any]] = []
    skipped_metrics: list[dict[str, Any]] = []
    export_results: list[dict[str, Any]] = []
    collection_plan: dict[str, Any] | None = None
    detail_collection = ""
    last_error = ""

    def run_once(plan: dict[str, Any], scheme: dict[str, Any] | None = None, reset_filters: bool = False, preflight_only: bool = False) -> dict[str, Any]:
        result = collect_visible_list(
            brief=brief,
            screening_plan=plan,
            apply_filters=payload.apply_filters,
            include_details=payload.include_details,
            collect_profile_urls=payload.collect_profile_urls,
            export_metrics=payload.export_metrics,
            limit=payload.limit,
            reset_filters=reset_filters,
            preflight_only=preflight_only,
        )
        scheme_id = str((scheme or {}).get("scheme_id") or (scheme or {}).get("id") or (scheme or {}).get("name") or "default")
        scheme_name = str((scheme or {}).get("name") or scheme_id)
        result["scheme_id"] = scheme_id
        result["scheme_name"] = scheme_name
        return result

    if use_multi_scheme:
        for index, scheme in enumerate(schemes):
            scheme_id = str(scheme.get("scheme_id") or scheme.get("id") or scheme.get("name") or "scheme")
            active_additional_filters: list[dict[str, Any]] = []
            plan_for_scheme = _scheme_plan(screening_plan, scheme, active_additional_filters)
            plan_filters = (plan_for_scheme.get("pgyCollectionPlan") or {}).get("filters") or []
            history = scheme_count_memory(project_id, scheme_id, plan_filters)
            expected_count = _scheme_expected_count({**scheme, "filters": plan_filters}, pgy_plan.get("target_count_range") if isinstance(pgy_plan, dict) else None, history)
            preflight_result = (
                run_once(plan_for_scheme, scheme, reset_filters=True, preflight_only=True)
                if payload.preflight
                else {"ok": True, "actual_recommend_count": None, "actual_count_text": "", "actual_count_is_lower_bound": False}
            )
            evaluation = _evaluate_scheme_count(
                expected_count,
                preflight_result.get("actual_recommend_count"),
                bool(preflight_result.get("actual_count_is_lower_bound")),
            )
            preflight_steps = [
                {
                    "stage": "required",
                    "label": "必备筛选条件",
                    "added_filter": None,
                    "active_additional_filters": [],
                    "actual_recommend_count": preflight_result.get("actual_recommend_count"),
                    "actual_count_text": preflight_result.get("actual_count_text"),
                    "actual_count_is_lower_bound": bool(preflight_result.get("actual_count_is_lower_bound")),
                    "evaluation": evaluation,
                    "filters": plan_filters,
                }
            ]
            if payload.preflight and evaluation.get("status") == "too_many" and not payload.collect_out_of_range:
                for additional_filter in _extra_filters_for_scheme(scheme):
                    active_additional_filters = [*active_additional_filters, additional_filter]
                    plan_for_scheme = _scheme_plan(screening_plan, scheme, active_additional_filters)
                    plan_filters = (plan_for_scheme.get("pgyCollectionPlan") or {}).get("filters") or []
                    expected_count = _scheme_expected_count(
                        {**scheme, "filters": plan_filters, "enabled_additional_filters": active_additional_filters},
                        pgy_plan.get("target_count_range") if isinstance(pgy_plan, dict) else None,
                        history,
                    )
                    preflight_result = run_once(plan_for_scheme, scheme, reset_filters=False, preflight_only=True)
                    evaluation = _evaluate_scheme_count(
                        expected_count,
                        preflight_result.get("actual_recommend_count"),
                        bool(preflight_result.get("actual_count_is_lower_bound")),
                    )
                    preflight_steps.append(
                        {
                            "stage": "additional",
                            "label": "附加筛选条件",
                            "added_filter": additional_filter,
                            "active_additional_filters": active_additional_filters,
                            "actual_recommend_count": preflight_result.get("actual_recommend_count"),
                            "actual_count_text": preflight_result.get("actual_count_text"),
                            "actual_count_is_lower_bound": bool(preflight_result.get("actual_count_is_lower_bound")),
                            "evaluation": evaluation,
                            "filters": plan_filters,
                        }
                    )
                    if evaluation.get("status") != "too_many":
                        break
            should_collect = bool(evaluation.get("should_collect") or payload.collect_out_of_range)
            scheme_result = (
                run_once(plan_for_scheme, scheme, reset_filters=not payload.preflight, preflight_only=False)
                if should_collect
                else {
                    "ok": False,
                    "scheme_id": str(scheme.get("scheme_id") or scheme.get("id") or scheme.get("name") or "scheme"),
                    "scheme_name": str(scheme.get("name") or scheme.get("scheme_id") or scheme.get("id") or "scheme"),
                    "message": evaluation["message"],
                    "creators": [],
                    "collection_plan": preflight_result.get("collection_plan"),
                    "applied_filters": preflight_result.get("applied_filters") or [],
                    "skipped_filters": preflight_result.get("skipped_filters") or [],
                    "selected_metrics": preflight_result.get("selected_metrics") or [],
                    "skipped_metrics": preflight_result.get("skipped_metrics") or [],
                    "export_result": {"status": "skipped", "message": "数量预检未通过，未执行实际列表采集"},
                }
            )
            scheme_result["preflight"] = {
                "expected": expected_count,
                "memory": {"sample_size": len(history), "latest": history[0] if history else None},
                "steps": preflight_steps,
                "active_additional_filters": active_additional_filters,
                "actual_recommend_count": preflight_result.get("actual_recommend_count"),
                "actual_count_text": preflight_result.get("actual_count_text"),
                "actual_count_error": preflight_result.get("actual_count_error"),
                "actual_count_is_lower_bound": bool(preflight_result.get("actual_count_is_lower_bound")),
                "evaluation": evaluation,
                "collected_after_preflight": should_collect,
                "forced_collect": bool(payload.collect_out_of_range and not evaluation.get("should_collect")),
            }
            scheme_creators = scheme_result.get("creators") or []
            memory = record_scheme_count_memory(
                project_id,
                scheme,
                expected_count,
                scheme_result["preflight"],
                collected_count=len(scheme_creators),
                accepted_count=0,
                rejected_count=0,
            )
            memory_ids_by_scheme[scheme_result["scheme_id"]] = memory["memory_id"]
            for creator in scheme_creators:
                creator = {**creator, "collection_scheme_id": scheme_result["scheme_id"], "collection_scheme_name": scheme_result["scheme_name"]}
                raw_creators_by_key.setdefault(_creator_dedupe_key(creator), creator)
            applied_filters.extend(scheme_result.get("applied_filters") or [])
            skipped_filters_base.extend(scheme_result.get("skipped_filters") or [])
            selected_metrics.extend(scheme_result.get("selected_metrics") or [])
            skipped_metrics.extend(scheme_result.get("skipped_metrics") or [])
            if scheme_result.get("export_result"):
                export_results.append({"scheme_id": scheme_result["scheme_id"], **scheme_result["export_result"]})
            collection_plan = collection_plan or scheme_result.get("collection_plan")
            detail_collection = detail_collection or scheme_result.get("detail_collection") or ""
            if not scheme_result.get("ok"):
                last_error = scheme_result.get("message") or last_error
            scheme_results.append(
                {
                    "scheme_id": scheme_result["scheme_id"],
                    "scheme_name": scheme_result["scheme_name"],
                    "ok": bool(scheme_result.get("ok")),
                    "message": scheme_result.get("message"),
                    "collected_count": len(scheme_creators),
                    "preflight": scheme_result.get("preflight"),
                    "applied_filters": scheme_result.get("applied_filters") or [],
                    "skipped_filters": scheme_result.get("skipped_filters") or [],
                    "collection_plan": scheme_result.get("collection_plan"),
                    "export_result": scheme_result.get("export_result"),
                }
            )
            if scheme_creators:
                break
        result = {
            "ok": bool(raw_creators_by_key),
            "message": last_error if not raw_creators_by_key else "",
            "creators": list(raw_creators_by_key.values()),
            "collection_plan": {"multi_scheme": True, "schemes": scheme_results, "base_plan": pgy_plan},
            "applied_filters": applied_filters,
            "skipped_filters": skipped_filters_base,
            "selected_metrics": selected_metrics,
            "skipped_metrics": skipped_metrics,
            "detail_collection": detail_collection,
            "export_result": {"status": "multi_scheme", "items": export_results},
        }
    else:
        result = run_once(screening_plan, None, reset_filters=payload.apply_filters)

    if not result.get("ok"):
        batch = finish_batch(
            batch_id,
            "failed",
            0,
            0,
            1,
            result.get("message", "采集失败"),
            collection_plan=result.get("collection_plan"),
            applied_filters=result.get("applied_filters") or [],
            skipped_filters=result.get("skipped_filters") or [],
            selected_metrics=result.get("selected_metrics") or [],
            skipped_metrics=result.get("skipped_metrics") or [],
            detail_collection=result.get("detail_collection") or "",
        )
        return {
            "ok": False,
            "batch": batch,
            "message": result.get("message"),
            "collection_plan": result.get("collection_plan"),
            "export_result": result.get("export_result"),
            "scheme_results": scheme_results,
            "applied_filters": result.get("applied_filters") or [],
            "skipped_filters": result.get("skipped_filters") or [],
            "selected_metrics": result.get("selected_metrics") or [],
            "skipped_metrics": result.get("skipped_metrics") or [],
        }
    collected_creators = _merge_export_creators(result.get("creators") or [], result.get("export_result"))
    hard_filters = screening_plan.get("collectionHardFilters") or (screening_plan.get("pgyCollectionPlan") or {}).get("hard_filters") or screening_plan.get("hardFilters") or []
    _, rejected_by_hard_filters = _filter_creators_by_hard_filters(project_id, collected_creators, hard_filters)
    hard_filter_issue_by_key = {
        _creator_dedupe_key(item): item.get("issues") or []
        for item in rejected_by_hard_filters
    }
    creators = []
    for creator in collected_creators:
        issues = hard_filter_issue_by_key.get(_creator_dedupe_key(creator), [])
        if issues:
            raw_payload = creator.get("raw_payload") if isinstance(creator.get("raw_payload"), dict) else {}
            creator = {
                **creator,
                "collection_hard_filter_passed": False,
                "collection_hard_filter_issues": issues,
                "raw_payload": {
                    **raw_payload,
                    "collection_hard_filter_passed": False,
                    "collection_hard_filter_issues": issues,
                },
            }
        else:
            raw_payload = creator.get("raw_payload") if isinstance(creator.get("raw_payload"), dict) else {}
            creator = {
                **creator,
                "collection_hard_filter_passed": True,
                "collection_hard_filter_issues": [],
                "raw_payload": {
                    **raw_payload,
                    "collection_hard_filter_passed": True,
                    "collection_hard_filter_issues": [],
                },
            }
        creators.append(creator)
    if memory_ids_by_scheme:
        accepted_by_scheme: dict[str, int] = {}
        rejected_by_scheme: dict[str, int] = {}
        collected_by_scheme: dict[str, int] = {}
        for creator in collected_creators:
            scheme_id = str(creator.get("collection_scheme_id") or "")
            if scheme_id:
                collected_by_scheme[scheme_id] = collected_by_scheme.get(scheme_id, 0) + 1
        for creator in collected_creators:
            scheme_id = str(creator.get("collection_scheme_id") or "")
            if not scheme_id:
                continue
            accepted_by_scheme[scheme_id] = accepted_by_scheme.get(scheme_id, 0) + 1
        for scheme_id, memory_id in memory_ids_by_scheme.items():
            update_scheme_count_memory(
                memory_id,
                accepted_count=accepted_by_scheme.get(scheme_id, 0),
                rejected_count=rejected_by_scheme.get(scheme_id, 0),
                collected_count=collected_by_scheme.get(scheme_id, 0),
            )
    hard_filter_skips = [
        {
            "field": "筛选工作台标记",
            "value": item.get("nickname") or item.get("creator_id") or "",
            "message": "；".join(item.get("issues") or []),
            "creator_id": item.get("creator_id"),
        }
        for item in rejected_by_hard_filters
    ]
    skipped_filters = [*(result.get("skipped_filters") or []), *hard_filter_skips]
    if not creators:
        batch = finish_batch(
            batch_id,
            "failed",
            len(collected_creators),
            0,
            1,
            "未采集到有效达人",
            collection_plan=result.get("collection_plan"),
            applied_filters=result.get("applied_filters") or [],
            skipped_filters=skipped_filters,
            selected_metrics=result.get("selected_metrics") or [],
            skipped_metrics=result.get("skipped_metrics") or [],
            detail_collection=result.get("detail_collection") or "",
        )
        return {
            "ok": False,
            "batch": batch,
            "message": batch.get("error_message") or "未采集到有效达人",
            "rejected_by_hard_filters": rejected_by_hard_filters,
            "collection_plan": result.get("collection_plan"),
            "export_result": result.get("export_result"),
            "scheme_results": scheme_results,
            "applied_filters": result.get("applied_filters") or [],
            "skipped_filters": skipped_filters,
            "selected_metrics": result.get("selected_metrics") or [],
            "skipped_metrics": result.get("skipped_metrics") or [],
        }
    creator_ids = []
    for creator in creators:
        saved = upsert_creator(project_id, creator, score=False)
        creator_ids.append(saved["creator_id"])
    scoring = score_project(project_id, creator_ids=creator_ids, trigger_source="pgy_collect")
    batch = finish_batch(
        batch_id,
        "success",
        len(collected_creators),
        len(creators),
        0,
        collection_plan=result.get("collection_plan"),
        applied_filters=result.get("applied_filters") or [],
        skipped_filters=skipped_filters,
        selected_metrics=result.get("selected_metrics") or [],
        skipped_metrics=result.get("skipped_metrics") or [],
        detail_collection=result.get("detail_collection") or "",
    )
    rejected_count = len(rejected_by_hard_filters)
    return {
        "ok": True,
        "batch": batch,
        "creators": creators,
        "scoring": scoring,
        "message": f"蒲公英采集完成，采到 {len(collected_creators)} 个，已全部入库；{rejected_count} 个将在筛选工作台标记为条件不符并按档位区分",
        "collection_plan": result.get("collection_plan"),
        "export_result": result.get("export_result"),
        "scheme_results": scheme_results,
        "applied_filters": result.get("applied_filters") or [],
        "skipped_filters": skipped_filters,
        "selected_metrics": result.get("selected_metrics") or [],
        "skipped_metrics": result.get("skipped_metrics") or [],
        "detail_collection": result.get("detail_collection"),
        "rejected_by_hard_filters": rejected_by_hard_filters,
        "flagged_by_hard_filters": rejected_by_hard_filters,
    }


@app.get("/api/pgy/collect/batches/{batch_id}")
def api_pgy_batch(batch_id: str) -> dict[str, Any]:
    for batch in list_batches("youdao_001"):
        if batch["batch_id"] == batch_id:
            return {"batch": batch}
    raise HTTPException(status_code=404, detail={"message": "采集批次不存在"})


@app.get("/api/projects/{project_id}/pgy/scheme-memory")
def api_pgy_scheme_memory(project_id: str, scheme_id: str = Query(default=""), limit: int = Query(default=30)) -> dict[str, Any]:
    return {"memory": list_scheme_count_memory(project_id, scheme_id, limit=limit)}


@app.get("/api/llm/config")
def get_llm_config() -> dict[str, Any]:
    return {"config": read_ai_config()}


@app.post("/api/llm/config")
def save_llm_config(payload: LlmConfigPayload) -> dict[str, Any]:
    config = write_ai_config(payload.model_dump())
    return {"config": config, "message": "API 配置已保存"}


@app.post("/api/llm/test")
def test_llm(payload: LlmConfigPayload | None = None) -> dict[str, Any]:
    result = test_ai_config(payload.model_dump(exclude_unset=True) if payload else {})
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result)
    return result
