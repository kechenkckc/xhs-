from __future__ import annotations

import copy
import json
import re
import threading
import uuid
from datetime import datetime
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
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
    LLM_BATCH_MAX_CREATORS,
    LLM_SCORE_RETRY_ATTEMPTS,
    archive_project,
    bulk_upsert_creators,
    connect,
    change_creator_stage,
    compact_creator_for_list,
    count_creators,
    create_asset,
    create_handoff,
    create_task,
    create_tasks_from_handoff,
    create_batch,
    close_stale_running_batches,
    creator_pool,
    creator_pool_detail,
    creator_screening_stats,
    export_creator_pool_csv,
    finish_batch,
    get_batch,
    get_project,
    get_creator,
    delete_project,
    import_csv,
    get_project_writeback_settings,
    init_db,
    is_test_project_id,
    list_assets,
    list_batches,
    list_creators,
    creator_quality_summary,
    detail_completion_missing_fields,
    detail_completion_needs,
    detail_completion_actionable_missing_fields,
    detail_completion_actionable_needs,
    list_feishu_sync_state,
    list_handoffs,
    list_logs,
    list_projects,
    list_tasks,
    list_scheme_count_memory,
    log,
    management_overview,
    merge_feishu_rows,
    needs_detail_completion,
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
    cleanup_project_creator_duplicates,
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
    expected_kol_request_constraints_from_plan,
    parse_export_file,
    start_browser,
)


_COLLECT_LOCKS: dict[str, threading.Lock] = {}
_COLLECT_LOCKS_GUARD = threading.Lock()
_COLLECT_CANCEL_EVENTS: dict[str, threading.Event] = {}
_COLLECT_CANCEL_EVENTS_GUARD = threading.Lock()
_DETAIL_COLLECT_LOCKS: dict[str, threading.Lock] = {}
_DETAIL_COLLECT_LOCKS_GUARD = threading.Lock()
_DETAIL_COLLECT_TASKS: dict[str, dict[str, Any]] = {}
_DETAIL_COLLECT_TASKS_GUARD = threading.Lock()
SCREENING_OPTIMIZE_LLM_MAX_TOKENS = 64000
SCREENING_OPTIMIZE_LLM_TIMEOUT_SECONDS = 300
PGY_COLLECTION_SCHEME_COUNT = 4


def _queue_collect_scoring(project_id: str, creator_ids: list[str], batch_id: str) -> dict[str, Any]:
    queued_ids = list(dict.fromkeys(str(item) for item in creator_ids if item))
    if not queued_ids:
        return {"async": False, "queued": 0, "message": "无待评分达人"}
    update_batch_progress(
        batch_id,
        stage="score_queued",
        message=f"采集入库完成，已排队后台规则评分：{len(queued_ids)} 位达人",
    )
    if is_test_project_id(project_id):
        return {"async": True, "queued": len(queued_ids), "use_llm": False, "message": "测试项目已记录规则评分排队"}

    def runner() -> None:
        try:
            result = score_project(project_id, use_llm=False, creator_ids=queued_ids, trigger_source="pgy_collect_rule")
            scored = int(result.get("scored") or 0)
            update_batch_progress(
                batch_id,
                stage="rule_scored",
                message=f"后台规则评分完成：{scored}/{len(queued_ids)} 位达人",
            )
        except Exception as error:
            message = f"后台规则评分失败：{str(error)[:180]}"
            update_batch_progress(batch_id, stage="score_failed", message=message)
            with connect() as conn:
                log(conn, project_id, "score", "后台规则评分失败", project_id, "系统", message, "failed")

    threading.Thread(target=runner, name=f"pgy-score-{batch_id[:8]}", daemon=True).start()
    return {"async": True, "queued": len(queued_ids), "use_llm": False, "message": "规则评分已转入后台执行"}


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


def _detail_collect_lock(project_id: str) -> threading.Lock:
    with _DETAIL_COLLECT_LOCKS_GUARD:
        lock = _DETAIL_COLLECT_LOCKS.get(project_id)
        if lock is None:
            lock = threading.Lock()
            _DETAIL_COLLECT_LOCKS[project_id] = lock
        return lock


def _now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _detail_collect_task_snapshot(task_id: str) -> dict[str, Any] | None:
    with _DETAIL_COLLECT_TASKS_GUARD:
        task = _DETAIL_COLLECT_TASKS.get(task_id)
        return copy.deepcopy(task) if task else None


def _running_detail_collect_task(project_id: str) -> dict[str, Any] | None:
    with _DETAIL_COLLECT_TASKS_GUARD:
        running = [
            task
            for task in _DETAIL_COLLECT_TASKS.values()
            if task.get("project_id") == project_id and task.get("status") == "running"
        ]
        if not running:
            return None
        running.sort(key=lambda item: str(item.get("started_at") or ""), reverse=True)
        return copy.deepcopy(running[0])


def _update_detail_collect_task(task_id: str, **patch: Any) -> dict[str, Any]:
    with _DETAIL_COLLECT_TASKS_GUARD:
        task = _DETAIL_COLLECT_TASKS.get(task_id) or {"task_id": task_id}
        task.update({key: value for key, value in patch.items() if value is not None})
        total = int(task.get("total_count") or 0)
        completed = int(task.get("completed_count") or 0)
        failed = int(task.get("failed_count") or 0)
        done = min(total, completed + failed) if total else completed + failed
        if total:
            task["progress_text"] = f"{done}/{total} 达人已完成"
            if not task.get("progress_message"):
                task["progress_message"] = f"详情完善中：{done}/{total} 达人已完成"
        _DETAIL_COLLECT_TASKS[task_id] = task
        return copy.deepcopy(task)


def _create_detail_collect_task(project_id: str, targets: list[dict[str, Any]], payload: DetailCollectPayload) -> dict[str, Any]:
    task_id = f"detail_{uuid.uuid4().hex}"
    total = len(targets)
    return _update_detail_collect_task(
        task_id,
        project_id=project_id,
        status="running",
        progress_stage="starting",
        total_count=total,
        completed_count=0,
        failed_count=0,
        current_creator_id="",
        current_nickname="",
        segment=payload.segment or "",
        manual=bool(payload.manual or payload.creator_ids),
        started_at=_now_text(),
        finished_at="",
        progress_message=f"详情完善中：0/{total} 达人已完成",
    )


class FeishuConnectionPayload(BaseModel):
    project_id: str = Field(default="youdao_001")
    feishu_url: str
    app_id: str
    app_secret: str | None = None


class LlmConfigPayload(BaseModel):
    protocol: str = "openai-compatible"
    base_url: str = "https://api.openai.com"
    model: str = "gpt-4.1-mini"
    api_key: str | None = None
    api_key_env: str | None = None
    temperature: float = 0.2
    max_tokens: int | None = None
    timeout_seconds: int | None = None
    keep_existing_api_key: bool = True
    model_role: str | None = None
    main_model: dict[str, Any] | None = None
    secondary_model: dict[str, Any] | None = None


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


class ScorePayload(BaseModel):
    creator_ids: list[str] = Field(default_factory=list)
    source: str = "manual"
    segment: str = ""
    segment_label: str = ""
    confirm_large_llm_score: bool = False


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
    limit: int = 5000
    scheme_ids: list[str] = Field(default_factory=list)
    multi_scheme: bool = True
    preflight: bool = True
    collect_out_of_range: bool = False
    async_collect: bool = False


class BatchCollectStopPayload(BaseModel):
    project_id: str = "youdao_001"


class DetailCollectPayload(BaseModel):
    project_id: str = "youdao_001"
    creator_ids: list[str] = Field(default_factory=list)
    segment: str | None = None
    manual: bool = False
    limit: int = 500
    async_collect: bool = False


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
app.add_middleware(GZipMiddleware, minimum_size=1024)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

ensure_dirs()
init_db()
close_stale_running_batches("服务已重启，原采集线程不存在，已自动收口为停止状态；请以新批次为准")


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
    return {"projects": _hydrate_projects_for_response(list_projects(include_test_projects=include_test_projects, include_archived=include_archived))}


@app.get("/api/runtime/version")
def runtime_version() -> dict[str, Any]:
    return {"version": "pgy-python-playwright-20260508", "pgy_collector": "python-playwright"}


@app.get("/api/projects")
def api_projects(
    include_test_projects: bool = Query(default=False),
    include_archived: bool = Query(default=False),
) -> dict[str, Any]:
    return {"projects": _hydrate_projects_for_response(list_projects(include_test_projects=include_test_projects, include_archived=include_archived))}


@app.get("/api/projects/{project_id}")
def api_project(project_id: str) -> dict[str, Any]:
    project = get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail={"message": "项目不存在"})
    return {"project": _hydrate_project_for_response(project)}


@app.post("/api/projects/{project_id}")
def api_save_project(project_id: str, payload: ProjectPayload) -> dict[str, Any]:
    data = payload.model_dump(exclude_none=True)
    if isinstance(data.get("screening_plan"), dict):
        existing = get_project(project_id) or {}
        data["screening_plan"] = _sync_screening_plan_criteria(data["screening_plan"])
        brief_text = str(data.get("brief") or existing.get("brief") or "")
        data["screening_plan"] = _sync_screening_plan_criteria(
            _prune_default_fan_age_hard_filters_for_brief(data["screening_plan"], brief_text)
        )
        data["screening_plan"] = _hydrate_screening_plan_project_defaults(
            data["screening_plan"],
            brief_text,
        )
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
    include_raw: bool = Query(default=False),
    page: int | None = Query(default=None, ge=1),
    page_size: int | None = Query(default=None, ge=1, le=500),
) -> dict[str, Any]:
    limit = page_size if page and page_size else None
    offset = ((page or 1) - 1) * (page_size or 0) if limit is not None else 0
    creators = list_creators(project_id, status=status, q=q, include_raw=include_raw, limit=limit, offset=offset)
    if not include_raw:
        creators = [compact_creator_for_list(creator) for creator in creators]
    payload: dict[str, Any] = {"creators": creators}
    if limit is not None:
        total = count_creators(project_id, status=status, q=q)
        payload.update({
            "page": page or 1,
            "page_size": page_size,
            "total": total,
            "has_more": offset + len(creators) < total,
        })
    return payload


@app.get("/api/projects/{project_id}/creators/stats")
def api_creator_screening_stats(project_id: str) -> dict[str, Any]:
    return creator_screening_stats(project_id)


@app.get("/api/projects/{project_id}/creators/quality-summary")
def api_creator_quality_summary(project_id: str) -> dict[str, Any]:
    return creator_quality_summary(project_id)


