from __future__ import annotations

import copy
import json
import re
import threading
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
    DETAIL_PRIORITY_HIGH_VALUES,
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
    update_batch_progress,
    update_scheme_count_memory,
    upsert_creator,
)
from .feishu import FeishuClient, FeishuError, choose_table, column_name, parse_feishu_url
from .feishu_field_agent import analyze_field_mapping, apply_field_mapping, default_source_rows
from .llm_config import chat_json, read_ai_config, test_ai_config, write_ai_config
from .pgy_browser import (
    PGY_BLOGGER_CATEGORY_TAXONOMY,
    PGY_FILTER_CATALOG,
    PGY_MARKETING_GOAL_DEFAULT_METRIC,
    PGY_MARKETING_GOAL_METRIC_PARENT,
    _standard_region_filter_items,
    browser_status,
    build_collection_plan,
    collect_details_for_targets,
    collect_visible_list,
    parse_export_file,
    start_browser,
)


_COLLECT_LOCKS: dict[str, threading.Lock] = {}
_COLLECT_LOCKS_GUARD = threading.Lock()
_COLLECT_CANCEL_EVENTS: dict[str, threading.Event] = {}
_COLLECT_CANCEL_EVENTS_GUARD = threading.Lock()
SCREENING_OPTIMIZE_LLM_MAX_TOKENS = 64000
SCREENING_OPTIMIZE_LLM_TIMEOUT_SECONDS = 300
PGY_COLLECTION_SCHEME_COUNT = 4


def _collect_lock(project_id: str) -> threading.Lock:
    with _COLLECT_LOCKS_GUARD:
        lock = _COLLECT_LOCKS.get(project_id)
        if lock is None:
            lock = threading.Lock()
            _COLLECT_LOCKS[project_id] = lock
        return lock


def _collect_cancel_event(project_id: str) -> threading.Event:
    with _COLLECT_CANCEL_EVENTS_GUARD:
        event = _COLLECT_CANCEL_EVENTS.get(project_id)
        if event is None:
            event = threading.Event()
            _COLLECT_CANCEL_EVENTS[project_id] = event
        return event


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
    limit: int = 1000
    scheme_ids: list[str] = Field(default_factory=list)
    multi_scheme: bool = True
    preflight: bool = True
    collect_out_of_range: bool = False


class BatchCollectStopPayload(BaseModel):
    project_id: str = "youdao_001"


class DetailCollectPayload(BaseModel):
    project_id: str = "youdao_001"
    creator_ids: list[str] = Field(default_factory=list)
    segment: str | None = None
    manual: bool = False
    limit: int = 20


class XhsNoteParsePayload(BaseModel):
    url: str
    note: dict[str, Any] = Field(default_factory=dict)
    creator: dict[str, Any] = Field(default_factory=dict)
    project: dict[str, Any] = Field(default_factory=dict)


