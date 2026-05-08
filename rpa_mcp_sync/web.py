from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
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
    connect,
    create_batch,
    finish_batch,
    get_project,
    import_csv,
    init_db,
    list_batches,
    list_creators,
    list_logs,
    list_projects,
    log,
    review_creator,
    save_project,
    score_project,
    standard_feishu_rows,
    update_creator,
    upsert_creator,
)
from .feishu import FeishuClient, FeishuError, choose_table, parse_feishu_url
from .llm_config import chat_json, read_ai_config, test_ai_config, write_ai_config
from .pgy_browser import browser_status, collect_visible_list, start_browser


class FeishuConnectionPayload(BaseModel):
    project_id: str = Field(default="youdao_001")
    feishu_url: str
    app_id: str
    app_secret: str | None = None


class LlmConfigPayload(BaseModel):
    protocol: str = "openai-compatible"
    base_url: str
    model: str
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


class ProjectPayload(BaseModel):
    project_name: str | None = None
    target_qualified_creator_count: int | None = None
    period_start: str | None = None
    period_end: str | None = None
    brief: str | None = None


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


class BatchCollectPayload(BaseModel):
    source_url: str = "https://pgy.xiaohongshu.com/solar/pre-trade/note/kol"


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
def index() -> FileResponse:
    return FileResponse(ROOT / "screening-workbench.html")


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


@app.get("/api/overview")
def overview() -> dict[str, Any]:
    return {"projects": list_projects()}


@app.get("/api/runtime/version")
def runtime_version() -> dict[str, Any]:
    return {"version": "pgy-python-playwright-20260508", "pgy_collector": "python-playwright"}


@app.get("/api/projects")
def api_projects() -> dict[str, Any]:
    return {"projects": list_projects()}


@app.get("/api/projects/{project_id}")
def api_project(project_id: str) -> dict[str, Any]:
    project = get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail={"message": "项目不存在"})
    return {"project": project}


@app.post("/api/projects/{project_id}")
def api_save_project(project_id: str, payload: ProjectPayload) -> dict[str, Any]:
    return {"project": save_project(project_id, payload.model_dump(exclude_none=True))}


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
        for row in payload.rows:
            upsert_creator(project_id, row)
            imported += 1
        score_project(project_id)
        return {"imported": imported}
    path = ROOT / payload.csv_path if payload.csv_path else None
    result = import_csv(project_id, path)
    score_project(project_id)
    return result


@app.patch("/api/projects/{project_id}/creators/{creator_id}")
def api_update_creator(project_id: str, creator_id: str, payload: CreatorPayload) -> dict[str, Any]:
    try:
        return {"creator": update_creator(project_id, creator_id, payload.data)}
    except KeyError:
        raise HTTPException(status_code=404, detail={"message": "达人不存在"})


@app.post("/api/projects/{project_id}/creators/score")
def api_score_creators(project_id: str) -> dict[str, Any]:
    return score_project(project_id)


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


@app.get("/api/projects/{project_id}/batches")
def api_batches(project_id: str) -> dict[str, Any]:
    return {"batches": list_batches(project_id)}


@app.get("/api/projects/{project_id}/logs")
def api_logs(project_id: str) -> dict[str, Any]:
    return {"logs": list_logs(project_id)}


def _fallback_screening_standard(payload: ScreeningStandardPayload) -> dict[str, Any]:
    fields = payload.feishu_fields or []
    names = [str(item.get("field_name") or item.get("name") or item.get("title") or "") for item in fields]

    def match(*keywords: str) -> str | None:
        for name in names:
            if any(keyword in name for keyword in keywords):
                return name
        return None

    hard_filters = [
        {"field": match("35岁", "宝妈", "粉丝画像") or "35岁以上粉丝占比", "condition": ">=", "value": "40%", "required": True, "feishuField": match("35岁", "宝妈", "粉丝画像")},
        {"field": match("报价", "预算") or "平台报价", "condition": "<=", "value": "¥20,000", "required": True, "feishuField": match("报价", "预算")},
        {"field": match("蒲公英", "链接") or "蒲公英链接", "condition": "必须存在", "value": "", "required": True, "feishuField": match("蒲公英", "链接")},
    ]
    weights = {"budget": 20, "fans": 20, "cpe": 15, "engagement": 15, "persona": 20, "content": 10}
    return {
        "briefType": "complex" if len(payload.brief) > 40 else "simple",
        "hardFilters": hard_filters,
        "scoringWeights": weights,
        "fieldMappings": [
            {"standard": item["field"], "feishu": item.get("feishuField") or "未匹配", "confidence": 0.7 if item.get("feishuField") else 0.3}
            for item in hard_filters
        ],
        "summary": "已基于 Brief 和可用飞书字段生成量化标准。当前结果为规则兜底，配置大模型后可获得更细的字段匹配与口径优化。",
    }