@app.get("/api/projects/{project_id}/creators/{creator_id}")
def api_creator_detail(project_id: str, creator_id: str) -> dict[str, Any]:
    creator = get_creator(project_id, creator_id)
    if not creator:
        raise HTTPException(status_code=404, detail={"message": "达人不存在"})
    return {"creator": creator}


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
        scoring = score_project(project_id, use_llm=False, creator_ids=creator_ids, trigger_source="import")
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
def api_score_creators(project_id: str, payload: ScorePayload | None = None) -> dict[str, Any]:
    payload = payload or ScorePayload()
    creator_ids = [str(item) for item in payload.creator_ids if str(item or "").strip()]
    source = payload.source or "manual_rule"
    ai_sources = {"manual_ai", "manual_llm", "llm", "toolbar_ai", "save_plan_ai"}
    if source not in ai_sources:
        return score_project(
            project_id,
            use_llm=False,
            creator_ids=creator_ids or None,
            trigger_source=source,
        )
    if not creator_ids:
        raise HTTPException(
            status_code=400,
            detail={
                "ok": False,
                "error": "llm_score_scope_required",
                "message": "大模型评分必须先选择具体达人，禁止默认全量评分。",
                "source": "llm",
                "sources": {"llm": 0, "generated": 0, "rule": 0},
                "trigger_source": source,
                "suggestion": "请在筛选工作台勾选需要重评的达人；如需全量刷新，请使用规则评分。",
            },
        )
    estimated_llm_requests = (len(creator_ids) + LLM_BATCH_MAX_CREATORS - 1) // LLM_BATCH_MAX_CREATORS if creator_ids else 0
    estimated_max_attempts = estimated_llm_requests * LLM_SCORE_RETRY_ATTEMPTS
    if not payload.confirm_large_llm_score:
        raise HTTPException(
            status_code=400,
            detail={
                "ok": False,
                "error": "llm_score_confirmation_required",
                "message": f"大模型评分必须由用户手动确认后才能执行。本次预计约 {estimated_llm_requests} 次模型请求，失败重试后最多约 {estimated_max_attempts} 次；未收到确认信号，已拦截。",
                "source": "llm",
                "sources": {"llm": 0, "generated": 0, "rule": 0},
                "trigger_source": source,
                "suggestion": "请在前端勾选达人并确认 AI 评分；自动流程和普通手动评分只会使用规则评分。",
            },
        )
    all_ai_config = read_ai_config()
    ai_config = all_ai_config.get("secondary_model") if isinstance(all_ai_config.get("secondary_model"), dict) else all_ai_config
    if not ai_config.get("api_key_configured"):
        message = f"未配置 API Key（副模型）或环境变量 {ai_config.get('api_key_env') or 'OPENAI_API_KEY'}，无法调用大模型评分"
        raise HTTPException(
            status_code=400,
            detail={
                "ok": False,
                "error": "llm_config_missing",
                "message": message,
                "source": "llm",
                "sources": {"llm": 0, "generated": 0, "rule": 0},
                "trigger_source": source,
                "llm_errors": [message],
                "suggestion": "请在高级配置中填写副模型 API Key，或设置对应环境变量后重启服务，再点击模型连接测试。",
            },
        )
    try:
        return score_project(
            project_id,
            use_llm=True,
            creator_ids=creator_ids or None,
            trigger_source=source,
            fallback_on_llm_error=False,
        )
    except RuntimeError as error:
        message = str(error) or "大模型评分失败"
        raise HTTPException(
            status_code=502,
            detail={
                "ok": False,
                "error": "llm_score_failed",
                "message": message,
                "source": "llm",
                "sources": {"llm": 0, "generated": 0, "rule": 0},
                "trigger_source": source,
                "llm_errors": [message],
                "suggestion": "请检查大模型 API Key、Base URL、模型名称、网络连通性，或在高级配置中先测试模型连接。",
            },
        )


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
def api_creator_pool(
    project_id: str,
    include_screening: bool = Query(default=False),
) -> dict[str, Any]:
    try:
        return creator_pool(project_id, include_screening=include_screening)
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
def api_batches(
    project_id: str,
    status: str | None = Query(default=None),
    limit: int | None = Query(default=None, ge=1, le=100),
) -> dict[str, Any]:
    return {"batches": list_batches(project_id, status=status, limit=limit)}


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
    brief_text = payload.brief or ""

    def number(value: Any, default: float = 0) -> float:
        try:
            return float(value or default)
        except (TypeError, ValueError):
            return default

    single_hard_cap = number(project_info.get("singleBudget"), _brief_single_budget_cap(brief_text) or 20000)
    total_budget = number(project_info.get("budget"), 0)
    target_count = max(int(number(project_info.get("creatorCount"), 10)), 1)
    expected_single_cost = round(total_budget / target_count, 2) if total_budget else single_hard_cap

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
        {"field": "近30天效果", "condition": "同T级对比", "value": "曝光、阅读、互动需达到同T级正常线，明显低于P25视为数据风险", "required": True, "feishuField": match("曝光", "阅读", "互动")},
        {"field": "预算效果效率", "condition": "核算", "value": "用报价、CPM、CPC、CPE推导单达人可获得曝光/阅读/互动总量", "required": True, "feishuField": match("cpm", "cpc", "cpe")},
        {"field": "已确认风险", "condition": "规避", "value": "仅已确认限流、违规、异常流量作为风险；缺字段不等于风险", "required": True, "feishuField": match("限流风险", "流量稳定")},
    ]
    if any(keyword in brief_text for keyword in ["孩子", "年级", "初中", "高中", "小升初", "家长"]):
        hard_filters.append({"field": "孩子阶段", "condition": "匹配", "value": "按Brief目标学段/家庭阶段匹配", "required": False, "feishuField": match("孩子年级", "孩子年龄")})
    if _brief_mentions_region_priority(brief_text):
        hard_filters.append({"field": "地域优先级", "condition": "优先", "value": "按Brief明确地域/IP要求优先", "required": False, "feishuField": match("IP", "城市", "地域")})
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
    emphasizes_region = _brief_mentions_region_priority(brief_text)
    wants_parent = any(keyword in brief_text for keyword in ["母婴", "亲子", "妈妈", "爸爸", "孩子", "大孩", "家庭"])
    wants_education = any(keyword in brief_text for keyword in ["教育", "学习", "升学", "初中", "高中", "小升初", "答疑", "老师", "教师", "留学", "语言"])
    wants_parent_decision = any(keyword in brief_text for keyword in ["家长", "父母", "妈妈", "爸爸", "宝妈", "亲子", "家庭决策", "陪读"])
    wants_study_abroad = _brief_is_study_abroad(brief_text)
    strong_preferences = [
        "目标人群、使用者或决策者与产品推广目标一致",
        "内容场景能自然讲清产品痛点、使用链路和核心卖点",
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
            {"field": "粉丝量", "value": "1万以上", "mapping_type": "direct", "confidence": "medium", "business_requirement": "保证基础粉丝量；只设下限避免误卡上限"},
            {"field": "合作报价", "value": f"图文笔记：0.1万～{single_hard_cap / 10000:g}万", "mapping_type": "direct", "confidence": "high", "business_requirement": "单达人预算上限"},
        ]
    )
    if wants_parent_decision and not wants_study_abroad:
        backend_mappable_filters.append({"field": "粉丝年龄", "value": "35～44 占比高", "mapping_type": "proxy", "confidence": "medium", "business_requirement": "Brief 明确出现家长/亲子等人群时可作为代理字段"})
    if wants_study_abroad:
        backend_mappable_filters.extend(
            [
                {"field": "职业身份", "value": "学生", "mapping_type": "direct", "confidence": "medium", "business_requirement": "Brief 明确出现学生身份时可作为候选画像字段"},
                {"field": "特色背景", "value": "留学背景", "mapping_type": "direct", "confidence": "medium", "business_requirement": "Brief 明确出现留学/海外背景时可作为候选画像字段"},
            ]
        )
    if emphasizes_region:
        backend_mappable_filters.append({"field": "地域", "value": "北京/上海", "mapping_type": "direct", "confidence": "medium", "business_requirement": "地域优先"})
    brief_decomposition = {
        "brief_facts": [
            {"category": "budget", "fact": f"单达人预算上限约 ¥{single_hard_cap:g}，参考单人成本 ¥{expected_single_cost:g}"},
            {"category": "audience", "fact": "需要从 Brief 中识别核心使用者、决策者与目标受众"},
            {"category": "persona", "fact": "账号人设、内容场景和表达方式需要能承接产品推广策略"},
            {"category": "performance", "fact": "需要结合报价、CPM/CPC/CPE和近30天曝光/阅读/互动判断投流效果"},
        ],
        "promotion_audience_analysis": {
            "actual_users": ["Brief 中产品场景指向的真实使用者/体验者"],
            "decision_makers": ["Brief 中购买/报名/转化链路指向的决策者"],
            "content_influenced_audience": ["Brief 中内容场景主要影响的人群"],
            "inferred_fans_age": [
                {
                    "pgy_field": "粉丝年龄",
                    "pgy_value": "Brief未明确",
                    "reason": "本地兜底不预设固定年龄段；需依据 Brief 原文、产品使用者和转化链路人工校正。",
                    "confidence": "low",
                    "placement": "manual_review",
                }
            ],
            "not_target_audiences": ["Brief 未明确要求的历史模板人群"],
            "reasoning": "本地兜底只保留中性结构，不预设行业固定人群；最终应以 Brief 原文和采后证据校正。",
        },
        "rule_placement_matrix": [
            {"brief_requirement": "单达人预算上限", "placement": "hard_rule", "reason": "报价字段可直接确认，超预算会影响合作可行性", "is_one_vote_veto": True},
            {"brief_requirement": "身份/背景要求", "placement": "pgy_additional", "reason": "若 Brief 明确要求且蒲公英存在对应真实画像字段，可作为附加筛选；采后仍需用主页简介和笔记证据复核真实性", "is_one_vote_veto": False},
            {"brief_requirement": "内容主题/内容占比要求", "placement": "post_score", "reason": "默认需要结合近期笔记证据判断；如 Brief 明确为硬性且已有稳定字段可验证，可调整为 hard_rule", "is_one_vote_veto": False},
            {"brief_requirement": "限流/异常流量", "placement": "hard_rule", "reason": "仅在字段已确认高风险时作为硬风险", "is_one_vote_veto": True},
        ],
        "must_have_requirements": [
            "报价不超过单达人预算硬上限",
            "账号内容或人设需要与产品目标人群、使用场景或决策链路有明确证据",
            "近期内容需要能自然承接产品痛点和核心卖点，不能只靠类目关键词命中",
        ],
        "strong_preferences": strong_preferences,
        "negative_constraints": [
            "不优先只挂相关类目但缺少产品使用场景证据的账号",
            "不优先内容主题与产品痛点、目标人群或转化场景弱相关的账号",
            "不优先报价虽低但阅读互动过弱、无法支撑基础种草效果的账号",
            "不优先近期内容高度泛化、硬广感强或风险字段不明的账号",
        ],
        "assumptions": ["本地兜底无法完整理解 Brief，仅按预算、字段和可执行筛选结构生成保守假设"],
        "unknowns": ["Brief 中未明确的真实目标人群、硬性门槛和负向排除项需要人工复核"],
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
            {"rule_name": "产品场景相关度", "required_evidence": ["达人类目", "主页简介", "近期笔记标题", "笔记文案"], "fallback_action": "证据不足则降档并待复核", "score_impact": "high"},
            {"rule_name": "目标人群匹配度", "required_evidence": ["粉丝画像", "账号人设", "近期内容主题", "评论互动语境"], "fallback_action": "缺失不视为通过，最多备选", "score_impact": "high"},
            {"rule_name": "卖点承接能力", "required_evidence": ["内容形式", "表达方式", "产品痛点相关笔记", "历史商业内容"], "fallback_action": "无法自然讲清卖点则不进入强推荐", "score_impact": "medium"},
            {"rule_name": "投流效率", "required_evidence": ["报价", "CPM", "CPC", "CPE", "阅读/互动中位数"], "fallback_action": "效率缺失时保留但不进入强推荐", "score_impact": "high"},
            {"rule_name": "内容主题占比", "required_evidence": ["近期笔记标题", "笔记正文", "详情页内容标签"], "fallback_action": "作为内容匹配加减分和复核项，不作为一票否决", "score_impact": "medium"},
        ],
        "manual_review_rules": [
            "Brief 中无法被蒲公英前置筛出的目标人群、身份背景、真实使用场景需人工确认",
            "所有 proxy 补量池达人必须复核是否真的能承接产品推广策略",
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
                {"field": "合作报价", "value": "图文笔记：0.1万～2万", "reason": "必备筛选：控制单达人预算", "control_type": "subfield_preset_or_number_range", "sub_field": "图文笔记", "max": 20000},
            ],
            "additional_filters": [
                {"field": "预估阅读单价", "value": "图文笔记阅读单价≤2", "reason": "附加筛选：数量过多时控制阅读成本", "control_type": "subfield_preset_or_number_range", "sub_field": "图文笔记阅读单价", "max": 2},
                {"field": "预估互动单价", "value": "图文笔记互动单价≤20", "reason": "附加筛选：数量过多时控制互动成本", "control_type": "subfield_preset_or_number_range", "sub_field": "图文笔记互动单价", "max": 20},
            ],
            "filters": [],
            "expand_if_too_few": ["放宽合作报价上限但保留评分扣分", "放宽粉丝量下限"],
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
    if wants_study_abroad:
        quote_value = f"图文笔记：0-{single_hard_cap:g}；视频笔记：0-{single_hard_cap:g}"
        base_quote = {"field": "合作报价", "value": quote_value, "reason": "Brief 明确低预算KOC；图文与视频报价都需受控", "control_type": "subfield_preset_or_number_range", "max": single_hard_cap}
        base_followers = {"field": "粉丝量", "value": "0.1万以上", "reason": "低预算KOC优先放宽粉丝量，只设下限", "control_type": "preset_or_number_range", "min": 1000, "range_policy": "min_only"}
        pgy_plan["schemes"] = [
            {
                "scheme_id": "study_main",
                "name": "留学学习主池",
                "role": "primary",
                "precision_level": "high",
                "target_quota": 60,
                "max_quota": 70,
                "goal": "优先采集教育/留学/学习日常高相关达人",
                "target_count_range": "50-2000",
                "required_filters": [
                    {"field": "博主类目", "value": "教育", "sub_value": "留学教育", "reason": "留学听课宝核心相关类目"},
                    {"field": "博主类目", "value": "教育", "sub_value": "学习日常", "reason": "学习内容占比要求的主召回入口"},
                    {"field": "博主类目", "value": "教育", "sub_value": "大学教育", "reason": "补充大学/海外课堂学习场景"},
                    base_followers,
                    base_quote,
                ],
                "additional_filters": [],
                "enabled_additional_filters": [
                    {"field": "职业身份", "value": "学生", "reason": "留学生/学生画像提纯", "control_type": "checkbox_popover"},
                    {"field": "特色背景", "value": "留学背景", "reason": "留学/海外背景提纯", "control_type": "checkbox_popover"},
                ],
                "filters": [],
                "expand_if_too_few": ["先放宽职业身份/特色背景，采后复核身份", "保留报价硬约束"],
                "narrow_if_too_many": ["启用预估互动单价", "启用阅读中位数", "启用互动中位数"],
            },
            {
                "scheme_id": "video_focus",
                "name": "视频优先学习池",
                "role": "primary",
                "precision_level": "high",
                "target_quota": 30,
                "max_quota": 40,
                "goal": "优先采集适合视频演示听课/复盘场景的达人",
                "target_count_range": "50-2000",
                "required_filters": [
                    {"field": "博主类目", "value": "教育", "sub_value": "留学教育", "reason": "留学场景主类目"},
                    {"field": "博主类目", "value": "教育", "sub_value": "学习日常", "reason": "学习内容主类目"},
                    {"field": "博主类目", "value": "教育", "sub_value": "大学教育", "reason": "大学/课堂场景补充"},
                    base_followers,
                    base_quote,
                ],
                "additional_filters": [],
                "enabled_additional_filters": [
                    {"field": "笔记类型", "value": "视频笔记为主", "reason": "Brief 明确最好视频", "control_type": "dropdown_single"},
                    {"field": "职业身份", "value": "学生", "reason": "留学生/学生画像提纯", "control_type": "checkbox_popover"},
                    {"field": "特色背景", "value": "留学背景", "reason": "留学/海外背景提纯", "control_type": "checkbox_popover"},
                ],
                "filters": [],
                "expand_if_too_few": ["先放宽笔记类型，保留教育/留学类目", "放宽画像提纯条件并采后复核"],
                "narrow_if_too_many": ["启用预估互动单价", "启用阅读中位数", "启用互动中位数"],
            },
            {
                "scheme_id": "overseas_proxy",
                "name": "海外生活语境补量池",
                "role": "supplement",
                "precision_level": "medium",
                "target_quota": 10,
                "max_quota": 20,
                "precision_warning": "生活记录是海外语境代理，只能补量；采后必须复核学习内容占比。",
                "goal": "补充有海外/校园语境但需要采后验证学习内容的达人",
                "target_count_range": "50-2000",
                "required_filters": [
                    {"field": "博主类目", "value": "生活记录", "sub_value": "校园生活", "reason": "海外校园语境代理"},
                    {"field": "博主类目", "value": "生活记录", "sub_value": "中外生活", "reason": "海外生活语境代理"},
                    base_followers,
                    base_quote,
                ],
                "additional_filters": [],
                "enabled_additional_filters": [],
                "filters": [],
                "expand_if_too_few": ["放宽到教育广义补量池"],
                "narrow_if_too_many": ["启用阅读中位数", "启用互动中位数"],
            },
            {
                "scheme_id": "edu_broad_proxy",
                "name": "广教育学习补量池",
                "role": "supplement",
                "precision_level": "medium",
                "target_quota": 10,
                "max_quota": 25,
                "precision_warning": "语言教育/教育其他是补量入口，需采后复核留学听课场景。",
                "goal": "补充教育泛学习达人",
                "target_count_range": "50-2000",
                "required_filters": [
                    {"field": "博主类目", "value": "教育", "sub_value": "语言教育", "reason": "留学/语言学习相关补量"},
                    {"field": "博主类目", "value": "教育", "sub_value": "教育其他", "reason": "教育广义补量"},
                    base_followers,
                    base_quote,
                ],
                "additional_filters": [],
                "enabled_additional_filters": [],
                "filters": [],
                "expand_if_too_few": ["放宽画像附加筛选，采后复核"],
                "narrow_if_too_many": ["启用阅读中位数", "启用互动中位数"],
            },
        ]
    project_fit_config = _fallback_project_fit_config(brief_text, brief_decomposition)
    promotion_strategy = _fallback_promotion_strategy(brief_text, brief_decomposition, project_fit_config)
    project_special_scoring = _fallback_project_special_scoring(
        brief_text,
        brief_decomposition,
        promotion_strategy,
        project_fit_config,
    )
    koc_scoring_config = _fallback_koc_scoring_config(brief_text)
    format_budget_policy = _fallback_format_budget_policy(brief_text, budget_policy)
    hard_rules = _fallback_hard_rules(brief_text, project_fit_config)
    scoring_criteria = {
        "purpose": "用于采集后对达人做两阶段评分：先用找博主列表页数据做数据层分级，再用达人详情页、主页简介、笔记标题/文案做大模型人设内容判断。",
        "budget_policy": budget_policy,
        "format_budget_policy": format_budget_policy,
        "project_hard_rules": hard_rules,
        "tier_policy": tier_policy,
        "data_layer_scoring": data_layer_scoring,
        "hard_rules": hard_filters,
        "dimension_weights": weights,
        "dimensions": [
            {"key": "budget", "name": "预算效果核算", "weight": weights["budget"], "positive": ["报价未超硬上限", "报价能换来的曝光/阅读/互动容量达标"], "negative": ["报价超硬上限", "高价但CPM/CPC/CPE和效果容量不足"]},
            {"key": "fans", "name": "粉丝T级坐标", "weight": weights["fans"], "positive": ["用T级校准同量级预期"], "negative": ["不因粉丝多直接加分；不因缺画像直接淘汰"]},
            {"key": "cpe", "name": "CPM/CPC/CPE效率", "weight": weights["cpe"], "positive": ["CPM/CPC/CPE达到同T级正常或优秀水平"], "negative": ["成本效率明显低于同T级标准"]},
            {"key": "engagement", "name": "近30天曝光阅读互动", "weight": weights["engagement"], "positive": ["近30天曝光、阅读、互动达到同T级P50/P75"], "negative": ["多项低于P25或明显异常"]},
            {"key": "persona", "name": "人设与 Brief 匹配", "weight": weights["persona"], "positive": ["主页简介、详情页、笔记标题/文案能证明目标人群、使用场景或决策链路"], "negative": ["只有关键词或类目命中，缺少长期内容证据"]},
            {"key": "content", "name": "内容调性与笔记证据", "weight": weights["content"], "positive": ["整体内容调性稳定，能自然承接产品痛点、卖点和转化场景"], "negative": ["内容泛化、硬广感强或与Brief场景弱相关"]},
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
        "formatBudgetPolicy": format_budget_policy,
        "hardRules": hard_rules,
        "tierPolicy": tier_policy,
        "dataLayerScoring": data_layer_scoring,
        "hardFilters": hard_filters,
        "briefDecomposition": brief_decomposition,
        "projectFitConfig": project_fit_config,
        "promotionStrategy": promotion_strategy,
        "projectSpecialScoring": project_special_scoring,
        "kocScoringConfig": koc_scoring_config,
        "scoringWeights": weights,
        "scoringCriteria": scoring_criteria,
        "fieldMappings": field_mappings,
        "pgyCollectionPlan": pgy_plan,
        "summary": "已生成两阶段评分口径：先用找博主列表页的报价、近30天曝光/阅读/互动、CPM/CPC/CPE和动态T级做数据层分级，再用详情页与笔记内容证据做人设和内容质量分析。",
    }


def _brief_mentions_total_budget(brief: str) -> bool:
    text = str(brief or "")
    return bool(re.search(r"(总预算|整体预算|项目预算|预算总额|总费用|整体费用|总投放预算)", text))


def _normalize_budget_policy(value: Any, fallback: dict[str, Any], brief: str) -> dict[str, Any]:
    source = value if isinstance(value, dict) else {}
    result = {**fallback, **{key: val for key, val in source.items() if val not in (None, "")}}
    single_cap = (
        parse_number(source.get("single_hard_cap"))
        or parse_number(source.get("singleHardCap"))
        or parse_number(source.get("single_creator_budget_cap"))
        or _brief_single_budget_cap(brief)
        or parse_number(fallback.get("single_hard_cap"))
    )
    target_count = parse_number(source.get("target_creator_count") or source.get("targetCreatorCount") or fallback.get("target_creator_count"))
    expected = parse_number(source.get("expected_single_cost") or source.get("expectedSingleCost") or fallback.get("expected_single_cost"))
    total_budget = parse_number(source.get("total_budget") or source.get("totalBudget") or fallback.get("total_budget"))
    if single_cap is not None:
        result["single_hard_cap"] = single_cap
        if expected is None or expected > single_cap * 1.2:
            result["expected_single_cost"] = single_cap
        if total_budget is not None and total_budget <= 0:
            result["total_budget"] = ""
        if total_budget is not None and not _brief_mentions_total_budget(brief) and target_count and total_budget / max(target_count, 1) > single_cap * 1.2:
            result["total_budget"] = ""
    if target_count is not None:
        result["target_creator_count"] = int(target_count)
    result["principle"] = str(
        result.get("principle")
        or "报价不是越低越好，按报价能换来的曝光/阅读/互动总量和CPM/CPC/CPE效率判断单个达人质量。"
    )
    return result


def _weights_from_koc_guidance(weights: dict[str, Any], koc_scoring_config: dict[str, Any]) -> dict[str, Any]:
    guidance = koc_scoring_config.get("weight_guidance") if isinstance(koc_scoring_config, dict) else {}
    if not isinstance(guidance, dict) or koc_scoring_config.get("enabled") is False:
        return weights
    keys = ["budget", "fans", "cpe", "engagement", "persona", "content"]
    parsed = {key: parse_number(guidance.get(key)) for key in keys}
    if any(value is None for value in parsed.values()):
        return weights
    total = sum(float(value or 0) for value in parsed.values())
    if total <= 0:
        return weights
    return {key: round(float(parsed[key] or 0) * 100 / total) for key in keys}


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
    if any(keyword in text for keyword in ["留学", "海外留学", "留学生", "出国", "雅思", "托福", "语言学习"]):
        add("教育", "留学教育", "Brief 命中留学/海外学习场景")
    if any(keyword in text for keyword in ["大学", "大学生", "高校", "留学生"]):
        add("教育", "大学教育", "Brief 命中大学生/高校学习场景")
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
            has_non_education_category = any(str(existing.get("value") or "") != "教育" for existing in category_items)
            is_supplement_proxy = str(scheme.get("role") or "").lower() in {"supplement", "risk_test"} or any(keyword in text for keyword in ["proxy", "补量", "代理", "生活"])
            if (
                value == "教育"
                and not (has_non_education_category and is_supplement_proxy)
                and any(keyword in text for keyword in ["education", "教育", "学习", "k12", "family", "家庭", "city", "留学"])
            ):
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


def _pgy_filter_item(field: str, value: str, reason: str = "", **extra: Any) -> dict[str, Any]:
    item = {
        "field": field,
        "value": value,
        "reason": reason,
    }
    item.update({key: val for key, val in extra.items() if val not in (None, "", [])})
    return item


def _prepend_unique_filter(filters: list[dict[str, Any]], item: dict[str, Any]) -> list[dict[str, Any]]:
    return _dedupe_filters([item, *(filters or [])])


def _remove_filter(filters: list[dict[str, Any]], *, field: str, value: str | None = None, sub_value: str | None = None) -> list[dict[str, Any]]:
    result = []
    for item in filters or []:
        if not isinstance(item, dict):
            continue
        if str(item.get("field") or "") != field:
            result.append(item)
            continue
        if value is not None and str(item.get("value") or "") != value:
            result.append(item)
            continue
        if sub_value is not None and str(item.get("sub_value") or item.get("subValue") or "") != sub_value:
            result.append(item)
            continue
    return result


def _brief_prefers_video(brief: str) -> bool:
    text = str(brief or "")
    return any(keyword in text for keyword in ["最好是视频", "视频优先", "视频为主", "短视频", "视频"])


def _brief_is_study_abroad(brief: str) -> bool:
    text = str(brief or "")
    return any(keyword in text for keyword in ["留学", "海外留学", "海外留学生", "留学生", "出国", "雅思", "托福"])


def _brief_profile_filters_for_collection(brief: str) -> list[dict[str, Any]]:
    text = str(brief or "")
    filters: list[dict[str, Any]] = []
    if any(keyword in text for keyword in ["学生", "大学生", "留学生", "海外留学生"]):
        filters.append(
            _pgy_filter_item(
                "职业身份",
                "学生",
                "Brief 明确命中学生/留学生身份；作为采前画像提纯条件，采后仍需验证真实学习场景",
                control_type="checkbox_popover",
            )
        )
    if any(keyword in text for keyword in ["留学", "海外留学", "海外留学生", "留学生", "出国"]):
        filters.append(
            _pgy_filter_item(
                "特色背景",
                "留学背景",
                "Brief 明确要求留学/海外背景；作为采前画像提纯条件，采后仍需验证内容占比",
                control_type="checkbox_popover",
            )
        )
    return _dedupe_filters(filters)


def _is_default_fan_age_hard_filter(item: dict[str, Any]) -> bool:
    field = str(item.get("field") or item.get("standard") or "").strip()
    pgy_field = str(item.get("pgyField") or "").strip()
    value = str(item.get("value") or "").strip()
    reason = str(item.get("reason") or "").strip()
    return (
        (field == "粉丝年龄" or pgy_field == "粉丝年龄")
        and any(keyword in value for keyword in ["35", "34", "35～44", "35-44"])
        and not any(keyword in reason for keyword in ["手动", "用户", "Brief明确", "客户明确"])
    )


def _prune_default_fan_age_hard_filters_for_brief(plan: dict[str, Any], brief: str) -> dict[str, Any]:
    if not _brief_is_study_abroad(brief):
        return plan
    cleaned = copy.deepcopy(plan or {})

    def prune(items: Any) -> list[dict[str, Any]]:
        return [
            item
            for item in (items or [])
            if isinstance(item, dict) and not _is_default_fan_age_hard_filter(item)
        ]

    cleaned["collectionHardFilters"] = prune(cleaned.get("collectionHardFilters"))
    cleaned["scoringHardFilters"] = prune(cleaned.get("scoringHardFilters"))
    cleaned["hardFilters"] = prune(cleaned.get("hardFilters"))
    criteria = cleaned.get("scoringCriteria") if isinstance(cleaned.get("scoringCriteria"), dict) else {}
    cleaned["scoringCriteria"] = {**criteria, "hard_rules": prune(criteria.get("hard_rules"))}
    pgy_plan = cleaned.get("pgyCollectionPlan") if isinstance(cleaned.get("pgyCollectionPlan"), dict) else {}
    if pgy_plan:
        cleaned["pgyCollectionPlan"] = {**pgy_plan, "hard_filters": prune(pgy_plan.get("hard_filters"))}
    return cleaned


def _brief_has_low_koc_budget(brief: str) -> bool:
    text = str(brief or "").lower()
    return "koc" in text and any(keyword in text for keyword in ["1000", "1,000", "一千", "千元"])


def _quality_narrowing_filters_for_scheme(brief: str, scheme: dict[str, Any], *, video_scheme: bool = False) -> list[dict[str, Any]]:
    low_budget = _brief_has_low_koc_budget(brief)
    cpc_candidates = [3, 2, 1.5] if low_budget else [5, 3, 2]
    cpe_candidates = [20, 15, 10] if low_budget else [30, 20, 15]
    read_candidates = [300, 500, 1000] if low_budget else [500, 1000, 3000]
    exposure_candidates = [500, 1000, 2000] if low_budget else [1000, 3000, 5000]
    interaction_candidates = [30, 50, 100] if low_budget else [50, 100, 300]
    cpc_max = cpc_candidates[0]
    cpe_max = cpe_candidates[0]
    read_min = read_candidates[0]
    exposure_min = exposure_candidates[0]
    interaction_min = interaction_candidates[0]
    cpc_sub_fields = ["视频笔记阅读单价"] if video_scheme else ["图文笔记阅读单价", "视频笔记阅读单价"]
    cpe_sub_fields = ["视频笔记互动单价"] if video_scheme else ["图文笔记互动单价", "视频笔记互动单价"]
    cpc_label = "/".join(cpc_sub_fields)
    cpe_label = "/".join(cpe_sub_fields)
    return [
        _pgy_filter_item(
            "预估互动单价",
            f"{cpe_label}≤{cpe_max:g}",
            "超出估量时优先追加：温和控制 CPE，保留互动效率更好的达人",
            control_type="subfield_preset_or_number_range",
            sub_field=cpe_sub_fields[0] if len(cpe_sub_fields) == 1 else "",
            sub_fields=cpe_sub_fields,
            max=cpe_max,
            adaptive_direction="max",
            adaptive_values=cpe_candidates,
        ),
        _pgy_filter_item(
            "曝光中位数",
            _format_saved_min_only_value(exposure_min, wan_unit=True),
            "超出估量时追加：提高常规曝光稳定性",
            control_type="preset_or_number_range",
            min=exposure_min,
            max="",
            range_policy="min_only",
            adaptive_direction="min",
            adaptive_values=exposure_candidates,
        ),
        _pgy_filter_item(
            "阅读中位数",
            _format_saved_min_only_value(read_min, wan_unit=True),
            "超出估量时追加：提高常规阅读稳定性",
            control_type="preset_or_number_range",
            min=read_min,
            max="",
            range_policy="min_only",
            adaptive_direction="min",
            adaptive_values=read_candidates,
        ),
        _pgy_filter_item(
            "互动中位数",
            _format_saved_min_only_value(interaction_min),
            "超出估量时追加：过滤低互动样本",
            control_type="preset_or_number_range",
            min=interaction_min,
            max="",
            range_policy="min_only",
            adaptive_direction="min",
            adaptive_values=interaction_candidates,
        ),
        _pgy_filter_item(
            "预估阅读单价",
            f"{cpc_label}≤{cpc_max:g}",
            "超出估量时追加：控制 CPC，保留阅读效率更好的达人",
            control_type="subfield_preset_or_number_range",
            sub_field=cpc_sub_fields[0] if len(cpc_sub_fields) == 1 else "",
            sub_fields=cpc_sub_fields,
            max=cpc_max,
            adaptive_direction="max",
            adaptive_values=cpc_candidates,
        ),
    ]


def _quality_narrowing_labels(filters: list[dict[str, Any]]) -> list[str]:
    labels = []
    for item in filters:
        field = str(item.get("field") or "")
        value = str(item.get("value") or "")
        if field and value:
            labels.append(f"启用{field}：{value}")
    return labels


PGY_QUALITY_NARROWING_FIELDS = {"预估互动单价", "曝光中位数", "阅读中位数", "互动中位数", "预估阅读单价"}
PGY_LEGACY_QUALITY_NARROWING_FIELDS = PGY_QUALITY_NARROWING_FIELDS | {"预估CPM"}
PGY_DYNAMIC_RECOMMEND_TARGET_MIN = 100
PGY_DYNAMIC_RECOMMEND_TARGET_MAX = 2000


def _adaptive_filter_variants(item: dict[str, Any]) -> list[dict[str, Any]]:
    if item.get("adaptive_locked") is True or item.get("fixed") is True or item.get("locked") is True:
        return [copy.deepcopy(item)]
    direction = str(item.get("adaptive_direction") or "").strip()
    values = item.get("adaptive_values")
    if direction not in {"min", "max"} or not isinstance(values, list) or not values:
        return [copy.deepcopy(item)]
    variants = []
    field = str(item.get("field") or "")
    sub_field = str(item.get("sub_field") or item.get("subField") or "")
    sub_fields = item.get("sub_fields") or item.get("subFields") or []
    if not isinstance(sub_fields, list):
        sub_fields = [sub_fields] if sub_fields else []
    sub_field_label = "/".join(str(part) for part in sub_fields if str(part)) or sub_field
    for raw_value in values:
        value = parse_number(raw_value)
        if value is None:
            continue
        variant = copy.deepcopy(item)
        if direction == "min":
            variant["min"] = value
            variant["max"] = ""
            variant["range_policy"] = "min_only"
            variant["value"] = _format_saved_min_only_value(value, wan_unit=field in PGY_WAN_UNIT_SAVED_FIELDS)
        else:
            variant["min"] = ""
            variant["max"] = value
            variant["range_policy"] = "max_only"
            variant["value"] = f"{sub_field_label or field}≤{value:g}"
        variant["adaptive_selected_value"] = value
        variants.append(variant)
    return variants or [copy.deepcopy(item)]


def _active_filter_replace_key(item: dict[str, Any]) -> tuple[str, str]:
    sub_fields = item.get("sub_fields") or item.get("subFields") or []
    if isinstance(sub_fields, list) and sub_fields:
        sub_key = "|".join(str(part) for part in sub_fields if str(part))
    else:
        sub_key = str(item.get("sub_field") or item.get("subField") or "")
    return (str(item.get("field") or ""), sub_key)


def _replace_active_additional_filter(filters: list[dict[str, Any]], item: dict[str, Any]) -> list[dict[str, Any]]:
    replace_key = _active_filter_replace_key(item)
    kept = [
        existing
        for existing in (filters or [])
        if _active_filter_replace_key(existing) != replace_key
    ]
    return _dedupe_filters([*kept, item])


def _refresh_auto_quality_narrowing_filters(pgy_plan: dict[str, Any], brief: str) -> dict[str, Any]:
    plan = copy.deepcopy(pgy_plan or {})
    schemes = [scheme for scheme in (plan.get("schemes") or []) if isinstance(scheme, dict)]
    refreshed_schemes = []
    for index, scheme in enumerate(schemes):
        next_scheme = copy.deepcopy(scheme)
        text = f"{next_scheme.get('scheme_id') or ''} {next_scheme.get('name') or ''} {next_scheme.get('goal') or ''}".lower()
        is_video_scheme = index == 1 or any(keyword in text for keyword in ["video", "视频"])
        quality_filters = _quality_narrowing_filters_for_scheme(brief, next_scheme, video_scheme=is_video_scheme)
        raw_additional = next_scheme.get("additional_filters") or next_scheme.get("extra_filters") or []
        additional = _clean_scheme_filters(raw_additional, allowed_fields=PGY_EXTRA_FILTER_FIELDS)
        enabled = _clean_scheme_filters(next_scheme.get("enabled_additional_filters") or next_scheme.get("enabled_extra_filters") or [], allowed_fields=PGY_EXTRA_FILTER_FIELDS)
        has_auto_quality = any(
            isinstance(item, dict) and str(item.get("field") or "") in PGY_LEGACY_QUALITY_NARROWING_FIELDS
            for item in raw_additional
        )
        if has_auto_quality:
            pinned_additional = [
                item
                for item in additional
                if item.get("field") == "笔记类型" and item.get("value") == "视频笔记为主"
            ]
            preserved_additional = [
                item
                for item in additional
                if str(item.get("field") or "") not in PGY_LEGACY_QUALITY_NARROWING_FIELDS
                and not (item.get("field") == "笔记类型" and item.get("value") == "视频笔记为主")
            ]
            preserved_enabled = [
                item
                for item in enabled
                if str(item.get("field") or "") not in PGY_LEGACY_QUALITY_NARROWING_FIELDS
            ]
            next_scheme["additional_filters"] = _dedupe_filters([*pinned_additional, *preserved_additional, *quality_filters])
            next_scheme["extra_filters"] = next_scheme["additional_filters"]
            next_scheme["enabled_additional_filters"] = _dedupe_filters(preserved_enabled)
            next_scheme["enabled_extra_filters"] = next_scheme["enabled_additional_filters"]
            next_scheme["narrow_if_too_many"] = _quality_narrowing_labels(quality_filters)
        refreshed_schemes.append(next_scheme)
    plan["schemes"] = refreshed_schemes
    return plan


def _enforce_scheme_distinct_collection_logic(pgy_plan: dict[str, Any], brief: str) -> dict[str, Any]:
    plan = copy.deepcopy(pgy_plan or {})
    schemes = [scheme for scheme in (plan.get("schemes") or []) if isinstance(scheme, dict)]
    if not schemes:
        return plan
    study_abroad = _brief_is_study_abroad(brief)
    video_preferred = _brief_prefers_video(brief)
    for index, scheme in enumerate(schemes):
        text = f"{scheme.get('scheme_id') or ''} {scheme.get('name') or ''} {scheme.get('goal') or ''}".lower()
        required = _clean_scheme_filters(scheme.get("required_filters") or scheme.get("base_filters") or [], allowed_fields=PGY_BASE_FILTER_FIELDS)
        additional = _clean_scheme_filters(scheme.get("additional_filters") or scheme.get("extra_filters") or [], allowed_fields=PGY_EXTRA_FILTER_FIELDS)
        enabled = _clean_scheme_filters(scheme.get("enabled_additional_filters") or scheme.get("enabled_extra_filters") or [], allowed_fields=PGY_EXTRA_FILTER_FIELDS)

        is_video_scheme = index == 1 or any(keyword in text for keyword in ["video", "视频"])
        is_overseas_proxy = study_abroad and index not in {0, 1} and (
            index == 2
            or any(keyword in text for keyword in ["overseas", "海外", "生活"])
        )
        is_broad_education = (
            index == 3
            or any(keyword in text for keyword in ["广", "泛", "其他"])
            or any(token in text for token in ["edu_broad", "broad_proxy", "broad_education", "broad education"])
        )
        is_primary_scheme = str(scheme.get("role") or "").lower() == "primary" or index in {0, 1}
        profile_filters = _brief_profile_filters_for_collection(brief)

        if study_abroad and index == 0:
            required = _remove_filter(required, field="博主类目", value="生活记录")
            required = _prepend_unique_filter(required, _pgy_filter_item("博主类目", "教育", "Brief 命中留学学习主场景", control_type="tag_select_with_hover_subcategory", sub_value="留学教育"))
            required = _prepend_unique_filter(required, _pgy_filter_item("博主类目", "教育", "Brief 要求学习类内容占比高", control_type="tag_select_with_hover_subcategory", sub_value="学习日常"))

        if is_video_scheme and video_preferred:
            video_filter = _pgy_filter_item("笔记类型", "视频笔记为主", "Brief 明确视频优先，视频池默认启用该附加筛选", control_type="dropdown_single")
            additional = _prepend_unique_filter(additional, video_filter)
            enabled = _prepend_unique_filter(enabled, video_filter)
            scheme["goal"] = scheme.get("goal") or "优先采集视频笔记为主、适合视频报备合作的达人"
            scheme["target_count_range"] = scheme.get("target_count_range") or "80-800"

        if is_overseas_proxy:
            required = _remove_filter(required, field="博主类目", value="教育", sub_value="学习日常")
            required = _remove_filter(required, field="博主类目", value="教育", sub_value="留学教育")
            required = _remove_filter(required, field="博主类目", value="教育", sub_value="大学教育")
            required = _prepend_unique_filter(required, _pgy_filter_item("博主类目", "生活记录", "补量承接海外/留学日常场景，采后复核学习内容占比", control_type="tag_select_with_hover_subcategory", sub_value="中外生活"))
            required = _prepend_unique_filter(required, _pgy_filter_item("博主类目", "生活记录", "补量承接海外校园生活场景，采后复核是否真留学/学习内容", control_type="tag_select_with_hover_subcategory", sub_value="校园生活"))
            scheme["role"] = "supplement"
            scheme["precision_level"] = "medium"
            scheme["max_quota"] = min(_parse_positive_int(scheme.get("max_quota"), 16) or 16, 20)
            scheme["precision_warning"] = scheme.get("precision_warning") or "海外生活是留学场景代理条件，只能作为补量池；采后必须复核留学身份和学习内容占比。"

        if is_broad_education:
            has_language_or_other = any(
                item.get("field") == "博主类目"
                and item.get("value") == "教育"
                and item.get("sub_value") in {"语言教育", "教育其他"}
                for item in required
            )
            if has_language_or_other:
                required = _remove_filter(required, field="博主类目", value="教育", sub_value="学习日常")
                required = _remove_filter(required, field="博主类目", value="教育", sub_value="留学教育")
                required = _remove_filter(required, field="博主类目", value="教育", sub_value="大学教育")
                required = _remove_filter(required, field="博主类目", value="生活记录")
            scheme["role"] = "supplement"
            scheme["precision_level"] = "medium"
            scheme["max_quota"] = min(_parse_positive_int(scheme.get("max_quota"), 20) or 20, 25)

        quality_filters = _quality_narrowing_filters_for_scheme(brief, scheme, video_scheme=is_video_scheme)
        pinned_additional = [
            item
            for item in additional
            if item.get("field") == "笔记类型" and item.get("value") == "视频笔记为主"
        ]
        preserved_profile_filters = [
            item
            for item in additional
            if str(item.get("field") or "") in PGY_PROFILE_EXTRA_FILTER_FIELDS
        ]
        if study_abroad:
            preserved_profile_filters = _dedupe_filters([*preserved_profile_filters, *profile_filters])
        additional = _dedupe_filters([*pinned_additional, *preserved_profile_filters, *quality_filters])
        enabled = [
            item
            for item in enabled
            if item.get("field") == "笔记类型"
            or item.get("field") in PGY_PROFILE_EXTRA_FILTER_FIELDS
            or item.get("field") in PGY_QUALITY_NARROWING_FIELDS
        ]
        if study_abroad and is_primary_scheme:
            enabled = _dedupe_filters([*enabled, *profile_filters])
        scheme["narrow_if_too_many"] = _quality_narrowing_labels(quality_filters)
        scheme["required_filters"] = _dedupe_filters(required)
        scheme["base_filters"] = scheme["required_filters"]
        scheme["additional_filters"] = _dedupe_filters(additional)
        scheme["extra_filters"] = scheme["additional_filters"]
        scheme["enabled_additional_filters"] = _dedupe_filters(enabled)
        scheme["enabled_extra_filters"] = scheme["enabled_additional_filters"]
    plan["schemes"] = schemes[:PGY_COLLECTION_SCHEME_COUNT]
    plan["filters"] = [
        item
        for item in (plan.get("filters") or [])
        if isinstance(item, dict) and _is_manual_pgy_filter(item)
    ]
    return plan


def _normalize_brief_decomposition(value: Any, fallback: dict[str, Any]) -> dict[str, Any]:
    source = value if isinstance(value, dict) else {}
    fallback_source = fallback.get("briefDecomposition") if isinstance(fallback.get("briefDecomposition"), dict) else {}

    def list_of_dicts(key: str) -> list[dict[str, Any]]:
        items = source.get(key)
        if not isinstance(items, list):
            items = fallback_source.get(key) or []
        return [item for item in items if isinstance(item, dict)]

    def dict_value(key: str) -> dict[str, Any]:
        item = source.get(key)
        if not isinstance(item, dict):
            item = fallback_source.get(key) if isinstance(fallback_source.get(key), dict) else {}
        return item if isinstance(item, dict) else {}

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
        "promotion_audience_analysis": dict_value("promotion_audience_analysis"),
        "rule_placement_matrix": list_of_dicts("rule_placement_matrix"),
        "must_have_requirements": list_of_strings("must_have_requirements"),
        "strong_preferences": list_of_strings("strong_preferences"),
        "negative_constraints": list_of_strings("negative_constraints"),
        "assumptions": list_of_strings("assumptions"),
        "unknowns": list_of_strings("unknowns"),
        "backend_mappable_filters": list_of_dicts("backend_mappable_filters"),
        "proxy_filters": list_of_dicts("proxy_filters"),
        "post_score_rules": list_of_dicts("post_score_rules"),
        "manual_review_rules": list_of_strings("manual_review_rules"),
    }