def _xhs_note_missing_fields(note: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    if not str(note.get("title") or "").strip():
        missing.append("标题")
    if not str(note.get("content") or "").strip():
        missing.append("正文")
    if not str(note.get("cover_url") or "").strip() and not str(note.get("cover_text") or "").strip():
        missing.append("封面")
    if not (note.get("topics") or []):
        missing.append("话题")

    metrics = note.get("metrics") if isinstance(note.get("metrics"), dict) else {}
    if not str(metrics.get("read_count") or "").strip():
        missing.append("阅读量")
    if not str(metrics.get("like_count") or "").strip():
        missing.append("点赞量")
    if not str(metrics.get("save_count") or "").strip():
        missing.append("收藏量")
    if not str(metrics.get("comment_count") or "").strip():
        missing.append("评论量")
    if not str(metrics.get("share_count") or "").strip():
        missing.append("分享量")
    return missing


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
    project_info = payload.project or {}

    def number(value: Any, default: float = 0) -> float:
        try:
            return float(value or default)
        except (TypeError, ValueError):
            return default

    total_budget = number(project_info.get("budget"), 120000)
    target_count = max(int(number(project_info.get("creatorCount"), 10)), 1)
    expected_single_cost = round(total_budget / target_count, 2)
    single_hard_cap = number(project_info.get("singleBudget"), 20000)

    def match(*keywords: str) -> str | None:
        for name in names:
            if any(keyword in name for keyword in keywords):
                return name
        return None

    def mapping(standard: str, *keywords: str, confidence: float = 0.75) -> dict[str, Any]:
        feishu = match(*keywords)
        return {"standard": standard, "feishu": feishu or "未匹配", "confidence": confidence if feishu else 0.25}

    hard_filters = [
        {"field": "单达人预算硬上限", "condition": "<=", "value": f"报价≤¥{single_hard_cap:g}；参考成本¥{expected_single_cost:g}", "required": True, "feishuField": match("平台报价", "报价", "合作价格")},
        {"field": "已确认粉丝画像", "condition": ">=", "value": "35岁以上占比 40%；仅在已采到该字段时作为确认事实", "required": True, "feishuField": match("34岁以上", "35岁以上")},
        {"field": "近30天效果", "condition": "同T级对比", "value": "曝光、阅读、互动需达到同T级正常线，明显低于P25视为数据风险", "required": True, "feishuField": match("曝光", "阅读", "互动")},
        {"field": "预算效果效率", "condition": "核算", "value": "用报价、CPM、CPC、CPE推导单达人可获得曝光/阅读/互动总量", "required": True, "feishuField": match("cpm", "cpc", "cpe")},
        {"field": "已确认风险", "condition": "规避", "value": "仅已确认限流、违规、异常流量作为风险；缺字段不等于风险", "required": True, "feishuField": match("限流风险", "流量稳定")},
        {"field": "孩子阶段", "condition": "匹配", "value": "小升初、初中、高中大孩家庭", "required": False, "feishuField": match("孩子年级", "孩子年龄")},
        {"field": "地域优先级", "condition": "优先", "value": "北京、上海 IP 或中产家庭叙事", "required": False, "feishuField": match("IP", "城市", "地域")},
    ]
    weights = {"budget": 15, "fans": 5, "cpe": 20, "engagement": 30, "persona": 20, "content": 10}
    budget_policy = {
        "total_budget": total_budget,
        "target_creator_count": target_count,
        "expected_single_cost": expected_single_cost,
        "single_hard_cap": single_hard_cap,
        "principle": "报价不是越低越好，按报价能换来的曝光/阅读/互动总量和CPM/CPC/CPE效率判断单个达人质量。",
    }
    tier_policy = {
        "principle": "T级由项目类目、Brief和本轮抓取样本动态生成；粉丝量只作为比较坐标，不作为高权重加分。",
        "benchmark_method": "按T级计算近30天曝光、阅读、互动、报价、CPM、CPC、CPE的P25/P50/P75/P90；去除极端低质和极端异常高值只用于计算基准。",
    }
    data_layer_scoring = {
        "purpose": "找博主列表页数据已经足够做数据层分级；详情页用于高优先级达人做人设、内容调性和笔记证据分析。",
        "core_metrics": ["报价", "近30天曝光中位数", "近30天阅读中位数", "近30天互动中位数", "CPM", "CPC", "CPE"],
        "levels": [
            {"level": "S", "rule": "近30天曝光/阅读/互动至少两项达到同T级P75以上，且CPM/CPC/CPE整体达标，报价未超硬上限。"},
            {"level": "A", "rule": "近30天核心数据大多达到同T级P50-P75，或单项突出且成本效率合理。"},
            {"level": "B", "rule": "数据接近P50或略低，没有明确硬伤但优势不明显。"},
            {"level": "C", "rule": "多项近30天核心数据低于同T级P25，或成本效率明显偏差，或报价超硬上限。"},
        ],
    }
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
    brief_text = payload.brief or ""
    emphasizes_region = _brief_mentions_region_priority(brief_text)
    wants_parent = any(keyword in brief_text for keyword in ["母婴", "亲子", "妈妈", "爸爸", "孩子", "大孩", "家庭"])
    wants_education = any(keyword in brief_text for keyword in ["教育", "学习", "升学", "初中", "高中", "小升初", "答疑", "老师", "教师"])
    strong_preferences = [
        "高知/教师/教育规划人设",
        "小升初、初中、高中等大孩家庭",
        "自然流量效率较好，CPC/CPE可解释",
    ]
    if emphasizes_region:
        strong_preferences.append("北京/上海IP或一线中产家庭叙事")
    backend_mappable_filters = []
    if wants_education:
        backend_mappable_filters.append({"field": "博主类目", "value": "教育", "mapping_type": "direct", "confidence": "high", "business_requirement": "教育/学习场景相关"})
    if wants_parent:
        backend_mappable_filters.append({"field": "博主类目", "value": "母婴", "mapping_type": "proxy", "confidence": "low", "business_requirement": "亲子/家庭场景补量"})
    backend_mappable_filters.extend(
        [
            {"field": "粉丝量", "value": "1万～10万", "mapping_type": "direct", "confidence": "medium", "business_requirement": "控制中腰部量级与预算"},
            {"field": "粉丝年龄", "value": "35～44 占比高", "mapping_type": "direct", "confidence": "high", "business_requirement": "家长决策人群"},
            {"field": "合作报价", "value": f"图文笔记：0.1万～{single_hard_cap / 10000:g}万", "mapping_type": "direct", "confidence": "high", "business_requirement": "单达人预算上限"},
        ]
    )
    if emphasizes_region:
        backend_mappable_filters.append({"field": "地域", "value": "北京/上海", "mapping_type": "direct", "confidence": "medium", "business_requirement": "地域优先"})
    brief_decomposition = {
        "brief_facts": [
            {"category": "budget", "fact": f"单达人预算上限约 ¥{single_hard_cap:g}，参考单人成本 ¥{expected_single_cost:g}"},
            {"category": "audience", "fact": "优先家长决策人群，粉丝年龄以35岁以上为重要信号"},
            {"category": "persona", "fact": "教育、亲子、家庭教育决策场景是核心相关方向"},
            {"category": "performance", "fact": "需要结合报价、CPM/CPC/CPE和近30天曝光/阅读/互动判断投流效果"},
        ],
        "must_have_requirements": [
            "报价不超过单达人预算硬上限",
            "粉丝年龄与家长决策人群相关",
            "账号内容或人设需要与教育/亲子/家庭教育场景有明确证据",
        ],
        "strong_preferences": strong_preferences,
        "negative_constraints": [
            "不优先孕期、低幼辅食、低龄早教等与大孩教育决策弱相关账号",
            "不优先纯生活方式妈妈或泛家庭日常账号",
            "不优先护肤、养生、家居等只挂母婴标签但教育场景弱的账号",
            "不优先缺少教育内容证据、仅靠类目关键词命中的账号",
        ],
        "backend_mappable_filters": backend_mappable_filters,
        "proxy_filters": [
            {
                "business_intent": "大孩教育家庭",
                "proxy_field": "博主类目",
                "proxy_value": "母婴",
                "proxy_risk": "会混入孕期、低幼、泛家庭、生活方式妈妈和非教育决策账号",
                "confidence": "low",
                "max_quota_policy": "只能作为补量池，不能吞掉主配额",
            }
        ] if wants_parent else [],
        "post_score_rules": [
            {"rule_name": "教育决策场景相关度", "required_evidence": ["达人类目", "主页简介", "近期笔记标题", "笔记文案"], "fallback_action": "证据不足则降档并待复核", "score_impact": "high"},
            {"rule_name": "大孩家庭相关度", "required_evidence": ["孩子年龄", "孩子年级", "近期内容主题"], "fallback_action": "缺失不视为通过，最多备选", "score_impact": "high"},
            {"rule_name": "高知/教师人设", "required_evidence": ["主页简介", "身份标签", "长期内容主题"], "fallback_action": "仅关键词命中不加高分", "score_impact": "medium"},
            {"rule_name": "投流效率", "required_evidence": ["报价", "CPM", "CPC", "CPE", "阅读/互动中位数"], "fallback_action": "效率缺失时保留但不进入强推荐", "score_impact": "high"},
        ],
        "manual_review_rules": [
            "高知家庭、教师身份、国际学校/住校生/学区房叙事需人工确认",
            "母婴补量池达人必须复核是否真有大孩教育场景",
            "类目相关但内容证据不足的达人不得直接进入强推荐",
        ],
    }
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
            "role": "primary",
            "precision_level": "high",
            "target_quota": 50,
            "max_quota": 60,
            "goal": "优先找到教育/升学场景强匹配达人",
            "target_count_range": "50-2000",
            "required_filters": [
                {"field": "博主类目", "value": "教育", "sub_value": "家庭教育", "reason": "必备筛选：教育学习场景强相关"},
                {"field": "博主类目", "value": "教育", "sub_value": "k12教育", "reason": "必备筛选：覆盖K12/小升初/初高中学习场景"},
                {"field": "粉丝量", "value": "1万以上", "reason": "必备筛选：优先有基础粉丝量达人；只设下限避免误卡上限", "control_type": "preset_or_number_range", "min": 10000, "range_policy": "min_only"},
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
            "role": "supplement",
            "precision_level": "low",
            "target_quota": 20,
            "max_quota": 30,
            "precision_warning": "母婴是宽代理，只能表示可能有家庭/亲子场景，不能代表已满足大孩教育家庭要求。",
            "goal": "补充真实家庭陪伴、亲子教育、家长口吻达人",
            "target_count_range": "50-2000",
            "required_filters": [
                {"field": "博主类目", "value": "母婴", "sub_value": "育儿经验", "reason": "覆盖家长和亲子账号"},
                {"field": "博主类目", "value": "母婴", "sub_value": "早教", "reason": "补充亲子教育/启蒙相关账号，需采后复核是否符合大孩教育"},
                {"field": "粉丝量", "value": "1万以上", "reason": "必备筛选：优先有基础粉丝量达人；只设下限避免误卡上限", "control_type": "preset_or_number_range", "min": 10000, "range_policy": "min_only"},
                {"field": "粉丝年龄", "value": "35～44 占比高", "reason": "必备筛选：家长决策人群优先", "control_type": "dropdown"},
                {"field": "合作报价", "value": "图文笔记：0.1万～2万", "reason": "必备筛选：控制单达人预算", "control_type": "subfield_preset_or_number_range", "sub_field": "图文笔记", "max": 20000},
            ],
            "additional_filters": [
                {"field": "阅读中位数", "value": "0.5万以上", "reason": "附加筛选：数量过多时提高阅读门槛；只设下限", "control_type": "preset_or_number_range", "min": 5000, "range_policy": "min_only"},
            ],
            "filters": [],
            "expand_if_too_few": ["放宽粉丝量级", "放宽合作报价上限但保留评分扣分"],
            "narrow_if_too_many": ["启用阅读中位数门槛"],
        },
        {
            "scheme_id": "efficiency_value",
            "name": "性价比转化池",
            "role": "supplement",
            "precision_level": "medium",
            "target_quota": 20,
            "max_quota": 30,
            "goal": "找到预算友好、数据效率较好的测评/卖货型达人",
            "target_count_range": "50-2000",
            "required_filters": [
                {"field": "博主类目", "value": "教育", "sub_value": "k12教育", "reason": "保持教育场景相关"},
                {"field": "博主类目", "value": "教育", "sub_value": "学习日常", "reason": "补充学习效率/学习工具内容型达人"},
                {"field": "粉丝量", "value": "0.5万以上", "reason": "必备筛选：扩大低预算中腰部达人；只设下限避免误卡上限", "control_type": "preset_or_number_range", "min": 5000, "range_policy": "min_only"},
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
        {
            "scheme_id": "education_parent_cross",
            "name": "教育+亲子交叉话题池",
            "role": "supplement",
            "precision_level": "medium",
            "target_quota": 10,
            "max_quota": 20,
            "goal": "补充兼具教育内容和真实家庭叙事的曝光型达人",
            "target_count_range": "50-2000",
            "required_filters": [
                {"field": "博主类目", "value": "教育", "sub_value": "家庭教育", "reason": "保留教育产品场景相关性"},
                {"field": "博主类目", "value": "教育", "sub_value": "k12教育", "reason": "覆盖K12/大孩学习场景"},
                {"field": "博主类目", "value": "母婴", "sub_value": "育儿经验", "reason": "覆盖亲子和家庭教育叙事"},
                {"field": "粉丝量", "value": "1万以上", "reason": "保证基础讨论度；只设下限避免误卡上限", "control_type": "preset_or_number_range", "min": 10000, "range_policy": "min_only"},
                {"field": "粉丝年龄", "value": "35～44 占比高", "reason": "优先命中家长决策人群", "control_type": "dropdown"},
                {"field": "合作报价", "value": "图文笔记：0.1万～2万", "reason": "满足单达人预算上限", "control_type": "subfield_preset_or_number_range", "sub_field": "图文笔记", "max": 20000},
            ],
            "additional_filters": [
                {"field": "曝光中位数", "value": "1万以上", "reason": "结果过多时优先保留曝光基础较好的达人；只设下限", "control_type": "preset_or_number_range", "min": 10000, "range_policy": "min_only"},
                {"field": "阅读中位数", "value": "0.5万以上", "reason": "进一步提高常规阅读稳定性；只设下限", "control_type": "preset_or_number_range", "min": 5000, "range_policy": "min_only"},
            ],
            "filters": [],
            "expand_if_too_few": ["拆回教育单类目或母婴单类目扩量", "放宽粉丝量级"],
            "narrow_if_too_many": ["启用曝光中位数门槛", "启用阅读中位数门槛"],
        },
    ]
    scoring_criteria = {
        "purpose": "用于采集后对达人做两阶段评分：先用找博主列表页数据做数据层分级，再用达人详情页、主页简介、笔记标题/文案做大模型人设内容判断。",
        "budget_policy": budget_policy,
        "tier_policy": tier_policy,
        "data_layer_scoring": data_layer_scoring,
        "hard_rules": hard_filters,
        "dimension_weights": weights,
        "dimensions": [
            {"key": "budget", "name": "预算效果核算", "weight": weights["budget"], "positive": ["报价未超硬上限", "报价能换来的曝光/阅读/互动容量达标"], "negative": ["报价超硬上限", "高价但CPM/CPC/CPE和效果容量不足"]},
            {"key": "fans", "name": "粉丝T级坐标", "weight": weights["fans"], "positive": ["用T级校准同量级预期"], "negative": ["不因粉丝多直接加分；不因缺画像直接淘汰"]},
            {"key": "cpe", "name": "CPM/CPC/CPE效率", "weight": weights["cpe"], "positive": ["CPM/CPC/CPE达到同T级正常或优秀水平"], "negative": ["成本效率明显低于同T级标准"]},
            {"key": "engagement", "name": "近30天曝光阅读互动", "weight": weights["engagement"], "positive": ["近30天曝光、阅读、互动达到同T级P50/P75"], "negative": ["多项低于P25或明显异常"]},
            {"key": "persona", "name": "人设与 Brief 匹配", "weight": weights["persona"], "positive": ["主页简介、详情页、笔记标题/文案能证明大孩家长、教育规划等场景"], "negative": ["只有关键词或偶发内容，缺少长期证据"]},
            {"key": "content", "name": "内容调性与笔记证据", "weight": weights["content"], "positive": ["整体内容调性稳定，笔记标题/正文有真实场景"], "negative": ["内容泛化、硬广感强或与Brief场景弱相关"]},
        ],
        "recommendation_rules": [
            {"level": "强推荐", "condition": "硬性条件通过且综合分≥85，至少一个核心人设或效率优势明显"},
            {"level": "推荐", "condition": "硬性条件通过且综合分≥75，主要指标匹配"},
            {"level": "备选", "condition": "存在一项短板但可通过价格、内容角度或补数据复核"},
            {"level": "不推荐", "condition": "命中硬性淘汰项、流量风险高或项目场景弱相关"},
        ],
        "evidence_fields": ["报价", "粉丝量T级", "近30天曝光中位数", "近30天阅读中位数", "近30天互动中位数", "CPM", "CPC", "CPE", "主页简介", "笔记标题", "笔记文案", "内容调性", "已确认风险"],
        "reason_requirements": ["说明数据层级", "说明预算效果核算", "引用人设/内容证据", "指出已确认风险和评分置信度"],
    }
    return {
        "briefType": "complex",
        "budgetPolicy": budget_policy,
        "tierPolicy": tier_policy,
        "dataLayerScoring": data_layer_scoring,
        "hardFilters": hard_filters,
        "briefDecomposition": brief_decomposition,
        "scoringWeights": weights,
        "scoringCriteria": scoring_criteria,
        "fieldMappings": field_mappings,
        "pgyCollectionPlan": pgy_plan,
        "summary": "已生成两阶段评分口径：先用找博主列表页的报价、近30天曝光/阅读/互动、CPM/CPC/CPE和动态T级做数据层分级，再用详情页与笔记内容证据做人设和内容质量分析。",
    }


def _ensure_pgy_scheme_count(pgy_plan: dict[str, Any], fallback_plan: dict[str, Any]) -> dict[str, Any]:
    plan = copy.deepcopy(pgy_plan or {})
    schemes = [copy.deepcopy(item) for item in (plan.get("schemes") or []) if isinstance(item, dict)]
    fallback_schemes = [copy.deepcopy(item) for item in ((fallback_plan or {}).get("schemes") or []) if isinstance(item, dict)]
    seen = {str(item.get("scheme_id") or item.get("id") or item.get("name") or "") for item in schemes}
    for scheme in fallback_schemes:
        if len(schemes) >= PGY_COLLECTION_SCHEME_COUNT:
            break
        key = str(scheme.get("scheme_id") or scheme.get("id") or scheme.get("name") or "")
        if key and key in seen:
            continue
        schemes.append(scheme)
        if key:
            seen.add(key)
    plan["schemes"] = schemes[:PGY_COLLECTION_SCHEME_COUNT]
    enabled_scheme_ids = plan.get("enabled_scheme_ids")
    if isinstance(enabled_scheme_ids, list):
        valid_ids = {
            str(item.get("scheme_id") or item.get("id") or item.get("name") or "")
            for item in plan["schemes"]
        }
        plan["enabled_scheme_ids"] = [str(item) for item in enabled_scheme_ids if str(item) in valid_ids]
    return plan


def _scheme_has_proxy_category(scheme: dict[str, Any], proxy_filters: list[dict[str, Any]] | None = None) -> bool:
    proxy_pairs = {
        (str(item.get("proxy_field") or "").strip(), str(item.get("proxy_value") or "").strip())
        for item in (proxy_filters or [])
        if isinstance(item, dict)
    }
    filters = [
        item
        for item in [
            *(scheme.get("required_filters") or []),
            *(scheme.get("base_filters") or []),
            *(scheme.get("filters") or []),
        ]
        if isinstance(item, dict)
    ]
    for item in filters:
        field = str(item.get("field") or "").strip()
        value = str(item.get("value") or "").strip()
        if (field, value) in proxy_pairs:
            return True
        if field == "博主类目" and any(keyword in value for keyword in ["母婴", "亲子", "生活记录"]):
            return True
    text = f"{scheme.get('name') or ''} {scheme.get('goal') or ''} {scheme.get('precision_warning') or ''}"
    return any(keyword in text for keyword in ["母婴", "亲子", "家庭", "补量", "代理"])


def _normalize_pgy_scheme_metadata(pgy_plan: dict[str, Any], fallback_plan: dict[str, Any], brief_decomposition: dict[str, Any] | None = None) -> dict[str, Any]:
    plan = copy.deepcopy(pgy_plan or {})
    fallback_schemes = [
        item
        for item in ((fallback_plan or {}).get("schemes") or [])
        if isinstance(item, dict)
    ]
    proxy_filters = (brief_decomposition or {}).get("proxy_filters") if isinstance(brief_decomposition, dict) else []
    default_quota_by_index = [
        {"role": "primary", "precision_level": "high", "target_quota": 50, "max_quota": 60},
        {"role": "supplement", "precision_level": "low", "target_quota": 20, "max_quota": 30},
        {"role": "supplement", "precision_level": "medium", "target_quota": 20, "max_quota": 30},
        {"role": "supplement", "precision_level": "medium", "target_quota": 10, "max_quota": 20},
    ]
    normalized_schemes: list[dict[str, Any]] = []
    for index, scheme in enumerate([item for item in (plan.get("schemes") or []) if isinstance(item, dict)]):
        fallback_scheme = fallback_schemes[index] if index < len(fallback_schemes) else {}
        defaults = default_quota_by_index[min(index, len(default_quota_by_index) - 1)]
        next_scheme = copy.deepcopy(scheme)
        proxy_like = _scheme_has_proxy_category(next_scheme, proxy_filters if isinstance(proxy_filters, list) else [])
        role = str(next_scheme.get("role") or fallback_scheme.get("role") or defaults["role"]).strip().lower()
        if role not in {"primary", "supplement", "risk_test"}:
            role = "primary" if index == 0 else "supplement"
        precision = str(next_scheme.get("precision_level") or next_scheme.get("precisionLevel") or fallback_scheme.get("precision_level") or defaults["precision_level"]).strip().lower()
        if precision not in {"high", "medium", "low"}:
            precision = "low" if proxy_like and role != "primary" else ("high" if role == "primary" else "medium")
        if proxy_like and role != "primary" and precision == "high":
            precision = "medium"
        target_quota = _parse_positive_int(next_scheme.get("target_quota") or next_scheme.get("targetQuota"), int(fallback_scheme.get("target_quota") or defaults["target_quota"]))
        max_quota = _parse_positive_int(next_scheme.get("max_quota") or next_scheme.get("maxQuota"), int(fallback_scheme.get("max_quota") or defaults["max_quota"]))
        if role in {"supplement", "risk_test"} or precision == "low" or proxy_like:
            cap = 30 if precision == "low" or proxy_like else 40
            max_quota = min(max_quota or cap, cap)
            target_quota = min(target_quota or max_quota, max_quota)
        else:
            max_quota = max_quota or int(defaults["max_quota"])
            target_quota = target_quota or int(defaults["target_quota"])
        if not next_scheme.get("scheme_id") and not next_scheme.get("id"):
            next_scheme["scheme_id"] = fallback_scheme.get("scheme_id") or f"scheme_{index + 1}"
        next_scheme["role"] = role
        next_scheme["precision_level"] = precision
        next_scheme["target_quota"] = target_quota
        next_scheme["max_quota"] = max_quota
        if proxy_like and not next_scheme.get("precision_warning"):
            next_scheme["precision_warning"] = "该方案包含宽代理条件，只能作为补量池；采后必须用主页、详情页和笔记证据确认真实匹配度。"
        normalized_schemes.append(next_scheme)
    plan["schemes"] = normalized_schemes
    return plan


def _brief_preferred_blogger_categories(brief: str) -> list[dict[str, Any]]:
    text = str(brief or "")
    text_lower = text.lower()
    result: list[dict[str, Any]] = []

    def add(value: str, sub_value: str, reason: str) -> None:
        item = {"field": "博主类目", "value": value, "sub_value": sub_value, "reason": reason}
        if sub_value in (PGY_BLOGGER_CATEGORY_TAXONOMY.get(value) or []) and _filter_key(item) not in {_filter_key(existing) for existing in result}:
            result.append(item)

    if any(keyword in text for keyword in ["教育", "家庭教育", "家长", "父母", "亲子", "大孩", "小升初", "初中", "高中", "升学"]):
        add("教育", "家庭教育", "Brief 命中教育/家庭教育/家长决策场景")
    if any(keyword in text_lower for keyword in ["k12"]) or any(keyword in text for keyword in ["小升初", "初中", "高中", "小学", "教辅", "答疑", "作业", "升学"]):
        add("教育", "k12教育", "Brief 命中K12/小升初/初高中学习场景")
    if any(keyword in text for keyword in ["学习日常", "学习博主", "学习效率", "学习工具", "学霸", "学习"]):
        add("教育", "学习日常", "Brief 命中学习日常/学习效率内容场景")
    if any(keyword in text for keyword in ["母婴", "亲子", "妈妈", "爸爸", "孩子", "育儿", "陪伴", "大孩"]):
        add("母婴", "育儿经验", "Brief 命中母婴/育儿/亲子家庭场景")
    if any(keyword in text for keyword in ["早教", "启蒙"]):
        add("母婴", "早教", "Brief 命中早教/启蒙场景")
    return result


def _ensure_scheme_multi_blogger_subcategories(pgy_plan: dict[str, Any], brief: str) -> dict[str, Any]:
    preferred = _brief_preferred_blogger_categories(brief)
    if not preferred:
        return pgy_plan
    plan = copy.deepcopy(pgy_plan or {})
    for scheme in plan.get("schemes") or []:
        if not isinstance(scheme, dict):
            continue
        filters = [item for item in (scheme.get("required_filters") or scheme.get("base_filters") or []) if isinstance(item, dict)]
        category_items = [item for item in filters if str(item.get("field") or "") == "博主类目"]
        if not category_items:
            continue
        text = f"{scheme.get('scheme_id') or ''} {scheme.get('name') or ''} {scheme.get('goal') or ''} {scheme.get('precision_warning') or ''}".lower()
        existing_keys = {_filter_key(item) for item in category_items}
        additions: list[dict[str, Any]] = []
        for item in preferred:
            value = item["value"]
            sub_value = item["sub_value"]
            should_add = any(str(existing.get("value") or "") == value for existing in category_items)
            if value == "教育" and any(keyword in text for keyword in ["education", "教育", "学习", "k12", "family", "家庭", "city"]):
                should_add = True
            if value == "母婴" and any(keyword in text for keyword in ["parent", "parenting", "母婴", "亲子", "家庭", "补量", "育儿"]):
                should_add = True
            if not should_add:
                continue
            next_item = {
                **item,
                "control_type": "tag_select_with_hover_subcategory",
            }
            key = _filter_key(next_item)
            if key not in existing_keys:
                additions.append(next_item)
                existing_keys.add(key)
        if additions:
            scheme["required_filters"] = _dedupe_filters([*filters, *additions])
            scheme["base_filters"] = scheme["required_filters"]
    return plan


def _normalize_brief_decomposition(value: Any, fallback: dict[str, Any]) -> dict[str, Any]:
    source = value if isinstance(value, dict) else {}
    fallback_source = fallback.get("briefDecomposition") if isinstance(fallback.get("briefDecomposition"), dict) else {}

    def list_of_dicts(key: str) -> list[dict[str, Any]]:
        items = source.get(key)
        if not isinstance(items, list):
            items = fallback_source.get(key) or []
        return [item for item in items if isinstance(item, dict)]

    def list_of_strings(key: str) -> list[str]:
        items = source.get(key)
        if not isinstance(items, list):
            items = fallback_source.get(key) or []
        result: list[str] = []
        for item in items:
            if isinstance(item, str) and item.strip():
                result.append(item.strip())
            elif isinstance(item, dict):
                text = str(item.get("rule_name") or item.get("fact") or item.get("requirement") or item.get("value") or "").strip()
                if text:
                    result.append(text)
        return result

    return {
        "brief_facts": list_of_dicts("brief_facts"),
        "must_have_requirements": list_of_strings("must_have_requirements"),
        "strong_preferences": list_of_strings("strong_preferences"),
        "negative_constraints": list_of_strings("negative_constraints"),
        "backend_mappable_filters": list_of_dicts("backend_mappable_filters"),
        "proxy_filters": list_of_dicts("proxy_filters"),
        "post_score_rules": list_of_dicts("post_score_rules"),
        "manual_review_rules": list_of_strings("manual_review_rules"),
    }


def _normalize_screening_standard(result: dict[str, Any], payload: ScreeningStandardPayload) -> dict[str, Any]:
    fallback = _fallback_screening_standard(payload)
    plan = result.get("screeningPlan") if isinstance(result.get("screeningPlan"), dict) else result
    scoring_hard_filters = plan.get("scoringHardFilters") or (plan.get("scoringCriteria") or {}).get("hard_rules") or plan.get("hardFilters") or fallback["hardFilters"]
    collection_hard_filters = plan.get("collectionHardFilters") or ((plan.get("pgyCollectionPlan") or {}).get("hard_filters") if isinstance(plan.get("pgyCollectionPlan"), dict) else None) or [
        item for item in fallback["hardFilters"] if item.get("pgyField") or item.get("field") in {"单达人预算硬上限", "已确认粉丝画像", "预算效果效率"}
    ]
    hard_filters = scoring_hard_filters
    weights = plan.get("scoringWeights") or fallback["scoringWeights"]
    total = sum(float(value or 0) for value in weights.values()) or 100
    if abs(total - 100) > 0.01:
        weights = {key: round(float(value or 0) * 100 / total) for key, value in weights.items()}
    pgy_plan = plan.get("pgyCollectionPlan") or fallback.get("pgyCollectionPlan") or build_collection_plan(payload.brief, {"collectionHardFilters": collection_hard_filters, "hardFilters": hard_filters, "scoringWeights": weights})
    brief_decomposition = _normalize_brief_decomposition(
        plan.get("briefDecomposition") or plan.get("brief_decomposition") or result.get("briefDecomposition") or result.get("brief_decomposition"),
        fallback,
    )
    if isinstance(pgy_plan, dict):
        pgy_plan = {
            **pgy_plan,
            "hard_filters": collection_hard_filters,
            "filters": pgy_plan.get("filters") or fallback["pgyCollectionPlan"].get("filters") or [],
            "schemes": pgy_plan.get("schemes") or fallback["pgyCollectionPlan"].get("schemes") or [],
            "target_count_range": pgy_plan.get("target_count_range") or "50-2000",
            "strategy": pgy_plan.get("strategy") or fallback["pgyCollectionPlan"].get("strategy"),
        }
        pgy_plan = _ensure_pgy_scheme_count(pgy_plan, fallback["pgyCollectionPlan"])
        pgy_plan = _normalize_pgy_scheme_metadata(pgy_plan, fallback["pgyCollectionPlan"], brief_decomposition)
        pgy_plan = _ensure_scheme_multi_blogger_subcategories(pgy_plan, payload.brief)
        pgy_plan = _normalize_scheme_filter_structure(pgy_plan)
    scoring_criteria = plan.get("scoringCriteria") or plan.get("matchingCriteria") or fallback["scoringCriteria"]
    budget_policy = plan.get("budgetPolicy") or (scoring_criteria.get("budget_policy") if isinstance(scoring_criteria, dict) else None) or fallback.get("budgetPolicy") or {}
    tier_policy = plan.get("tierPolicy") or (scoring_criteria.get("tier_policy") if isinstance(scoring_criteria, dict) else None) or fallback.get("tierPolicy") or {}
    data_layer_scoring = plan.get("dataLayerScoring") or (scoring_criteria.get("data_layer_scoring") if isinstance(scoring_criteria, dict) else None) or fallback.get("dataLayerScoring") or {}
    if isinstance(scoring_criteria, dict):
        scoring_criteria = {
            **scoring_criteria,
            "budget_policy": scoring_criteria.get("budget_policy") or budget_policy,
            "tier_policy": scoring_criteria.get("tier_policy") or tier_policy,
            "data_layer_scoring": scoring_criteria.get("data_layer_scoring") or data_layer_scoring,
            "dimension_weights": scoring_criteria.get("dimension_weights") or weights,
            "hard_rules": scoring_criteria.get("hard_rules") or hard_filters,
        }
    return {
        "briefType": plan.get("briefType") or fallback["briefType"],
        "budgetPolicy": budget_policy,
        "tierPolicy": tier_policy,
        "dataLayerScoring": data_layer_scoring,
        "collectionHardFilters": collection_hard_filters,
        "scoringHardFilters": scoring_hard_filters,
        "hardFilters": hard_filters,
        "briefDecomposition": brief_decomposition,
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
        "budget_policy": scoring_criteria.get("budget_policy") or normalized.get("budgetPolicy") or {},
        "tier_policy": scoring_criteria.get("tier_policy") or normalized.get("tierPolicy") or {},
        "data_layer_scoring": scoring_criteria.get("data_layer_scoring") or normalized.get("dataLayerScoring") or {},
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
            continue
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


def _brief_mentions_region_priority(text: str) -> bool:
    source = str(text or "")
    if not source:
        return False
    region_keywords = ["北京", "上海", "广州", "深圳", "一线", "地域", "城市", "IP", "ip"]
    priority_keywords = ["优先", "必须", "重点", "要求", "覆盖", "北上", "北京上海"]
    return any(region in source for region in region_keywords) and any(priority in source for priority in priority_keywords)


def _safe_llm_error(error: Exception) -> str:
    text = str(error) or error.__class__.__name__
    text = re.sub(r"(Bearer\s+)[A-Za-z0-9._\-]+", r"\1***", text)
    text = re.sub(r"(sk-[A-Za-z0-9_\-]{8})[A-Za-z0-9_\-]+", r"\1***", text)
    return f"{error.__class__.__name__}: {text[:360]}"


@app.post("/api/projects/{project_id}/screening-standard/optimize")
def optimize_screening_standard(project_id: str, payload: ScreeningStandardPayload) -> dict[str, Any]:
    payload.project_id = project_id
    project = get_project(project_id) or payload.project
    system_prompt = (
        "你是广告投放达人评分机制设计专家。请先把客户 Brief 拆成标准化 briefDecomposition："
        "明确区分蒲公英后台能直接执行的白名单前置筛选、只能宽代理表达的 proxy 条件、蒲公英做不到但必须采后评分的规则、以及人工复核项。"
        "然后再输出两个互相独立但可协同使用的结果：第一，面向小红书蒲公英找博主页面的多套筛选方案，必须只使用真实蒲公英筛选字段；"
        "第二，面向本项目工具的两阶段评分机制：先用找博主列表页数据做数据层分级，再用达人详情页、主页简介、笔记标题/文案做大模型人设内容评分。"
        "不允许把高知家庭、教师人设、大孩家庭、国际学校、学区房等蒲公英无法精确前置筛选的业务语义伪装成已筛选条件。"
        "母婴、教育等宽类目若用于表达复杂业务意图，必须标记为 proxy，并说明风险和 quota 上限。"
        "报价不是越低越好，必须结合CPM/CPC/CPE和近30天曝光/阅读/互动判断单个达人预算能买到的效果总量。"
        "粉丝量只用于动态T级和同T级基准，不作为高权重得分项。缺蒲公英链接或缺字段不是达人质量问题，不得作为硬性淘汰项。"
        "只输出 JSON。"
    )
    user_payload = {
        "project": project,
        "brief": payload.brief,
        "feishuFields": payload.feishu_fields,
        "requiredSchema": {
            "briefType": "simple|complex",
            "briefDecomposition": {
                "brief_facts": [{"category": "budget|audience|persona|performance|risk", "fact": "从Brief抽取的业务事实"}],
                "must_have_requirements": ["必须满足的业务条件；若蒲公英不能前置，则必须进入采后评分或人工复核"],
                "strong_preferences": ["强偏好条件"],
                "negative_constraints": ["负向约束，例如不优先孕期/低幼/泛生活方式妈妈等"],
                        "backend_mappable_filters": [
                            {
                                "field": "必须来自 pgyFilterCatalog 的真实字段",
                                "value": "真实可选值或可填写区间",
                                "sub_value": "博主类目二级类目；仅 field=博主类目 且二级类目真实存在时填写",
                                "mapping_type": "direct|proxy",
                                "confidence": "high|medium|low",
                                "business_requirement": "映射的业务需求",
                    }
                ],
                "proxy_filters": [
                    {
                        "business_intent": "无法被蒲公英精确筛出的业务意图",
                        "proxy_field": "使用的蒲公英宽代理字段",
                        "proxy_value": "代理值",
                        "proxy_risk": "会混入什么人群",
                        "confidence": "low|medium",
                        "max_quota_policy": "该代理池最多贡献多少或只能作为补量池",
                    }
                ],
                "post_score_rules": [
                    {
                        "rule_name": "采后评分规则名",
                        "required_evidence": ["需要哪些达人字段/主页/笔记证据"],
                        "fallback_action": "字段缺失或证据不足时如何处理",
                        "score_impact": "high|medium|low",
                    }
                ],
                "manual_review_rules": ["必须人工确认的事项"],
            },
            "budgetPolicy": {"total_budget": "总达人预算", "target_creator_count": "目标达人数量", "expected_single_cost": "总预算/目标人数", "single_hard_cap": "单达人硬上限", "principle": "报价与效果总量/效率的关系"},
            "tierPolicy": {"principle": "按类目、项目和抓取样本动态生成T级；粉丝量只作为比较坐标", "benchmark_method": "用P25/P50/P75/P90建立同T级基准"},
            "dataLayerScoring": {"purpose": "找博主列表页数据分级", "core_metrics": ["报价", "近30天曝光", "近30天阅读", "近30天互动", "CPM", "CPC", "CPE"], "levels": [{"level": "S|A|B|C", "rule": "分级规则"}]},
            "hardFilters": [{"field": "只允许明确事实类硬性标准", "condition": ">=|<=|规避|同T级对比|核算", "value": "阈值或规则", "required": True, "feishuField": "匹配到的飞书字段名或空"}],
            "scoringWeights": {"budget": 15, "fans": 5, "cpe": 20, "engagement": 30, "persona": 20, "content": 10},
            "scoringCriteria": {
                "purpose": "说明这是两阶段评分机制，不等同于蒲公英筛选条件",
                "budget_policy": "同 budgetPolicy",
                "tier_policy": "同 tierPolicy",
                "data_layer_scoring": "同 dataLayerScoring",
                "hard_rules": [{"field": "硬性淘汰项仅能基于已确认事实", "condition": "规则", "value": "阈值", "evidenceField": "使用哪个达人字段判断"}],
                "dimension_weights": {"budget": 15, "fans": 5, "cpe": 20, "engagement": 30, "persona": 20, "content": 10},
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
                "evidence_fields": ["报价", "近30天曝光", "近30天阅读", "近30天互动", "CPM", "CPC", "CPE", "主页简介", "笔记标题", "笔记文案"],
                "reason_requirements": ["必须说明数据层级", "必须说明预算效果核算", "人设内容必须引用证据", "必须区分已确认风险和证据缺口"],
            },
            "pgyCollectionPlan": {
                "strategy": "说明如何用4套独立蒲公英方案扩展候选达人；每套方案由 required_filters + additional_filters 组成，先用必备筛选条件预检推荐数，数量过多时按顺序叠加附加筛选条件",
                "target_count_range": "50-2000",
                "schemes": [
                    {
                        "scheme_id": "短英文ID",
                        "name": "筛选方案名称",
                        "role": "primary|supplement|risk_test",
                        "precision_level": "high|medium|low",
                        "target_quota": "建议目标贡献人数",
                        "max_quota": "最大贡献人数；proxy/low 精度方案必须较低",
                        "precision_warning": "低精度或代理方案必须说明混入风险",
                        "goal": "覆盖的人群/达人类型",
                        "target_count_range": "50-2000",
                        "required_filters": [
                            {
                                "field": "只能是 博主类目|粉丝量|粉丝年龄|合作报价 之一",
                                "value": "筛选值或待填写内容",
                                "sub_value": "仅博主类目可填写真实二级类目；例如 教育-家庭教育、教育-k12教育、母婴-育儿经验",
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
            "必须输出 briefDecomposition；briefDecomposition 要先于 pgyCollectionPlan 表达 Brief 如何被拆成 direct/proxy/post_score/manual_review",
            "pgyCollectionPlan 只能使用 pgyFilterCatalog 中真实存在的字段和控件类型；白名单外字段不得进入前置筛选",
            "高知家庭、教师人设、大孩家庭、国际学校、住校生、学区房、中产教育叙事、教育决策强度等，不能作为蒲公英前置筛选；必须进入 post_score_rules 或 manual_review_rules",
            "母婴、教育、生活记录等宽类目如果用于承接复杂业务意图，必须在 proxy_filters 标记 mapping_type=proxy、confidence=low/medium、proxy_risk，并限制 max_quota",
            "主池必须优先使用 direct 且高置信字段；补量池可以使用 proxy，但不能吞掉全部配额",
            "每套 scheme 必须包含 role、precision_level、target_quota、max_quota；precision_level=low 的补量池 max_quota 不得超过总目标的30%",
            "负向约束必须进入 negative_constraints，并转化为 post_score_rules 或 manual_review_rules；不得幻想蒲公英已前置排除",
            "scoringWeights 六项总和必须为 100",
            "必须把蒲公英筛选方案和采集后评分标准拆开：pgyCollectionPlan 只服务找博主采集，scoringCriteria 只服务采集后评分/推荐/匹配",
            "hardFilters 只能包含已确认事实类硬性规则；缺蒲公英链接、缺字段、缺近期笔记正文不能作为达人硬性不符",
            "评分机制必须分两阶段：找博主列表页数据先分 S/A/B/C 数据层级；详情页、主页简介、笔记标题/文案只用于高优先级达人的人设内容分析",
            "预算评分必须解释报价、CPM、CPC、CPE和近30天曝光/阅读/互动的关系，输出单个达人预算能换来的效果总量；报价不是越低越好",
            "粉丝量只用于T级坐标和同T级benchmark；T级边界和标准必须根据项目类目、Brief和抓取样本动态生成，不得把粉丝量作为高权重加分",
            "近30天曝光、阅读、互动必须是数据层级的核心指标，和CPM/CPC/CPE一起决定预算效果质量",
            "蒲公英 schemes 必须且只输出 4 套，分别作为方案一、方案二、方案三、方案四映射到前端卡片；4套要覆盖不同达人来源或人群角度；每套 required_filters 的字段类型必须只来自：博主类目、粉丝量、粉丝年龄、合作报价；其中博主类目允许出现多条",
            "博主类目可多选：既可以多选不同一级类目，也可以在同一一级类目下多选多个二级类目；跨一级多二级也必须同时保留，例如 {field:'博主类目', value:'教育', sub_value:'家庭教育'}、{field:'博主类目', value:'教育', sub_value:'学习日常'}、{field:'博主类目', value:'母婴', sub_value:'育儿经验'} 可以同时出现在同一套 required_filters；不能合并成字符串或只留一个",
            "博主类目支持二级类目，二级类目必须来自 pgyFilterCatalog.option_groups；禁止输出不存在或不属于该主类目的二级类目；禁止把多个二级类目写成数组、逗号文本或斜杠文本，必须拆成多条 required_filters",
            "有道答疑笔这类教育/大孩家庭 Brief 优先多选 教育-家庭教育 与 教育-k12教育；学习效率/工具型可补 教育-学习日常；母婴补量可多选 母婴-育儿经验 与 母婴-早教，并标记 proxy 风险和较低 max_quota",
            "一般不要选择笔记类目，只选择博主类目即可；笔记类目不是博主类目，不能用汽车/游戏/母婴/美妆等笔记类目去替代或追加到博主类目",
            "笔记类目在蒲公英真实页面是父级类目下继续展开的二级/三级弹层；除非用户明确要求按笔记内容类目筛选，否则 pgyCollectionPlan 不要输出 笔记类目/内容题材",
            "营销目标是低优先级附加条件，只能放入 additional_filters 或用户手动 filters，不能放入 required_filters；字段结构要用父子指标，如 {field:'营销目标', value:'互动表现', goal:'种草', parent_value:'种草', control_type:'marketing_goal_metric'}",
            "地域/粉丝地域只有 Brief 明确强调地域、IP、城市优先/必须/重点覆盖时才放入筛选条件；仅出现城市案例或品牌叙事时不要自动加入地域",
            "不要在 required_filters 或自动 filters 中加入 家庭身份、职业身份、特色背景、母婴阶段、行业推荐博主、近期合作品牌、按博主粉丝推荐；这些低频项只有用户在前端手动添加时才允许进入 filters",
            "预估阅读单价、预估互动单价、阅读/互动/曝光中位数等提质条件放入 additional_filters，默认非必要；如果必备筛选下博主过多，按 additional_filters 数组顺序逐个叠加，越靠上越先启用，一旦数量达标就不再继续加下面的条件",
            "区间字段必须按字段语义输出：粉丝量、曝光中位数、阅读中位数、互动中位数、合作订单数、传播规模子字段、合作信用度只设下限，写 range_policy='min_only' 和 min；合作报价必须同时设置 min 和 max；预估阅读单价、预估互动单价、预估CPM、外溢进店单价维持只设 max",
            "每套蒲公英方案需要 target_count_range、expand_if_too_few、narrow_if_too_many，用来根据页面推荐数量动态扩缩条件",
            "当蒲公英页面推荐数量类似 5000+ 时，narrow_if_too_many 必须给出可追加的真实蒲公英附加筛选条件；目标是不超过约 2000",
            "评分硬性条件只使用 Brief 明确要求且能被采集字段确认的事实；人设/内容不能只靠关键词命中，需要详情页、主页简介、笔记标题/文案等证据",
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
            ],
            config={
                "max_tokens": SCREENING_OPTIMIZE_LLM_MAX_TOKENS,
                "timeout_seconds": SCREENING_OPTIMIZE_LLM_TIMEOUT_SECONDS,
            },
        )
        plan = _sync_screening_plan_criteria(_normalize_screening_standard(result, payload))
        source = "llm"
        status = "success"
        detail = plan.get("summary") or "量化标准已由大模型优化"
    except Exception as error:
        plan = _sync_screening_plan_criteria(_normalize_screening_standard({}, payload))
        source = "generated"
        status = "fallback"
        detail = f"大模型未返回可用 JSON，已使用本地规则生成量化标准。原因：{_safe_llm_error(error)}"
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


def _feishu_failure_title(failed_step: str | None) -> str:
    return {
        "parse_url": "飞书链接无法识别",
        "auth": "应用鉴权或 Wiki 解析失败",
        "list_tables": "读取子表失败",
        "read_fields": "读取字段失败",
        "write_test": "测试写入失败",
    }.get(failed_step or "", "飞书连接测试未通过")


def _normalize_feishu_test_failure(result: dict[str, Any]) -> dict[str, Any]:
    error = result.get("error") if isinstance(result.get("error"), dict) else {}
    permission_urls = list(dict.fromkeys([
        *(result.get("permission_urls") or []),
        *(error.get("permission_urls") or []),
        *([error.get("console_url")] if error.get("console_url") else []),
    ]))
    failed_step = result.get("failed_step")
    return {
        **result,
        "ok": False,
        "title": _feishu_failure_title(failed_step),
        "failed_reason": result.get("message") or error.get("message") or _feishu_failure_title(failed_step),
        "permission_urls": permission_urls,
        "required_scope": result.get("required_scope") or error.get("required_scope"),
        "permission_violations": result.get("permission_violations") or error.get("permission_violations") or [],
        "fix_actions": result.get("fix_actions") or error.get("fix_actions") or [],
    }


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
    try:
        target = parse_feishu_url(feishu_url)
    except FeishuError as error:
        return _normalize_feishu_test_failure({
            "ok": False,
            "failed_step": "parse_url",
            "steps": [
                {"key": "parse_url", "label": "识别飞书链接", "status": "failed", "message": str(error), "error": _error_detail(error)},
                {"key": "auth", "label": "应用鉴权 / Wiki 解析", "status": "pending"},
                {"key": "list_tables", "label": "读取子表", "status": "pending"},
                {"key": "read_fields", "label": "读取字段", "status": "pending"},
                {"key": "write_test", "label": "测试写入", "status": "pending"},
            ],
            "message": str(error),
            "error": _error_detail(error),
        })
    if not app_secret:
        return _normalize_feishu_test_failure({
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
        })
    result = _run_feishu_full_test(feishu_url, app_id, app_secret)
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=_normalize_feishu_test_failure(result))
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
        return {"enabled": True, "written_count": 0, "message": "没有详情完善成功的达人需要写回"}
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
                creator.get("detail_collection_priority") in DETAIL_PRIORITY_HIGH_VALUES
                or _number_or_zero(creator.get("total_score")) >= 80
            )
        ]
    if not targets:
        message = "当前分段没有可完善详情页的达人" if (payload.manual or target_ids) else "没有达到详情完善优先级的达人"
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
    duration_text = result.get("duration_text") or ""
    average_duration_text = result.get("average_duration_text") or ""
    timing_suffix = f"；总耗时 {duration_text}" if duration_text else ""
    if average_duration_text:
        timing_suffix += f"，单个约 {average_duration_text}"
    return {
        **result,
        "updated": updated,
        "auto_writeback": auto_writeback,
        "message": (
            f"详情页完善完成，已更新 {len(updated)} 个{'当前分段达人' if (payload.manual or target_ids) else '通过初筛达人'}"
            f"；失败 {len(result.get('failed') or [])} 个{timing_suffix}"
        ),
    }


@app.post("/api/xhs/notes/parse")
def api_xhs_note_parse(payload: XhsNoteParsePayload) -> dict[str, Any]:
    url = str(payload.url or "").strip()
    if not url:
        raise HTTPException(status_code=400, detail={"message": "请提供小红书笔记链接"})
    if not re.search(r"(xiaohongshu\.com|xhslink\.com|xhsurl\.com)", url, re.I):
        raise HTTPException(status_code=400, detail={"message": "当前仅接受小红书笔记链接"})

    note = payload.note or {}
    metrics = note.get("metrics") if isinstance(note.get("metrics"), dict) else {}
    title = str(note.get("title") or "").strip()
    content = str(note.get("content") or "").strip()
    topics = note.get("topics") if isinstance(note.get("topics"), list) else []
    comments = note.get("comments") if isinstance(note.get("comments"), list) else []
    comments = [str(item.get("content") if isinstance(item, dict) else item or "").strip() for item in comments]
    comments = [item for item in comments if item][:20]
    extracted_id = ""
    match = re.search(r"(?:explore|discovery/item|note)/([^/?#]+)", url)
    if match:
        extracted_id = match.group(1)

    return {
        "ok": True,
        "source": "preset-xhs-parser",
        "status": "stub",
        "message": "小红书笔记解析端口已预置，当前返回前端传入的样本信息；接入真实解析服务后在此替换正文、话题、组件和评论字段。",
        "url": url,
        "note_id": extracted_id,
        "note": {
            "title": title,
            "cover_url": note.get("cover_url") or "",
            "cover_text": note.get("cover_text") or "",
            "published_at": note.get("published_at") or "",
            "content": content,
            "topics": topics,
            "comments": comments,
            "metrics": {
                "read_count": metrics.get("read_count") or "",
                "like_count": metrics.get("like_count") or "",
                "save_count": metrics.get("save_count") or "",
                "comment_count": metrics.get("comment_count") or "",
                "share_count": metrics.get("share_count") or "",
            },
            "missing_fields": _xhs_note_missing_fields(note),
        },
        "creator": payload.creator,
        "project": payload.project,
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
    "followers": {"field": "粉丝量", "value": "1万以上", "reason": "必备筛选：先保证基础粉丝量；只设下限", "control_type": "preset_or_number_range", "min": 10000, "range_policy": "min_only"},
    "age": {"field": "粉丝年龄", "value": "35～44 占比高", "reason": "必备筛选：家长决策人群优先", "control_type": "dropdown"},
    "quote": {"field": "合作报价", "value": "图文笔记：0.1万～2万", "reason": "必备筛选：控制单达人预算", "control_type": "subfield_preset_or_number_range", "sub_field": "图文笔记", "max": 20000},
}

PGY_BASE_FILTER_FIELDS = {"博主类目", "粉丝量", "粉丝年龄", "合作报价"}
PGY_EXTRA_FILTER_FIELDS = {"预估阅读单价", "预估互动单价", "阅读中位数", "互动中位数", "曝光中位数", "常规剔除", "地域", "粉丝地域"}
PGY_MANUAL_ONLY_FILTER_FIELDS = {"职业身份", "特色背景", "家庭身份", "母婴阶段", "行业推荐博主", "平台推荐", "近期合作品牌", "按博主粉丝推荐", "笔记类目", "内容题材"}
PGY_MANUAL_FLAGS = {"manual", "manual_added", "user_added", "frontend_added"}


def _filter_key(item: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(item.get("field") or ""),
        str(item.get("value") or ""),
        str(item.get("sub_value") or item.get("subValue") or ""),
        str(item.get("sub_field") or item.get("subField") or ""),
    )


def _filter_field_sub_key(item: dict[str, Any]) -> tuple[str, str]:
    return (str(item.get("field") or item.get("pgyField") or ""), str(item.get("sub_field") or item.get("subField") or ""))


def _dedupe_filters(filters: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()
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


def _infer_blogger_category_sub_value(value: str, item: dict[str, Any]) -> str:
    valid_subcategories = PGY_BLOGGER_CATEGORY_TAXONOMY.get(value) or []
    if not valid_subcategories:
        return ""
    text = " ".join(str(item.get(key) or "") for key in (
        "value",
        "reason",
        "label",
        "role",
        "goal",
        "scheme_name",
        "name",
        "business_requirement",
    ))
    text_lower = text.lower()
    if value == "教育":
        if any(keyword in text_lower for keyword in ("k12", "小学", "初中", "高中", "教辅", "答疑", "作业", "升学")):
            return "k12教育" if "k12教育" in valid_subcategories else ""
        if any(keyword in text for keyword in ("家庭", "家长", "亲子", "父母", "妈妈", "陪伴", "规划")):
            return "家庭教育" if "家庭教育" in valid_subcategories else ""
        return "家庭教育" if "家庭教育" in valid_subcategories else ""
    if value == "母婴":
        if any(keyword in text for keyword in ("早教", "启蒙", "幼儿", "低龄", "学龄前")):
            return "早教" if "早教" in valid_subcategories else ""
        return "育儿经验" if "育儿经验" in valid_subcategories else ""
    return ""


def _standardize_saved_pgy_filter(item: dict[str, Any]) -> list[dict[str, Any]]:
    field = str(item.get("field") or "").strip()
    if field == "博主类目":
        value = str(item.get("value") or "").strip()
        sub_value = str(item.get("sub_value") or item.get("subValue") or "").strip()
        base_item = {key: val for key, val in item.items() if key not in {"sub_value", "subValue"}}
        if value not in PGY_BLOGGER_CATEGORY_TAXONOMY:
            for category, subcategories in PGY_BLOGGER_CATEGORY_TAXONOMY.items():
                if value in subcategories:
                    value, sub_value = category, value
                    break
        if value not in PGY_BLOGGER_CATEGORY_TAXONOMY:
            return []
        valid_subcategories = PGY_BLOGGER_CATEGORY_TAXONOMY.get(value) or []
        if sub_value and sub_value not in valid_subcategories:
            sub_value = ""
        if not sub_value:
            sub_value = _infer_blogger_category_sub_value(value, item)
        return [
            {
                **base_item,
                "field": field,
                "value": value,
                "control_type": "tag_select_with_hover_subcategory",
                **({"sub_value": sub_value} if sub_value else {}),
            }
        ]
    if field in {"地域", "粉丝地域"}:
        region_items = _standard_region_filter_items(item)
        if region_items:
            return region_items
    if field == "营销目标":
        value = str(item.get("value") or "").strip()
        parent = str(item.get("goal") or item.get("parent_value") or item.get("parentValue") or "").strip()
        metric = value
        if metric in PGY_MARKETING_GOAL_DEFAULT_METRIC:
            parent = metric
            metric = PGY_MARKETING_GOAL_DEFAULT_METRIC[metric]
        if not parent:
            parent = PGY_MARKETING_GOAL_METRIC_PARENT.get(metric) or ""
        return [
            {
                **item,
                "field": field,
                "value": metric,
                "control_type": "marketing_goal_metric",
                "goal": parent,
                "parent_value": parent,
                "priority": item.get("priority") or "low",
            }
        ]
    return [item]


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
        for normalized_item in _standardize_saved_pgy_filter(copy.deepcopy(item)):
            normalized_field = str(normalized_item.get("field") or "").strip()
            if allowed_fields is not None and normalized_field not in allowed_fields:
                continue
            cleaned.append(normalized_item)
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
    base_candidates = [item for item in filters if str(item.get("field") or "") in PGY_BASE_FILTER_FIELDS]
    pgy_plan = screening_plan.get("pgyCollectionPlan") if isinstance(screening_plan.get("pgyCollectionPlan"), dict) else {}
    plan_filters = [item for item in (pgy_plan.get("filters") or []) if isinstance(item, dict)]
    for item in plan_filters:
        field = str(item.get("field") or "")
        if field in PGY_BASE_FILTER_FIELDS:
            base_candidates.append(item)
    base_candidates = _dedupe_filters(base_candidates)
    category_filters = [item for item in base_candidates if str(item.get("field") or "") == "博主类目"] or [{**PGY_DEFAULT_BASE_FILTERS["category"]}]
    follower_filters = [item for item in base_candidates if str(item.get("field") or "") == "粉丝量"] or [{**PGY_DEFAULT_BASE_FILTERS["followers"]}]
    age_filters = [item for item in base_candidates if str(item.get("field") or "") == "粉丝年龄"] or [{**PGY_DEFAULT_BASE_FILTERS["age"]}]
    quote_filters = [item for item in base_candidates if str(item.get("field") or "") == "合作报价"] or [{**PGY_DEFAULT_BASE_FILTERS["quote"]}]
    return _clean_scheme_filters(
        _dedupe_filters([*category_filters, *follower_filters, *age_filters, *quote_filters]),
        allowed_fields=PGY_BASE_FILTER_FIELDS,
    )


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


def _parse_positive_int(value: Any, default: int | None = None) -> int | None:
    if value in (None, ""):
        return default
    if isinstance(value, (int, float)):
        return int(value) if int(value) > 0 else default
    match = re.search(r"\d+", str(value))
    if not match:
        return default
    parsed = int(match.group(0))
    return parsed if parsed > 0 else default


def _scheme_collect_limit(scheme: dict[str, Any], remaining: int) -> int:
    if remaining <= 0:
        return 0
    max_quota = _parse_positive_int(scheme.get("max_quota") or scheme.get("maxQuota"))
    if max_quota is None:
        precision = str(scheme.get("precision_level") or scheme.get("precisionLevel") or "").lower()
        role = str(scheme.get("role") or "").lower()
        if precision == "low" or role in {"supplement", "risk_test"}:
            max_quota = max(1, min(remaining, 30))
    return max(1, min(remaining, max_quota or remaining))


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
    lock = _collect_lock(project_id)
    if not lock.acquire(blocking=False):
        running_batch = next((batch for batch in list_batches(project_id) if batch.get("status") == "running"), None)
        return {
            "ok": False,
            "message": "当前项目已有采集任务在运行，请等待完成后再启动新的采集",
            "batch": running_batch or {},
            "error": "collection_already_running",
        }
    cancel_event = _collect_cancel_event(project_id)
    cancel_event.clear()
    try:
        return _api_pgy_collect_batch_locked(payload, project_id, cancel_event)
    finally:
        lock.release()


@app.post("/api/pgy/collect/stop")
def api_pgy_collect_stop(payload: BatchCollectStopPayload) -> dict[str, Any]:
    project_id = payload.project_id or "youdao_001"
    event = _collect_cancel_event(project_id)
    event.set()
    running_batch = next((batch for batch in list_batches(project_id) if batch.get("status") == "running"), None)
    if running_batch:
        batch = update_batch_progress(
            running_batch["batch_id"],
            stage="stopping",
            message="已收到停止请求，正在安全停止当前采集",
        )
        return {"ok": True, "batch": batch, "message": "已发送停止请求"}
    return {"ok": True, "batch": {}, "message": "当前没有运行中的采集任务"}


def _api_pgy_collect_batch_locked(payload: BatchCollectPayload, project_id: str, cancel_event: threading.Event) -> dict[str, Any]:
    project = get_project(project_id) or {}
    brief = project.get("brief") or ""
    screening_plan = payload.screening_plan or _normalize_project_screening_plan(project.get("screening_plan")) or {}
    pgy_plan = screening_plan.get("pgyCollectionPlan") if isinstance(screening_plan, dict) else {}
    if isinstance(pgy_plan, dict):
        pgy_plan = _normalize_scheme_filter_structure(pgy_plan)
        screening_plan = {**screening_plan, "pgyCollectionPlan": pgy_plan}
    all_schemes = pgy_plan.get("schemes") if isinstance(pgy_plan, dict) else []
    saved_scheme_ids = pgy_plan.get("enabled_scheme_ids") if isinstance(pgy_plan, dict) else []
    selected_ids = {str(item) for item in payload.scheme_ids or []}
    if not selected_ids and isinstance(saved_scheme_ids, list):
        selected_ids = {str(item) for item in saved_scheme_ids if str(item)}
    schemes = [
        scheme
        for scheme in (all_schemes or [])
        if isinstance(scheme, dict) and (not selected_ids or str(scheme.get("scheme_id") or scheme.get("id") or scheme.get("name")) in selected_ids)
    ]
    use_multi_scheme = bool(payload.multi_scheme and payload.apply_filters and schemes)
    batch_id = create_batch(project_id, payload.source_url)
    update_batch_progress(batch_id, stage="preflight", message="正在应用采集条件并预检推荐数量")

    def stop_if_requested(
        *,
        total: int = 0,
        success: int = 0,
        failed: int = 0,
        collection_plan: dict[str, Any] | None = None,
        applied_filters_arg: list[dict[str, Any]] | None = None,
        skipped_filters_arg: list[dict[str, Any]] | None = None,
        selected_metrics_arg: list[dict[str, Any]] | None = None,
        skipped_metrics_arg: list[dict[str, Any]] | None = None,
        detail_collection_arg: str = "",
    ) -> dict[str, Any] | None:
        if not cancel_event.is_set():
            return None
        batch = finish_batch(
            batch_id,
            "stopped",
            total,
            success,
            failed,
            "用户已停止当前采集",
            collection_plan=collection_plan,
            applied_filters=applied_filters_arg or [],
            skipped_filters=skipped_filters_arg or [],
            selected_metrics=selected_metrics_arg or [],
            skipped_metrics=skipped_metrics_arg or [],
            detail_collection=detail_collection_arg,
        )
        return {"ok": False, "stopped": True, "batch": batch, "message": "用户已停止当前采集"}

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

    def run_once(
        plan: dict[str, Any],
        scheme: dict[str, Any] | None = None,
        reset_filters: bool = False,
        preflight_only: bool = False,
        apply_filters: bool | None = None,
        limit_override: int | None = None,
    ) -> dict[str, Any]:
        result = collect_visible_list(
            brief=brief,
            screening_plan=plan,
            apply_filters=payload.apply_filters if apply_filters is None else apply_filters,
            include_details=payload.include_details,
            collect_profile_urls=payload.collect_profile_urls,
            export_metrics=payload.export_metrics,
            limit=limit_override or payload.limit,
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
            stopped_result = stop_if_requested(
                total=len(raw_creators_by_key),
                success=0,
                collection_plan={"multi_scheme": True, "schemes": scheme_results, "base_plan": pgy_plan},
                applied_filters_arg=applied_filters,
                skipped_filters_arg=skipped_filters_base,
                selected_metrics_arg=selected_metrics,
                skipped_metrics_arg=skipped_metrics,
                detail_collection_arg=detail_collection,
            )
            if stopped_result:
                return stopped_result
            scheme_id = str(scheme.get("scheme_id") or scheme.get("id") or scheme.get("name") or "scheme")
            update_batch_progress(
                batch_id,
                stage="preflight",
                message=f"正在预检方案 {index + 1}/{len(schemes)}：{scheme.get('name') or scheme_id}",
                total_count=len(raw_creators_by_key),
            )
            active_additional_filters = [
                item
                for item in (
                    scheme.get("enabled_additional_filters")
                    or scheme.get("active_additional_filters")
                    or scheme.get("enabled_extra_filters")
                    or scheme.get("active_extra_filters")
                    or []
                )
                if isinstance(item, dict)
            ]
            plan_for_scheme = _scheme_plan(screening_plan, scheme, active_additional_filters)
            plan_filters = (plan_for_scheme.get("pgyCollectionPlan") or {}).get("filters") or []
            history = scheme_count_memory(project_id, scheme_id, plan_filters)
            expected_count = _scheme_expected_count({**scheme, "filters": plan_filters}, pgy_plan.get("target_count_range") if isinstance(pgy_plan, dict) else None, history)
            preflight_result = (
                run_once(plan_for_scheme, scheme, reset_filters=True, preflight_only=True)
                if payload.preflight
                else {"ok": True, "actual_recommend_count": None, "actual_count_text": "", "actual_count_is_lower_bound": False}
            )
            stopped_result = stop_if_requested(
                total=len(raw_creators_by_key),
                success=0,
                collection_plan={"multi_scheme": True, "schemes": scheme_results, "base_plan": pgy_plan},
                applied_filters_arg=applied_filters,
                skipped_filters_arg=skipped_filters_base,
                selected_metrics_arg=selected_metrics,
                skipped_metrics_arg=skipped_metrics,
                detail_collection_arg=detail_collection,
            )
            if stopped_result:
                return stopped_result
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
                    "active_additional_filters": active_additional_filters,
                    "actual_recommend_count": preflight_result.get("actual_recommend_count"),
                    "actual_count_text": preflight_result.get("actual_count_text"),
                    "actual_count_is_lower_bound": bool(preflight_result.get("actual_count_is_lower_bound")),
                    "evaluation": evaluation,
                    "filters": plan_filters,
                }
            ]
            if payload.preflight and evaluation.get("status") == "too_many" and not payload.collect_out_of_range:
                active_filter_keys = {_filter_key(item) for item in active_additional_filters if isinstance(item, dict)}
                for additional_filter in _extra_filters_for_scheme(scheme):
                    if _filter_key(additional_filter) in active_filter_keys:
                        continue
                    active_additional_filters = [*active_additional_filters, additional_filter]
                    active_filter_keys.add(_filter_key(additional_filter))
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
            if should_collect:
                update_batch_progress(
                    batch_id,
                    stage="collecting",
                    message=f"方案 {index + 1}/{len(schemes)} 预检{preflight_result.get('actual_count_text') or '完成'}，正在沿用当前筛选结果采集",
                    total_count=len(raw_creators_by_key),
                )
            stopped_result = stop_if_requested(
                total=len(raw_creators_by_key),
                success=0,
                collection_plan={"multi_scheme": True, "schemes": scheme_results, "base_plan": pgy_plan},
                applied_filters_arg=applied_filters,
                skipped_filters_arg=skipped_filters_base,
                selected_metrics_arg=selected_metrics,
                skipped_metrics_arg=skipped_metrics,
                detail_collection_arg=detail_collection,
            )
            if stopped_result:
                return stopped_result
            scheme_result = (
                run_once(
                    plan_for_scheme,
                    scheme,
                    reset_filters=not payload.preflight,
                    preflight_only=False,
                    apply_filters=not payload.preflight,
                    limit_override=_scheme_collect_limit(scheme, payload.limit - len(raw_creators_by_key)),
                )
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
            stopped_result = stop_if_requested(
                total=len(raw_creators_by_key),
                success=0,
                collection_plan={"multi_scheme": True, "schemes": scheme_results, "base_plan": pgy_plan},
                applied_filters_arg=applied_filters,
                skipped_filters_arg=skipped_filters_base,
                selected_metrics_arg=selected_metrics,
                skipped_metrics_arg=skipped_metrics,
                detail_collection_arg=detail_collection,
            )
            if stopped_result:
                return stopped_result
            if should_collect and payload.preflight:
                scheme_result["filters_preserved_after_preflight"] = True
                if not scheme_result.get("applied_filters") and preflight_result.get("applied_filters"):
                    scheme_result["applied_filters"] = preflight_result.get("applied_filters") or []
                if not scheme_result.get("skipped_filters") and preflight_result.get("skipped_filters"):
                    scheme_result["skipped_filters"] = preflight_result.get("skipped_filters") or []
                if not scheme_result.get("selected_metrics") and preflight_result.get("selected_metrics"):
                    scheme_result["selected_metrics"] = preflight_result.get("selected_metrics") or []
                if not scheme_result.get("skipped_metrics") and preflight_result.get("skipped_metrics"):
                    scheme_result["skipped_metrics"] = preflight_result.get("skipped_metrics") or []
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
            if (
                should_collect
                and payload.preflight
                and (preflight_result.get("actual_recommend_count") or 0) > 0
                and not scheme_creators
            ):
                scheme_result["ok"] = False
                scheme_result["message"] = (
                    scheme_result.get("message")
                    or "预检已确认当前方案有推荐博主，但正式采集未读到列表，已停止以避免空条件误采"
                )
                last_error = scheme_result["message"]
            update_batch_progress(
                batch_id,
                stage="collected",
                message=f"方案 {index + 1}/{len(schemes)} 完成，已从蒲公英读取 {len(raw_creators_by_key) + len(scheme_creators)} 个候选达人",
                total_count=len(raw_creators_by_key) + len(scheme_creators),
            )
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
                    "role": scheme.get("role"),
                    "precision_level": scheme.get("precision_level") or scheme.get("precisionLevel"),
                    "target_quota": scheme.get("target_quota") or scheme.get("targetQuota"),
                    "max_quota": scheme.get("max_quota") or scheme.get("maxQuota"),
                    "ok": bool(scheme_result.get("ok")),
                    "message": scheme_result.get("message"),
                    "collected_count": len(scheme_creators),
                    "estimated_count": preflight_result.get("actual_recommend_count"),
                    "estimated_count_text": preflight_result.get("actual_count_text"),
                    "estimated_count_is_lower_bound": bool(preflight_result.get("actual_count_is_lower_bound")),
                    "ingested_count": 0,
                    "filters_preserved_after_preflight": bool(scheme_result.get("filters_preserved_after_preflight")),
                    "filters_reapplied_after_preflight": False,
                    "preflight": scheme_result.get("preflight"),
                    "applied_filters": scheme_result.get("applied_filters") or [],
                    "skipped_filters": scheme_result.get("skipped_filters") or [],
                    "collection_plan": scheme_result.get("collection_plan"),
                    "export_result": scheme_result.get("export_result"),
                }
            )
            if len(raw_creators_by_key) >= payload.limit:
                break
            if (
                should_collect
                and payload.preflight
                and (preflight_result.get("actual_recommend_count") or 0) > 0
                and not scheme_creators
            ):
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

    stopped_result = stop_if_requested(
        total=len(result.get("creators") or []),
        success=0,
        collection_plan=result.get("collection_plan"),
        applied_filters_arg=result.get("applied_filters") or [],
        skipped_filters_arg=result.get("skipped_filters") or [],
        selected_metrics_arg=result.get("selected_metrics") or [],
        skipped_metrics_arg=result.get("skipped_metrics") or [],
        detail_collection_arg=result.get("detail_collection") or "",
    )
    if stopped_result:
        return stopped_result

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
    update_batch_progress(
        batch_id,
        stage="collected",
        message=f"已采集 {len(collected_creators)} 个候选达人，正在执行硬性条件标记",
        total_count=len(collected_creators),
    )
    stopped_result = stop_if_requested(
        total=len(collected_creators),
        success=0,
        collection_plan=result.get("collection_plan"),
        applied_filters_arg=result.get("applied_filters") or [],
        skipped_filters_arg=result.get("skipped_filters") or [],
        selected_metrics_arg=result.get("selected_metrics") or [],
        skipped_metrics_arg=result.get("skipped_metrics") or [],
        detail_collection_arg=result.get("detail_collection") or "",
    )
    if stopped_result:
        return stopped_result
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
    total_creators = len(creators)
    ingested_by_scheme: dict[str, int] = {}
    for index, creator in enumerate(creators, start=1):
        stopped_result = stop_if_requested(
            total=len(collected_creators),
            success=len(creator_ids),
            collection_plan=result.get("collection_plan"),
            applied_filters_arg=result.get("applied_filters") or [],
            skipped_filters_arg=skipped_filters,
            selected_metrics_arg=result.get("selected_metrics") or [],
            skipped_metrics_arg=result.get("skipped_metrics") or [],
            detail_collection_arg=result.get("detail_collection") or "",
        )
        if stopped_result:
            return stopped_result
        saved = upsert_creator(project_id, creator, score=False)
        creator_ids.append(saved["creator_id"])
        scheme_id = str(creator.get("collection_scheme_id") or "")
        if scheme_id:
            ingested_by_scheme[scheme_id] = ingested_by_scheme.get(scheme_id, 0) + 1
        if index == 1 or index == total_creators or index % 20 == 0:
            update_batch_progress(
                batch_id,
                stage="ingesting",
                message=f"正在写入筛选工作台 {index}/{total_creators} 个达人",
                total_count=len(collected_creators),
                success_count=index,
            )
    if ingested_by_scheme:
        for item in scheme_results:
            scheme_id = str(item.get("scheme_id") or "")
            item["ingested_count"] = ingested_by_scheme.get(scheme_id, 0)
        collection_plan = result.get("collection_plan")
        if isinstance(collection_plan, dict) and isinstance(collection_plan.get("schemes"), list):
            for item in collection_plan["schemes"]:
                if isinstance(item, dict):
                    scheme_id = str(item.get("scheme_id") or "")
                    item["ingested_count"] = ingested_by_scheme.get(scheme_id, 0)
    update_batch_progress(
        batch_id,
        stage="scoring",
        message=f"已进入筛选工作台 {len(creator_ids)} 个达人，正在评分匹配",
        total_count=len(collected_creators),
        success_count=len(creator_ids),
    )
    stopped_result = stop_if_requested(
        total=len(collected_creators),
        success=len(creator_ids),
        collection_plan=result.get("collection_plan"),
        applied_filters_arg=result.get("applied_filters") or [],
        skipped_filters_arg=skipped_filters,
        selected_metrics_arg=result.get("selected_metrics") or [],
        skipped_metrics_arg=result.get("skipped_metrics") or [],
        detail_collection_arg=result.get("detail_collection") or "",
    )
    if stopped_result:
        return stopped_result
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
        "message": f"蒲公英采集完成，采到 {len(collected_creators)} 个，已进入筛选工作台评分匹配；{rejected_count} 个将在筛选工作台标记为条件不符并按档位区分",
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
