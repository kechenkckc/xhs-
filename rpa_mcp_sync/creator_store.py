from __future__ import annotations

import csv
import json
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from .config_store import ROOT

DB_PATH = ROOT / "runtime" / "tasks.db"
PROJECT_ID = "youdao_001"
PROJECT_NAME = "有道答疑笔5-6月合作"


def now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def row_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(row) if row else None


def rows_dict(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
    return [dict(row) for row in rows]


SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
  project_id TEXT PRIMARY KEY,
  project_name TEXT NOT NULL,
  target_qualified_creator_count INTEGER DEFAULT 10,
  period_start TEXT,
  period_end TEXT,
  brief TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS creators (
  creator_id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  source TEXT DEFAULT 'manual',
  xiaohongshu_id TEXT,
  pgy_blogger_id TEXT,
  pgy_url TEXT,
  nickname TEXT,
  creator_type TEXT,
  persona_tags TEXT,
  ip_city TEXT,
  profile_url TEXT,
  avatar_url TEXT,
  status TEXT DEFAULT '待补数据',
  raw_payload TEXT DEFAULT '{}',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS creator_metrics (
  creator_id TEXT PRIMARY KEY,
  followers_count REAL,
  quote_price REAL,
  budget_status TEXT,
  traffic_stability TEXT,
  rate_limit_risk TEXT,
  natural_cpc REAL,
  natural_cpe REAL,
  search_recommend_ratio REAL,
  fans_35_plus_ratio REAL,
  child_age TEXT,
  child_grade TEXT,
  child_gender TEXT,
  topic_point TEXT,
  cost_30d REAL,
  cost_90d REAL,
  audience_profile_screenshot TEXT,
  collected_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS creator_scores (
  creator_id TEXT PRIMARY KEY,
  total_score REAL,
  budget_score REAL,
  fans_score REAL,
  cpe_score REAL,
  traffic_score REAL,
  persona_score REAL,
  content_score REAL,
  hard_filter_passed INTEGER,
  recommend_level TEXT,
  score_reason TEXT,
  scored_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS screening_reviews (
  creator_id TEXT PRIMARY KEY,
  review_status TEXT,
  review_reason TEXT,
  reviewer TEXT,
  reviewed_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS collection_batches (
  batch_id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  source_url TEXT,
  status TEXT,
  started_at TEXT NOT NULL,
  finished_at TEXT,
  total_count INTEGER DEFAULT 0,
  success_count INTEGER DEFAULT 0,
  failed_count INTEGER DEFAULT 0,
  error_message TEXT
);

CREATE TABLE IF NOT EXISTS operation_logs (
  log_id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  action_type TEXT,
  action TEXT,
  target TEXT,
  operator TEXT,
  detail TEXT,
  status TEXT,
  created_at TEXT NOT NULL
);
"""


def init_db() -> None:
    with connect() as conn:
        conn.executescript(SCHEMA)
        existing = conn.execute("SELECT project_id FROM projects WHERE project_id=?", (PROJECT_ID,)).fetchone()
        if not existing:
            ts = now()
            conn.execute(
                """
                INSERT INTO projects(project_id, project_name, target_qualified_creator_count, period_start, period_end, brief, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    PROJECT_ID,
                    PROJECT_NAME,
                    10,
                    "2026-05-07",
                    "2026-05-19",
                    "教育/亲子大孩/高知家庭达人，聚焦有道答疑笔5-6月合作。",
                    ts,
                    ts,
                ),
            )
            log(conn, PROJECT_ID, "project", "创建项目", PROJECT_NAME, "系统", "初始化有道单项目", "success")


def log(
    conn: sqlite3.Connection,
    project_id: str,
    action_type: str,
    action: str,
    target: str,
    operator: str,
    detail: str,
    status: str = "success",
) -> None:
    conn.execute(
        """
        INSERT INTO operation_logs(log_id, project_id, action_type, action, target, operator, detail, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (str(uuid.uuid4()), project_id, action_type, action, target, operator, detail, status, now()),
    )


def parse_number(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text in {"待填", "待核", "待评估", "-"}:
        return None
    text = text.replace(",", "").replace("¥", "").replace("￥", "").replace("%", "")
    try:
        return float(text)
    except ValueError:
        return None


def ratio(value: Any) -> float | None:
    number = parse_number(value)
    if number is None:
        return None
    return number / 100 if number > 1 else number


def normalize_creator(payload: dict[str, Any], project_id: str) -> dict[str, Any]:
    return {
        "creator_id": str(payload.get("creator_id") or payload.get("达人ID") or uuid.uuid4()),
        "project_id": project_id,
        "source": payload.get("source") or "manual",
        "xiaohongshu_id": payload.get("xiaohongshu_id") or payload.get("小红书号") or "",
        "pgy_blogger_id": payload.get("pgy_blogger_id") or "",
        "pgy_url": payload.get("pgy_url") or payload.get("蒲公英链接") or "",
        "nickname": payload.get("nickname") or payload.get("达人昵称") or "",
        "creator_type": payload.get("creator_type") or payload.get("达人类型") or "",
        "persona_tags": payload.get("persona_tags") or payload.get("人设标签") or "",
        "ip_city": payload.get("ip_city") or payload.get("IP城市") or "",
        "profile_url": payload.get("profile_url") or "",
        "avatar_url": payload.get("avatar_url") or "",
        "status": payload.get("status") or payload.get("当前状态") or "待补数据",
        "raw_payload": json.dumps(payload.get("raw_payload") or payload, ensure_ascii=False),
        "followers_count": parse_number(payload.get("followers_count") or payload.get("粉丝数")),
        "quote_price": parse_number(payload.get("quote_price") or payload.get("报价")),
        "budget_status": payload.get("budget_status") or payload.get("预算状态") or "",
        "traffic_stability": payload.get("traffic_stability") or payload.get("近30天流量稳定性") or "",
        "rate_limit_risk": payload.get("rate_limit_risk") or payload.get("限流风险判断") or "",
        "natural_cpc": parse_number(payload.get("natural_cpc") or payload.get("合作笔记自然CPC")),
        "natural_cpe": parse_number(payload.get("natural_cpe") or payload.get("合作笔记自然CPE")),
        "search_recommend_ratio": ratio(payload.get("search_recommend_ratio") or payload.get("搜索+推荐占比")),
        "fans_35_plus_ratio": ratio(payload.get("fans_35_plus_ratio") or payload.get("35岁以上粉丝占比")),
        "child_age": payload.get("child_age") or payload.get("孩子年龄") or "",
        "child_grade": payload.get("child_grade") or payload.get("孩子年级") or "",
        "child_gender": payload.get("child_gender") or payload.get("孩子性别") or "",
        "topic_point": payload.get("topic_point") or payload.get("家庭/教育话题点") or "",
        "cost_30d": parse_number(payload.get("cost_30d") or payload.get("30天外溢进店成本")),
        "cost_90d": parse_number(payload.get("cost_90d") or payload.get("90天外溢进店成本")),
        "audience_profile_screenshot": payload.get("audience_profile_screenshot") or "",
    }


def find_existing(conn: sqlite3.Connection, creator: dict[str, Any]) -> str | None:
    checks = [
        ("xiaohongshu_id", creator.get("xiaohongshu_id")),
        ("pgy_blogger_id", creator.get("pgy_blogger_id")),
        ("pgy_url", creator.get("pgy_url")),
    ]
    for field, value in checks:
        if value:
            row = conn.execute(
                f"SELECT creator_id FROM creators WHERE project_id=? AND {field}=?",
                (creator["project_id"], value),
            ).fetchone()
            if row:
                return row["creator_id"]
    if creator.get("nickname") and creator.get("followers_count") and creator.get("quote_price"):
        row = conn.execute(
            """
            SELECT c.creator_id FROM creators c
            JOIN creator_metrics m ON c.creator_id=m.creator_id
            WHERE c.project_id=? AND c.nickname=? AND m.followers_count=? AND m.quote_price=?
            """,
            (creator["project_id"], creator["nickname"], creator["followers_count"], creator["quote_price"]),
        ).fetchone()
        if row:
            return row["creator_id"]
    return None


def upsert_creator(project_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    init_db()
    creator = normalize_creator(payload, project_id)
    ts = now()
    with connect() as conn:
        existing_id = find_existing(conn, creator)
        creator_id = existing_id or creator["creator_id"]
        review = conn.execute("SELECT review_status FROM screening_reviews WHERE creator_id=?", (creator_id,)).fetchone()
        current = conn.execute("SELECT status FROM creators WHERE creator_id=?", (creator_id,)).fetchone()
        status = current["status"] if review and current else creator["status"]
        if existing_id:
            conn.execute(
                """
                UPDATE creators SET source=?, xiaohongshu_id=?, pgy_blogger_id=?, pgy_url=?, nickname=?,
                creator_type=?, persona_tags=?, ip_city=?, profile_url=?, avatar_url=?, status=?, raw_payload=?, updated_at=?
                WHERE creator_id=?
                """,
                (
                    creator["source"], creator["xiaohongshu_id"], creator["pgy_blogger_id"], creator["pgy_url"],
                    creator["nickname"], creator["creator_type"], creator["persona_tags"], creator["ip_city"],
                    creator["profile_url"], creator["avatar_url"], status, creator["raw_payload"], ts, creator_id,
                ),
            )
            action = "更新达人"
        else:
            conn.execute(
                """
                INSERT INTO creators(creator_id, project_id, source, xiaohongshu_id, pgy_blogger_id, pgy_url, nickname,
                creator_type, persona_tags, ip_city, profile_url, avatar_url, status, raw_payload, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    creator_id, project_id, creator["source"], creator["xiaohongshu_id"], creator["pgy_blogger_id"],
                    creator["pgy_url"], creator["nickname"], creator["creator_type"], creator["persona_tags"],
                    creator["ip_city"], creator["profile_url"], creator["avatar_url"], status, creator["raw_payload"], ts, ts,
                ),
            )
            action = "新增达人"
        conn.execute(
            """
            INSERT INTO creator_metrics(creator_id, followers_count, quote_price, budget_status, traffic_stability,
            rate_limit_risk, natural_cpc, natural_cpe, search_recommend_ratio, fans_35_plus_ratio, child_age,
            child_grade, child_gender, topic_point, cost_30d, cost_90d, audience_profile_screenshot, collected_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(creator_id) DO UPDATE SET followers_count=excluded.followers_count, quote_price=excluded.quote_price,
            budget_status=excluded.budget_status, traffic_stability=excluded.traffic_stability,
            rate_limit_risk=excluded.rate_limit_risk, natural_cpc=excluded.natural_cpc, natural_cpe=excluded.natural_cpe,
            search_recommend_ratio=excluded.search_recommend_ratio, fans_35_plus_ratio=excluded.fans_35_plus_ratio,
            child_age=excluded.child_age, child_grade=excluded.child_grade, child_gender=excluded.child_gender,
            topic_point=excluded.topic_point, cost_30d=excluded.cost_30d, cost_90d=excluded.cost_90d,
            audience_profile_screenshot=excluded.audience_profile_screenshot, collected_at=excluded.collected_at
            """,
            (
                creator_id, creator["followers_count"], creator["quote_price"], creator["budget_status"],
                creator["traffic_stability"], creator["rate_limit_risk"], creator["natural_cpc"], creator["natural_cpe"],
                creator["search_recommend_ratio"], creator["fans_35_plus_ratio"], creator["child_age"], creator["child_grade"],
                creator["child_gender"], creator["topic_point"], creator["cost_30d"], creator["cost_90d"],
                creator["audience_profile_screenshot"], ts,
            ),
        )
        log(conn, project_id, "creator", action, creator.get("nickname") or creator_id, "系统", "达人池已去重入库", "success")
    score_creator(project_id, creator_id)
    return get_creator(project_id, creator_id) or {}


def import_csv(project_id: str, path: Path | None = None) -> dict[str, Any]:
    init_db()
    csv_path = path or ROOT / "有道答疑笔5-6月合作_测试项目" / "03_达人池实体表.csv"
    count = 0
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            upsert_creator(project_id, row)
            count += 1
    with connect() as conn:
        log(conn, project_id, "import", "导入达人模板", csv_path.name, "系统", f"导入 {count} 条达人记录", "success")
    return {"imported": count}


def list_projects() -> list[dict[str, Any]]:
    init_db()
    with connect() as conn:
        projects = rows_dict(conn.execute("SELECT * FROM projects ORDER BY created_at").fetchall())
    return [with_project_stats(project) for project in projects]


def get_project(project_id: str) -> dict[str, Any] | None:
    init_db()
    with connect() as conn:
        project = row_dict(conn.execute("SELECT * FROM projects WHERE project_id=?", (project_id,)).fetchone())
    return with_project_stats(project) if project else None


def save_project(project_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    init_db()
    existing = get_project(project_id)
    ts = now()
    with connect() as conn:
        if existing:
            conn.execute(
                "UPDATE projects SET project_name=?, target_qualified_creator_count=?, period_start=?, period_end=?, brief=?, updated_at=? WHERE project_id=?",
                (
                    payload.get("project_name") or existing["project_name"],
                    int(payload.get("target_qualified_creator_count") or existing["target_qualified_creator_count"]),
                    payload.get("period_start") or existing.get("period_start"),
                    payload.get("period_end") or existing.get("period_end"),
                    payload.get("brief") or existing.get("brief"),
                    ts,
                    project_id,
                ),
            )
        else:
            conn.execute(
                "INSERT INTO projects(project_id, project_name, target_qualified_creator_count, period_start, period_end, brief, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (project_id, payload.get("project_name") or project_id, int(payload.get("target_qualified_creator_count") or 10), payload.get("period_start"), payload.get("period_end"), payload.get("brief") or "", ts, ts),
            )
        log(conn, project_id, "project", "保存项目", payload.get("project_name") or project_id, "用户", "立项信息已保存", "success")
    return get_project(project_id) or {}


def with_project_stats(project: dict[str, Any]) -> dict[str, Any]:
    with connect() as conn:
        pool = conn.execute("SELECT COUNT(*) AS count FROM creators WHERE project_id=?", (project["project_id"],)).fetchone()["count"]
        qualified = conn.execute("SELECT COUNT(*) AS count FROM creators WHERE project_id=? AND status IN ('已通过','已写回飞书')", (project["project_id"],)).fetchone()["count"]
    target = project.get("target_qualified_creator_count") or 10
    project["creator_pool_count"] = pool
    project["qualified_creator_count"] = qualified
    project["qualified_ratio"] = qualified / target if target else 0
    return project


def list_creators(project_id: str, status: str | None = None, q: str | None = None) -> list[dict[str, Any]]:
    init_db()
    where = ["c.project_id=?"]
    params: list[Any] = [project_id]
    if status:
        where.append("c.status=?")
        params.append(status)
    if q:
        where.append("(c.nickname LIKE ? OR c.persona_tags LIKE ? OR c.ip_city LIKE ?)")
        params.extend([f"%{q}%", f"%{q}%", f"%{q}%"])
    sql = f"""
    SELECT c.*, m.*, s.total_score, s.recommend_level, s.score_reason, s.hard_filter_passed,
           r.review_status, r.review_reason, r.reviewer, r.reviewed_at
    FROM creators c
    LEFT JOIN creator_metrics m ON c.creator_id=m.creator_id
    LEFT JOIN creator_scores s ON c.creator_id=s.creator_id
    LEFT JOIN screening_reviews r ON c.creator_id=r.creator_id
    WHERE {' AND '.join(where)}
    ORDER BY COALESCE(s.total_score, 0) DESC, c.updated_at DESC
    """
    with connect() as conn:
        return rows_dict(conn.execute(sql, params).fetchall())


def get_creator(project_id: str, creator_id: str) -> dict[str, Any] | None:
    items = list_creators(project_id)
    return next((item for item in items if item["creator_id"] == creator_id), None)


def update_creator(project_id: str, creator_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    existing = get_creator(project_id, creator_id)
    if not existing:
        raise KeyError(creator_id)
    merged = {**existing, **payload, "creator_id": creator_id}
    return upsert_creator(project_id, merged)


def score_values(creator: dict[str, Any]) -> dict[str, Any]:
    quote = creator.get("quote_price")
    fans35 = creator.get("fans_35_plus_ratio")
    cpc = creator.get("natural_cpc")
    cpe = creator.get("natural_cpe")
    search = creator.get("search_recommend_ratio")
    city = creator.get("ip_city") or ""
    tags = f"{creator.get('persona_tags') or ''} {creator.get('topic_point') or ''} {creator.get('child_grade') or ''}"
    risk = creator.get("rate_limit_risk") or ""
    has_pgy = bool(creator.get("pgy_url") and creator.get("pgy_url") != "待填")
    hard_pass = has_pgy and (quote is None or quote < 20000) and (fans35 is None or fans35 > 0.4)
    budget = 20 if quote is None or quote < 12000 else 15 if quote < 20000 else 0
    fans = 20 if fans35 and fans35 > 0.5 else 16 if fans35 and fans35 > 0.4 else 8 if fans35 is None else 0
    traffic = 15 if search and search > 0.5 else 12 if search and search > 0.4 else 8 if search is None else 3
    cpe_score = 15
    if cpc is not None:
        cpe_score -= 6 if cpc >= 2 else 0
    if cpe is not None:
        cpe_score -= 6 if cpe >= 20 else 0
    persona = 12
    if any(word in tags for word in ["小升初", "初中", "高中", "教师", "高知", "中产", "教育"]):
        persona += 6
    if "北京" in city or "上海" in city:
        persona += 2
    content = 10 if any(word in tags for word in ["学区房", "住校", "国际学校", "家庭", "教育"]) else 7
    if "限流" in risk or "违规" in risk:
        traffic = min(traffic, 4)
        content = min(content, 4)
    total = max(0, min(100, budget + fans + traffic + cpe_score + min(persona, 20) + content))
    reasons = []
    if not has_pgy:
        reasons.append("缺少蒲公英链接")
    if quote and quote >= 20000:
        reasons.append("报价超过2万元")
    if fans35 is not None and fans35 <= 0.4:
        reasons.append("35岁以上粉丝占比未达40%")
    if search is not None and search <= 0.4:
        reasons.append("搜索+推荐占比偏低")
    if cpc is not None and cpc >= 2:
        reasons.append("自然CPC偏高")
    if cpe is not None and cpe >= 20:
        reasons.append("自然CPE偏高")
    if hard_pass and not reasons:
        reasons.append("预算、粉丝画像和自然流量指标满足核心口径")
    level = "强推荐" if total >= 85 and hard_pass else "推荐" if total >= 75 and hard_pass else "备选" if total >= 60 else "不推荐"
    return {
        "total_score": total,
        "budget_score": budget,
        "fans_score": fans,
        "cpe_score": cpe_score,
        "traffic_score": traffic,
        "persona_score": min(persona, 20),
        "content_score": content,
        "hard_filter_passed": 1 if hard_pass else 0,
        "recommend_level": level,
        "score_reason": "；".join(reasons),
    }


def score_creator(project_id: str, creator_id: str) -> dict[str, Any]:
    creator = get_creator(project_id, creator_id)
    if not creator:
        raise KeyError(creator_id)
    score = score_values(creator)
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO creator_scores(creator_id, total_score, budget_score, fans_score, cpe_score, traffic_score,
            persona_score, content_score, hard_filter_passed, recommend_level, score_reason, scored_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(creator_id) DO UPDATE SET total_score=excluded.total_score, budget_score=excluded.budget_score,
            fans_score=excluded.fans_score, cpe_score=excluded.cpe_score, traffic_score=excluded.traffic_score,
            persona_score=excluded.persona_score, content_score=excluded.content_score,
            hard_filter_passed=excluded.hard_filter_passed, recommend_level=excluded.recommend_level,
            score_reason=excluded.score_reason, scored_at=excluded.scored_at
            """,
            (
                creator_id, score["total_score"], score["budget_score"], score["fans_score"], score["cpe_score"],
                score["traffic_score"], score["persona_score"], score["content_score"], score["hard_filter_passed"],
                score["recommend_level"], score["score_reason"], now(),
            ),
        )
        if creator["status"] == "待补数据" and score["hard_filter_passed"]:
            conn.execute("UPDATE creators SET status='待审核', updated_at=? WHERE creator_id=?", (now(), creator_id))
    return get_creator(project_id, creator_id) or {}


def score_project(project_id: str) -> dict[str, Any]:
    creators = list_creators(project_id)
    for creator in creators:
        score_creator(project_id, creator["creator_id"])
    with connect() as conn:
        log(conn, project_id, "score", "执行评分", PROJECT_NAME, "系统", f"完成 {len(creators)} 位达人评分", "success")
    return {"scored": len(creators)}


def review_creator(project_id: str, creator_id: str, status: str, reason: str = "", reviewer: str = "用户") -> dict[str, Any]:
    if status not in {"待补数据", "待审核", "已通过", "备选", "已驳回", "已写回飞书"}:
        raise ValueError("invalid status")
    ts = now()
    with connect() as conn:
        conn.execute("UPDATE creators SET status=?, updated_at=? WHERE project_id=? AND creator_id=?", (status, ts, project_id, creator_id))
        conn.execute(
            """
            INSERT INTO screening_reviews(creator_id, review_status, review_reason, reviewer, reviewed_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(creator_id) DO UPDATE SET review_status=excluded.review_status,
            review_reason=excluded.review_reason, reviewer=excluded.reviewer, reviewed_at=excluded.reviewed_at
            """,
            (creator_id, status, reason, reviewer, ts),
        )
        log(conn, project_id, "review", f"审核{status}", creator_id, reviewer, reason or f"状态更新为{status}", "success")
    return get_creator(project_id, creator_id) or {}


def list_batches(project_id: str) -> list[dict[str, Any]]:
    init_db()
    with connect() as conn:
        return rows_dict(conn.execute("SELECT * FROM collection_batches WHERE project_id=? ORDER BY started_at DESC", (project_id,)).fetchall())


def create_batch(project_id: str, source_url: str, status: str = "running") -> str:
    batch_id = str(uuid.uuid4())
    with connect() as conn:
        conn.execute(
            "INSERT INTO collection_batches(batch_id, project_id, source_url, status, started_at) VALUES (?, ?, ?, ?, ?)",
            (batch_id, project_id, source_url, status, now()),
        )
    return batch_id


def finish_batch(batch_id: str, status: str, total: int, success: int, failed: int, error: str = "") -> dict[str, Any]:
    with connect() as conn:
        conn.execute(
            "UPDATE collection_batches SET status=?, finished_at=?, total_count=?, success_count=?, failed_count=?, error_message=? WHERE batch_id=?",
            (status, now(), total, success, failed, error, batch_id),
        )
        row = row_dict(conn.execute("SELECT * FROM collection_batches WHERE batch_id=?", (batch_id,)).fetchone())
    return row or {}


def list_logs(project_id: str) -> list[dict[str, Any]]:
    init_db()
    with connect() as conn:
        return rows_dict(conn.execute("SELECT * FROM operation_logs WHERE project_id=? ORDER BY created_at DESC LIMIT 200", (project_id,)).fetchall())


def standard_feishu_rows(project_id: str, statuses: list[str] | None = None) -> list[dict[str, Any]]:
    statuses = statuses or ["已通过", "备选"]
    creators = [c for c in list_creators(project_id) if c["status"] in statuses]
    rows = []
    for c in creators:
        rows.append(
            {
                "达人ID": c["creator_id"],
                "达人昵称": c.get("nickname") or "",
                "蒲公英链接": c.get("pgy_url") or "",
                "达人类型": c.get("creator_type") or "",
                "人设标签": c.get("persona_tags") or "",
                "IP城市": c.get("ip_city") or "",
                "报价": c.get("quote_price") or "",
                "预算状态": c.get("budget_status") or "",
                "粉丝数": c.get("followers_count") or "",
                "近30天流量稳定性": c.get("traffic_stability") or "",
                "限流风险判断": c.get("rate_limit_risk") or "",
                "合作笔记自然CPC": c.get("natural_cpc") or "",
                "合作笔记自然CPE": c.get("natural_cpe") or "",
                "搜索+推荐占比": c.get("search_recommend_ratio") or "",
                "35岁以上粉丝占比": c.get("fans_35_plus_ratio") or "",
                "孩子年龄": c.get("child_age") or "",
                "孩子年级": c.get("child_grade") or "",
                "孩子性别": c.get("child_gender") or "",
                "家庭/教育话题点": c.get("topic_point") or "",
                "30天外溢进店成本": c.get("cost_30d") or "",
                "90天外溢进店成本": c.get("cost_90d") or "",
                "推荐等级": c.get("recommend_level") or "",
                "当前状态": c.get("status") or "",
                "备注": c.get("score_reason") or "",
            }
        )
    return rows