def _contains_any_keyword(text: str, keywords: list[str]) -> bool:
    return any(keyword in text for keyword in keywords if keyword)


def _fallback_project_fit_config(brief: str, brief_decomposition: dict[str, Any] | None = None) -> dict[str, Any]:
    text = str(brief or "")
    is_koc = _brief_has_low_koc_budget(text) or bool(re.search(r"\bkoc\b|达人量级[^，。；;\n]*koc|项目[^，。；;\n]*koc", text, re.IGNORECASE))
    negative_constraints = []
    manual_review_rules = []
    if isinstance(brief_decomposition, dict):
        negative_constraints = [str(item).strip() for item in (brief_decomposition.get("negative_constraints") or []) if str(item).strip()]
        manual_review_rules = [str(item).strip() for item in (brief_decomposition.get("manual_review_rules") or []) if str(item).strip()]

    target_city_priority = []
    if _brief_mentions_region_priority(text):
        for city in ["北京", "上海", "广州", "深圳"]:
            if city in text:
                target_city_priority.append(city)
        if not target_city_priority:
            target_city_priority = ["北京", "上海"]

    if "答疑笔" in text:
        product_name = "有道答疑笔" if "有道" in text else "答疑笔"
        product_category = "学习答疑工具"
        core_users = ["小学高年级学生", "初中学生"]
        core_decision_makers = ["家长"]
        target_grade_keywords = ["六年级", "小升初", "初中", "初一", "初二", "初三", "高中", "高一", "高二", "高三"]
        parent_decision_keywords = ["家长", "妈妈", "爸爸", "陪学", "辅导", "家庭教育", "家校", "提分", "作业"]
        preferred_content_scenes = ["作业答疑", "错题讲解", "家长辅导", "学习规划", "中高考/升学"]
        preferred_presentation_styles = ["老师讲解型", "经验型", "测评对比型", "清单型"]
        discouraged_keywords = ["低幼", "启蒙", "早教", "孕期", "辅食", "纯生活方式", "纯情绪", "纯校园段子"]
        high_priority_signals = ["能讲清作业卡点和解法", "有真实家长辅导场景", "能展示工具使用前后差异", "内容里有提分、效率、错题复盘链路"]
        target_audience_summary = "重点看小学高年级到初中家庭，家长是决策者，学生是使用者。"
    elif "听课宝" in text:
        product_name = "有道留学听课宝" if "有道" in text else "听课宝"
        product_category = "留学听课与学习效率工具"
        core_users = ["海外留学生", "留学备考学生", "大学阶段学习者"]
        core_decision_makers = ["学生本人"]
        target_grade_keywords = ["留学", "海外", "大学", "本科", "研究生", "雅思", "托福", "课堂", "听课"]
        parent_decision_keywords = ["学生本人", "留学生", "海外学习", "课堂记录", "复习"]
        preferred_content_scenes = ["海外课堂听课", "课后复盘", "学习效率工具测评", "考试周复习", "留学学习日常"]
        preferred_presentation_styles = ["测评对比型", "教程型", "学习经验型", "真实场景演示型"]
        discouraged_keywords = ["低幼", "宝妈", "泛亲子", "纯生活方式", "全是vlog", "无学习内容"]
        high_priority_signals = ["有真实留学或海外课堂场景", "能讲清听课记录和课后复盘链路", "学习类内容占比高", "能展示工具使用前后效率差异"]
        target_audience_summary = "重点看留学生或海外学习人群，学生本人是核心使用者和决策者。"
    elif "点读笔" in text:
        product_name = "有道点读笔" if "有道" in text else "点读笔"
        product_category = "亲子阅读与语言学习工具"
        core_users = ["学龄前儿童", "小学低年级学生"]
        core_decision_makers = ["家长"]
        target_grade_keywords = ["幼儿园", "学龄前", "启蒙", "一年级", "二年级", "三年级", "小学低年级"]
        parent_decision_keywords = ["家长", "妈妈", "爸爸", "亲子阅读", "英语启蒙", "自主阅读", "发音", "查词"]
        preferred_content_scenes = ["亲子阅读", "英语启蒙", "自主阅读", "查词发音", "家长陪读"]
        preferred_presentation_styles = ["老师讲解型", "经验型", "日常记录型", "测评对比型"]
        discouraged_keywords = ["高考", "中考", "刷题", "错题", "纯鸡汤", "纯生活方式"]
        high_priority_signals = ["能展示孩子跟读或点读过程", "有真实亲子阅读场景", "能体现发音/查词/自主阅读价值"]
        target_audience_summary = "重点看亲子阅读和英语启蒙家庭，家长关注陪伴效率和孩子自主阅读体验。"
    else:
        product_name = "当前 Brief 产品"
        product_category = "教育产品"
        core_users = ["目标学生"]
        core_decision_makers = ["家长"]
        target_grade_keywords = ["小学", "初中", "高中", "大孩", "亲子"]
        parent_decision_keywords = ["家长", "妈妈", "爸爸", "亲子", "家庭教育", "学习"]
        preferred_content_scenes = ["学习规划", "家长辅导", "产品测评"]
        preferred_presentation_styles = ["经验型", "老师讲解型", "测评对比型"]
        discouraged_keywords = ["纯情绪", "纯生活方式", "低幼", "泛娱乐"]
        high_priority_signals = ["能讲清问题场景", "能自然承接产品", "有真实家庭或学习内容证据"]
        target_audience_summary = "优先看真正覆盖产品目标人群和决策者的内容。"

    return {
        "product_name": product_name,
        "product_category": product_category,
        "project_delivery_type": "KOC达人投放" if is_koc else "达人投放",
        "creator_matrix_type": "低预算KOC矩阵" if is_koc else "",
        "is_koc_project": bool(is_koc),
        "koc_activation_reason": "Brief明确提到KOC或达人量级为KOC时启用；不因低预算单独触发。" if is_koc else "",
        "summary": f"围绕{product_name}生成项目化评分配置，重点判断达人是否真的能自然承接产品使用场景与决策链路。",
        "target_audience_summary": target_audience_summary,
        "core_users": core_users,
        "core_decision_makers": core_decision_makers,
        "target_grade_keywords": target_grade_keywords,
        "parent_decision_keywords": parent_decision_keywords,
        "target_city_priority": target_city_priority,
        "preferred_content_scenes": preferred_content_scenes,
        "preferred_presentation_styles": preferred_presentation_styles,
        "discouraged_keywords": list(dict.fromkeys([*discouraged_keywords, *negative_constraints])),
        "high_priority_signals": high_priority_signals,
        "manual_review_focus": manual_review_rules,
        "evidence_rules": {
            "minimum_recent_note_count_for_high_score": 2,
            "require_scene_evidence_for_a_tier": True,
            "require_grade_or_parent_evidence_for_s_tier": True,
            "insufficient_evidence_max_score": 84,
            "weak_scene_match_max_score": 79,
            "negative_hit_max_score": 74,
        },
    }


def _is_stale_project_fit_config(value: dict[str, Any], brief: str) -> bool:
    if not isinstance(value, dict) or not value:
        return False
    text = str(brief or "")
    serialized = json.dumps(value, ensure_ascii=False)
    generic_product_names = {"当前 Brief 产品", "当前Brief产品", "教育产品", "项目产品"}
    product_name = str(value.get("product_name") or "").strip()
    if product_name in generic_product_names:
        return True
    if "答疑笔" in text and "答疑笔" not in serialized:
        return True
    if "听课宝" in text and "听课宝" not in serialized and any(keyword in serialized for keyword in ["家长", "亲子", "宝妈", "小学", "初中"]):
        return True
    return False


def _fallback_promotion_strategy(
    brief: str,
    brief_decomposition: dict[str, Any] | None,
    project_fit_config: dict[str, Any] | None,
) -> dict[str, Any]:
    fit = project_fit_config if isinstance(project_fit_config, dict) else _fallback_project_fit_config(brief, brief_decomposition)
    facts = []
    if isinstance(brief_decomposition, dict):
        facts = [str(item.get("fact") or "").strip() for item in (brief_decomposition.get("brief_facts") or []) if isinstance(item, dict) and str(item.get("fact") or "").strip()]
    product_name = str(fit.get("product_name") or "当前 Brief 产品")
    category = str(fit.get("product_category") or "项目产品")
    scenes = [str(item).strip() for item in (fit.get("preferred_content_scenes") or []) if str(item).strip()]
    styles = [str(item).strip() for item in (fit.get("preferred_presentation_styles") or []) if str(item).strip()]
    high_priority_signals = [str(item).strip() for item in (fit.get("high_priority_signals") or []) if str(item).strip()]
    return {
        "product_positioning": f"{product_name} / {category}",
        "target_users": fit.get("core_users") or ["Brief目标用户"],
        "decision_makers": fit.get("core_decision_makers") or ["Brief决策人群"],
        "core_selling_points": high_priority_signals or ["能解决目标人群的核心痛点", "内容能自然展示产品使用价值"],
        "conversion_scenes": scenes or ["产品使用场景", "痛点解决场景", "对比测评场景"],
        "content_angles": styles or ["经验分享型", "测评对比型", "场景演示型"],
        "creator_fit_hypotheses": [
            "达人长期内容应覆盖目标人群或使用场景",
            "达人表达方式应能自然讲清产品痛点、卖点和使用链路",
            "达人数据效率应支持本轮预算下的基础曝光、阅读或互动目标",
        ],
        "screening_implications": [
            "蒲公英前置只筛可执行字段，用类目/粉丝量/年龄/报价先召回候选池",
            "产品人群、真实身份、内容占比和卖点承接能力进入采后评分",
            "宽类目召回必须作为proxy补量，并限制配额和人工复核",
        ],
        "scoring_implications": [
            "相关性低的达人即使数据效率高也不能进入强推荐",
            "内容证据不足时降低人设与内容分，并标记待复核",
            "报价需结合CPM/CPC/CPE和近30天曝光/阅读/互动判断投放价值",
        ],
        "negative_fit_risks": (fit.get("discouraged_keywords") or [])[:8],
        "source_facts": facts[:8],
    }


def _normalize_promotion_strategy(
    value: Any,
    brief: str,
    brief_decomposition: dict[str, Any] | None,
    project_fit_config: dict[str, Any] | None,
    fallback_value: dict[str, Any] | None = None,
) -> dict[str, Any]:
    base = copy.deepcopy(
        fallback_value
        if isinstance(fallback_value, dict)
        else _fallback_promotion_strategy(brief, brief_decomposition, project_fit_config)
    )
    source = value if isinstance(value, dict) else {}
    for key, val in source.items():
        if val in (None, "", []):
            continue
        if isinstance(val, list):
            base[key] = [str(item).strip() for item in val if str(item).strip()]
        elif isinstance(val, dict):
            base[key] = val
        else:
            base[key] = str(val).strip()
    return base


def _keywords_from_values(values: list[Any], fallback: list[str], limit: int = 12) -> list[str]:
    keywords: list[str] = []
    for value in values:
        text = " ".join(str(item) for item in value.values() if item) if isinstance(value, dict) else str(value or "")
        for part in re.split(r"[、,，;；/|\s]+", text):
            part = part.strip()
            if 1 < len(part) <= 24 and part not in {"Brief", "未明确", "当前", "项目", "产品", "达人"}:
                keywords.append(part)
    keywords.extend(fallback)
    return list(dict.fromkeys(item for item in keywords if item))[:limit]