def _normalize_screening_standard(result: dict[str, Any], payload: ScreeningStandardPayload) -> dict[str, Any]:
    fallback = _fallback_screening_standard(payload)
    plan = result.get("screeningPlan") if isinstance(result.get("screeningPlan"), dict) else result
    hard_filters = plan.get("hardFilters") or fallback["hardFilters"]
    weights = plan.get("scoringWeights") or fallback["scoringWeights"]
    total = sum(float(value or 0) for value in weights.values()) or 100
    if abs(total - 100) > 0.01:
        weights = {key: round(float(value or 0) * 100 / total) for key, value in weights.items()}
    return {
        "briefType": plan.get("briefType") or fallback["briefType"],
        "hardFilters": hard_filters,
        "scoringWeights": weights,
        "fieldMappings": plan.get("fieldMappings") or result.get("fieldMappings") or fallback["fieldMappings"],
        "summary": plan.get("summary") or result.get("summary") or fallback["summary"],
    }


@app.post("/api/projects/{project_id}/screening-standard/optimize")
def optimize_screening_standard(project_id: str, payload: ScreeningStandardPayload) -> dict[str, Any]:
    payload.project_id = project_id
    project = get_project(project_id) or payload.project
    system_prompt = (
        "你是广告投放达人筛选策略专家。请把客户 Brief 转换为可执行的达人筛选量化标准，"
        "并优先匹配飞书表中的真实字段。只输出 JSON。"
    )
    user_payload = {
        "project": project,
        "brief": payload.brief,
        "feishuFields": payload.feishu_fields,
        "requiredSchema": {
            "briefType": "simple|complex",
            "hardFilters": [{"field": "标准名", "condition": ">=|<=|必须存在|包含", "value": "阈值", "required": True, "feishuField": "匹配到的飞书字段名或空"}],
            "scoringWeights": {"budget": 20, "fans": 20, "cpe": 15, "engagement": 15, "persona": 20, "content": 10},
            "fieldMappings": [{"standard": "标准字段", "feishu": "飞书字段", "confidence": 0.0}],
            "summary": "一句话说明优化依据",
        },
        "constraints": [
            "scoringWeights 六项总和必须为 100",
            "硬性条件只使用 Brief 明确要求或达人筛选必需字段",
            "飞书字段匹配要使用 feishuFields 中实际存在的字段名",
        ],
    }
    try:
        result = chat_json(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"请根据以下 JSON 输出筛选标准：\n{user_payload}"},
            ]
        )
        plan = _normalize_screening_standard(result, payload)
        source = "llm"
        status = "success"
        detail = plan.get("summary") or "量化标准已由大模型优化"
    except Exception as error:
        plan = _normalize_screening_standard({}, payload)
        source = "fallback"
        status = "warning"
        detail = f"大模型调用失败，已使用规则兜底：{error}"
    with connect() as conn:
        log(conn, project_id, "screening", "优化量化标准", project.get("project_name") or project_id, "AI", detail, status)
    save_project(project_id, {"brief": payload.brief})
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
        raise HTTPException(status_code=400, detail={"code": error.code, "message": str(error), **error.details})
    write_json(path, config)
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


@app.post("/api/projects/feishu/test")
def test_feishu_connection(payload: FeishuConnectionPayload) -> dict[str, Any]:
    try:
        target = parse_feishu_url(payload.feishu_url)
        if not payload.app_secret:
            return {
                "ok": True,
                "target": target.as_dict(),
                "message": "飞书链接格式已识别；未提供 App Secret，已跳过远端读取测试",
            }
        client = FeishuClient(payload.app_id, payload.app_secret)
        resolved = client.resolve_wiki_target(target)
        if resolved.resource_type == "sheet":
            tabs = client.list_sheet_tabs(resolved.token)
            selected = choose_table(tabs, resolved.table_id)
            fields = client.list_sheet_fields(resolved.token, selected.get("sheet_id") or selected.get("id"))
        elif resolved.resource_type == "bitable":
            tables = client.list_bitable_tables(resolved.token)
            selected = choose_table(tables, resolved.table_id)
            fields = client.list_bitable_fields(resolved.token, selected.get("table_id") or selected.get("id"))
        else:
            raise FeishuError("unsupported_resource_type", f"暂不支持该飞书资源：{resolved.resource_type}")
        return {
            "ok": True,
            "target": resolved.as_dict(),
            "selected_table": selected,
            "fields": fields,
            "message": "飞书连接读取成功",
        }
    except FeishuError as error:
        raise HTTPException(status_code=400, detail={"code": error.code, "message": str(error), **error.details})