def _fallback_project_special_scoring(
    brief: str,
    brief_decomposition: dict[str, Any] | None = None,
    promotion_strategy: dict[str, Any] | None = None,
    project_fit_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    brief_decomposition = brief_decomposition if isinstance(brief_decomposition, dict) else {}
    promotion_strategy = promotion_strategy if isinstance(promotion_strategy, dict) else {}
    project_fit_config = project_fit_config if isinstance(project_fit_config, dict) else {}
    label = str(project_fit_config.get("product_name") or promotion_strategy.get("product_positioning") or "项目专属")[:24]
    facts = [item.get("fact") for item in brief_decomposition.get("brief_facts") or [] if isinstance(item, dict)]
    identity_keywords = _keywords_from_values(
        [*(promotion_strategy.get("target_users") or []), *(promotion_strategy.get("decision_makers") or []), *facts, *(brief_decomposition.get("must_have_requirements") or [])],
        ["目标用户", "决策者", "核心人群"],
    )
    scene_keywords = _keywords_from_values(
        [*(promotion_strategy.get("content_angles") or []), *(promotion_strategy.get("conversion_scenes") or []), *(project_fit_config.get("preferred_content_scenes") or []), *(brief_decomposition.get("strong_preferences") or [])],
        ["使用场景", "测评", "教程", "体验", "种草"],
        limit=18,
    )
    negative_keywords = _keywords_from_values(
        [*(brief_decomposition.get("negative_constraints") or []), *(promotion_strategy.get("negative_fit_risks") or []), *(project_fit_config.get("discouraged_keywords") or [])],
        ["弱相关", "泛化", "硬广"],
        limit=10,
    )
    return {
        "enabled": True,
        "label": label or "项目专属",
        "source": "brief_decomposition_fallback",
        "identity": {
            "name": "核心目标人群/身份",
            "points": 30,
            "fields": ["nickname", "creator_type", "persona_tags", "ip_city", "topic_point", "child_grade", "child_age"],
            "keywords": identity_keywords,
            "evidence_keywords": identity_keywords,
        },
        "scene": {
            "name": "Brief核心内容/转化场景",
            "max_points": 30,
            "base_points": 10,
            "points_per_hit": 4,
            "max_keyword_hits": 5,
            "direction_bonus": {"strong": 4, "medium": 2},
            "keywords": scene_keywords,
        },
        "data": {
            "max_points": 20,
            "good_points": 15,
            "excellent_points": 20,
            "read_ratio_points": [{"min": 0.75, "points": 10}, {"min": 0.5, "points": 6}],
            "interaction_bonus": [{"min": 120, "points": 4}, {"min": 60, "points": 2}],
        },
        "efficiency": {"max_points": 20, "good_points": 14, "excellent_points": 20, "fallback_points": 6},
        "tier_rules": {
            "s_min_priority_score": 86,
            "s_score": 95,
            "s_high_priority_score": 93,
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
        "negative": {"keywords": negative_keywords, "cap_without_scene": 84},
        "project_fit_config_patch": {
            "preferred_content_scenes": scene_keywords,
            "preferred_presentation_styles": _keywords_from_values(promotion_strategy.get("content_angles") or [], ["测评", "教程", "经验", "日常体验"], limit=8),
            "target_grade_keywords": project_fit_config.get("target_grade_keywords") or [],
            "parent_decision_keywords": project_fit_config.get("parent_decision_keywords") or [],
            "discouraged_keywords": negative_keywords,
        },
        "ignore_hard_filter_keywords": [],
        "generation_notes": "由 Brief 拆解、promotionStrategy 和 projectFitConfig 生成，供初筛评分解释器读取。",
    }


def _fallback_format_budget_policy(brief: str, budget_policy: dict[str, Any] | None = None) -> dict[str, Any]:
    text = str(brief or "")
    budget_policy = budget_policy if isinstance(budget_policy, dict) else {}
    cap = (
        parse_number(budget_policy.get("single_hard_cap"))
        or parse_number(budget_policy.get("single_creator_budget_cap"))
        or _brief_single_budget_cap(text)
    )
    preferred_format = "视频" if _brief_prefers_video(text) else "图文"
    mentions_image = any(keyword in text for keyword in ["图文", "图片", "笔记"])
    mentions_video = any(keyword in text for keyword in ["视频", "短视频"])
    if mentions_image and mentions_video:
        allowed_formats = ["图文", "视频"]
    elif mentions_video:
        allowed_formats = ["视频"]
    else:
        allowed_formats = ["图文"]
    if preferred_format not in allowed_formats:
        allowed_formats.append(preferred_format)
    result = {
        "allowed_formats": allowed_formats,
        "preferred_format": preferred_format,
        "single_creator_budget_cap": cap,
        "image_quote_field": "quote_price",
        "video_quote_field": "video_quote_price",
        "image_quote_cap": cap,
        "video_quote_cap": cap,
        "premium_exception_policy": {
            "enabled": True,
            "data_top_percent": 5,
            "max_budget_multiplier": 1.5,
            "decision": "enter_detail_completion",
            "rule": "当达人核心数据达到同量级前5%或优秀线以上，且对应合作形态报价不超过预算上限1.5倍时，不直接Pass，进入补详情/人工复核。",
        },
        "budget_rule": "按推荐投放形式校验预算；若偏好视频，必须读取视频报价；视频超预算但图文预算内时，只能推荐图文。",
    }
    return {key: value for key, value in result.items() if value not in (None, "", [])}


def _normalize_format_budget_policy(
    value: Any,
    brief: str,
    budget_policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    base = _fallback_format_budget_policy(brief, budget_policy)
    source = value if isinstance(value, dict) else {}
    allowed = source.get("allowed_formats") or source.get("allowedFormats") or base.get("allowed_formats") or []
    if isinstance(allowed, str):
        allowed = [item.strip() for item in re.split(r"[、,，/|]+", allowed) if item.strip()]
    normalized_allowed = []
    for item in allowed if isinstance(allowed, list) else []:
        text = str(item or "").strip()
        if "视频" in text:
            text = "视频"
        elif "图文" in text or "图片" in text:
            text = "图文"
        if text and text not in normalized_allowed:
            normalized_allowed.append(text)
    preferred = str(source.get("preferred_format") or source.get("preferredFormat") or base.get("preferred_format") or "").strip()
    if "视频" in preferred:
        preferred = "视频"
    elif "图文" in preferred or "图片" in preferred:
        preferred = "图文"
    elif normalized_allowed:
        preferred = normalized_allowed[0]
    if preferred and preferred not in normalized_allowed:
        normalized_allowed.append(preferred)
    is_koc_project = _brief_has_low_koc_budget(brief) or bool(re.search(r"\bkoc\b|达人量级[^，。；;\n]*koc|项目[^，。；;\n]*koc", str(brief or ""), re.IGNORECASE))
    single_cap = (
        parse_number(source.get("single_creator_budget_cap"))
        or parse_number(source.get("singleCreatorBudgetCap"))
        or parse_number(source.get("single_hard_cap"))
        or parse_number(source.get("singleHardCap"))
        or parse_number(base.get("single_creator_budget_cap"))
    )
    image_cap = (
        parse_number(source.get("image_quote_cap"))
        or parse_number(source.get("imageQuoteCap"))
        or single_cap
        or parse_number(base.get("image_quote_cap"))
    )
    video_cap = (
        parse_number(source.get("video_quote_cap"))
        or parse_number(source.get("videoQuoteCap"))
        or single_cap
        or parse_number(base.get("video_quote_cap"))
    )
    return {
        **base,
        **{key: val for key, val in source.items() if val not in (None, "", [])},
        "allowed_formats": normalized_allowed or base.get("allowed_formats") or ["图文"],
        "preferred_format": preferred or base.get("preferred_format") or "图文",
        "single_creator_budget_cap": single_cap,
        "image_quote_field": str(source.get("image_quote_field") or source.get("imageQuoteField") or base.get("image_quote_field") or "quote_price"),
        "video_quote_field": str(source.get("video_quote_field") or source.get("videoQuoteField") or base.get("video_quote_field") or "video_quote_price"),
        "image_quote_cap": image_cap,
        "video_quote_cap": video_cap,
        "koc_budget_gate": {
            "enabled": bool(is_koc_project),
            "activation_rule": "仅当Brief明确KOC或项目配置选择KOC时启用；低预算本身不自动触发KOC结构。",
            "stage1_decision": "一阶段只决定入库/补详情优先级，不直接产出强推荐。",
        },
        "premium_exception_policy": _normalize_premium_exception_policy(
            source.get("premium_exception_policy") or source.get("premiumExceptionPolicy"),
            base.get("premium_exception_policy") if isinstance(base.get("premium_exception_policy"), dict) else {},
        ),
    }


def _normalize_premium_exception_policy(value: Any, fallback: dict[str, Any]) -> dict[str, Any]:
    source = value if isinstance(value, dict) else {}
    result = {**fallback, **{key: val for key, val in source.items() if val not in (None, "")}}
    if "maxBudgetMultiplier" in source:
        result["max_budget_multiplier"] = source.get("maxBudgetMultiplier")
    if "dataTopPercent" in source:
        result["data_top_percent"] = source.get("dataTopPercent")
    result["enabled"] = result.get("enabled") is not False
    multiplier = parse_number(result.get("max_budget_multiplier"))
    top_percent = parse_number(result.get("data_top_percent"))
    result["max_budget_multiplier"] = multiplier if multiplier is not None else 1.5
    result["data_top_percent"] = top_percent if top_percent is not None else 5
    result["decision"] = str(result.get("decision") or "enter_detail_completion")
    return result


KOC_SAMPLE_CALIBRATED_SCORING_GUIDE = {
    "source": "真实优质样本校准后的规则",
    "sample_size": 126,
    "quote_reference": {"median": 600, "p75": 780, "accept_max": 1000},
    "read_reference": {"p25": 1279, "median": 2402, "p75": 4117},
    "interaction_reference": {"p25": 116, "median": 274, "p75": 461},
    "efficiency_reference": {"cpe_median": 2.16, "cpe_p75": 3.81, "cpe_observe_max": 10, "cpm_p75": 65.85, "cpm_risk_max": 100},
    "content_reference": {"target_content_required_ratio": 0.5, "identity_trace_reference_ratio": 0.25},
    "weight_guidance": {"budget": 18, "fans": 5, "cpe": 22, "engagement": 25, "persona": 20, "content": 10},
    "decision_principles": [
        "一阶段只决定入库/补详情优先级，不直接产出强推荐。",
        "粉丝量只做T级坐标，CPE、阅读、互动和内容证据权重更高。",
        "缺主页、近期笔记正文、合作笔记或回复率时，不得直接强推荐。",
        "vlog/旅行/海外日常等冲突内容按占比风险处理，不因单个关键词直接Pass。",
        "只有双方报价均超预算且无高数据溢价例外、无接单权限、回复率明确低于阈值、链接失效等才硬Pass。",
    ],
}


def _fallback_koc_scoring_config(brief: str) -> dict[str, Any]:
    if not (_brief_has_low_koc_budget(brief) or re.search(r"\bkoc\b|达人量级[^，。；;\n]*koc|项目[^，。；;\n]*koc", str(brief or ""), re.IGNORECASE)):
        return {}
    return {
        "enabled": True,
        "architecture": "koc_two_stage_scoring",
        "stage1_labels": ["P0", "P1", "P2", "P3", "不入库"],
        "stage1_thresholds": {
            "budget_full_score_max": 800,
            "budget_accept_max": 1000,
            "premium_backup_max": 1600,
            "read_priority_min": 1000,
            "read_strong_min": 2400,
            "interaction_priority_min": 100,
            "interaction_strong_min": 274,
            "cpe_strong_max": 3.8,
            "cpe_priority_max": 7,
            "cpe_observe_max": 10,
            "cpm_risk_max": 100,
        },
        "detail_stage_rules": {
            "note_sample_min": 8,
            "minimum_sample_for_decision": 5,
            "target_content_required_ratio": 0.5,
            "identity_trace_reference_ratio": 0.25,
            "product_scene_strong_ratio": 0.25,
            "conflict_warning_ratio": 0.5,
            "conflict_is_hard_only_when_target_below": 0.5,
            "missing_evidence_status": "待人工确认",
        },
        "final_match_thresholds": {
            "good_read_min": 1000,
            "good_interaction_min": 100,
            "good_cpe_max": 7,
            "strong_read_min": 2400,
            "strong_interaction_min": 274,
            "strong_cpe_max": 3.8,
        },
        "weight_guidance": {
            "budget": 18,
            "fans": 5,
            "cpe": 22,
            "engagement": 25,
            "persona": 20,
            "content": 10,
        },
        "negative_policy": "vlog/旅行/海外日常按占比风险处理；只在学习内容不足且冲突内容占比过高时强降级。",
        "evidence_policy": "一阶段只决定入库/补详情优先级；缺主页简介、近期笔记正文、合作笔记或回复率时不得直接强推荐。",
    }


def _normalize_koc_scoring_config(value: Any, brief: str) -> dict[str, Any]:
    base = _fallback_koc_scoring_config(brief)
    source = value if isinstance(value, dict) else {}
    if not base and not source:
        return {}
    result = {**base, **{key: val for key, val in source.items() if val not in (None, "", [])}}
    for section in ("stage1_thresholds", "detail_stage_rules", "final_match_thresholds", "weight_guidance"):
        merged = {}
        if isinstance(base.get(section), dict):
            merged.update(base[section])
        if isinstance(source.get(section), dict):
            merged.update({key: val for key, val in source[section].items() if val not in (None, "")})
        if merged:
            result[section] = merged
    result["enabled"] = result.get("enabled") is not False
    return result


def _fallback_hard_rules(brief: str, project_fit_config: dict[str, Any] | None = None) -> dict[str, Any]:
    text = str(brief or "")
    fit = project_fit_config if isinstance(project_fit_config, dict) else {}
    study_abroad = _brief_is_study_abroad(text) or any("留学" in str(item) or "海外" in str(item) for item in (fit.get("core_users") or []))
    low_like_threshold = 20 if any(keyword in text for keyword in ["个位数", "十几", "低赞", "点赞"]) else None
    return {
        "must_have_commercial_order": any(keyword in text for keyword in ["接过商单", "商单", "合作笔记"]),
        "reply_rate_min": 0.5 if any(keyword in text for keyword in ["回复率", "回复"]) else 0.5,
        "recent_update_days": 30 if any(keyword in text for keyword in ["近1个月", "近一个月", "1个月内", "30天", "近期"]) else None,
        "low_like_threshold": low_like_threshold,
        "ignore_low_like_if_same_day": True,
        "must_have_identity_match": bool(study_abroad),
        "must_have_study_abroad_trace": bool(study_abroad),
        "must_have_study_content_ratio": 0.5 if any(keyword in text for keyword in ["50%以上学习", "50%学习", "学习类内容需要50", "学习类内容 50"]) else None,
        "commercial_order_rule": "仅在已有合作笔记/商单字段明确证明时通过；缺字段进入补全，不直接淘汰。",
        "identity_rule": "必须基于类目、人设、标签、地域、近期标题/正文、主页信息等多字段综合判断，不能只看昵称。",
    }


def _normalize_hard_rules(value: Any, brief: str, project_fit_config: dict[str, Any] | None = None) -> dict[str, Any]:
    base = _fallback_hard_rules(brief, project_fit_config)
    source = value if isinstance(value, dict) else {}
    result = {**base, **{key: val for key, val in source.items() if val not in (None, "")}}
    aliases = {
        "mustHaveCommercialOrder": "must_have_commercial_order",
        "replyRateMin": "reply_rate_min",
        "recentUpdateDays": "recent_update_days",
        "lowLikeThreshold": "low_like_threshold",
        "ignoreLowLikeIfSameDay": "ignore_low_like_if_same_day",
        "mustHaveIdentityMatch": "must_have_identity_match",
        "mustHaveStudyAbroadTrace": "must_have_study_abroad_trace",
        "mustHaveStudyContentRatio": "must_have_study_content_ratio",
    }
    for source_key, target_key in aliases.items():
        if source_key in source and source[source_key] not in (None, ""):
            result[target_key] = source[source_key]
    for key in ("reply_rate_min", "must_have_study_content_ratio"):
        parsed = ratio(result.get(key))
        result[key] = parsed
    for key in ("recent_update_days", "low_like_threshold"):
        parsed = parse_number(result.get(key))
        result[key] = int(parsed) if parsed is not None else None
    for key in ("must_have_commercial_order", "ignore_low_like_if_same_day", "must_have_identity_match", "must_have_study_abroad_trace"):
        result[key] = bool(result.get(key))
    result["koc_activation_rule"] = "仅当Brief明确KOC或项目配置选择KOC时启用；低预算本身不自动触发KOC结构。"
    result["stage_policy"] = "KOC项目先做一阶段入库/补详情优先级，再做二阶段项目匹配；证据不足输出待人工确认或备选。"
    return result


def _normalize_project_special_scoring(value: Any, fallback: dict[str, Any]) -> dict[str, Any]:
    config = copy.deepcopy(value) if isinstance(value, dict) else {}
    if config.get("enabled") is False:
        return {"enabled": False}
    config = {**copy.deepcopy(fallback), **config} if config else copy.deepcopy(fallback)
    config["enabled"] = config.get("enabled", True)
    for section in ("identity", "scene", "data", "efficiency", "tier_rules", "negative"):
        defaults = fallback.get(section) if isinstance(fallback.get(section), dict) else {}
        source = config.get(section) if isinstance(config.get(section), dict) else {}
        config[section] = {**defaults, **source}
    identity = config["identity"]
    identity["fields"] = identity.get("fields") or ["nickname", "creator_type", "persona_tags", "ip_city", "topic_point"]
    identity["keywords"] = [str(item).strip() for item in (identity.get("keywords") or []) if str(item).strip()]
    identity["evidence_keywords"] = [str(item).strip() for item in (identity.get("evidence_keywords") or identity.get("keywords") or []) if str(item).strip()]
    scene = config["scene"]
    scene["keywords"] = [str(item).strip() for item in (scene.get("keywords") or []) if str(item).strip()]
    scene["direction_bonus"] = scene.get("direction_bonus") if isinstance(scene.get("direction_bonus"), dict) else {"strong": 4, "medium": 2}
    for key in ("read_ratio_points", "interaction_bonus"):
        if not isinstance(config["data"].get(key), list):
            config["data"][key] = fallback.get("data", {}).get(key, [])
    config["negative"]["keywords"] = [str(item).strip() for item in (config["negative"].get("keywords") or []) if str(item).strip()]
    patch = config.get("project_fit_config_patch") if isinstance(config.get("project_fit_config_patch"), dict) else {}
    fallback_patch = fallback.get("project_fit_config_patch") if isinstance(fallback.get("project_fit_config_patch"), dict) else {}
    config["project_fit_config_patch"] = {**fallback_patch, **patch}
    config["ignore_hard_filter_keywords"] = [str(item).strip() for item in (config.get("ignore_hard_filter_keywords") or []) if str(item).strip()]
    return config


def _normalize_project_fit_config(
    value: Any,
    brief: str,
    brief_decomposition: dict[str, Any] | None,
    fallback_value: dict[str, Any] | None = None,
) -> dict[str, Any]:
    base = copy.deepcopy(fallback_value if isinstance(fallback_value, dict) else _fallback_project_fit_config(brief, brief_decomposition))
    source = value if isinstance(value, dict) else {}
    if _is_stale_project_fit_config(source, brief):
        source = {}

    string_fields = ["product_name", "product_category", "summary", "target_audience_summary"]
    list_fields = [
        "core_users",
        "core_decision_makers",
        "target_grade_keywords",
        "parent_decision_keywords",
        "target_city_priority",
        "preferred_content_scenes",
        "preferred_presentation_styles",
        "discouraged_keywords",
        "high_priority_signals",
        "manual_review_focus",
    ]
    for field in string_fields:
        text = str(source.get(field) or "").strip()
        if text:
            base[field] = text
    for field in list_fields:
        items = source.get(field)
        if isinstance(items, list):
            base[field] = [str(item).strip() for item in items if str(item).strip()]

    evidence_rules = source.get("evidence_rules")
    if isinstance(evidence_rules, dict):
        base_rules = base.get("evidence_rules") if isinstance(base.get("evidence_rules"), dict) else {}
        base["evidence_rules"] = {
            **base_rules,
            **{key: evidence_rules[key] for key in evidence_rules if evidence_rules.get(key) not in (None, "")},
        }
    return base


def _hydrate_screening_plan_project_defaults(plan: dict[str, Any], brief: str) -> dict[str, Any]:
    normalized = copy.deepcopy(plan or {})
    brief_decomposition = (
        normalized.get("briefDecomposition")
        if isinstance(normalized.get("briefDecomposition"), dict)
        else normalized.get("brief_decomposition")
        if isinstance(normalized.get("brief_decomposition"), dict)
        else None
    )
    project_fit_config = _normalize_project_fit_config(
        normalized.get("projectFitConfig"),
        brief,
        brief_decomposition,
    )
    promotion_strategy = _normalize_promotion_strategy(
        normalized.get("promotionStrategy") or normalized.get("productPromotionStrategy"),
        brief,
        brief_decomposition,
        project_fit_config,
    )
    normalized["projectSpecialScoring"] = _normalize_project_special_scoring(
        normalized.get("projectSpecialScoring") or normalized.get("specialScoringPolicy") or normalized.get("project_scoring_policy"),
        _fallback_project_special_scoring(brief, brief_decomposition, promotion_strategy, project_fit_config),
    )
    normalized["kocScoringConfig"] = _normalize_koc_scoring_config(
        normalized.get("kocScoringConfig") or normalized.get("koc_scoring_config"),
        brief,
    )
    budget_policy_source = normalized.get("budgetPolicy")
    if not isinstance(budget_policy_source, dict):
        scoring_criteria = normalized.get("scoringCriteria") if isinstance(normalized.get("scoringCriteria"), dict) else {}
        budget_policy_source = scoring_criteria.get("budget_policy") if isinstance(scoring_criteria.get("budget_policy"), dict) else {}
    budget_policy = _normalize_budget_policy(
        budget_policy_source,
        _fallback_screening_standard(ScreeningStandardPayload(brief=brief)).get("budgetPolicy") if brief else {},
        brief,
    )
    normalized["budgetPolicy"] = budget_policy
    if isinstance(normalized.get("kocScoringConfig"), dict) and normalized["kocScoringConfig"].get("enabled") is not False:
        normalized["scoringWeights"] = _weights_from_koc_guidance(
            normalized.get("scoringWeights") if isinstance(normalized.get("scoringWeights"), dict) else {},
            normalized["kocScoringConfig"],
        )
    normalized["formatBudgetPolicy"] = _normalize_format_budget_policy(
        normalized.get("formatBudgetPolicy") or normalized.get("format_budget_policy"),
        brief,
        budget_policy,
    )
    normalized["hardRules"] = _normalize_hard_rules(
        normalized.get("hardRules") or normalized.get("hard_rules") or normalized.get("projectHardRules"),
        brief,
        project_fit_config,
    )
    normalized["projectFitConfig"] = project_fit_config
    normalized["promotionStrategy"] = promotion_strategy
    scoring_criteria = normalized.get("scoringCriteria") if isinstance(normalized.get("scoringCriteria"), dict) else {}
    if scoring_criteria:
        normalized["scoringCriteria"] = {
            **scoring_criteria,
            "format_budget_policy": scoring_criteria.get("format_budget_policy") or normalized["formatBudgetPolicy"],
            "project_hard_rules": scoring_criteria.get("project_hard_rules") or normalized["hardRules"],
        }
    return normalized


def _hydrate_project_for_response(project: dict[str, Any] | None) -> dict[str, Any] | None:
    if not project:
        return project
    plan = _normalize_project_screening_plan(project.get("screening_plan"))
    if not plan:
        return project
    brief = str(project.get("brief") or project.get("project_name") or "")
    hydrated = _hydrate_screening_plan_project_defaults(plan, brief)
    if hydrated == plan:
        return project
    result = dict(project)
    result["screening_plan"] = json.dumps(hydrated, ensure_ascii=False)
    return result


def _hydrate_projects_for_response(projects: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        hydrated if isinstance(hydrated, dict) else project
        for project in projects
        for hydrated in [_hydrate_project_for_response(project)]
    ]


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
    project_fit_config = _normalize_project_fit_config(
        plan.get("projectFitConfig") or result.get("projectFitConfig"),
        payload.brief,
        brief_decomposition,
        fallback.get("projectFitConfig") if isinstance(fallback.get("projectFitConfig"), dict) else None,
    )
    promotion_strategy = _normalize_promotion_strategy(
        plan.get("promotionStrategy") or plan.get("productPromotionStrategy") or result.get("promotionStrategy") or result.get("productPromotionStrategy"),
        payload.brief,
        brief_decomposition,
        project_fit_config,
        fallback.get("promotionStrategy") if isinstance(fallback.get("promotionStrategy"), dict) else None,
    )
    project_special_scoring = _normalize_project_special_scoring(
        plan.get("projectSpecialScoring") or plan.get("specialScoringPolicy") or plan.get("project_scoring_policy") or result.get("projectSpecialScoring") or result.get("specialScoringPolicy") or result.get("project_scoring_policy"),
        fallback.get("projectSpecialScoring")
        if isinstance(fallback.get("projectSpecialScoring"), dict)
        else _fallback_project_special_scoring(payload.brief, brief_decomposition, promotion_strategy, project_fit_config),
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
        pgy_plan = _enforce_scheme_distinct_collection_logic(pgy_plan, payload.brief)
        pgy_plan = _normalize_scheme_filter_structure(pgy_plan)
    scoring_criteria = plan.get("scoringCriteria") or plan.get("matchingCriteria") or fallback["scoringCriteria"]
    budget_policy = _normalize_budget_policy(
        plan.get("budgetPolicy") or (scoring_criteria.get("budget_policy") if isinstance(scoring_criteria, dict) else None),
        fallback.get("budgetPolicy") if isinstance(fallback.get("budgetPolicy"), dict) else {},
        payload.brief,
    )
    format_budget_policy = _normalize_format_budget_policy(
        plan.get("formatBudgetPolicy")
        or plan.get("format_budget_policy")
        or result.get("formatBudgetPolicy")
        or result.get("format_budget_policy"),
        payload.brief,
        budget_policy,
    )
    hard_rules = _normalize_hard_rules(
        plan.get("hardRules")
        or plan.get("hard_rules")
        or plan.get("projectHardRules")
        or result.get("hardRules")
        or result.get("hard_rules")
        or result.get("projectHardRules"),
        payload.brief,
        project_fit_config,
    )
    tier_policy = plan.get("tierPolicy") or (scoring_criteria.get("tier_policy") if isinstance(scoring_criteria, dict) else None) or fallback.get("tierPolicy") or {}
    data_layer_scoring = plan.get("dataLayerScoring") or (scoring_criteria.get("data_layer_scoring") if isinstance(scoring_criteria, dict) else None) or fallback.get("dataLayerScoring") or {}
    koc_scoring_config = _normalize_koc_scoring_config(
        plan.get("kocScoringConfig")
        or plan.get("koc_scoring_config")
        or result.get("kocScoringConfig")
        or result.get("koc_scoring_config"),
        payload.brief,
    )
    weights = _weights_from_koc_guidance(weights, koc_scoring_config)
    if isinstance(scoring_criteria, dict):
        post_score_rules = scoring_criteria.get("post_score_rules")
        if not isinstance(post_score_rules, list):
            post_score_rules = []
        scoring_criteria = {
            **scoring_criteria,
            "budget_policy": scoring_criteria.get("budget_policy") or budget_policy,
            "format_budget_policy": scoring_criteria.get("format_budget_policy") or format_budget_policy,
            "project_hard_rules": scoring_criteria.get("project_hard_rules") or hard_rules,
            "tier_policy": scoring_criteria.get("tier_policy") or tier_policy,
            "data_layer_scoring": scoring_criteria.get("data_layer_scoring") or data_layer_scoring,
            "dimension_weights": scoring_criteria.get("dimension_weights") or weights,
            "hard_rules": scoring_criteria.get("hard_rules") or hard_filters,
            "post_score_rules": post_score_rules,
        }
        scoring_criteria["hard_rules"] = scoring_hard_filters
    normalized = {
        "briefType": plan.get("briefType") or fallback["briefType"],
        "budgetPolicy": budget_policy,
        "formatBudgetPolicy": format_budget_policy,
        "hardRules": hard_rules,
        "tierPolicy": tier_policy,
        "dataLayerScoring": data_layer_scoring,
        "collectionHardFilters": collection_hard_filters,
        "scoringHardFilters": scoring_hard_filters,
        "hardFilters": hard_filters,
        "briefDecomposition": brief_decomposition,
        "projectFitConfig": project_fit_config,
        "promotionStrategy": promotion_strategy,
        "projectSpecialScoring": project_special_scoring,
        "kocScoringConfig": koc_scoring_config,
        "scoringWeights": weights,
        "scoringCriteria": scoring_criteria,
        "fieldMappings": plan.get("fieldMappings") or result.get("fieldMappings") or fallback["fieldMappings"],
        "pgyCollectionPlan": pgy_plan,
        "summary": plan.get("summary") or result.get("summary") or fallback["summary"],
    }
    return _prune_default_fan_age_hard_filters_for_brief(normalized, payload.brief)


def _sync_screening_plan_criteria(plan: dict[str, Any]) -> dict[str, Any]:
    normalized = copy.deepcopy(plan or {})
    def normalize_hard_filters(items: Any) -> list[dict[str, Any]]:
        cleaned = items or []
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
            for item in cleaned
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
    if "collectionHardFilters" in normalized:
        collection_hard_filters = normalize_hard_filters(normalized.get("collectionHardFilters") or [])
    elif "hard_filters" in pgy_plan or "hardFilters" in pgy_plan:
        collection_hard_filters = normalize_hard_filters(pgy_plan.get("hard_filters") or pgy_plan.get("hardFilters") or [])
    else:
        collection_hard_filters = normalize_hard_filters(pgy_filter_hard_filters or legacy_hard_filters)
    scoring_criteria_source = normalized.get("scoringCriteria") if isinstance(normalized.get("scoringCriteria"), dict) else {}
    scoring_hard_filters = normalize_hard_filters(
        normalized.get("scoringHardFilters") or scoring_criteria_source.get("hard_rules"),
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
        "format_budget_policy": scoring_criteria.get("format_budget_policy") or normalized.get("formatBudgetPolicy") or {},
        "project_hard_rules": scoring_criteria.get("project_hard_rules") or normalized.get("hardRules") or {},
        "tier_policy": scoring_criteria.get("tier_policy") or normalized.get("tierPolicy") or {},
        "data_layer_scoring": scoring_criteria.get("data_layer_scoring") or normalized.get("dataLayerScoring") or {},
        "hard_rules": scoring_hard_filters,
        "dimension_weights": scoring_criteria.get("dimension_weights") or normalized.get("scoringWeights") or {},
    }
    normalized["scoringCriteria"] = scoring_criteria
    if not isinstance(normalized.get("projectFitConfig"), dict):
        normalized["projectFitConfig"] = {}
    brief_text = json.dumps(normalized.get("briefDecomposition") or {}, ensure_ascii=False)
    normalized["projectSpecialScoring"] = _normalize_project_special_scoring(
        normalized.get("projectSpecialScoring") or normalized.get("specialScoringPolicy") or normalized.get("project_scoring_policy"),
        _fallback_project_special_scoring(
            brief_text,
            normalized.get("briefDecomposition") if isinstance(normalized.get("briefDecomposition"), dict) else {},
            normalized.get("promotionStrategy") if isinstance(normalized.get("promotionStrategy"), dict) else {},
            normalized.get("projectFitConfig") if isinstance(normalized.get("projectFitConfig"), dict) else {},
        ),
    )
    normalized["kocScoringConfig"] = _normalize_koc_scoring_config(
        normalized.get("kocScoringConfig") or normalized.get("koc_scoring_config"),
        brief_text,
    )
    return normalized


def _creator_no_order_permission_issue(creator: dict[str, Any], raw_payload: dict[str, Any] | None = None) -> str:
    raw = raw_payload if isinstance(raw_payload, dict) else {}
    values = [
        creator.get("order_permission_status"),
        raw.get("order_permission_status"),
        raw.get("text"),
        raw.get("detail_text"),
        raw.get("raw_table"),
        raw.get("list_api_kol"),
    ]
    text = "".join(
        json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else str(value or "")
        for value in values
    )
    compact = re.sub(r"\s+", "", text)
    if any(hint in compact for hint in ["无接单权限", "暂无接单权限", "不可接单", "不能接单", "暂不接单", "未开通接单"]):
        return "接单权限：蒲公英显示无接单权限，无法发起合作"
    return ""


def _creator_hard_filter_issues(project_id: str, creator: dict[str, Any], hard_filters: list[dict[str, Any]]) -> list[str]:
    normalized = normalize_creator(creator, project_id)
    source_raw_payload = creator.get("raw_payload") if isinstance(creator.get("raw_payload"), dict) else {}
    text_blob = " ".join(
        str(normalized.get(key) or "")
        for key in ["nickname", "creator_type", "persona_tags", "ip_city", "topic_point", "child_age", "child_grade"]
    )
    if source_raw_payload:
        text_blob = f"{text_blob} {json.dumps(source_raw_payload, ensure_ascii=False)}"
    category_items: list[dict[str, Any]] = []
    issues: list[str] = []
    no_order_issue = _creator_no_order_permission_issue(creator, source_raw_payload)
    if no_order_issue:
        issues.append(no_order_issue)
    for item in hard_filters or []:
        if item.get("required") is False:
            continue
        field = str(item.get("field") or item.get("standard") or "")
        condition = str(item.get("condition") or "")
        value = str(item.get("value") or "")
        pgy_field = str(item.get("pgyField") or "")
        if field in {"营销目标"} or pgy_field in {"营销目标"}:
            continue
        if field == "博主类目":
            category_items.append(item)
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
            cpc = parse_number(normalized.get("effective_cpc")) or parse_number(normalized.get("natural_cpc"))
            if cpc is not None and cpc >= threshold:
                issues.append(f"{label}：CPC {cpc:g} 未低于 {threshold:g}")
        if "cpe" in text:
            threshold = _threshold_from_text(value, "cpe", 20)
            cpe = parse_number(normalized.get("effective_cpe")) or parse_number(normalized.get("natural_cpe"))
            if cpe is not None and cpe >= threshold:
                issues.append(f"{label}：CPE {cpe:g} 未低于 {threshold:g}")
        if any(keyword in text for keyword in ["搜索+推荐", "搜索推荐"]):
            if str(normalized.get("search_recommend_review_status") or "") != "已复核":
                issues.append(f"{label}：搜索+推荐占比待人工复核")
        if any(keyword in text for keyword in ["孩子年级", "小升初", "初中", "高中", "大孩"]):
            expected_values = _expand_rule_values(_split_rule_values(value) or ["小升初", "初中", "高中", "初一", "初二", "初三", "高一", "高二", "高三", "大孩"])
            if not any(keyword in text_blob for keyword in expected_values):
                issues.append(f"{label}：未识别到小升初/初中/高中大孩场景")
        if any(keyword in text for keyword in ["限流", "违规", "流量稳定", "异常"]):
            risk_text = f"{normalized.get('rate_limit_risk') or ''} {normalized.get('traffic_stability') or ''}"
            if any(keyword in risk_text for keyword in ["高", "限流", "违规", "异常"]):
                issues.append(f"{label}：存在限流/异常流量风险")
        if condition in {"包含", "匹配", "约等于", "优先"} and value and not any(
            keyword in text for keyword in ["报价", "预算", "合作价格", "平台价格", "35", "34", "粉丝年龄", "宝妈", "家长", "cpc", "cpe", "搜索+推荐", "搜索推荐", "孩子年级", "小升初", "初中", "高中", "大孩", "限流", "违规", "流量稳定", "异常"]
        ):
            expected_values = _expand_rule_values(_split_rule_values(value))
            if expected_values and not any(keyword in text_blob for keyword in expected_values):
                issues.append(f"{label}：未识别到匹配信息")
        if condition in {"不包含", "规避"} and value and not any(keyword in text for keyword in ["限流", "违规", "流量稳定", "异常"]):
            avoided_values = _expand_rule_values(_split_rule_values(value))
            if avoided_values and any(keyword in text_blob for keyword in avoided_values):
                issues.append(f"{label}：命中规避项")
    if category_items:
        if not any(_creator_blogger_category_match(normalized, source_raw_payload, item) for item in category_items):
            category_labels = " / ".join(dict.fromkeys(_creator_blogger_category_label(item) for item in category_items))
            issues.append(f"博主类目：未命中 {category_labels}")
    return list(dict.fromkeys(issues))


def _creator_blogger_category_label(item: dict[str, Any]) -> str:
    value = str(item.get("value") or item.get("standard") or "").strip()
    sub_value = str(item.get("sub_value") or item.get("subValue") or "").strip()
    return f"{value}-{sub_value}" if sub_value else value


def _creator_blogger_category_match_terms(item: dict[str, Any]) -> list[str]:
    value = str(item.get("value") or item.get("standard") or "").strip()
    sub_value = str(item.get("sub_value") or item.get("subValue") or "").strip()
    terms: list[str] = [value, sub_value]
    if value == "教育":
        if sub_value == "家庭教育":
            terms.extend(["家庭教育", "家庭", "家长", "亲子", "父母", "妈妈", "陪伴", "规划"])
        elif sub_value == "k12教育":
            terms.extend(["k12教育", "k12", "小学", "初中", "高中", "教辅", "答疑", "作业", "升学"])
        elif sub_value == "学习日常":
            terms.extend(["学习日常", "学习效率", "学习工具", "学习博主", "学霸", "学习"])
        elif sub_value == "留学教育":
            terms.extend(["留学教育", "留学", "国际学校", "海外教育"])
        elif sub_value == "大学教育":
            terms.extend(["大学教育", "大学", "高校"])
        elif sub_value == "语言教育":
            terms.extend(["语言教育", "英语", "外语", "语文"])
        else:
            terms.extend(["教育", "学习", "升学", "教辅", "答疑", "家长", "亲子"])
    elif value == "母婴":
        if sub_value == "育儿经验":
            terms.extend(["育儿经验", "育儿", "亲子", "家长", "父母", "妈妈", "爸爸", "宝宝", "孩子", "大孩", "小升初", "初中", "高中"])
        elif sub_value == "早教":
            terms.extend(["早教", "启蒙", "幼儿", "低龄", "学龄前"])
        elif sub_value == "母婴日常":
            terms.extend(["母婴日常", "日常", "家庭"])
        elif sub_value == "婴童用品":
            terms.extend(["婴童用品", "母婴用品", "宝宝用品"])
        else:
            terms.extend(["母婴", "育儿", "亲子", "妈妈", "宝宝"])
    return list(dict.fromkeys(term for term in terms if term))


def _creator_blogger_category_match(normalized: dict[str, Any], raw_payload: dict[str, Any], item: dict[str, Any]) -> bool:
    text_blob = " ".join(
        str(normalized.get(key) or "")
        for key in ["nickname", "creator_type", "persona_tags", "ip_city", "topic_point", "child_age", "child_grade"]
    )
    if raw_payload:
        text_blob = f"{text_blob} {json.dumps(raw_payload, ensure_ascii=False)}"
    text_blob = text_blob.lower()
    return any(keyword.lower() in text_blob for keyword in _creator_blogger_category_match_terms(item))


def _filter_creators_by_hard_filters(
    project_id: str,
    creators: list[dict[str, Any]],
    hard_filters: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
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


def _brief_single_budget_cap(brief: str) -> float | None:
    text = str(brief or "")
    if not text:
        return None
    patterns = [
        r"(?:单达人|单个达人|单人|达人)?(?:预算|报价|合作报价|费用|价格)[^\d一二三四五六七八九十百千万]{0,12}(\d+(?:\.\d+)?)\s*(万|千|k|K|元)?\s*(?:以下|以内|内|不超过|小于|≤|<)",
        r"(\d+(?:\.\d+)?)\s*(万|千|k|K|元)?\s*(?:以下|以内|内|不超过).{0,12}(?:KOC|达人|博主)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if not match:
            continue
        amount = parse_number(match.group(1))
        if amount is None:
            continue
        unit = match.group(2) or ""
        if unit == "万":
            amount *= 10000
        elif unit in {"千", "k", "K"}:
            amount *= 1000
        if amount > 0:
            return float(amount)
    return None


def _pgy_filter_field_guide() -> dict[str, Any]:
    def normalize_options(value: Any) -> Any:
        if isinstance(value, list):
            normalized = []
            for item in value:
                if isinstance(item, dict):
                    normalized.append({
                        key: normalize_options(val)
                        for key, val in item.items()
                        if key in {"label", "options", "value", "children"}
                    })
                else:
                    normalized.append(item)
            return normalized
        return value

    fields = []
    for item in PGY_FILTER_CATALOG:
        if not isinstance(item, dict):
            continue
        field = str(item.get("field") or "").strip()
        if not field:
            continue
        if field in PGY_BASE_FILTER_FIELDS:
            usage_group = "required_filters_allowed"
            llm_usage = "可放入每套方案的 required_filters；其中博主类目可多条，粉丝量只设下限，合作报价按图文/视频子字段设置。"
        elif field in PGY_PROFILE_EXTRA_FILTER_FIELDS:
            usage_group = "additional_filters_allowed"
            llm_usage = "高频画像筛选；Brief 明确要求且选项真实存在时，可放入 additional_filters 或 enabled_additional_filters，但不要作为每套方案的 required_filters。"
        elif field in PGY_EXTRA_FILTER_FIELDS:
            usage_group = "additional_filters_allowed"
            llm_usage = "只放入 additional_filters 或 enabled_additional_filters，用于数量过多时提质收窄；不要作为主池必备条件。"
        elif field in PGY_MANUAL_ONLY_FILTER_FIELDS:
            usage_group = "manual_only"
            llm_usage = "只允许用户手动添加或作为待补充建议；不要自动放入 required_filters。"
        else:
            usage_group = "cautious_or_manual"
            llm_usage = "谨慎使用；只有 Brief 明确要求且字段选项真实存在时，才作为手动 filters 或低优先级附加条件。"
        fields.append(
            {
                "field": field,
                "usage_group": usage_group,
                "control_type": item.get("control_type") or "",
                "options": normalize_options(item.get("options") or []),
                "option_groups": normalize_options(item.get("option_groups") or []),
                "sub_fields": normalize_options(item.get("sub_fields") or []),
                "input_fields": normalize_options(item.get("input_fields") or []),
                "notes": item.get("notes") or "",
                "llm_usage": llm_usage,
            }
        )
    return {
        "source": "pgy_scraped_filter_catalog",
        "purpose": "告诉大模型蒲公英找博主页面真实存在的筛选字段、控件类型、可选项、二级选项和允许落位。",
        "required_filters_allowed_fields": sorted(PGY_BASE_FILTER_FIELDS),
        "additional_filters_allowed_fields": sorted(PGY_EXTRA_FILTER_FIELDS),
        "manual_only_fields": sorted(PGY_MANUAL_ONLY_FILTER_FIELDS),
        "unavailable_as_frontend_filters": [
            "高知家庭",
            "教师人设",
            "国际学校家庭",
            "大孩家庭",
            "孩子年级",
            "学习内容占比",
            "是否全是vlog",
            "真实使用场景",
            "教育决策强度",
            "中产教育叙事",
        ],
        "rules": [
            "pgyCollectionPlan 只能从 fields 中选择真实字段；不在 fields 里的业务语义只能进入 post_score_rules/manual_review_rules。",
            "required_filters 只能使用 required_filters_allowed_fields；additional_filters 只能使用 additional_filters_allowed_fields。",
            "字段 value、sub_value、parent_value、sub_field 必须来自该字段 options/option_groups/sub_fields 或符合 input_fields 的填写规则。",
            "宽类目只能作为召回入口或 proxy，不代表业务意图已被精准满足。",
        ],
        "fields": fields,
    }


@app.post("/api/projects/{project_id}/screening-standard/optimize")
def optimize_screening_standard(project_id: str, payload: ScreeningStandardPayload) -> dict[str, Any]:
    payload.project_id = project_id
    project = get_project(project_id) or payload.project
    system_prompt = (
        "你是广告投放达人策略与评分机制设计专家。请先把客户 Brief 拆成标准化 briefDecomposition，"
        "再输出 promotionStrategy：从产品定位、目标用户、决策链路、核心卖点、内容场景、转化路径和风险点解释这个产品应该怎样被推广。"
        "筛选方案和评分机制都必须由 promotionStrategy 推导，而不是套用某个固定产品模板。"
        "你必须先判断当前项目的真实推广对象：使用者是谁、购买/报名/转化决策者是谁、内容影响对象是谁、达人需要说服谁；"
        "不要套用固定行业模板，也不要把历史项目中的人群年龄、身份或决策链路直接迁移到当前项目。"
        "reasoning 只描述当前 Brief 的正向依据和未明确项，不要通过反驳某个历史模板、默认人群或固定年龄段来论证。"
        "受众分析必须推导适合当前项目的粉丝年龄段，并映射到蒲公英前端真实筛选字段“粉丝年龄”的可选值；如果 Brief 证据不足，写明低置信假设或 Brief未明确。"
        "你会收到 pgyFilterCatalog 和 pgyFilterFieldGuide，它们来自蒲公英找博主页面真实筛选项；生成蒲公英前置筛选时必须严格使用这些真实字段、控件和可选项。"
        "然后再输出两个互相独立但可协同使用的结果：第一，面向小红书蒲公英找博主页面的多套筛选方案，必须只使用真实蒲公英筛选字段；"
        "第二，面向本项目工具的两阶段评分机制：先用找博主列表页数据做数据层分级，再用达人详情页、主页简介、笔记标题/文案做人设、内容和卖点承接评分。"
        "同时必须生成 projectSpecialScoring：这是该项目专属初筛评分逻辑，必须由当前 Brief、briefDecomposition 和 promotionStrategy 推导，保存后由系统解释执行；不要依赖代码里的项目名或历史模板。"
        "如果当前 Brief 明确提到 KOC，或项目配置已选择 KOC，还必须生成 kocScoringConfig：它是项目专属评分配置文件的一部分，系统通用评分架构只负责读取并执行这些阈值和规则。"
        "kocScoringConfig 的生成方向必须参考真实优质样本校准后的规则：低预算KOC更重视报价-效果效率、阅读/互动中位数、人设和内容证据；粉丝量只作坐标；证据缺失和冲突内容按阶段规则处理。"
        "briefDecomposition 必须明确区分蒲公英后台能直接执行的白名单前置筛选、只能宽代理表达的 proxy 条件、采后评分/硬规则、以及人工复核项。"
        "pgy_required 只代表蒲公英页面可执行的前置条件；scoringCriteria.hard_rules 代表采后判断的合作门槛。蒲公英不能前置，不等于不能成为采后硬性规则。"
        "无法被蒲公英字段直接筛选的业务语义，不得写成 pgy_required；但如果 Brief 明确将其设为合作门槛，可进入 scoringCriteria.hard_rules 或 manual_review_rules，并说明证据来源和判断方式。"
        "母婴、教育等宽类目若用于表达复杂业务意图，必须标记为 proxy，并说明风险和 quota 上限。"
        "报价不是越低越好，必须结合CPM/CPC/CPE和近30天曝光/阅读/互动判断单个达人预算能买到的效果总量。"
        "粉丝量只用于动态T级和同T级基准，不作为高权重得分项。缺蒲公英链接或缺字段不是达人质量问题，不得作为硬性淘汰项。"
        "规则落位必须严格分层：hardFilters/scoringCriteria.hard_rules 放当前 Brief 明确要求且能被字段或证据稳定判断的硬性条件；"
        "post_score_rules/manual_review_rules 放需要采后结合主页、笔记、详情页或人工判断的匹配度、真实性和风险复核项。"
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
                "promotion_audience_analysis": {
                    "actual_users": ["真实使用者/体验者"],
                    "decision_makers": ["购买/转化决策者"],
                    "content_influenced_audience": ["内容主要影响谁"],
                    "inferred_fans_age": [
                        {
                            "pgy_field": "粉丝年龄",
                            "pgy_value": "必须来自 pgyFilterCatalog 中粉丝年龄的真实选项，例如 <18 占比高|18～24 占比高|25～34 占比高|35～44 占比高|>44 占比高；Brief 未明确时写 Brief未明确",
                            "reason": "根据当前 Brief 正向推导该年龄段的原因",
                            "confidence": "high|medium|low",
                            "placement": "pgy_required|pgy_additional|post_score|manual_review|not_used"
                        }
                    ],
                    "not_target_audiences": ["不应默认套用的人群"],
                    "reasoning": "只描述当前 Brief 的正向依据和未明确项；不要通过反驳某个历史模板、默认人群或固定年龄段来论证"
                },
                "rule_placement_matrix": [
                    {
                        "brief_requirement": "Brief中的一个要求",
                        "placement": "pgy_required|pgy_additional|hard_rule|post_score|manual_review|negative_preference",
                        "reason": "为什么放在这里，是否能被字段直接确认",
                        "is_one_vote_veto": False,
                        "evidence_from_brief": "引用 Brief 原文或说明 Brief 未明确",
                        "confidence": "high|medium|low"
                    }
                ],
                "must_have_requirements": ["必须满足的业务条件；若蒲公英不能前置，则必须进入采后评分或人工复核"],
                "strong_preferences": ["强偏好条件"],
                "negative_constraints": ["Brief 明确排除或低优先级的人群/内容/风险类型"],
                "assumptions": ["模型为了生成方案所做的低置信假设；没有则为空数组"],
                "unknowns": ["Brief 未明确但影响筛选/评分的问题；没有则为空数组"],
                        "backend_mappable_filters": [
                            {
                                "field": "必须来自 pgyFilterCatalog 的真实字段；粉丝年龄判断必须使用字段名“粉丝年龄”",
                                "value": "真实可选值或可填写区间",
                                "sub_value": "博主类目二级类目；仅 field=博主类目 且二级类目真实存在时填写",
                                "mapping_type": "direct|proxy",
                                "confidence": "high|medium|low",
                                "business_requirement": "映射的业务需求",
                                "evidence_from_brief": "引用 Brief 原文或说明 Brief 未明确",
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
                        "evidence_from_brief": "引用 Brief 原文或说明 Brief 未明确",
                    }
                ],
                "post_score_rules": [
                    {
                        "rule_name": "采后评分规则名",
                        "required_evidence": ["需要哪些达人字段/主页/笔记证据"],
                        "fallback_action": "字段缺失或证据不足时如何处理",
                        "score_impact": "high|medium|low",
                        "evidence_from_brief": "引用 Brief 原文或说明 Brief 未明确",
                        "confidence": "high|medium|low",
                    }
                ],
                "manual_review_rules": ["必须人工确认的事项"],
            },
            "promotionStrategy": {
                "product_positioning": "基于Brief推导产品定位，不按固定产品名模板套用",
                "target_users": ["产品真实使用者"],
                "decision_makers": ["购买/合作/转化决策者"],
                "core_selling_points": ["产品核心卖点/痛点解决点"],
                "conversion_scenes": ["适合达人内容呈现的使用/决策/种草场景"],
                "content_angles": ["达人可讲的内容角度，例如体验、测评、教程、日常场景、对比"],
                "creator_fit_hypotheses": ["什么类型的达人理论上更容易讲清产品"],
                "screening_implications": ["这些策略如何转化为蒲公英前置筛选/代理筛选"],
                "scoring_implications": ["这些策略如何转化为采后评分维度和证据要求"],
                "negative_fit_risks": ["不适合承接该产品的内容/人群/表达风险"],
            },
            "budgetPolicy": {"total_budget": "总达人预算", "target_creator_count": "目标达人数量", "expected_single_cost": "总预算/目标人数", "single_hard_cap": "单达人硬上限", "principle": "报价与效果总量/效率的关系"},
            "formatBudgetPolicy": {"allowed_formats": ["图文", "视频"], "preferred_format": "首选合作形态", "single_creator_budget_cap": "单达人预算", "image_quote_cap": "图文报价上限", "video_quote_cap": "视频报价上限", "premium_exception_policy": {"enabled": True, "data_top_percent": 5, "max_budget_multiplier": 1.5}, "budget_rule": "按推荐投放形态校验预算；高性价比溢价例外进入补详情"},
            "hardRules": {"must_have_commercial_order": "是否必须接过商单", "reply_rate_min": "回复率下限", "recent_update_days": "近期更新窗口", "low_like_threshold": "低赞风险阈值", "ignore_low_like_if_same_day": "当天笔记是否豁免", "must_have_identity_match": "是否要求人设匹配", "must_have_study_abroad_trace": "是否要求留学/海外痕迹", "must_have_study_content_ratio": "目标内容占比要求"},
            "tierPolicy": {"principle": "按类目、项目和抓取样本动态生成T级；粉丝量只作为比较坐标", "benchmark_method": "用P25/P50/P75/P90建立同T级基准"},
            "dataLayerScoring": {"purpose": "找博主列表页数据分级", "core_metrics": ["报价", "近30天曝光", "近30天阅读", "近30天互动", "CPM", "CPC", "CPE"], "levels": [{"level": "S|A|B|C", "rule": "分级规则"}]},
            "projectSpecialScoring": {
                "enabled": True,
                "label": "项目专属评分名称，例如产品名/项目名",
                "source": "llm_brief_decomposition",
                "identity": {
                    "name": "该项目最优先识别的身份/人群/背景",
                    "points": 30,
                    "fields": ["nickname", "creator_type", "persona_tags", "ip_city", "topic_point", "child_grade", "child_age"],
                    "keywords": ["从 Brief 提取的身份、人群、背景关键词"],
                    "evidence_keywords": ["可在主页/笔记/详情里验证该身份或背景的证据词"],
                },
                "scene": {
                    "name": "Brief核心内容/使用/转化场景",
                    "max_points": 30,
                    "base_points": 10,
                    "points_per_hit": 4,
                    "max_keyword_hits": 5,
                    "direction_bonus": {"strong": 4, "medium": 2},
                    "keywords": ["从 Brief 和 promotionStrategy 提取的内容场景、卖点承接、转化场景关键词"],
                },
                "data": {
                    "max_points": 20,
                    "good_points": 15,
                    "excellent_points": 20,
                    "read_ratio_points": [{"min": 0.75, "points": 10}, {"min": 0.5, "points": 6}],
                    "interaction_bonus": [{"min": 120, "points": 4}, {"min": 60, "points": 2}],
                },
                "efficiency": {"max_points": 20, "good_points": 14, "excellent_points": 20, "fallback_points": 6},
                "tier_rules": {
                    "s_min_priority_score": 86,
                    "s_score": 95,
                    "s_high_priority_score": 93,
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
                "negative": {"keywords": ["Brief明确低优先或不适合的人群/内容/场景"], "cap_without_scene": 84},
                "project_fit_config_patch": {
                    "preferred_content_scenes": ["需要注入 projectFitConfig 的专属内容场景"],
                    "preferred_presentation_styles": ["适合该产品的表达方式"],
                    "target_grade_keywords": [],
                    "parent_decision_keywords": [],
                    "discouraged_keywords": ["负向关键词"],
                },
                "ignore_hard_filter_keywords": ["只有当 Brief 明确不应使用某些历史/代理硬筛时填写，例如不适用的年龄画像词"],
            },
            "kocScoringConfig": {
                "enabled": "仅当 Brief 明确 KOC 或项目配置选择 KOC 时为 true；不能只因预算低自动启用",
                "architecture": "koc_two_stage_scoring",
                "stage1_labels": ["P0", "P1", "P2", "P3", "不入库"],
                "stage1_thresholds": {
                    "budget_full_score_max": "预算满分线；低预算KOC可参考优质样本中位报价/上四分位",
                    "budget_accept_max": "预算可接受硬线",
                    "premium_backup_max": "数据极强但略超预算时进入备选/补详情的上限",
                    "read_priority_min": "一阶段优先补采阅读线",
                    "read_strong_min": "强数据阅读线",
                    "interaction_priority_min": "一阶段优先补采互动线",
                    "interaction_strong_min": "强数据互动线",
                    "cpe_strong_max": "强CPE线",
                    "cpe_priority_max": "优先补采CPE线",
                    "cpe_observe_max": "观察CPE线",
                    "cpm_risk_max": "CPM风险线；一般不直接淘汰",
                },
                "detail_stage_rules": {
                    "note_sample_min": "建议采样笔记数，例如8-20",
                    "minimum_sample_for_decision": "低于该样本数只能待人工确认/备选",
                    "target_content_required_ratio": "目标内容占比要求",
                    "identity_trace_reference_ratio": "身份痕迹参考占比",
                    "product_scene_strong_ratio": "产品场景强推荐占比线",
                    "conflict_warning_ratio": "冲突内容占比预警线",
                    "conflict_is_hard_only_when_target_below": "只有目标内容占比低于该值时，冲突内容才强降级",
                    "missing_evidence_status": "证据不足时输出状态",
                },
                "final_match_thresholds": {
                    "good_read_min": "二阶段推荐阅读线",
                    "good_interaction_min": "二阶段推荐互动线",
                    "good_cpe_max": "二阶段推荐CPE线",
                    "strong_read_min": "二阶段强推荐阅读线",
                    "strong_interaction_min": "二阶段强推荐互动线",
                    "strong_cpe_max": "二阶段强推荐CPE线",
                },
                "weight_guidance": {"budget": 18, "fans": 5, "cpe": 22, "engagement": 25, "persona": 20, "content": 10},
                "negative_policy": "vlog/旅行/海外日常等冲突内容按占比风险处理，不因单个关键词直接Pass",
                "evidence_policy": "一阶段只决定入库/补详情优先级；缺主页/笔记正文/合作笔记/回复率时不得直接强推荐",
            },
            "hardFilters": [{"field": "只允许明确事实类硬性标准", "condition": ">=|<=|规避|同T级对比|核算", "value": "阈值或规则", "required": True, "feishuField": "匹配到的飞书字段名或空"}],
            "scoringWeights": {"budget": 15, "fans": 5, "cpe": 20, "engagement": 30, "persona": 20, "content": 10},
            "scoringCriteria": {
                "purpose": "说明这是两阶段评分机制，不等同于蒲公英筛选条件",
                "budget_policy": "同 budgetPolicy",
                "format_budget_policy": "同 formatBudgetPolicy",
                "project_hard_rules": "同 hardRules",
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
                "expected_request_constraints": "系统会根据 filters 自动生成真实蒲公英 API 请求期望约束；模型不要编造字段，只需输出 filters",
                "application_validation": {"mode": "api_request_body", "on_mismatch": "repair_then_validate", "stop_on_repair_failed": True},
                "schemes": [
                    {
                        "scheme_id": "短英文ID",
                        "name": "筛选方案名称",
                        "role": "primary|supplement|risk_test",
                        "precision_level": "high|medium|low",
                        "target_quota": "建议目标贡献人数",
                        "max_quota": "最大贡献人数；proxy/low 精度方案必须较低",
                        "precision_warning": "低精度、代理或验证方案必须说明混入风险；没有明确业务证据时写 Brief 未明确",
                        "goal": "覆盖的人群/达人类型",
                        "evidence_from_brief": "引用 Brief 原文或说明 Brief 未明确",
                        "assumptions": ["低置信假设；没有则为空数组"],
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
                                "field": "笔记类型|预估互动单价|曝光中位数|阅读中位数|互动中位数|预估阅读单价 等可调整提质条件",
                                "value": "筛选值",
                                "reason": "数量过多或质量不足时才启用",
                                "control_type": "必须与 pgyFilterCatalog 对应字段的控件类型一致",
                            }
                        ],
                        "enabled_additional_filters": [],
                        "filters": [],
                        "expand_if_too_few": ["推荐博主数太少时先放宽哪些条件"],
                        "narrow_if_too_many": ["推荐博主数太多时追加哪些真实蒲公英条件"],
                        "expected_request_constraints": "系统根据该方案实际启用 filters 自动生成，用于校验 contentTag/personalTags/报价/阅读/互动等请求体字段",
                        "application_validation": {"mode": "api_request_body", "on_mismatch": "repair_then_validate", "stop_on_repair_failed": True},
                    }
                ],
                "filters": [
                    {
                        "field": "全局手动添加条件；默认留空，需要品牌搜索、剔除品牌、平台推荐等人工输入/确认的条件才放这里",
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
        "pgyFilterFieldGuide": _pgy_filter_field_guide(),
        "kocSampleCalibratedScoringGuide": KOC_SAMPLE_CALIBRATED_SCORING_GUIDE,
        "constraints": [
            "必须输出 briefDecomposition 和 promotionStrategy；promotionStrategy 要先于 pgyCollectionPlan/scoringCriteria 表达产品推广策略如何驱动筛选和评分",
            "必须输出 projectSpecialScoring；它是保存到项目 screening_plan 的专属初筛评分逻辑，系统会解析 identity/scene/data/efficiency/tier_rules/negative/project_fit_config_patch 来给达人评分；不得依赖代码硬编码项目名称",
            "当 Brief 明确 KOC 或项目配置选择 KOC 时，必须输出 kocScoringConfig；这是项目专属评分配置，不是代码架构本身。更换项目时系统评分代码保持不变，只替换该配置。",
            "kocScoringConfig 必须吸收 kocSampleCalibratedScoringGuide 的真实优质样本校准方向：报价参考中位600/P75约780/1000以内优先，阅读参考P25约1279/中位2402，互动参考P25约116/中位274，CPE参考中位2.16/P75约3.81；项目Brief有更强证据时可调整但要保守说明。",
            "KOC评分必须保留两阶段边界：P0/P1/P2/P3只表示入库和补详情优先级；强推荐/推荐/备选/待人工确认/不推荐/Pass在详情证据补全后判断。",
            "KOC硬Pass只用于明确事实类风险：对应合作形态均超预算且无高数据溢价例外、无接单权限、回复率明确低于阈值、链接失效或明确不合作。缺合作笔记、缺主页正文、缺回复率只能降级为待确认/备选，不能强推荐也不能直接Pass。",
            "KOC冲突内容如vlog/旅行/海外日常必须按占比和目标内容占比共同判断：目标内容足够时只做预警，目标内容不足且冲突占比过高才强降级。",
            "projectSpecialScoring 的身份关键词、场景关键词、负向关键词、S/A/B+分段和封顶规则都必须从当前 Brief、briefDecomposition 和 promotionStrategy 推导；如果 Brief 证据不足，写低置信关键词或保守阈值，不要套用历史项目",
            "promotionStrategy 必须基于当前 Brief 逐项推导产品定位、目标用户、决策者、核心卖点、内容场景、转化路径和负向风险；禁止套用固定产品名模板或把某个历史项目方案照搬到新项目",
            "必须先输出 promotion_audience_analysis：区分当前项目的真实使用者、决策者、内容影响对象和非目标人群；所有判断都必须从当前 Brief、产品场景和转化链路推导，不能套用行业默认人群",
            "promotion_audience_analysis.reasoning 只描述当前 Brief 的正向依据和未明确项，不要通过反驳某个历史模板、默认人群或固定年龄段来论证",
            "promotion_audience_analysis 必须输出 inferred_fans_age：从当前 Brief 推导合适的粉丝年龄段，并映射到蒲公英真实字段“粉丝年龄”的真实选项；若适合用于前置筛选，可进入 backend_mappable_filters 或 pgyCollectionPlan，若证据不足则 placement=manual_review/not_used 并说明 Brief未明确",
            "briefDecomposition 要表达 Brief 如何被拆成 direct/proxy/hard_rule/post_score/manual_review，并输出 assumptions 和 unknowns；Brief 未明确的地方不要自行补全行业默认答案",
            "必须输出 rule_placement_matrix，并为每条 Brief 要求选择唯一主落位：pgy_required、pgy_additional、hard_rule、post_score、manual_review 或 negative_preference；同时输出 evidence_from_brief 和 confidence",
            "pgy_required 只代表蒲公英页面可执行的前置条件；scoringCriteria.hard_rules 代表采后判断的合作门槛。蒲公英不能前置，不等于不能成为采后硬性规则",
            "如果 Brief 使用“必须、硬性、不要、不合作、不推荐、需要达到”等强约束表达，应优先保留其约束强度；只有当无法判断证据来源或无法稳定判断时，才标记为 manual_review，而不是自动降为加减分",
            "pgyFilterFieldGuide 是模型生成蒲公英筛选条件的字段字典：必须先查字段是否存在、usage_group 是否允许、control_type 怎么填写、options/option_groups/sub_fields 有哪些可选项，再输出筛选条件",
            "pgyCollectionPlan 只能使用 pgyFilterCatalog/pgyFilterFieldGuide 中真实存在的字段和控件类型；白名单外字段不得进入前置筛选",
            "采前筛选方案必须生成可被蒲公英 API 请求体验证的 filters；系统会把 filters 转换为 expected_request_constraints，并用真实请求体校验。",
            "如果 Brief 明确提到 KOC 或项目配置选择 KOC，且单达人预算低于2000元，合作报价必须同时覆盖图文笔记和视频笔记两个子字段；不能只筛图文导致视频高价混入。",
            "低预算 KOC 初始方案优先使用温和但可验证的质量门槛，例如阅读中位数下限和互动中位数下限；这些进入 additional_filters，预检数量过多时再逐步启用。",
            "生成后应用必须以真实蒲公英达人列表 API 请求为准；若请求体缺少期望字段、出现 similarUserId、或为空筛选请求，系统应先尝试重组/修复为正确 API 请求并再次校验；只有修复失败才停止采集。",
            "无法被蒲公英字段直接筛选的业务语义，不得写成 pgy_required；但如果 Brief 明确将其设为合作门槛，可进入 scoringCriteria.hard_rules 或 manual_review_rules，并说明证据来源和判断方式",
            "母婴、教育、生活记录等宽类目如果用于承接复杂业务意图，必须在 proxy_filters 标记 mapping_type=proxy、confidence=low/medium、proxy_risk，并限制 max_quota",
            "主池必须优先使用 direct 且高置信字段；补量池可以使用 proxy，但不能吞掉全部配额",
            "每套 scheme 必须包含 role、precision_level、target_quota、max_quota；precision_level=low 的补量池 max_quota 不得超过总目标的30%",
            "负向约束必须来自 Brief 明确排除或低优先级的人群/内容/风险类型；按可执行性转化为 pgy 条件、post_score_rules、manual_review_rules 或 hard_rules，不得幻想蒲公英已前置排除",
            "如果 Brief 没有明确说明目标人群、决策者、硬性门槛或负向约束，不要自行补全行业默认答案；请写“Brief未明确”，并把该项放入 manual_review_rules、assumptions 或 unknowns",
            "scoringWeights 六项总和必须为 100",
            "必须把蒲公英筛选方案和采集后评分标准拆开：pgyCollectionPlan 只服务找博主采集，scoringCriteria 只服务采集后评分/推荐/匹配",
            "hardFilters/scoringCriteria.hard_rules 应包含当前 Brief 明确为硬性、且能被已有字段或稳定证据判断的规则；缺蒲公英链接、缺字段、缺近期笔记正文不能自动等同于达人不符合",
            "学习类内容占比、内容适配、人设适配、主页简介与笔记证据等要求的落位由当前 Brief 的措辞和可验证性决定：可稳定判断的硬性要求可进入 hard_rules，需要采后解释或人工判断的要求进入 post_score_rules/manual_review_rules。",
            "评分机制必须分两阶段：找博主列表页数据先分 S/A/B/C 数据层级；详情页、主页简介、笔记标题/文案只用于高优先级达人的人设内容分析",
            "预算评分必须解释报价、CPM、CPC、CPE和近30天曝光/阅读/互动的关系，输出单个达人预算能换来的效果总量；报价不是越低越好",
            "粉丝量只用于T级坐标和同T级benchmark；T级边界和标准必须根据项目类目、Brief和抓取样本动态生成，不得把粉丝量作为高权重加分",
            "近30天曝光、阅读、互动必须是数据层级的核心指标，和CPM/CPC/CPE一起决定预算效果质量",
            "蒲公英 schemes 必须且只输出 4 套，分别作为方案一、方案二、方案三、方案四映射到前端卡片；4套是前端展示容器要求，不得为了凑满方案编造 Brief 没有依据的人群；每套 required_filters 的字段类型必须只来自：博主类目、粉丝量、粉丝年龄、合作报价；其中博主类目允许出现多条",
            "4套方案必须有真实筛选差异，不允许只是换名字：方案一是核心高相关主池；方案二若 Brief 提到视频优先/最好视频，必须成为视频优先池，并在 additional_filters 与 enabled_additional_filters 默认放入 {field:'笔记类型', value:'视频笔记为主', control_type:'dropdown_single'}；方案三/四若 Brief 只支持少量真实方向，可以输出保守补量/验证方案，并明确 precision_level、proxy_risk、max_quota、evidence_from_brief 和 assumptions。",
            "博主类目可多选：既可以多选不同一级类目，也可以在同一一级类目下多选多个二级类目；跨一级多二级也必须同时保留，例如 {field:'博主类目', value:'教育', sub_value:'家庭教育'}、{field:'博主类目', value:'教育', sub_value:'学习日常'}、{field:'博主类目', value:'母婴', sub_value:'育儿经验'} 可以同时出现在同一套 required_filters；不能合并成字符串或只留一个",
            "博主类目支持二级类目，二级类目必须来自 pgyFilterCatalog.option_groups；禁止输出不存在或不属于该主类目的二级类目；禁止把多个二级类目写成数组、逗号文本或斜杠文本，必须拆成多条 required_filters",
            "博主类目选择必须从当前 Brief 的产品定位、目标用户、内容场景和推广策略推导；例如教育、母婴、生活记录等都只是可用召回入口，不得在没有策略证据时默认套用",
            "粉丝年龄、地域、内容形态、报价区间必须从当前 Brief 的目标用户、决策者、预算和内容要求推导；粉丝年龄必须使用蒲公英字段“粉丝年龄”的真实选项表达，不要默认套用固定年龄段、固定城市或固定报价模板",
            "评分条件必须显式引用 promotionStrategy：人设分看目标用户/决策者匹配，内容分看核心卖点和转化场景承接，数据分看预算能换来的曝光/阅读/互动效率",
            "一般不要选择笔记类目，只选择博主类目即可；笔记类目不是博主类目，不能用汽车/游戏/母婴/美妆等笔记类目去替代或追加到博主类目",
            "笔记类目在蒲公英真实页面是父级类目下继续展开的二级/三级弹层；除非用户明确要求按笔记内容类目筛选，否则 pgyCollectionPlan 不要输出 笔记类目/内容题材",
            "营销目标是低优先级附加条件，只能放入 additional_filters 或用户手动 filters，不能放入 required_filters；字段结构要用父子指标，如 {field:'营销目标', value:'互动表现', goal:'种草', parent_value:'种草', control_type:'marketing_goal_metric'}",
            "地域/粉丝地域只有 Brief 明确强调地域、IP、城市优先/必须/重点覆盖时才放入筛选条件；仅出现城市案例或品牌叙事时不要自动加入地域",
            "家庭身份、职业身份、特色背景、母婴阶段属于高频画像筛选；Brief 明确要求且选项真实存在时，可以放入 additional_filters 或 enabled_additional_filters，但不要放入 required_filters，也不要强行解释为已精准满足业务语义。",
            "如果 Brief 明确要求留学背景/海外留学生，应把 {field:'特色背景', value:'留学背景'} 放入主池和视频池 additional_filters 与 enabled_additional_filters；如果 Brief 明确要求学生/留学生，应把 {field:'职业身份', value:'学生'} 放入主池和视频池 additional_filters 与 enabled_additional_filters。它们是采前提纯条件，采后仍需验证真实身份和学习内容占比。",
            "不要在 required_filters 或自动 filters 中加入 行业推荐博主、平台推荐、近期合作品牌、按博主粉丝推荐、笔记类目、内容题材；这些需要人工输入/确认或容易误用的条件只有用户在前端手动添加时才允许进入 filters。",
            "超出估量时必须按顺序追加能明确缩小范围且提高达人质量的指标条件：预估互动单价(CPE)、曝光中位数、阅读中位数、互动中位数、预估阅读单价(CPC)；不要自动追加预估CPM，也不要用地域、常规剔除来充当自动收紧条件。画像筛选仅在 Brief 明确要求时使用，不能作为泛化收紧手段。",
            "笔记类型、预估互动单价、曝光中位数、阅读中位数、互动中位数、预估阅读单价等提质条件放入 additional_filters；除视频优先池的“视频笔记为主”可默认启用外，其余默认非必要；如果必备筛选下博主过多，按 additional_filters 数组顺序逐个叠加，越靠上越先启用，一旦数量达标就不再继续加下面的条件；门槛要温和，避免一追加就只剩十几名推荐。",
            "区间字段必须按字段语义输出：粉丝量、曝光中位数、阅读中位数、互动中位数、合作订单数、传播规模子字段、合作信用度只设下限，写 range_policy='min_only' 和 min；展示 value 也必须写成“3000以上/1000以上/100以上/邀约48h回复率：60%以上”这类下限表达，禁止写“1万～10万、0.5万～1万、500～1000、60～100”这类带上限区间；合作报价必须同时设置 min 和 max；预估阅读单价、预估互动单价、外溢进店单价维持只设 max",
            "每套蒲公英方案需要 target_count_range、expand_if_too_few、narrow_if_too_many，用来根据页面推荐数量动态扩缩条件",
            "当蒲公英页面推荐数量类似 5000+ 时，narrow_if_too_many 必须给出可追加的真实蒲公英附加筛选条件；目标是不超过约 2000",
            "评分硬性条件只使用 Brief 明确要求且能被采集字段确认的事实；人设/内容不能只靠关键词命中，需要详情页、主页简介、笔记标题/文案等证据",
            "飞书字段匹配要使用 feishuFields 中实际存在的字段名",
            "蒲公英筛选条件必须优先使用 pgyFilterCatalog 中的真实字段和控件类型",
            "近期合作品牌是可搜索品牌多选，不是普通标签；若 Brief 提供品牌名要写入 input_values；品牌不足3个时 pending_detail 标注待补足",
            "按博主粉丝推荐不是普通行内筛选项，而是右上角智能推荐博主/合作品牌搜索入口；Brief 中的合作品牌、目标品牌、竞品、对标品牌都可写入 input_values 或 competitor_values",
            "行业推荐博主打开后仍有“我的行业/请选择”下拉，必须标注为 nested_select_popover 和 pending_detail",
            "合作报价、预估阅读单价、预估互动单价是图文/视频子字段，每个子字段还会打开预设档位和自定义区间；预估CPM不作为自动追加收窄条件",
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
    *,
    use_llm: bool = False,
) -> dict[str, Any]:
    table_id = _table_identifier(selected)
    field_names = _field_signature(fields)
    plan = analyze_field_mapping(field_names, default_source_rows(), use_llm=use_llm)
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


def _refresh_feishu_field_mapping_cache(project_id: str, *, use_llm: bool = False) -> dict[str, Any]:
    config, client, target = _load_feishu_client(project_id)
    tables, fields_by_id = _load_tables_and_fields(client, target)
    cache: dict[str, Any] = {}
    for table in tables:
        table_id = _table_identifier(table)
        fields = fields_by_id.get(table_id) or []
        if not table_id or not fields:
            continue
        cache[_mapping_cache_key(target.resource_type, table_id)] = _analyze_table_field_mapping(target, table, fields, use_llm=use_llm)
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
    *,
    use_llm: bool = False,
) -> dict[str, Any]:
    table_id = _table_identifier(selected)
    cached = _cached_field_mapping_plan(config, target, table_id, fields)
    if cached and not use_llm:
        return cached
    plan = _analyze_table_field_mapping(target, selected, fields, use_llm=use_llm)
    cache = config.get("field_mapping_cache") if isinstance(config.get("field_mapping_cache"), dict) else {}
    cache[_mapping_cache_key(target.resource_type, table_id)] = plan
    config["field_mapping_cache"] = cache
    _write_feishu_config(project_id, config)
    return plan


AUDIENCE_PROFILE_IMAGE_FIELD_NAMES = ("粉丝画像", "粉丝画像截图")


def _field_name_from_meta(field: dict[str, Any]) -> str:
    return str(field.get("field_name") or field.get("name") or field.get("title") or "").strip()


def _is_audience_profile_image_field(field_name: str) -> bool:
    normalized = re.sub(r"\s+", "", str(field_name or ""))
    return normalized in AUDIENCE_PROFILE_IMAGE_FIELD_NAMES


def _audience_profile_image_path(row: dict[str, Any]) -> str:
    for field_name in AUDIENCE_PROFILE_IMAGE_FIELD_NAMES:
        value = str(row.get(field_name) or "").strip()
        if value:
            return value
    return ""


def _find_sheet_audience_profile_image_field(fields: list[dict[str, Any]]) -> dict[str, Any] | None:
    by_name = {_field_name_from_meta(field): field for field in fields}
    for field_name in AUDIENCE_PROFILE_IMAGE_FIELD_NAMES:
        if field_name in by_name:
            return by_name[field_name]
    return None


def _ensure_sheet_audience_profile_image_field(
    client: FeishuClient,
    spreadsheet_token: str,
    sheet_id: str,
    fields: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    existing = _find_sheet_audience_profile_image_field(fields)
    if existing:
        return fields, {"created": False, "field": existing}
    return client.ensure_sheet_field(spreadsheet_token, sheet_id, fields, "粉丝画像截图")


def _clear_sheet_audience_profile_image_values(
    rows: list[dict[str, Any]],
    fields: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    image_field_names = {
        name
        for name in (_field_name_from_meta(field) for field in fields)
        if _is_audience_profile_image_field(name)
    }
    if not image_field_names:
        return rows
    cleared_rows: list[dict[str, Any]] = []
    for row in rows:
        next_row = dict(row)
        for field_name in image_field_names:
            if field_name in next_row:
                next_row[field_name] = ""
        cleared_rows.append(next_row)
    return cleared_rows


def _write_sheet_audience_profile_images(
    client: FeishuClient,
    spreadsheet_token: str,
    sheet_id: str,
    fields: list[dict[str, Any]],
    rows: list[dict[str, Any]],
    result: dict[str, Any],
) -> dict[str, Any]:
    image_rows = [row for row in rows if _audience_profile_image_path(row)]
    if not image_rows:
        return {"enabled": False, "message": "本次写回没有粉丝画像截图"}
    fields, field_result = _ensure_sheet_audience_profile_image_field(client, spreadsheet_token, sheet_id, fields)
    profile_field = _find_sheet_audience_profile_image_field(fields)
    if not profile_field:
        return {"enabled": False, "message": "未找到可写入的粉丝画像列"}
    profile_column = column_name(int(profile_field["column_index"]) + 1)
    row_lookup: dict[str, str] = {}
    result_items = (result.get("created") or []) + (result.get("updated") or [])
    for fallback_row, item in zip(rows, result_items):
        row = item.get("row") if isinstance(item.get("row"), dict) else fallback_row
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
        image_path = _audience_profile_image_path(row)
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
    use_ai_mapping: bool = Query(default=False),
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
        field_mapping = _ensure_field_mapping_plan(project_id, config, target, selected, fields, use_llm=use_ai_mapping)
        message = "字段映射已使用本地规则分析"
        if use_ai_mapping:
            message = "字段映射已按前端确认使用大模型分析" if field_mapping.get("source") == "llm" else "大模型字段映射未命中，已使用本地规则映射"
        return {"target": target.as_dict(), "selected_table": selected, "fields": fields, "field_mapping": field_mapping, "message": message}
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
            fields, image_field_result = _ensure_sheet_audience_profile_image_field(client, target.token, sheet_id, fields)
            field_mapping = _ensure_field_mapping_plan(payload.project_id, config, target, selected, fields)
            mapped_rows, field_mapping = apply_field_mapping(rows, fields, mapping_plan=field_mapping)
            mapped_rows = _clear_sheet_audience_profile_image_values(mapped_rows, fields)
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
    running_task = _running_detail_collect_task(project_id)
    if running_task:
        return {
            "ok": False,
            "accepted": True,
            "error": "detail_collection_already_running",
            "message": running_task.get("progress_message") or "已有达人详情完善任务正在运行，请等待当前任务结束后再试",
            "task": running_task,
            "creators": [],
            "failed": [],
        }
    if _detail_collect_lock(project_id).locked():
        return {
            "ok": False,
            "error": "detail_collection_already_running",
            "message": "已有达人详情完善任务正在运行，请等待当前任务结束后再试",
            "creators": [],
            "failed": [],
        }
    creators = list_creators(project_id)
    targets = _detail_collect_targets(project_id, payload, creators)
    if not targets:
        message = "当前分段没有可完善详情页的达人" if (payload.manual or payload.creator_ids) else "没有达到详情完善优先级的达人"
        return {"ok": False, "message": message, "creators": [], "failed": []}
    limit = _detail_collect_limit(payload, len(targets))
    targets = targets[:limit]
    if payload.async_collect:
        task = _create_detail_collect_task(project_id, targets, payload)

        def runner() -> None:
            detail_lock = _detail_collect_lock(project_id)
            detail_lock.acquire()
            try:
                result = _run_detail_collect_targets(project_id, targets, payload, task_id=task["task_id"])
                status = "success" if result.get("ok") else "failed"
                total = int(task.get("total_count") or len(targets))
                completed = len(result.get("updated") or result.get("creators") or [])
                failed = len(result.get("failed") or [])
                _update_detail_collect_task(
                    task["task_id"],
                    status=status,
                    progress_stage="finished" if result.get("ok") else "failed",
                    completed_count=completed,
                    failed_count=failed,
                    finished_at=result.get("finished_at") or _now_text(),
                    result=result,
                    progress_message=result.get("message") or f"详情完善完成：{min(total, completed + failed)}/{total} 达人已完成",
                )
            except Exception as error:
                _update_detail_collect_task(
                    task["task_id"],
                    status="failed",
                    progress_stage="failed",
                    finished_at=_now_text(),
                    result={"ok": False, "message": f"详情页完善失败：{error}", "creators": [], "failed": []},
                    progress_message=f"详情页完善失败：{error}",
                )
            finally:
                detail_lock.release()

        threading.Thread(target=runner, name=f"pgy-detail-{task['task_id'][-8:]}", daemon=True).start()
        return {"ok": True, "accepted": True, "task": task, "message": task["progress_message"]}

    detail_lock = _detail_collect_lock(project_id)
    if not detail_lock.acquire(blocking=False):
        return {
            "ok": False,
            "error": "detail_collection_already_running",
            "message": "已有达人详情完善任务正在运行，请等待当前任务结束后再试",
            "creators": [],
            "failed": [],
        }
    try:
        return _run_detail_collect_targets(project_id, targets, payload)
    finally:
        detail_lock.release()


def _detail_collect_limit(payload: DetailCollectPayload, target_count: int) -> int:
    explicit_limit = int(payload.limit or 0)
    if payload.creator_ids:
        return max(1, min(explicit_limit if explicit_limit > 0 else target_count, target_count, 500))
    return max(1, min(explicit_limit if explicit_limit > 0 else 500, target_count, 500))


def _detail_collect_targets(project_id: str, payload: DetailCollectPayload, creators: list[dict[str, Any]]) -> list[dict[str, Any]]:
    target_ids = set(payload.creator_ids or [])
    if payload.manual or target_ids:
        targets = [creator for creator in creators if creator["creator_id"] in target_ids]
    else:
        targets = [
            creator
            for creator in creators
            if needs_detail_completion(creator)
        ]
        priority_order = {"最高优先级": 0, "高优先级": 1, "中高优先级": 2, "中优先级": 3, "低优先级": 4}
        tier_order = {"S": 0, "A": 1, "B+": 2, "B": 3, "C": 4}
        targets.sort(
            key=lambda creator: (
                priority_order.get(str(creator.get("detail_collection_priority") or ""), 99),
                tier_order.get(str(creator.get("initial_tier") or ""), 99),
                -(parse_number(creator.get("total_score")) or 0),
            )
        )
    for creator in targets:
        creator["detail_completion_needs"] = detail_completion_actionable_needs(creator)
    return targets


def _run_detail_collect_targets(
    project_id: str,
    targets: list[dict[str, Any]],
    payload: DetailCollectPayload,
    *,
    task_id: str | None = None,
) -> dict[str, Any]:
    def progress_callback(event: dict[str, Any]) -> None:
        if not task_id:
            return
        total = int(event.get("total_count") or len(targets))
        completed = int(event.get("completed_count") or 0)
        failed = int(event.get("failed_count") or 0)
        done = min(total, completed + failed)
        _update_detail_collect_task(
            task_id,
            progress_stage=event.get("stage") or "collecting",
            total_count=total,
            completed_count=completed,
            failed_count=failed,
            current_creator_id=event.get("current_creator_id") or "",
            current_nickname=event.get("current_nickname") or "",
            progress_message=f"详情完善中：{done}/{total} 达人已完成",
        )

    try:
        result = collect_details_for_targets(targets, limit=len(targets), progress_callback=progress_callback)
    except TypeError as error:
        if "progress_callback" not in str(error):
            raise
        result = collect_details_for_targets(targets, limit=len(targets))
    if not result.get("ok"):
        return result
    updated = []
    for creator in result.get("creators") or []:
        updated.append(update_creator(project_id, creator["creator_id"], creator, score=False))
    if updated:
        score_project(project_id, use_llm=False, creator_ids=[creator["creator_id"] for creator in updated], trigger_source="pgy_detail")
    auto_writeback = _auto_writeback_after_detail(project_id, [creator["creator_id"] for creator in updated])
    duration_text = result.get("duration_text") or ""
    average_duration_text = result.get("average_duration_text") or ""
    timing_suffix = f"；总耗时 {duration_text}" if duration_text else ""
    if average_duration_text:
        timing_suffix += f"，单个约 {average_duration_text}"
    manual_scope = bool(payload.manual or payload.creator_ids)
    return {
        **result,
        "updated": updated,
        "auto_writeback": auto_writeback,
        "message": (
            f"详情页完善完成，已更新 {len(updated)} 个{'当前分段达人' if manual_scope else '通过初筛达人'}"
            f"；失败 {len(result.get('failed') or [])} 个{timing_suffix}"
        ),
        "target_needs": [
            {
                "creator_id": creator.get("creator_id"),
                "nickname": creator.get("nickname"),
                "needs": creator.get("detail_completion_needs") or detail_completion_actionable_needs(creator),
                "missing_fields": detail_completion_actionable_missing_fields(creator),
            }
            for creator in targets
        ],
    }


@app.get("/api/pgy/collect/detail/tasks/{task_id}")
def api_pgy_detail_task(task_id: str) -> dict[str, Any]:
    task = _detail_collect_task_snapshot(task_id)
    if not task:
        raise HTTPException(status_code=404, detail={"message": "详情完善任务不存在"})
    return {"task": task}


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
    "quote": {"field": "合作报价", "value": "图文笔记：0.1万～2万", "reason": "必备筛选：控制单达人预算", "control_type": "subfield_preset_or_number_range", "sub_field": "图文笔记", "max": 20000},
}

PGY_BASE_FILTER_FIELDS = {"博主类目", "粉丝量", "粉丝年龄", "合作报价"}
PGY_PROFILE_EXTRA_FILTER_FIELDS = {"家庭身份", "职业身份", "特色背景", "母婴阶段"}
PGY_EXTRA_FILTER_FIELDS = {
    "笔记类型",
    "预估阅读单价",
    "预估互动单价",
    "阅读中位数",
    "互动中位数",
    "曝光中位数",
    "合作订单数",
    "传播规模",
    "合作信用度",
    "常规剔除",
    "地域",
    "粉丝地域",
    *PGY_PROFILE_EXTRA_FILTER_FIELDS,
}
PGY_MANUAL_ONLY_FILTER_FIELDS = {"行业推荐博主", "平台推荐", "近期合作品牌", "按博主粉丝推荐", "笔记类目", "内容题材"}
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


PGY_MIN_ONLY_SAVED_RANGE_FIELDS = {"粉丝量", "曝光中位数", "阅读中位数", "互动中位数", "合作订单数"}
PGY_MIN_ONLY_SAVED_SUBFIELD_RANGE_FIELDS = {"传播规模", "合作信用度"}
PGY_WAN_UNIT_SAVED_FIELDS = {"粉丝量", "曝光中位数", "阅读中位数", "外溢进店中位数"}
PGY_PERCENT_SAVED_SUBFIELDS = {"邀约48h回复率"}


def _saved_min_from_range_text(value: Any) -> float | None:
    text = str(value or "").strip()
    if not text:
        return None
    text = text.split("：", 1)[-1].split(":", 1)[-1]
    parts = [part.strip() for part in re.split(r"～|~|至|到|-", text) if part.strip()]
    return parse_number(parts[0] if parts else text)


def _normalize_wan_saved_min(field: str, value: str, min_value: Any) -> Any:
    if field not in PGY_WAN_UNIT_SAVED_FIELDS or min_value in (None, ""):
        return min_value
    parsed = parse_number(min_value)
    if parsed is None:
        return min_value
    if parsed < 1000 and "万" in str(value or ""):
        return parsed * 10000
    return min_value


def _format_saved_min_only_value(value: Any, *, percent: bool = False, wan_unit: bool = False) -> str:
    if value in (None, ""):
        return ""
    parsed = parse_number(value)
    if parsed is not None:
        value = parsed
    try:
        number = float(str(value).replace(",", "").replace("，", ""))
    except Exception:
        return str(value)
    if percent:
        return f"{int(number) if number.is_integer() else number:g}%以上"
    if wan_unit and number >= 1000:
        return f"{number / 10000:g}万以上"
    if number >= 10000 and number % 10000 == 0:
        return f"{int(number / 10000)}万以上"
    if number >= 10000:
        return f"{number / 10000:g}万以上"
    return f"{int(number) if number.is_integer() else number:g}以上"


def _standardize_min_only_saved_range(item: dict[str, Any]) -> dict[str, Any]:
    field = str(item.get("field") or "").strip()
    value = str(item.get("value") or "").strip()
    min_value = item.get("min")
    if min_value in (None, ""):
        min_value = _saved_min_from_range_text(value)
    min_value = _normalize_wan_saved_min(field, value, min_value)
    normalized_value = _format_saved_min_only_value(min_value, wan_unit=field in PGY_WAN_UNIT_SAVED_FIELDS) or value
    return {
        **item,
        "value": normalized_value,
        "control_type": item.get("control_type") or ("number_range" if item.get("field") == "合作订单数" else "preset_or_number_range"),
        "min": min_value if min_value not in (None, "") else "",
        "max": "",
        "range_policy": "min_only",
    }


def _standardize_min_only_saved_subfield_range(item: dict[str, Any]) -> dict[str, Any]:
    value = str(item.get("value") or "").strip()
    sub_field = str(item.get("sub_field") or item.get("subField") or "").strip()
    label = sub_field or (re.split(r"[：:]", value, maxsplit=1)[0].strip() if re.search(r"[：:]", value) else "")
    min_value = item.get("min")
    if min_value in (None, ""):
        min_value = _saved_min_from_range_text(value)
    min_text = _format_saved_min_only_value(
        min_value,
        percent=label in PGY_PERCENT_SAVED_SUBFIELDS,
        wan_unit=label in PGY_WAN_UNIT_SAVED_FIELDS,
    )
    normalized_value = f"{label}：{min_text}" if label and min_text else (min_text or value)
    return {
        **item,
        "value": normalized_value,
        "control_type": item.get("control_type") or ("subfield_preset_or_percent_range" if item.get("field") == "合作信用度" else "multi_subfield_preset_or_number_range"),
        "sub_field": sub_field or label,
        "min": min_value if min_value not in (None, "") else "",
        "max": "",
        "range_policy": "min_only",
    }


def _parse_money_amount(text: Any, default_unit: str = "") -> float | None:
    source = str(text or "").strip()
    if not source:
        return None
    match = re.search(r"(\d+(?:\.\d+)?)\s*(万|千|k|K|元)?", source)
    if not match:
        return None
    amount = parse_number(match.group(1))
    if amount is None:
        return None
    unit = match.group(2) or default_unit
    if unit == "万":
        amount *= 10000
    elif unit in {"千", "k", "K"}:
        amount *= 1000
    return float(amount)


def _standardize_quote_filter(item: dict[str, Any]) -> list[dict[str, Any]]:
    value = str(item.get("value") or "").strip()
    sub_field = str(item.get("sub_field") or item.get("subField") or "").strip()
    min_value = item.get("min")
    max_value = item.get("max")
    if sub_field:
        range_text = re.split(r"[：:]", value, maxsplit=1)[-1]
        parts = [part.strip() for part in re.split(r"～|~|至|到|-", range_text) if part.strip()]
        default_unit = "万" if "万" in range_text else ("千" if "千" in range_text else "")
        parsed_min = _parse_money_amount(parts[0], default_unit) if parts else None
        parsed_max = _parse_money_amount(parts[-1], default_unit) if len(parts) >= 2 else _parse_money_amount(range_text, default_unit)
        return [
            {
                **item,
                "field": "合作报价",
                "control_type": item.get("control_type") or "subfield_preset_or_number_range",
                "sub_field": sub_field,
                "min": min_value if min_value not in (None, "") else (parsed_min if parsed_min is not None else ""),
                "max": max_value if max_value not in (None, "") else (parsed_max if parsed_max is not None else ""),
            }
        ]

    segments = [part.strip() for part in re.split(r"[；;]+", value) if part.strip()]
    result: list[dict[str, Any]] = []
    for segment in segments:
        if "图文" in segment:
            next_sub_field = "图文笔记"
        elif "视频" in segment:
            next_sub_field = "视频笔记"
        else:
            continue
        range_text = re.split(r"[：:]", segment, maxsplit=1)[-1]
        parts = [part.strip() for part in re.split(r"～|~|至|到|-", range_text) if part.strip()]
        default_unit = "万" if "万" in range_text else ("千" if "千" in range_text else "")
        next_min = _parse_money_amount(parts[0], default_unit) if parts else None
        next_max = _parse_money_amount(parts[-1], default_unit) if len(parts) >= 2 else _parse_money_amount(range_text, default_unit)
        result.append(
            {
                **{key: val for key, val in item.items() if key not in {"sub_fields", "subFields", "sub_field", "subField", "min", "max"}},
                "field": "合作报价",
                "value": f"{next_sub_field}：{(next_min if next_min not in (None, '') else 0):g}～{next_max:g}" if next_max is not None else segment,
                "control_type": item.get("control_type") or "subfield_preset_or_number_range",
                "sub_field": next_sub_field,
                "min": next_min if next_min is not None else "",
                "max": next_max if next_max is not None else "",
            }
        )
    return result


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
    if field == "合作报价":
        quote_items = _standardize_quote_filter(item)
        if quote_items:
            return quote_items
    if field in PGY_MIN_ONLY_SAVED_RANGE_FIELDS:
        return [_standardize_min_only_saved_range(item)]
    if field in PGY_MIN_ONLY_SAVED_SUBFIELD_RANGE_FIELDS:
        return [_standardize_min_only_saved_subfield_range(item)]
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


def _global_filters_for_scheme(screening_plan: dict[str, Any]) -> list[dict[str, Any]]:
    pgy_plan = screening_plan.get("pgyCollectionPlan") if isinstance(screening_plan.get("pgyCollectionPlan"), dict) else {}
    allowed_global_fields = {*PGY_BASE_FILTER_FIELDS, *PGY_EXTRA_FILTER_FIELDS}
    return _clean_scheme_filters(
        [
            item
            for item in (pgy_plan.get("filters") or [])
            if isinstance(item, dict)
            and (_is_manual_pgy_filter(item) or str(item.get("field") or "") in allowed_global_fields)
        ],
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
        preview_plan = {
            **plan,
            "filters": _dedupe_filters([*required_filters, *enabled_additional_filters]),
        }
        next_scheme["expected_request_constraints"] = expected_kol_request_constraints_from_plan(preview_plan)
        next_scheme["application_validation"] = {
            "mode": "api_request_body",
            "on_mismatch": "repair_then_validate",
            "stop_on_repair_failed": True,
            "invalid_when": [
                "自动修复后真实请求仍缺少期望的 contentTag/personalTags/noteType/报价/阅读/互动门槛",
                "自动修复后真实请求仍包含 similarUserId",
                "自动修复后最新响应与累计 API 池不一致且无法确认只沿用当前请求分页",
            ],
        }
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
    age_filters = [item for item in base_candidates if str(item.get("field") or "") == "粉丝年龄"]
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
    active_additional_filters = _clean_scheme_filters(active_additional_filters, allowed_fields=PGY_EXTRA_FILTER_FIELDS)
    enabled_extra_keys = {_filter_key(item) for item in active_additional_filters if isinstance(item, dict)}
    enabled_extra_filters = [item for item in extra_filters if _filter_key(item) in enabled_extra_keys]
    existing_enabled_keys = {_filter_key(item) for item in enabled_extra_filters}
    enabled_extra_filters.extend(
        item
        for item in active_additional_filters
        if _filter_key(item) not in existing_enabled_keys
    )
    global_filters = _global_filters_for_scheme(screening_plan)
    pgy_plan["active_scheme_id"] = scheme.get("scheme_id") or scheme.get("id") or scheme.get("name") or "scheme"
    pgy_plan["active_scheme_name"] = scheme.get("name") or pgy_plan["active_scheme_id"]
    pgy_plan["active_scheme_goal"] = scheme.get("goal") or ""
    pgy_plan["required_filters"] = base_filters
    pgy_plan["additional_filters"] = extra_filters
    pgy_plan["enabled_additional_filters"] = enabled_extra_filters
    pgy_plan["base_filters"] = base_filters
    pgy_plan["extra_filters"] = extra_filters
    pgy_plan["enabled_extra_filters"] = enabled_extra_filters
    pgy_plan["manual_filters"] = [item for item in global_filters if _is_manual_pgy_filter(item)]
    pgy_plan["global_filters"] = global_filters
    pgy_plan["filters"] = _dedupe_filters([*base_filters, *enabled_extra_filters, *global_filters])
    pgy_plan["expected_request_constraints"] = expected_kol_request_constraints_from_plan(pgy_plan)
    pgy_plan["application_validation"] = {
        "mode": "api_request_body",
        "on_mismatch": "repair_then_validate",
        "stop_on_repair_failed": True,
        "reason": "前端采集前筛选必须以蒲公英真实达人列表 API 请求为准；请求不一致时先自动修复为正确 API 请求，修复失败才停止。",
    }
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


def _creator_identity_missing_fields(creator: dict[str, Any]) -> list[str]:
    identity_fields = (
        ("pgy_url", "蒲公英达人主页"),
        ("pgy_blogger_id", "蒲公英达人ID"),
        ("xiaohongshu_id", "小红书号"),
        ("creator_id", "采集达人ID"),
        ("nickname", "达人昵称"),
    )
    if any(str(creator.get(field) or "").strip() for field, _ in identity_fields):
        return []
    return ["可用于入库的达人身份"]


def _split_identity_ready_creators(creators: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    ready: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for creator in creators:
        if not isinstance(creator, dict):
            continue
        missing = _creator_identity_missing_fields(creator)
        if not missing:
            ready.append(creator)
            continue
        skipped.append({**creator, "identity_missing_fields": missing})
    return ready, skipped


def _identity_skip_records(creators: list[dict[str, Any]]) -> list[dict[str, Any]]:
    records = []
    for creator in creators:
        missing = creator.get("identity_missing_fields") or _creator_identity_missing_fields(creator)
        records.append(
            {
                "field": "必填身份字段",
                "value": creator.get("nickname") or creator.get("creator_id") or "",
                "message": f"缺少{ '、'.join(missing) }，已跳过入库",
                "creator_id": creator.get("creator_id"),
            }
        )
    return records


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


def _scheme_collect_limit(scheme: dict[str, Any], remaining: int, actual_recommend_count: Any = None) -> int:
    if remaining <= 0:
        return 0
    actual_count = _parse_positive_int(actual_recommend_count)
    if actual_count:
        return max(1, min(remaining, actual_count))
    target_min, _ = _parse_count_range(scheme.get("target_count_range") or scheme.get("targetCountRange"))
    planned_floor = target_min or _parse_positive_int(scheme.get("target_quota") or scheme.get("targetQuota"))
    max_quota = _parse_positive_int(scheme.get("max_quota") or scheme.get("maxQuota"))
    if max_quota is None:
        precision = str(scheme.get("precision_level") or scheme.get("precisionLevel") or "").lower()
        role = str(scheme.get("role") or "").lower()
        if precision == "low" or role in {"supplement", "risk_test"}:
            max_quota = max(1, min(remaining, 30))
    if planned_floor:
        precision = str(scheme.get("precision_level") or scheme.get("precisionLevel") or "").lower()
        role = str(scheme.get("role") or "").lower()
        if (role not in {"supplement", "risk_test"} or precision != "low") and max_quota is not None and max_quota < planned_floor:
            max_quota = planned_floor
    return max(1, min(remaining, max_quota or remaining))


def _scheme_expected_collect_count(preflight_result: dict[str, Any], collect_limit: int) -> int | None:
    actual_count = _parse_positive_int((preflight_result or {}).get("actual_recommend_count"))
    if not actual_count or collect_limit <= 0:
        return None
    return max(1, min(int(collect_limit), actual_count))


def _scheme_collection_shortfall(
    preflight_result: dict[str, Any],
    collected_count: int,
    collect_limit: int,
    *,
    has_next_scheme: bool = True,
) -> dict[str, Any]:
    expected_count = _scheme_expected_collect_count(preflight_result, collect_limit)
    if expected_count is None:
        return {"ok": True, "expected_count": None, "collected_count": int(collected_count)}
    collected = int(collected_count)
    if collected >= expected_count:
        return {"ok": True, "expected_count": expected_count, "collected_count": collected}
    if collected > 0:
        ratio = collected / max(1, expected_count)
        if ratio >= 0.8:
            return {
                "ok": True,
                "warning": True,
                "expected_count": expected_count,
                "collected_count": collected,
                "message": f"本方案预检{preflight_result.get('actual_count_text') or f'推荐 {expected_count} 位博主'}，正式采集读取到 {collected} 个；短缺在可接受范围内，已按已读取结果继续入库",
            }
        if not has_next_scheme:
            return {
                "ok": True,
                "warning": True,
                "expected_count": expected_count,
                "collected_count": collected,
                "message": f"本方案预检{preflight_result.get('actual_count_text') or f'推荐 {expected_count} 位博主'}，正式采集读取到 {collected} 个；当前已是最后一套方案，已按已读取结果继续入库",
            }
    return {
        "ok": False,
        "expected_count": expected_count,
        "collected_count": collected,
        "message": f"本方案预检{preflight_result.get('actual_count_text') or f'推荐 {expected_count} 位博主'}，但正式采集只读取到 {collected} 个；已停止，避免未采完就应用下一套筛选条件",
    }


def _scheme_expected_count(scheme: dict[str, Any], base_target: Any = None, history: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    target_min, target_max = _parse_count_range(scheme.get("target_count_range") or base_target)
    filters = scheme.get("filters") or scheme.get("required_filters") or scheme.get("base_filters") or []
    enabled_additional = scheme.get("enabled_additional_filters") or scheme.get("enabled_extra_filters") or []
    if enabled_additional:
        filters = [*filters, *enabled_additional]
    strong_fields = {"合作报价", "预估CPM", "预估阅读单价", "预估互动单价", "合作订单数", "外溢进店单价", "近期合作品牌", "按博主粉丝推荐"}
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
    allowed_max = max(expected_max, target_max, PGY_DYNAMIC_RECOMMEND_TARGET_MAX)
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
        running_batch = next(iter(list_batches(project_id, status="running", limit=1)), None)
        return {
            "ok": False,
            "message": "当前项目已有采集任务在运行，请等待完成后再启动新的采集",
            "batch": running_batch or {},
            "error": "collection_already_running",
        }
    cancel_event = _collect_cancel_event(project_id)
    cancel_event.clear()
    if payload.async_collect:
        batch_id = create_batch(project_id, payload.source_url)
        batch = update_batch_progress(batch_id, stage="starting", message="采集任务已进入后台队列，正在启动")

        def run_background_collect() -> None:
            try:
                _api_pgy_collect_batch_locked(payload, project_id, cancel_event, batch_id=batch_id)
            except Exception as exc:  # pragma: no cover - defensive guard for long-running browser work
                current_batch = get_batch(batch_id)
                finish_batch(
                    batch_id,
                    "failed",
                    int(current_batch.get("total_count") or 0),
                    int(current_batch.get("success_count") or 0),
                    max(1, int(current_batch.get("failed_count") or 0)),
                    f"后台采集异常：{exc}",
                    collection_plan=current_batch.get("collection_plan") if isinstance(current_batch.get("collection_plan"), dict) else {},
                    applied_filters=current_batch.get("applied_filters") if isinstance(current_batch.get("applied_filters"), list) else [],
                    skipped_filters=current_batch.get("skipped_filters") if isinstance(current_batch.get("skipped_filters"), list) else [],
                    selected_metrics=current_batch.get("selected_metrics") if isinstance(current_batch.get("selected_metrics"), list) else [],
                    skipped_metrics=current_batch.get("skipped_metrics") if isinstance(current_batch.get("skipped_metrics"), list) else [],
                    detail_collection=str(current_batch.get("detail_collection") or ""),
                )
            finally:
                lock.release()

        thread = threading.Thread(target=run_background_collect, name=f"pgy-collect-{project_id}", daemon=True)
        thread.start()
        return {"ok": True, "accepted": True, "async": True, "batch": batch, "message": "采集已在后台启动，可在页面查看实时进度"}
    try:
        return _api_pgy_collect_batch_locked(payload, project_id, cancel_event)
    finally:
        lock.release()


@app.post("/api/pgy/collect/stop")
def api_pgy_collect_stop(payload: BatchCollectStopPayload) -> dict[str, Any]:
    project_id = payload.project_id or "youdao_001"
    event = _collect_cancel_event(project_id)
    event.set()
    running_batch = next(iter(list_batches(project_id, status="running", limit=1)), None)
    if running_batch:
        batch = update_batch_progress(
            running_batch["batch_id"],
            stage="stopping",
            message="已收到停止请求，正在安全停止当前采集",
        )
        return {"ok": True, "batch": batch, "message": "已发送停止请求"}
    return {"ok": True, "batch": {}, "message": "当前没有运行中的采集任务"}


def _api_pgy_collect_batch_locked(
    payload: BatchCollectPayload,
    project_id: str,
    cancel_event: threading.Event,
    *,
    batch_id: str | None = None,
) -> dict[str, Any]:
    project = get_project(project_id) or {}
    brief = project.get("brief") or ""
    screening_plan = payload.screening_plan or _normalize_project_screening_plan(project.get("screening_plan")) or {}
    if isinstance(screening_plan, dict):
        screening_plan = _hydrate_screening_plan_project_defaults(screening_plan, brief)
    pgy_plan = screening_plan.get("pgyCollectionPlan") if isinstance(screening_plan, dict) else {}
    if isinstance(pgy_plan, dict):
        pgy_plan = _normalize_scheme_filter_structure(pgy_plan)
        pgy_plan = _refresh_auto_quality_narrowing_filters(pgy_plan, brief)
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
    batch_id = batch_id or create_batch(project_id, payload.source_url)
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
    collected_creators: list[dict[str, Any]] = []
    creators: list[dict[str, Any]] = []
    creator_ids: list[str] = []
    rejected_by_hard_filters: list[dict[str, Any]] = []
    hard_filter_skips: list[dict[str, Any]] = []
    ingested_by_scheme: dict[str, int] = {}
    ingested_creator_keys: set[str] = set()

    def run_once(
        plan: dict[str, Any],
        scheme: dict[str, Any] | None = None,
        reset_filters: bool = False,
        preflight_only: bool = False,
        apply_filters: bool | None = None,
        limit_override: int | None = None,
        kol_request_snapshot: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        scheme_id = str((scheme or {}).get("scheme_id") or (scheme or {}).get("id") or (scheme or {}).get("name") or "default")
        scheme_name = str((scheme or {}).get("name") or scheme_id)

        def progress_callback(event: dict[str, Any]) -> None:
            if preflight_only or not isinstance(event, dict):
                return
            mode = str(event.get("mode") or "")
            collected = int(event.get("collected_count") or 0)
            target = int(event.get("limit") or limit_override or payload.limit or 0)
            page_number = event.get("page_number")
            api_labels = {
                "api_snapshot": "预检快照 API",
                "api_browser_capture": "浏览器补抓 API",
                "api_template": "接口模板 API",
            }
            base_mode = mode
            suffix = ""
            for prefix in api_labels:
                if mode == prefix or mode.startswith(f"{prefix}_"):
                    base_mode = prefix
                    suffix = mode[len(prefix):]
                    break
            if base_mode in api_labels and suffix == "_start":
                message = f"方案 {scheme_name} 正在尝试{api_labels[base_mode]}"
            elif base_mode in api_labels and suffix == "_failed":
                message = f"方案 {scheme_name} {api_labels[base_mode]}未命中，继续下一采集方案"
            elif base_mode in api_labels and suffix == "_done":
                message = f"方案 {scheme_name} {api_labels[base_mode]}采集完成：已读取 {collected}/{target} 个"
            elif base_mode in api_labels:
                page_text = f"第 {page_number} 页，" if page_number else ""
                message = f"方案 {scheme_name} 正在通过{api_labels[base_mode]}采集：{page_text}已读取 {collected}/{target} 个"
            elif mode == "api":
                page_text = f"第 {page_number} 页，" if page_number else ""
                message = f"方案 {scheme_name} 正在接口采集：{page_text}已读取 {collected}/{target} 个"
            elif mode == "api_done":
                message = f"方案 {scheme_name} 接口采集完成：已读取 {collected}/{target} 个"
            elif mode == "dom_fallback":
                message = f"方案 {scheme_name} API 未命中，切换页面翻页采集"
            elif mode in {"dom", "dom_no_change"}:
                page_text = f"第 {page_number} 页，" if page_number else ""
                message = f"方案 {scheme_name} 正在页面翻页采集：{page_text}已读取 {collected}/{target} 个"
            elif mode == "dom_done":
                message = f"方案 {scheme_name} 页面翻页采集完成：已读取 {collected}/{target} 个"
            else:
                return
            update_batch_progress(
                batch_id,
                stage="collecting",
                message=message,
                total_count=len(raw_creators_by_key) + collected,
                success_count=len(creator_ids),
            )

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
            kol_request_snapshot=kol_request_snapshot,
            progress_callback=progress_callback,
            stop_callback=cancel_event.is_set,
        )
        result["scheme_id"] = scheme_id
        result["scheme_name"] = scheme_name
        if isinstance(result.get("collection_plan"), dict):
            result["expected_request_constraints"] = expected_kol_request_constraints_from_plan(result["collection_plan"])
        return result

    def sync_scheme_ingested_counts() -> None:
        if not ingested_by_scheme:
            return
        for item in scheme_results:
            scheme_id = str(item.get("scheme_id") or "")
            item["ingested_count"] = ingested_by_scheme.get(scheme_id, 0)

    def ingest_scheme_creators(scheme_result: dict[str, Any], scheme_creators_arg: list[dict[str, Any]]) -> dict[str, Any]:
        nonlocal collected_creators, creators, creator_ids, rejected_by_hard_filters, hard_filter_skips
        scheme_id = str(scheme_result.get("scheme_id") or "")
        scheme_name = str(scheme_result.get("scheme_name") or scheme_id)
        tagged_creators = [
            {**creator, "collection_scheme_id": scheme_id, "collection_scheme_name": scheme_name}
            for creator in (scheme_creators_arg or [])
            if isinstance(creator, dict)
        ]
        merged_creators = _merge_export_creators(tagged_creators, scheme_result.get("export_result"))
        unique_creators = []
        for creator in merged_creators:
            creator = {**creator, "collection_scheme_id": scheme_id, "collection_scheme_name": scheme_name}
            key = _creator_dedupe_key(creator)
            raw_creators_by_key.setdefault(key, creator)
            if key in ingested_creator_keys:
                continue
            ingested_creator_keys.add(key)
            unique_creators.append(creator)
        if not unique_creators:
            return {"collected_count": len(merged_creators), "ingested_count": 0, "creator_ids": []}
        unique_creators, identity_skipped = _split_identity_ready_creators(unique_creators)
        if identity_skipped:
            hard_filter_skips.extend(_identity_skip_records(identity_skipped))
            update_batch_progress(
                batch_id,
                stage="collecting",
                message=f"方案 {scheme_name} 跳过 {len(identity_skipped)} 个缺达人主页/小红书号的候选达人",
                total_count=len(raw_creators_by_key),
                success_count=len(creator_ids),
            )
        if not unique_creators:
            return {"collected_count": len(merged_creators), "ingested_count": 0, "creator_ids": [], "identity_skipped_count": len(identity_skipped)}

        hard_filters = screening_plan.get("collectionHardFilters") or (screening_plan.get("pgyCollectionPlan") or {}).get("hard_filters") or screening_plan.get("hardFilters") or []
        _, scheme_rejected = _filter_creators_by_hard_filters(project_id, unique_creators, hard_filters)
        issue_by_key = {
            _creator_dedupe_key(item): item.get("issues") or []
            for item in scheme_rejected
        }
        rejected_by_hard_filters.extend(scheme_rejected)
        hard_filter_skips.extend(
            {
                "field": "筛选工作台标记",
                "value": item.get("nickname") or item.get("creator_id") or "",
                "message": "；".join(item.get("issues") or []),
                "creator_id": item.get("creator_id"),
            }
            for item in scheme_rejected
        )

        prepared_creators = []
        total_after_scheme = len(creator_ids) + len(unique_creators)
        stopped_result = stop_if_requested(
            total=total_after_scheme,
            success=len(creator_ids),
            collection_plan={"multi_scheme": True, "schemes": scheme_results, "base_plan": pgy_plan},
            applied_filters_arg=applied_filters,
            skipped_filters_arg=[*skipped_filters_base, *hard_filter_skips],
            selected_metrics_arg=selected_metrics,
            skipped_metrics_arg=skipped_metrics,
            detail_collection_arg=detail_collection,
        )
        if stopped_result:
            return {"stopped_result": stopped_result}
        for creator in unique_creators:
            issues = issue_by_key.get(_creator_dedupe_key(creator), [])
            raw_payload = creator.get("raw_payload") if isinstance(creator.get("raw_payload"), dict) else {}
            prepared_creators.append(
                {
                    **creator,
                    "collection_hard_filter_passed": not bool(issues),
                    "collection_hard_filter_issues": issues,
                    "raw_payload": {
                        **raw_payload,
                        "collection_hard_filter_passed": not bool(issues),
                        "collection_hard_filter_issues": issues,
                    },
                }
            )
        update_batch_progress(
            batch_id,
            stage="ingesting",
            message=f"方案 {scheme_name} 正在批量写入筛选工作台 {len(prepared_creators)} 个达人；累计 {len(creator_ids)} 个",
            total_count=total_after_scheme,
            success_count=len(creator_ids),
        )
        saved_items = bulk_upsert_creators(project_id, prepared_creators, score=True)
        saved_ids = [str(item["creator_id"]) for item in saved_items if item.get("creator_id")]
        creator_ids.extend(saved_ids)
        collected_creators.extend(prepared_creators)
        creators.extend(prepared_creators)
        if scheme_id:
            ingested_by_scheme[scheme_id] = ingested_by_scheme.get(scheme_id, 0) + len(saved_ids)
        update_batch_progress(
            batch_id,
            stage="ingesting",
            message=f"方案 {scheme_name} 已写入筛选工作台 {len(saved_ids)}/{len(prepared_creators)} 个达人；累计 {len(creator_ids)} 个",
            total_count=total_after_scheme,
            success_count=len(creator_ids),
        )
        sync_scheme_ingested_counts()
        return {"collected_count": len(merged_creators), "ingested_count": len(saved_ids), "creator_ids": saved_ids}

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
                    "api_request_captured": bool(preflight_result.get("kol_request_snapshot")),
                    "api_request_valid": bool((preflight_result.get("kol_request_validation") or {}).get("request_valid")),
                    "api_request_validation": preflight_result.get("kol_request_validation") or {},
                    "evaluation": evaluation,
                    "filters": plan_filters,
                }
            ]
            if payload.preflight and evaluation.get("status") == "too_many" and not payload.collect_out_of_range:
                initial_active_filter_keys = {_active_filter_replace_key(item) for item in active_additional_filters if isinstance(item, dict)}
                active_filter_keys = {_active_filter_replace_key(item) for item in active_additional_filters if isinstance(item, dict)}
                adaptive_filters = _extra_filters_for_scheme(scheme)
                newly_added_adaptive_filters: list[dict[str, Any]] = []
                for additional_filter in adaptive_filters:
                    if _active_filter_replace_key(additional_filter) in active_filter_keys:
                        continue
                    variants = _adaptive_filter_variants(additional_filter)
                    trial_filter = variants[0]
                    trial_active_filters = _replace_active_additional_filter(active_additional_filters, trial_filter)
                    plan_for_scheme = _scheme_plan(screening_plan, scheme, trial_active_filters)
                    plan_filters = (plan_for_scheme.get("pgyCollectionPlan") or {}).get("filters") or []
                    expected_count = _scheme_expected_count(
                        {**scheme, "filters": plan_filters, "enabled_additional_filters": trial_active_filters},
                        pgy_plan.get("target_count_range") if isinstance(pgy_plan, dict) else None,
                        history,
                    )
                    preflight_result = run_once(plan_for_scheme, scheme, reset_filters=False, preflight_only=True)
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
                    active_additional_filters = trial_active_filters
                    newly_added_adaptive_filters.append(trial_filter)
                    preflight_steps.append(
                        {
                            "stage": "additional",
                            "label": "附加筛选条件",
                            "added_filter": trial_filter,
                            "active_additional_filters": active_additional_filters,
                            "actual_recommend_count": preflight_result.get("actual_recommend_count"),
                            "actual_count_text": preflight_result.get("actual_count_text"),
                            "actual_count_is_lower_bound": bool(preflight_result.get("actual_count_is_lower_bound")),
                            "api_request_captured": bool(preflight_result.get("kol_request_snapshot")),
                            "api_request_valid": bool((preflight_result.get("kol_request_validation") or {}).get("request_valid")),
                            "api_request_validation": preflight_result.get("kol_request_validation") or {},
                            "evaluation": evaluation,
                            "filters": plan_filters,
                            "adaptive": len(variants) > 1,
                            "adaptive_candidate_index": 0,
                        }
                    )
                    active_filter_keys.add(_active_filter_replace_key(additional_filter))
                    if evaluation.get("status") != "too_many":
                        break
                if evaluation.get("status") == "too_many":
                    for additional_filter in reversed(newly_added_adaptive_filters):
                        if _active_filter_replace_key(additional_filter) in initial_active_filter_keys:
                            continue
                        variants = _adaptive_filter_variants(additional_filter)
                        if len(variants) <= 1:
                            continue
                        previous_viable_state: dict[str, Any] | None = None
                        for variant_index, trial_filter in enumerate(variants[1:], start=1):
                            trial_active_filters = _replace_active_additional_filter(active_additional_filters, trial_filter)
                            trial_plan_for_scheme = _scheme_plan(screening_plan, scheme, trial_active_filters)
                            trial_plan_filters = (trial_plan_for_scheme.get("pgyCollectionPlan") or {}).get("filters") or []
                            trial_expected_count = _scheme_expected_count(
                                {**scheme, "filters": trial_plan_filters, "enabled_additional_filters": trial_active_filters},
                                pgy_plan.get("target_count_range") if isinstance(pgy_plan, dict) else None,
                                history,
                            )
                            trial_preflight_result = run_once(trial_plan_for_scheme, scheme, reset_filters=False, preflight_only=True)
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
                            trial_evaluation = _evaluate_scheme_count(
                                trial_expected_count,
                                trial_preflight_result.get("actual_recommend_count"),
                                bool(trial_preflight_result.get("actual_count_is_lower_bound")),
                            )
                            actual_count = _parse_positive_int(trial_preflight_result.get("actual_recommend_count"))
                            too_narrow = bool(
                                actual_count is not None
                                and actual_count < PGY_DYNAMIC_RECOMMEND_TARGET_MIN
                                and previous_viable_state is not None
                            )
                            preflight_steps.append(
                                {
                                    "stage": "additional_adjustment",
                                    "label": "附加筛选参数调整",
                                    "added_filter": trial_filter,
                                    "active_additional_filters": trial_active_filters,
                                    "actual_recommend_count": trial_preflight_result.get("actual_recommend_count"),
                                    "actual_count_text": trial_preflight_result.get("actual_count_text"),
                                    "actual_count_is_lower_bound": bool(trial_preflight_result.get("actual_count_is_lower_bound")),
                                    "api_request_captured": bool(trial_preflight_result.get("kol_request_snapshot")),
                                    "api_request_valid": bool((trial_preflight_result.get("kol_request_validation") or {}).get("request_valid")),
                                    "api_request_validation": trial_preflight_result.get("kol_request_validation") or {},
                                    "evaluation": trial_evaluation,
                                    "filters": trial_plan_filters,
                                    "adaptive": True,
                                    "adaptive_candidate_index": variant_index,
                                    "adaptive_too_narrow": too_narrow,
                                }
                            )
                            if too_narrow:
                                active_additional_filters = previous_viable_state["active_additional_filters"]
                                plan_for_scheme = previous_viable_state["plan_for_scheme"]
                                plan_filters = previous_viable_state["plan_filters"]
                                expected_count = previous_viable_state["expected_count"]
                                preflight_result = previous_viable_state["preflight_result"]
                                evaluation = previous_viable_state["evaluation"]
                                break
                            active_additional_filters = trial_active_filters
                            plan_for_scheme = trial_plan_for_scheme
                            plan_filters = trial_plan_filters
                            expected_count = trial_expected_count
                            preflight_result = trial_preflight_result
                            evaluation = trial_evaluation
                            previous_viable_state = {
                                "active_additional_filters": active_additional_filters,
                                "plan_for_scheme": plan_for_scheme,
                                "plan_filters": plan_filters,
                                "expected_count": expected_count,
                                "preflight_result": preflight_result,
                                "evaluation": evaluation,
                            }
                            if evaluation.get("status") != "too_many":
                                break
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
            collect_limit_for_scheme = (
                _scheme_collect_limit(
                    scheme,
                    payload.limit - len(raw_creators_by_key),
                    preflight_result.get("actual_recommend_count"),
                )
                if should_collect
                else 0
            )
            scheme_result = (
                run_once(
                    plan_for_scheme,
                    scheme,
                    reset_filters=not payload.preflight,
                    preflight_only=False,
                    apply_filters=not payload.preflight,
                    limit_override=collect_limit_for_scheme,
                    kol_request_snapshot=preflight_result.get("kol_request_snapshot") if payload.preflight else None,
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
                    "kol_request_snapshot": preflight_result.get("kol_request_snapshot"),
                    "kol_request_validation": preflight_result.get("kol_request_validation") or {},
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
                "api_request_captured": bool(preflight_result.get("kol_request_snapshot")),
                "api_request_valid": bool((preflight_result.get("kol_request_validation") or {}).get("request_valid")),
                "api_request_validation": preflight_result.get("kol_request_validation") or {},
                "evaluation": evaluation,
                "collected_after_preflight": should_collect,
                "forced_collect": bool(payload.collect_out_of_range and not evaluation.get("should_collect")),
            }
            scheme_creators = scheme_result.get("creators") or []
            shortfall = (
                _scheme_collection_shortfall(
                    preflight_result,
                    len(scheme_creators),
                    collect_limit_for_scheme,
                    has_next_scheme=index < len(schemes) - 1,
                )
                if should_collect
                else {"ok": True}
            )
            if shortfall.get("warning"):
                scheme_result["collection_shortfall"] = shortfall
                scheme_result["message"] = scheme_result.get("message") or shortfall.get("message")
                scheme_result["preflight"]["expected_collect_count"] = shortfall.get("expected_count")
                scheme_result["preflight"]["actual_collected_count"] = shortfall.get("collected_count")
            elif not shortfall.get("ok"):
                scheme_result["ok"] = False
                scheme_result["message"] = shortfall.get("message") or scheme_result.get("message")
                scheme_result["collection_shortfall"] = shortfall
                scheme_result["preflight"]["expected_collect_count"] = shortfall.get("expected_count")
                scheme_result["preflight"]["actual_collected_count"] = shortfall.get("collected_count")
                last_error = scheme_result["message"]
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
                    "collection_shortfall": scheme_result.get("collection_shortfall"),
                    "applied_filters": scheme_result.get("applied_filters") or [],
                    "skipped_filters": scheme_result.get("skipped_filters") or [],
                    "collection_plan": scheme_result.get("collection_plan"),
                    "kol_request_snapshot": scheme_result.get("kol_request_snapshot") or preflight_result.get("kol_request_snapshot"),
                    "kol_request_validation": scheme_result.get("kol_request_validation") or preflight_result.get("kol_request_validation") or {},
                    "export_result": scheme_result.get("export_result"),
                }
            )
            if scheme_creators:
                ingest_result = ingest_scheme_creators(scheme_result, scheme_creators)
                if ingest_result.get("stopped_result"):
                    return ingest_result["stopped_result"]
                scheme_results[-1]["ingested_count"] = int(ingest_result.get("ingested_count") or 0)
                if memory_ids_by_scheme.get(scheme_result["scheme_id"]):
                    update_scheme_count_memory(
                        memory_ids_by_scheme[scheme_result["scheme_id"]],
                        accepted_count=int(ingest_result.get("ingested_count") or 0),
                        rejected_count=0,
                        collected_count=int(ingest_result.get("collected_count") or len(scheme_creators)),
                    )
                update_batch_progress(
                    batch_id,
                    stage="ingested",
                    message=f"方案 {index + 1}/{len(schemes)} 已入库 {scheme_results[-1]['ingested_count']} 个达人；累计 {len(creator_ids)} 个",
                    total_count=len(raw_creators_by_key),
                    success_count=len(creator_ids),
                )
            if len(raw_creators_by_key) >= payload.limit:
                break
            if should_collect and not shortfall.get("ok"):
                break
            if (
                should_collect
                and payload.preflight
                and (preflight_result.get("actual_recommend_count") or 0) > 0
                and not scheme_creators
            ):
                break
        shortfall_error = next(
            (
                item
                for item in scheme_results
                if isinstance(item.get("collection_shortfall"), dict)
                and not item["collection_shortfall"].get("ok")
            ),
            None,
        )
        result = {
            "ok": bool(raw_creators_by_key) and shortfall_error is None,
            "message": (shortfall_error.get("message") if shortfall_error else "") or (last_error if not raw_creators_by_key else ""),
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
        success=len(creator_ids) if use_multi_scheme else 0,
        collection_plan=result.get("collection_plan"),
        applied_filters_arg=result.get("applied_filters") or [],
        skipped_filters_arg=[*(result.get("skipped_filters") or []), *hard_filter_skips],
        selected_metrics_arg=result.get("selected_metrics") or [],
        skipped_metrics_arg=result.get("skipped_metrics") or [],
        detail_collection_arg=result.get("detail_collection") or "",
    )
    if stopped_result:
        return stopped_result

    if use_multi_scheme:
        sync_scheme_ingested_counts()
        collection_plan = result.get("collection_plan")
        if isinstance(collection_plan, dict):
            collection_plan["schemes"] = scheme_results
        skipped_filters = [*(result.get("skipped_filters") or []), *hard_filter_skips]
        if not result.get("ok"):
            batch = finish_batch(
                batch_id,
                "failed",
                len(collected_creators),
                len(creator_ids),
                1,
                result.get("message", "采集失败"),
                collection_plan=collection_plan,
                applied_filters=result.get("applied_filters") or [],
                skipped_filters=skipped_filters,
                selected_metrics=result.get("selected_metrics") or [],
                skipped_metrics=result.get("skipped_metrics") or [],
                detail_collection=result.get("detail_collection") or "",
            )
            return {
                "ok": False,
                "batch": batch,
                "message": result.get("message"),
                "creators": creators,
                "rejected_by_hard_filters": rejected_by_hard_filters,
                "collection_plan": collection_plan,
                "export_result": result.get("export_result"),
                "scheme_results": scheme_results,
                "applied_filters": result.get("applied_filters") or [],
                "skipped_filters": skipped_filters,
                "selected_metrics": result.get("selected_metrics") or [],
                "skipped_metrics": result.get("skipped_metrics") or [],
            }
        if not creator_ids:
            batch = finish_batch(
                batch_id,
                "failed",
                len(collected_creators),
                0,
                1,
                "未采集到有效达人",
                collection_plan=collection_plan,
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
                "collection_plan": collection_plan,
                "export_result": result.get("export_result"),
                "scheme_results": scheme_results,
                "applied_filters": result.get("applied_filters") or [],
                "skipped_filters": skipped_filters,
                "selected_metrics": result.get("selected_metrics") or [],
                "skipped_metrics": result.get("skipped_metrics") or [],
            }
        update_batch_progress(
            batch_id,
            stage="score_queued",
            message=f"已进入筛选工作台 {len(creator_ids)} 个达人，评分将后台执行",
            total_count=len(collected_creators),
            success_count=len(creator_ids),
        )
        stopped_result = stop_if_requested(
            total=len(collected_creators),
            success=len(creator_ids),
            collection_plan=collection_plan,
            applied_filters_arg=result.get("applied_filters") or [],
            skipped_filters_arg=skipped_filters,
            selected_metrics_arg=result.get("selected_metrics") or [],
            skipped_metrics_arg=result.get("skipped_metrics") or [],
            detail_collection_arg=result.get("detail_collection") or "",
        )
        if stopped_result:
            return stopped_result
        batch = finish_batch(
            batch_id,
            "success",
            len(collected_creators),
            len(creator_ids),
            0,
            collection_plan=collection_plan,
            applied_filters=result.get("applied_filters") or [],
            skipped_filters=skipped_filters,
            selected_metrics=result.get("selected_metrics") or [],
            skipped_metrics=result.get("skipped_metrics") or [],
            detail_collection=result.get("detail_collection") or "",
        )
        scoring = {
            "async": False,
            "queued": 0,
            "scored": len(creator_ids),
            "use_llm": False,
            "message": "规则评分已在达人入库时完成",
        }
        batch = get_batch(batch_id) or batch
        return {
            "ok": True,
            "batch": batch,
            "creators": creators,
            "scoring": scoring,
            "message": f"蒲公英采集完成，采到 {len(collected_creators)} 个，已按方案分批进入筛选工作台并完成规则评分；{len(rejected_by_hard_filters)} 个将在筛选工作台标记为条件不符并按档位区分",
            "collection_plan": collection_plan,
            "export_result": result.get("export_result"),
            "scheme_results": scheme_results,
            "rejected_by_hard_filters": rejected_by_hard_filters,
            "applied_filters": result.get("applied_filters") or [],
            "skipped_filters": skipped_filters,
            "selected_metrics": result.get("selected_metrics") or [],
            "skipped_metrics": result.get("skipped_metrics") or [],
        }

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
    pgy_collection_plan = screening_plan.get("pgyCollectionPlan") if isinstance(screening_plan.get("pgyCollectionPlan"), dict) else {}
    if "collectionHardFilters" in screening_plan:
        hard_filters = screening_plan.get("collectionHardFilters") or []
    elif "hard_filters" in pgy_collection_plan or "hardFilters" in pgy_collection_plan:
        hard_filters = pgy_collection_plan.get("hard_filters") or pgy_collection_plan.get("hardFilters") or []
    else:
        hard_filters = screening_plan.get("hardFilters") or []
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
    creators, identity_skipped = _split_identity_ready_creators(creators)
    if identity_skipped:
        hard_filter_skips.extend(_identity_skip_records(identity_skipped))
        update_batch_progress(
            batch_id,
            stage="collected",
            message=f"已跳过 {len(identity_skipped)} 个缺达人主页/小红书号的候选达人，剩余 {len(creators)} 个待入库",
            total_count=len(collected_creators),
            success_count=0,
        )
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
    stopped_result = stop_if_requested(
        total=len(collected_creators),
        success=0,
        collection_plan=result.get("collection_plan"),
        applied_filters_arg=result.get("applied_filters") or [],
        skipped_filters_arg=skipped_filters,
        selected_metrics_arg=result.get("selected_metrics") or [],
        skipped_metrics_arg=result.get("skipped_metrics") or [],
        detail_collection_arg=result.get("detail_collection") or "",
    )
    if stopped_result:
        return stopped_result
    update_batch_progress(
        batch_id,
        stage="ingesting",
        message=f"正在批量写入筛选工作台 {total_creators} 个达人",
        total_count=len(collected_creators),
        success_count=0,
    )
    saved_items = bulk_upsert_creators(project_id, creators, score=True)
    creator_ids = [str(item["creator_id"]) for item in saved_items if item.get("creator_id")]
    for creator in creators:
        scheme_id = str(creator.get("collection_scheme_id") or "")
        if scheme_id:
            ingested_by_scheme[scheme_id] = ingested_by_scheme.get(scheme_id, 0) + 1
    update_batch_progress(
        batch_id,
        stage="ingesting",
        message=f"已批量写入筛选工作台 {len(creator_ids)}/{total_creators} 个达人",
        total_count=len(collected_creators),
        success_count=len(creator_ids),
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
        stage="score_queued",
        message=f"已进入筛选工作台 {len(creator_ids)} 个达人，评分将后台执行",
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
    scoring = {
        "async": False,
        "queued": 0,
        "scored": len(creator_ids),
        "use_llm": False,
        "message": "规则评分已在达人入库时完成",
    }
    batch = get_batch(batch_id) or batch
    rejected_count = len(rejected_by_hard_filters)
    return {
        "ok": True,
        "batch": batch,
        "creators": creators,
        "scoring": scoring,
        "message": f"蒲公英采集完成，采到 {len(collected_creators)} 个，已进入筛选工作台并完成规则评分；{rejected_count} 个将在筛选工作台标记为条件不符并按档位区分",
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
def api_pgy_batch(batch_id: str, project_id: str = Query(default="")) -> dict[str, Any]:
    project_ids = [project_id] if project_id else [
        project["project_id"]
        for project in list_projects(include_test_projects=True, include_archived=True)
    ]
    for target_project_id in project_ids:
        for batch in list_batches(target_project_id):
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