@app.get("/api/projects/feishu/tables")
def list_feishu_tables(project_id: str = Query(default="youdao_001")) -> dict[str, Any]:
    try:
        _, client, target = _load_feishu_client(project_id)
        if target.resource_type == "sheet":
            tables = client.list_sheet_tabs(target.token)
        elif target.resource_type == "bitable":
            tables = client.list_bitable_tables(target.token)
        else:
            raise FeishuError("unsupported_resource_type", f"暂不支持该飞书资源：{target.resource_type}")
        return {"target": target.as_dict(), "tables": tables}
    except FeishuError as error:
        raise HTTPException(status_code=400, detail={"code": error.code, "message": str(error), **error.details})


@app.get("/api/projects/feishu/fields")
def list_feishu_fields(
    project_id: str = Query(default="youdao_001"),
    table_id: str | None = Query(default=None),
) -> dict[str, Any]:
    try:
        _, client, target = _load_feishu_client(project_id)
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
        return {"target": target.as_dict(), "selected_table": selected, "fields": fields}
    except FeishuError as error:
        raise HTTPException(status_code=400, detail={"code": error.code, "message": str(error), **error.details})


@app.post("/api/projects/feishu/records")
def create_feishu_records(payload: FeishuRecordsPayload) -> dict[str, Any]:
    try:
        rows = payload.rows or standard_feishu_rows(payload.project_id, payload.statuses)
        if not rows:
            raise FeishuError("empty_records", "没有要写入的记录")
        _, client, target = _load_feishu_client(payload.project_id)
        selected_id = payload.table_id or target.table_id
        if target.resource_type == "sheet":
            tables = client.list_sheet_tabs(target.token)
            selected = choose_table(tables, selected_id)
            sheet_id = selected.get("sheet_id") or selected.get("id")
            fields = client.list_sheet_fields(target.token, sheet_id)
            result = client.append_sheet_records(target.token, sheet_id, fields, rows)
        elif target.resource_type == "bitable":
            tables = client.list_bitable_tables(target.token)
            selected = choose_table(tables, selected_id)
            table_id = selected.get("table_id") or selected.get("id")
            result = client.create_bitable_records(target.token, table_id, rows)
        else:
            raise FeishuError("unsupported_resource_type", f"暂不支持该飞书资源：{target.resource_type}")
        for item in list_creators(payload.project_id):
            if item["status"] in payload.statuses:
                review_creator(payload.project_id, item["creator_id"], "已写回飞书", "写回飞书成功", "系统")
        return {"ok": True, "target": target.as_dict(), "selected_table": selected, "result": result, "written_count": len(rows)}
    except FeishuError as error:
        raise HTTPException(status_code=400, detail={"code": error.code, "message": str(error), **error.details})


@app.post("/api/projects/feishu/writeback")
def writeback_feishu_records(payload: FeishuRecordsPayload) -> dict[str, Any]:
    return create_feishu_records(payload)


@app.post("/api/pgy/browser/start")
def api_pgy_browser_start() -> dict[str, Any]:
    return start_browser()


@app.get("/api/pgy/browser/status")
def api_pgy_browser_status() -> dict[str, Any]:
    return browser_status()


@app.post("/api/pgy/collect/list")
def api_pgy_collect_list() -> dict[str, Any]:
    return collect_visible_list()


@app.post("/api/pgy/collect/detail")
def api_pgy_collect_detail() -> dict[str, Any]:
    return {"ok": False, "message": "详情页补全接口已预留，请先用列表采集入库后人工补字段"}


@app.post("/api/pgy/collect/batch")
def api_pgy_collect_batch(payload: BatchCollectPayload) -> dict[str, Any]:
    batch_id = create_batch("youdao_001", payload.source_url)
    result = collect_visible_list()
    if not result.get("ok"):
        batch = finish_batch(batch_id, "failed", 0, 0, 1, result.get("message", "采集失败"))
        return {"ok": False, "batch": batch, "message": result.get("message")}
    creators = result.get("creators") or []
    for creator in creators:
        upsert_creator("youdao_001", creator)
    score_project("youdao_001")
    batch = finish_batch(batch_id, "success", len(creators), len(creators), 0)
    return {"ok": True, "batch": batch, "creators": creators}


@app.get("/api/pgy/collect/batches/{batch_id}")
def api_pgy_batch(batch_id: str) -> dict[str, Any]:
    for batch in list_batches("youdao_001"):
        if batch["batch_id"] == batch_id:
            return {"batch": batch}
    raise HTTPException(status_code=404, detail={"message": "采集批次不存在"})


@app.get("/api/llm/config")
def get_llm_config() -> dict[str, Any]:
    return {"config": read_ai_config()}


@app.post("/api/llm/config")
def save_llm_config(payload: LlmConfigPayload) -> dict[str, Any]:
    config = write_ai_config(payload.model_dump())
    return {"config": config, "message": "API 配置已保存"}


@app.post("/api/llm/test")
def test_llm(payload: LlmConfigPayload) -> dict[str, Any]:
    result = test_ai_config(payload.model_dump())
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result)
    return result
