from __future__ import annotations

import csv
import json
import os
import re
import shutil
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from .config_store import ROOT
from .llm_config import chat_json

DB_PATH = ROOT / "runtime" / "tasks.db"
PROJECT_ID = "youdao_001"
PROJECT_NAME = "有道答疑笔5-6月合作"


def now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def database_path() -> Path:
    configured = os.environ.get("RPA_MCP_SYNC_DB_PATH")
    return Path(configured) if configured else DB_PATH


def connect() -> sqlite3.Connection:
    path = database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def row_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(row) if row else None


def rows_dict(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
    return [dict(row) for row in rows]


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    if column not in _table_columns(conn, table):
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
  project_id TEXT PRIMARY KEY,
  project_name TEXT NOT NULL,
  target_qualified_creator_count INTEGER DEFAULT 10,
  period_start TEXT,
  period_end TEXT,
  brief TEXT,
  screening_plan TEXT DEFAULT '{}',
  archived_at TEXT,
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

CREATE TABLE IF NOT EXISTS creators_global (
  creator_id TEXT PRIMARY KEY,
  source TEXT DEFAULT 'manual',
  pgy_url TEXT,
  xiaohongshu_id TEXT,
  pgy_blogger_id TEXT,
  nickname TEXT,
  creator_type TEXT,
  persona_tags TEXT,
  ip_city TEXT,
  profile_url TEXT,
  avatar_url TEXT,
  raw_payload TEXT DEFAULT '{}',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS project_creators (
  project_id TEXT NOT NULL,
  creator_id TEXT NOT NULL,
  pool_stage TEXT DEFAULT '待建联达人',
  review_status TEXT DEFAULT '待补数据',
  review_reason TEXT DEFAULT '',
  reviewer TEXT DEFAULT '',
  reviewed_at TEXT,
  total_score REAL,
  tier TEXT,
  portfolio_role TEXT DEFAULT '',
  owner TEXT DEFAULT '',
  note TEXT DEFAULT '',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  PRIMARY KEY(project_id, creator_id)
);

CREATE TABLE IF NOT EXISTS project_writeback_settings (
  project_id TEXT PRIMARY KEY,
  auto_writeback_enabled INTEGER DEFAULT 0,
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
  daily_exposure_median REAL,
  daily_read_median REAL,
  daily_interaction_median REAL,
  daily_thousand_like_note_ratio REAL,
  daily_hundred_like_note_ratio REAL,
  image_daily_exposure_median REAL,
  image_daily_read_median REAL,
  image_daily_interaction_median REAL,
  image_daily_thousand_like_note_ratio REAL,
  image_daily_hundred_like_note_ratio REAL,
  video_daily_exposure_median REAL,
  video_daily_read_median REAL,
  video_daily_interaction_median REAL,
  video_daily_thousand_like_note_ratio REAL,
  video_daily_hundred_like_note_ratio REAL,
  video_completion_rate REAL,
  cooperation_exposure_median REAL,
  cooperation_read_median REAL,
  cooperation_interaction_median REAL,
  overflow_store_median REAL,
  overflow_store_unit_price REAL,
  image_cpm REAL,
  image_read_unit_price REAL,
  image_interaction_unit_price REAL,
  video_cpm REAL,
  video_read_unit_price REAL,
  video_interaction_unit_price REAL,
  active_fans_ratio REAL,
  fans_growth_ratio REAL,
  read_fans_ratio REAL,
  interaction_fans_ratio REAL,
  order_fans_ratio REAL,
  reply_rate_48h REAL,
  active_days_7d REAL,
  video_quote_price REAL,
  live_30d_count REAL,
  live_avg_viewers REAL,
  live_avg_sales REAL,
  search_recommend_ratio REAL,
  fans_35_plus_ratio REAL,
  child_age TEXT,
  child_grade TEXT,
  child_gender TEXT,
  topic_point TEXT,
  cost_30d REAL,
  cost_90d REAL,
  audience_profile_screenshot TEXT,
  audience_age_distribution TEXT,
  audience_gender_distribution TEXT,
  collected_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS creator_metrics_current (
  creator_id TEXT PRIMARY KEY,
  followers_count REAL,
  quote_price REAL,
  budget_status TEXT,
  traffic_stability TEXT,
  rate_limit_risk TEXT,
  natural_cpc REAL,
  natural_cpe REAL,
  daily_exposure_median REAL,
  daily_read_median REAL,
  daily_interaction_median REAL,
  daily_thousand_like_note_ratio REAL,
  daily_hundred_like_note_ratio REAL,
  image_daily_exposure_median REAL,
  image_daily_read_median REAL,
  image_daily_interaction_median REAL,
  image_daily_thousand_like_note_ratio REAL,
  image_daily_hundred_like_note_ratio REAL,
  video_daily_exposure_median REAL,
  video_daily_read_median REAL,
  video_daily_interaction_median REAL,
  video_daily_thousand_like_note_ratio REAL,
  video_daily_hundred_like_note_ratio REAL,
  video_completion_rate REAL,
  cooperation_exposure_median REAL,
  cooperation_read_median REAL,
  cooperation_interaction_median REAL,
  overflow_store_median REAL,
  overflow_store_unit_price REAL,
  image_cpm REAL,
  image_read_unit_price REAL,
  image_interaction_unit_price REAL,
  video_cpm REAL,
  video_read_unit_price REAL,
  video_interaction_unit_price REAL,
  active_fans_ratio REAL,
  fans_growth_ratio REAL,
  read_fans_ratio REAL,
  interaction_fans_ratio REAL,
  order_fans_ratio REAL,
  reply_rate_48h REAL,
  active_days_7d REAL,
  video_quote_price REAL,
  live_30d_count REAL,
  live_avg_viewers REAL,
  live_avg_sales REAL,
  search_recommend_ratio REAL,
  fans_35_plus_ratio REAL,
  child_age TEXT,
  child_grade TEXT,
  child_gender TEXT,
  topic_point TEXT,
  cost_30d REAL,
  cost_90d REAL,
  audience_profile_screenshot TEXT,
  audience_age_distribution TEXT,
  audience_gender_distribution TEXT,
  collected_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS creator_metrics_history (
  snapshot_id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  creator_id TEXT NOT NULL,
  followers_count REAL,
  quote_price REAL,
  budget_status TEXT,
  traffic_stability TEXT,
  rate_limit_risk TEXT,
  natural_cpc REAL,
  natural_cpe REAL,
  daily_exposure_median REAL,
  daily_read_median REAL,
  daily_interaction_median REAL,
  daily_thousand_like_note_ratio REAL,
  daily_hundred_like_note_ratio REAL,
  image_daily_exposure_median REAL,
  image_daily_read_median REAL,
  image_daily_interaction_median REAL,
  image_daily_thousand_like_note_ratio REAL,
  image_daily_hundred_like_note_ratio REAL,
  video_daily_exposure_median REAL,
  video_daily_read_median REAL,
  video_daily_interaction_median REAL,
  video_daily_thousand_like_note_ratio REAL,
  video_daily_hundred_like_note_ratio REAL,
  video_completion_rate REAL,
  cooperation_exposure_median REAL,
  cooperation_read_median REAL,
  cooperation_interaction_median REAL,
  overflow_store_median REAL,
  overflow_store_unit_price REAL,
  image_cpm REAL,
  image_read_unit_price REAL,
  image_interaction_unit_price REAL,
  video_cpm REAL,
  video_read_unit_price REAL,
  video_interaction_unit_price REAL,
  active_fans_ratio REAL,
  fans_growth_ratio REAL,
  read_fans_ratio REAL,
  interaction_fans_ratio REAL,
  order_fans_ratio REAL,
  reply_rate_48h REAL,
  active_days_7d REAL,
  video_quote_price REAL,
  live_30d_count REAL,
  live_avg_viewers REAL,
  live_avg_sales REAL,
  search_recommend_ratio REAL,
  fans_35_plus_ratio REAL,
  child_age TEXT,
  child_grade TEXT,
  child_gender TEXT,
  topic_point TEXT,
  cost_30d REAL,
  cost_90d REAL,
  audience_profile_screenshot TEXT,
  audience_age_distribution TEXT,
  audience_gender_distribution TEXT,
  change_summary TEXT DEFAULT '{}',
  collected_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS creator_scores (
  creator_id TEXT PRIMARY KEY,
  total_score REAL,
  base_score REAL,
  bonus_score REAL,
  information_completeness REAL,
  initial_tier TEXT,
  detail_collection_priority TEXT,
  budget_score REAL,
  fans_score REAL,
  cpe_score REAL,
  traffic_score REAL,
  persona_score REAL,
  content_score REAL,
  hard_filter_passed INTEGER,
  recommend_level TEXT,
  score_reason TEXT,
  cooperation_direction TEXT DEFAULT '',
  scored_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS screening_reviews (
  creator_id TEXT PRIMARY KEY,
  review_status TEXT,
  review_reason TEXT,
  reviewer TEXT,
  reviewed_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS project_creator_stage_logs (
  log_id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  creator_id TEXT NOT NULL,
  from_stage TEXT,
  to_stage TEXT NOT NULL,
  from_status TEXT,
  to_status TEXT NOT NULL,
  operator TEXT,
  reason TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS feishu_sync_state (
  project_id TEXT NOT NULL,
  creator_id TEXT NOT NULL,
  table_id TEXT NOT NULL,
  feishu_record_id TEXT,
  last_synced_at TEXT,
  sync_direction TEXT,
  sync_status TEXT,
  last_error TEXT,
  PRIMARY KEY(project_id, creator_id, table_id)
);

CREATE TABLE IF NOT EXISTS score_runs (
  run_id TEXT PRIMARY KEY,
  batch_id TEXT DEFAULT '',
  project_id TEXT NOT NULL,
  creator_id TEXT NOT NULL,
  trigger_source TEXT DEFAULT '',
  score_version TEXT DEFAULT 'youdao-v1',
  rule_score REAL,
  llm_score REAL,
  total_score REAL,
  llm_result TEXT DEFAULT '{}',
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS score_feedback (
  feedback_id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  creator_id TEXT NOT NULL,
  run_id TEXT,
  feedback TEXT,
  operator TEXT,
  created_at TEXT NOT NULL
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
  error_message TEXT,
  collection_plan TEXT DEFAULT '{}',
  applied_filters TEXT DEFAULT '[]',
  skipped_filters TEXT DEFAULT '[]',
  selected_metrics TEXT DEFAULT '[]',
  skipped_metrics TEXT DEFAULT '[]',
  detail_collection TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS scheme_count_memory (
  memory_id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  scheme_id TEXT NOT NULL,
  scheme_name TEXT,
  signature TEXT NOT NULL,
  filters TEXT DEFAULT '[]',
  expected_min INTEGER,
  expected_max INTEGER,
  expected_center INTEGER,
  predicted_source TEXT DEFAULT 'formula',
  actual_recommend_count INTEGER,
  actual_count_text TEXT DEFAULT '',
  actual_count_is_lower_bound INTEGER DEFAULT 0,
  evaluation_status TEXT DEFAULT '',
  collected_count INTEGER DEFAULT 0,
  accepted_count INTEGER DEFAULT 0,
  rejected_count INTEGER DEFAULT 0,
  created_at TEXT NOT NULL
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


METRIC_FIELDS = [
    "followers_count",
    "quote_price",
    "budget_status",
    "traffic_stability",
    "rate_limit_risk",
    "natural_cpc",
    "natural_cpe",
    "daily_exposure_median",
    "daily_read_median",
    "daily_interaction_median",
    "daily_thousand_like_note_ratio",
    "daily_hundred_like_note_ratio",
    "image_daily_exposure_median",
    "image_daily_read_median",
    "image_daily_interaction_median",
    "image_daily_thousand_like_note_ratio",
    "image_daily_hundred_like_note_ratio",
    "video_daily_exposure_median",
    "video_daily_read_median",
    "video_daily_interaction_median",
    "video_daily_thousand_like_note_ratio",
    "video_daily_hundred_like_note_ratio",
    "video_completion_rate",
    "cooperation_exposure_median",
    "cooperation_read_median",
    "cooperation_interaction_median",
    "overflow_store_median",
    "overflow_store_unit_price",
    "image_cpm",
    "image_read_unit_price",
    "image_interaction_unit_price",
    "video_cpm",
    "video_read_unit_price",
    "video_interaction_unit_price",
    "active_fans_ratio",
    "fans_growth_ratio",
    "read_fans_ratio",
    "interaction_fans_ratio",
    "order_fans_ratio",
    "reply_rate_48h",
    "active_days_7d",
    "video_quote_price",
    "liked_collected_count",
    "female_fans_ratio",
    "male_fans_ratio",
    "fans_under_18_ratio",
    "fans_18_24_ratio",
    "fans_25_34_ratio",
    "fans_35_44_ratio",
    "fans_44_plus_ratio",
    "live_30d_count",
    "live_avg_viewers",
    "live_avg_sales",
    "search_recommend_ratio",
    "fans_35_plus_ratio",
    "child_age",
    "child_grade",
    "child_gender",
    "topic_point",
    "cost_30d",
    "cost_90d",
    "audience_profile_screenshot",
    "audience_age_distribution",
    "audience_gender_distribution",
]

PROJECT_STATUSES = {"待补数据", "待审核", "已通过", "备选", "已驳回", "已写回飞书", "待建联", "合作中"}
POOL_STAGES = ["已合作跟进中", "合格达人待合作", "待建联达人", "观察暂缓"]


def is_test_project_id(project_id: str | None) -> bool:
    return bool(project_id and str(project_id).startswith("pytest_"))


def is_test_creator_id(creator_id: str | None) -> bool:
    text = str(creator_id or "")
    return text.startswith("pytest_") or text.startswith("GEN-")


def is_test_creator(creator: dict[str, Any]) -> bool:
    source = str(creator.get("source") or "")
    creator_id = str(creator.get("creator_id") or "")
    return source == "test_generated" or creator_id.startswith("GEN-")


def init_db() -> None:
    with connect() as conn:
        had_projects_table = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='projects'"
        ).fetchone()
        conn.executescript(SCHEMA)
        _ensure_column(conn, "projects", "screening_plan", "TEXT DEFAULT '{}'")
        _ensure_column(conn, "projects", "archived_at", "TEXT")
        for column, definition in {
            "source": "TEXT DEFAULT 'manual'",
            "raw_payload": "TEXT DEFAULT '{}'",
        }.items():
            _ensure_column(conn, "creators_global", column, definition)
        for column, definition in {
            "portfolio_role": "TEXT DEFAULT ''",
            "owner": "TEXT DEFAULT ''",
            "note": "TEXT DEFAULT ''",
            "tier": "TEXT",
        }.items():
            _ensure_column(conn, "project_creators", column, definition)
        _ensure_column(conn, "creator_scores", "cooperation_direction", "TEXT DEFAULT ''")
        for table in ["creator_metrics", "creator_metrics_current", "creator_metrics_history"]:
            for field in METRIC_FIELDS:
                if field in {"audience_profile_screenshot", "audience_age_distribution", "audience_gender_distribution"}:
                    definition = "TEXT"
                elif field in {"budget_status", "traffic_stability", "rate_limit_risk", "child_age", "child_grade", "child_gender", "topic_point"}:
                    definition = "TEXT"
                else:
                    definition = "REAL"
                _ensure_column(conn, table, field, definition)
        for column, definition in {
            "base_score": "REAL",
            "bonus_score": "REAL",
            "information_completeness": "REAL",
            "initial_tier": "TEXT",
            "detail_collection_priority": "TEXT",
        }.items():
            _ensure_column(conn, "creator_scores", column, definition)
        _ensure_column(conn, "score_runs", "batch_id", "TEXT DEFAULT ''")
        _ensure_column(conn, "score_runs", "trigger_source", "TEXT DEFAULT ''")
        for column, definition in {
            "collection_plan": "TEXT DEFAULT '{}'",
            "applied_filters": "TEXT DEFAULT '[]'",
            "skipped_filters": "TEXT DEFAULT '[]'",
            "selected_metrics": "TEXT DEFAULT '[]'",
            "skipped_metrics": "TEXT DEFAULT '[]'",
            "detail_collection": "TEXT DEFAULT ''",
        }.items():
            _ensure_column(conn, "collection_batches", column, definition)
        for column, definition in {
            "scheme_name": "TEXT",
            "predicted_source": "TEXT DEFAULT 'formula'",
            "actual_count_is_lower_bound": "INTEGER DEFAULT 0",
            "accepted_count": "INTEGER DEFAULT 0",
            "rejected_count": "INTEGER DEFAULT 0",
        }.items():
            _ensure_column(conn, "scheme_count_memory", column, definition)
        existing = conn.execute("SELECT project_id FROM projects WHERE project_id=?", (PROJECT_ID,)).fetchone()
        if not existing and not had_projects_table:
            ts = now()
            conn.execute(
                """
                INSERT INTO projects(project_id, project_name, target_qualified_creator_count, period_start, period_end, brief, screening_plan, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    PROJECT_ID,
                    PROJECT_NAME,
                    10,
                    "2026-05-07",
                    "2026-05-19",
                    "教育/亲子大孩/高知家庭达人，聚焦有道答疑笔5-6月合作。",
                    "{}",
                    ts,
                    ts,
                ),
            )
            log(conn, PROJECT_ID, "project", "创建项目", PROJECT_NAME, "系统", "初始化有道单项目", "success")
        migrate_legacy_creators(conn)


def get_project_writeback_settings(project_id: str) -> dict[str, Any]:
    init_db()
    with connect() as conn:
        ensure_project(conn, project_id)
        row = conn.execute(
            "SELECT auto_writeback_enabled, created_at, updated_at FROM project_writeback_settings WHERE project_id=?",
            (project_id,),
        ).fetchone()
        if not row:
            ts = now()
            conn.execute(
                """
                INSERT INTO project_writeback_settings(project_id, auto_writeback_enabled, created_at, updated_at)
                VALUES (?, 0, ?, ?)
                """,
                (project_id, ts, ts),
            )
            return {"project_id": project_id, "auto_writeback_enabled": False, "created_at": ts, "updated_at": ts}
        return {
            "project_id": project_id,
            "auto_writeback_enabled": bool(row["auto_writeback_enabled"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }


def save_project_writeback_settings(project_id: str, auto_writeback_enabled: bool) -> dict[str, Any]:
    init_db()
    ts = now()
    with connect() as conn:
        ensure_project(conn, project_id)
        conn.execute(
            """
            INSERT INTO project_writeback_settings(project_id, auto_writeback_enabled, created_at, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(project_id) DO UPDATE SET auto_writeback_enabled=excluded.auto_writeback_enabled,
            updated_at=excluded.updated_at
            """,
            (project_id, 1 if auto_writeback_enabled else 0, ts, ts),
        )
        log(
            conn,
            project_id,
            "feishu",
            "更新写回设置",
            PROJECT_NAME,
            "系统",
            "已开启合格达人详情补采后自动写回" if auto_writeback_enabled else "已关闭自动写回，改为手动批量写回",
            "success",
        )
    return get_project_writeback_settings(project_id)


def migrate_legacy_creators(conn: sqlite3.Connection) -> None:
    ts = now()
    rows = conn.execute(
        """
        SELECT c.*, m.*, s.total_score, s.recommend_level
        FROM creators c
        LEFT JOIN creator_metrics m ON c.creator_id=m.creator_id
        LEFT JOIN creator_scores s ON c.creator_id=s.creator_id
        """
    ).fetchall()
    for row in rows:
        creator_id = row["creator_id"]
        conn.execute(
            """
            INSERT INTO creators_global(creator_id, source, pgy_url, xiaohongshu_id, pgy_blogger_id, nickname,
            creator_type, persona_tags, ip_city, profile_url, avatar_url, raw_payload, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(creator_id) DO UPDATE SET source=excluded.source, pgy_url=excluded.pgy_url,
            xiaohongshu_id=excluded.xiaohongshu_id, pgy_blogger_id=excluded.pgy_blogger_id,
            nickname=excluded.nickname, creator_type=excluded.creator_type, persona_tags=excluded.persona_tags,
            ip_city=excluded.ip_city, profile_url=excluded.profile_url, avatar_url=excluded.avatar_url,
            raw_payload=excluded.raw_payload, updated_at=excluded.updated_at
            """,
            (
                creator_id,
                row["source"],
                row["pgy_url"],
                row["xiaohongshu_id"],
                row["pgy_blogger_id"],
                row["nickname"],
                row["creator_type"],
                row["persona_tags"],
                row["ip_city"],
                row["profile_url"],
                row["avatar_url"],
                row["raw_payload"],
                row["created_at"] or ts,
                row["updated_at"] or ts,
            ),
        )
        pool_stage = stage_from_status(row["status"], row["total_score"])
        conn.execute(
            """
            INSERT INTO project_creators(project_id, creator_id, pool_stage, review_status, total_score, tier, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(project_id, creator_id) DO UPDATE SET pool_stage=excluded.pool_stage,
            review_status=excluded.review_status, total_score=excluded.total_score, tier=excluded.tier,
            updated_at=excluded.updated_at
            """,
            (
                row["project_id"],
                creator_id,
                pool_stage,
                row["status"] or "待补数据",
                row["total_score"],
                tier_from_score(row["total_score"]),
                row["created_at"] or ts,
                row["updated_at"] or ts,
            ),
        )
        if row["collected_at"]:
            values = [row[field] if field in row.keys() else None for field in METRIC_FIELDS]
            conn.execute(
                f"""
                INSERT INTO creator_metrics_current(creator_id, {', '.join(METRIC_FIELDS)}, collected_at)
                VALUES ({', '.join(['?'] * (len(METRIC_FIELDS) + 2))})
                ON CONFLICT(creator_id) DO UPDATE SET {', '.join(f'{field}=excluded.{field}' for field in METRIC_FIELDS)},
                collected_at=excluded.collected_at
                """,
                [creator_id, *values, row["collected_at"]],
            )


def ensure_project(conn: sqlite3.Connection, project_id: str) -> None:
    existing = conn.execute("SELECT project_id FROM projects WHERE project_id=?", (project_id,)).fetchone()
    if existing:
        return
    ts = now()
    conn.execute(
        """
        INSERT INTO projects(project_id, project_name, target_qualified_creator_count, period_start, period_end, brief, screening_plan, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (project_id, project_id, 10, "2026-05-07", "2026-05-19", "", "{}", ts, ts),
    )


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
    original = str(value).strip()
    text = original
    if not text or text in {"待填", "待核", "待评估", "-", "--"}:
        return None
    match = re.search(r"-?\d[\d,，]*(?:\.\d+)?\s*(?:万|w|W)?", text)
    if not match:
        return None
    token = match.group(0).strip()
    multiplier = 10000 if re.search(r"(?:万|w)\s*$", token, flags=re.I) else 1
    text = re.sub(r"[^\d.\-]", "", token.replace(",", "").replace("，", ""))
    try:
        return float(text) * multiplier
    except ValueError:
        return None


def ratio(value: Any) -> float | None:
    number = parse_number(value)
    if number is None:
        return None
    return number / 100 if number > 1 else number


def _number_matches(value: Any) -> list[tuple[float, str]]:
    if value is None:
        return []
    text = str(value).strip()
    if not text or text in {"待填", "待核", "待评估", "-"}:
        return []
    matches: list[tuple[float, str]] = []
    for match in re.finditer(r"[¥￥]?\s*-?\d[\d,]*(?:\.\d+)?\s*(?:万|w|W|%|元)?", text):
        token = match.group(0).strip()
        number_match = re.search(r"-?\d[\d,]*(?:\.\d+)?", token)
        if not number_match:
            continue
        number = float(number_match.group(0).replace(",", ""))
        if re.search(r"(万|w)\b|万", token, flags=re.I):
            number *= 10000
        matches.append((number, token))
    return matches


def _range_upper_from_text(value: Any) -> float | None:
    text = str(value or "")
    number_token = r"[¥￥]?\s*-?\d[\d,]*(?:\.\d+)?\s*(?:万|w|W|%|元)?"
    range_pattern = re.compile(
        rf"({number_token})\s*(?:~|～|—|–|-|至|到)\s*({number_token})",
        flags=re.I,
    )
    for match in range_pattern.finditer(text):
        numbers = [number for number, _ in _number_matches(match.group(0))]
        if len(numbers) >= 2:
            return max(numbers[:2])
    return None


def _threshold_from_text(value: Any, metric: str, default: float | None = None) -> float | None:
    matches = _number_matches(value)
    if not matches:
        return default
    text = str(value or "").lower()
    if metric in {"ratio", "fans35", "search"}:
        percent_matches = [number for number, token in matches if "%" in token]
        if percent_matches:
            return percent_matches[-1] / 100 if percent_matches[-1] > 1 else percent_matches[-1]
        plausible = [number for number, _ in matches if 0 <= number <= 100]
        if plausible:
            return plausible[-1] / 100 if plausible[-1] > 1 else plausible[-1]
    if metric == "quote":
        range_upper = _range_upper_from_text(value)
        if range_upper is not None:
            return range_upper
        money = [number for number, token in matches if any(mark in token for mark in ["¥", "￥", "元", "万", "w", "W"])]
        if money:
            return money[0]
        if "单个" in text or "达人" in text:
            return matches[0][0]
    if metric == "cpc":
        cpc_match = re.search(r"cpc[^\d]*(\d+(?:\.\d+)?)", text, flags=re.I)
        if cpc_match:
            return float(cpc_match.group(1))
        range_upper = _range_upper_from_text(value)
        if range_upper is not None:
            return range_upper
    if metric == "cpe":
        cpe_match = re.search(r"cpe[^\d]*(\d+(?:\.\d+)?)", text, flags=re.I)
        if cpe_match:
            return float(cpe_match.group(1))
        range_upper = _range_upper_from_text(value)
        if range_upper is not None:
            return range_upper
    return matches[0][0] if matches else default


def _split_rule_values(value: Any) -> list[str]:
    text = str(value or "").strip()
    if not text:
        return []
    text = re.sub(r"\b(?:或|或者|and|or)\b", "、", text, flags=re.I)
    parts = re.split(r"[、,，;；/｜|]+|\s+或\s+|\s+及\s+", text)
    return [part.strip() for part in parts if part.strip()]


def _expand_rule_values(values: list[str]) -> list[str]:
    expanded: list[str] = []
    for value in values:
        if value not in expanded:
            expanded.append(value)
        aliases = {
            "初中": ["初一", "初二", "初三", "七年级", "八年级", "九年级"],
            "高中": ["高一", "高二", "高三"],
            "小升初": ["六年级", "升初中", "初一"],
            "大孩": ["小升初", "初中", "高中", "初一", "初二", "初三", "高一", "高二", "高三"],
        }.get(value, [])
        for alias in aliases:
            if alias not in expanded:
                expanded.append(alias)
    return expanded


def _first_metric(payload: dict[str, Any], *names: str) -> Any:
    for name in names:
        value = payload.get(name)
        if value not in (None, ""):
            return value
    return None


def _json_metric(value: Any, default: Any) -> str:
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return json.dumps(default, ensure_ascii=False)
        try:
            json.loads(stripped)
            return stripped
        except json.JSONDecodeError:
            return json.dumps(default, ensure_ascii=False)
    if value in (None, ""):
        return json.dumps(default, ensure_ascii=False)
    return json.dumps(value, ensure_ascii=False)


def _audience_distribution_payload(payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    raw = payload.get("raw_payload") if isinstance(payload.get("raw_payload"), dict) else {}
    chart = raw.get("audience_profile_chart_metrics") if isinstance(raw.get("audience_profile_chart_metrics"), dict) else {}
    chart_metrics = chart.get("metrics") if isinstance(chart.get("metrics"), dict) else {}
    chart_sources = chart.get("sources") if isinstance(chart.get("sources"), list) else []

    def existing_distribution(name: str) -> dict[str, Any]:
        value = payload.get(name)
        if isinstance(value, dict):
            return value
        if isinstance(value, str) and value.strip():
            try:
                parsed = json.loads(value)
            except json.JSONDecodeError:
                return {}
            return parsed if isinstance(parsed, dict) else {}
        return {}

    existing_age = existing_distribution("audience_age_distribution")
    existing_gender = existing_distribution("audience_gender_distribution")
    existing_segments = []
    for distribution in (existing_age, existing_gender):
        segments = distribution.get("segments") if isinstance(distribution.get("segments"), list) else []
        existing_segments.extend(item for item in segments if isinstance(item, dict))

    def metric_value(key: str, *aliases: str) -> Any:
        for item in existing_segments:
            if item.get("key") == key or item.get("label") in aliases or item.get("label") == key:
                value = item.get("ratio")
                if value not in (None, ""):
                    return value
        for source in (payload, chart_metrics):
            for name in (key, *aliases):
                value = source.get(name) if isinstance(source, dict) else None
                if value not in (None, ""):
                    return value
        return None

    age_segments = [
        ("<18", "fans_under_18_ratio", ("粉丝年龄18岁以下占比", "<18占比")),
        ("18-24", "fans_18_24_ratio", ("粉丝年龄18-24占比", "18-24占比")),
        ("25-34", "fans_25_34_ratio", ("粉丝年龄25-34占比", "25-34占比")),
        ("35-44", "fans_35_44_ratio", ("粉丝年龄35-44占比", "35-44占比")),
        (">44", "fans_44_plus_ratio", ("粉丝年龄44岁以上占比", "44岁以上占比", ">44占比")),
    ]
    age_distribution = {
        "segments": [
            {"label": label, "key": key, "ratio": ratio(metric_value(key, *aliases))}
            for label, key, aliases in age_segments
            if ratio(metric_value(key, *aliases)) is not None
        ],
        "dominant": payload.get("audience_age_dominant") or chart_metrics.get("audience_age_dominant") or existing_age.get("dominant") or "",
        "source": existing_age.get("source") or chart.get("source") or ("normalized_fields" if payload else ""),
        "sources": [item for item in chart_sources if isinstance(item, dict) and str(item.get("key") or "").startswith("fans_")],
    }
    gender_segments = [
        ("女性", "female_fans_ratio", ("粉丝女性用户占比", "女性粉丝占比")),
        ("男性", "male_fans_ratio", ("粉丝男性用户占比", "男性粉丝占比")),
    ]
    gender_distribution = {
        "segments": [
            {"label": label, "key": key, "ratio": ratio(metric_value(key, *aliases))}
            for label, key, aliases in gender_segments
            if ratio(metric_value(key, *aliases)) is not None
        ],
        "dominant": payload.get("audience_gender_dominant") or chart_metrics.get("audience_gender_dominant") or existing_gender.get("dominant") or "",
        "source": existing_gender.get("source") or chart.get("source") or ("normalized_fields" if payload else ""),
        "sources": [item for item in chart_sources if isinstance(item, dict) and str(item.get("key") or "") in {"female_fans_ratio", "male_fans_ratio"}],
    }
    return age_distribution, gender_distribution


def normalize_creator(payload: dict[str, Any], project_id: str) -> dict[str, Any]:
    age_distribution, gender_distribution = _audience_distribution_payload(payload)
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
        "daily_exposure_median": parse_number(_first_metric(payload, "daily_exposure_median", "曝光中位数（日常）", "日常曝光中位数")),
        "daily_read_median": parse_number(_first_metric(payload, "daily_read_median", "阅读中位数（日常）", "日常阅读中位数")),
        "daily_interaction_median": parse_number(_first_metric(payload, "daily_interaction_median", "互动中位数（日常）", "日常互动中位数")),
        "daily_thousand_like_note_ratio": ratio(_first_metric(payload, "daily_thousand_like_note_ratio", "千赞笔记比例", "千赞笔记比例（日常）")),
        "daily_hundred_like_note_ratio": ratio(_first_metric(payload, "daily_hundred_like_note_ratio", "百赞笔记比例", "百赞笔记比例（日常）")),
        "image_daily_exposure_median": parse_number(_first_metric(payload, "image_daily_exposure_median", "图文曝光中位数（日常）")),
        "image_daily_read_median": parse_number(_first_metric(payload, "image_daily_read_median", "图文阅读中位数（日常）")),
        "image_daily_interaction_median": parse_number(_first_metric(payload, "image_daily_interaction_median", "图文互动中位数（日常）")),
        "image_daily_thousand_like_note_ratio": ratio(_first_metric(payload, "image_daily_thousand_like_note_ratio", "图文千赞笔记比例")),
        "image_daily_hundred_like_note_ratio": ratio(_first_metric(payload, "image_daily_hundred_like_note_ratio", "图文百赞笔记比例")),
        "video_daily_exposure_median": parse_number(_first_metric(payload, "video_daily_exposure_median", "视频曝光中位数（日常）")),
        "video_daily_read_median": parse_number(_first_metric(payload, "video_daily_read_median", "视频阅读中位数（日常）")),
        "video_daily_interaction_median": parse_number(_first_metric(payload, "video_daily_interaction_median", "视频互动中位数（日常）")),
        "video_daily_thousand_like_note_ratio": ratio(_first_metric(payload, "video_daily_thousand_like_note_ratio", "视频千赞笔记比例")),
        "video_daily_hundred_like_note_ratio": ratio(_first_metric(payload, "video_daily_hundred_like_note_ratio", "视频百赞笔记比例")),
        "video_completion_rate": ratio(_first_metric(payload, "video_completion_rate", "视频完播率")),
        "cooperation_exposure_median": parse_number(_first_metric(payload, "cooperation_exposure_median", "曝光中位数（合作）", "合作曝光中位数")),
        "cooperation_read_median": parse_number(_first_metric(payload, "cooperation_read_median", "阅读中位数（合作）", "合作阅读中位数")),
        "cooperation_interaction_median": parse_number(_first_metric(payload, "cooperation_interaction_median", "互动中位数（合作）", "合作互动中位数")),
        "overflow_store_median": parse_number(_first_metric(payload, "overflow_store_median", "外溢进店中位数")),
        "overflow_store_unit_price": parse_number(_first_metric(payload, "overflow_store_unit_price", "外溢进店单价")),
        "image_cpm": parse_number(_first_metric(payload, "image_cpm", "图文预估CPM价格", "预估图文CPM")),
        "image_read_unit_price": parse_number(_first_metric(payload, "image_read_unit_price", "图文预估阅读单价", "图文笔记阅读单价")),
        "image_interaction_unit_price": parse_number(_first_metric(payload, "image_interaction_unit_price", "图文预估互动单价", "图文笔记互动单价")),
        "video_cpm": parse_number(_first_metric(payload, "video_cpm", "视频预估CPM价格", "预估视频CPM")),
        "video_read_unit_price": parse_number(_first_metric(payload, "video_read_unit_price", "视频预估阅读单价", "视频笔记阅读单价")),
        "video_interaction_unit_price": parse_number(_first_metric(payload, "video_interaction_unit_price", "视频预估互动单价", "视频笔记互动单价")),
        "active_fans_ratio": ratio(_first_metric(payload, "active_fans_ratio", "活跃粉丝占比")),
        "fans_growth_ratio": ratio(_first_metric(payload, "fans_growth_ratio", "粉丝量变化幅度")),
        "read_fans_ratio": ratio(_first_metric(payload, "read_fans_ratio", "阅读粉丝占比")),
        "interaction_fans_ratio": ratio(_first_metric(payload, "interaction_fans_ratio", "互动粉丝占比")),
        "order_fans_ratio": ratio(_first_metric(payload, "order_fans_ratio", "下单粉丝占比")),
        "reply_rate_48h": ratio(_first_metric(payload, "reply_rate_48h", "邀约48h回复率", "邀约48小时回复率")),
        "active_days_7d": parse_number(_first_metric(payload, "active_days_7d", "近7天活跃天数")),
        "video_quote_price": parse_number(_first_metric(payload, "video_quote_price", "视频报价", "视频笔记一口价")),
        "liked_collected_count": parse_number(_first_metric(payload, "liked_collected_count", "获赞与收藏", "赞藏数", "赞藏量")),
        "female_fans_ratio": ratio(_first_metric(payload, "female_fans_ratio", "粉丝女性用户占比", "女性粉丝占比")) or next((item["ratio"] for item in gender_distribution["segments"] if item["key"] == "female_fans_ratio"), None),
        "male_fans_ratio": ratio(_first_metric(payload, "male_fans_ratio", "粉丝男性用户占比", "男性粉丝占比")) or next((item["ratio"] for item in gender_distribution["segments"] if item["key"] == "male_fans_ratio"), None),
        "fans_under_18_ratio": ratio(_first_metric(payload, "fans_under_18_ratio", "粉丝年龄18岁以下占比", "<18占比")) or next((item["ratio"] for item in age_distribution["segments"] if item["key"] == "fans_under_18_ratio"), None),
        "fans_18_24_ratio": ratio(_first_metric(payload, "fans_18_24_ratio", "粉丝年龄18-24占比", "18-24占比")) or next((item["ratio"] for item in age_distribution["segments"] if item["key"] == "fans_18_24_ratio"), None),
        "fans_25_34_ratio": ratio(_first_metric(payload, "fans_25_34_ratio", "粉丝年龄25-34占比", "25-34占比")) or next((item["ratio"] for item in age_distribution["segments"] if item["key"] == "fans_25_34_ratio"), None),
        "fans_35_44_ratio": ratio(_first_metric(payload, "fans_35_44_ratio", "粉丝年龄35-44占比", "35-44占比")) or next((item["ratio"] for item in age_distribution["segments"] if item["key"] == "fans_35_44_ratio"), None),
        "fans_44_plus_ratio": ratio(_first_metric(payload, "fans_44_plus_ratio", "粉丝年龄44岁以上占比", "44岁以上占比", ">44占比")) or next((item["ratio"] for item in age_distribution["segments"] if item["key"] == "fans_44_plus_ratio"), None),
        "live_30d_count": parse_number(_first_metric(payload, "live_30d_count", "近30天直播场次")),
        "live_avg_viewers": parse_number(_first_metric(payload, "live_avg_viewers", "场均观看人数", "场均观播人数")),
        "live_avg_sales": parse_number(_first_metric(payload, "live_avg_sales", "场均销售额")),
        "search_recommend_ratio": ratio(payload.get("search_recommend_ratio") or payload.get("搜索+推荐占比")),
        "fans_35_plus_ratio": ratio(payload.get("fans_35_plus_ratio") or payload.get("35岁以上粉丝占比") or payload.get("粉丝年龄34岁以上占比")),
        "child_age": payload.get("child_age") or payload.get("孩子年龄") or "",
        "child_grade": payload.get("child_grade") or payload.get("孩子年级") or "",
        "child_gender": payload.get("child_gender") or payload.get("孩子性别") or "",
        "topic_point": payload.get("topic_point") or payload.get("家庭/教育话题点") or "",
        "cost_30d": parse_number(payload.get("cost_30d") or payload.get("30天外溢进店成本")),
        "cost_90d": parse_number(payload.get("cost_90d") or payload.get("90天外溢进店成本")),
        "audience_profile_screenshot": payload.get("audience_profile_screenshot") or payload.get("粉丝画像截图") or "",
        "audience_age_distribution": _json_metric(payload.get("audience_age_distribution") or age_distribution, {"segments": []}),
        "audience_gender_distribution": _json_metric(payload.get("audience_gender_distribution") or gender_distribution, {"segments": []}),
    }


def tier_from_score(score: Any) -> str:
    number = parse_number(score) or 0
    if number >= 100:
        return "S"
    if number >= 90:
        return "A"
    if number >= 80:
        return "B+"
    if number >= 70:
        return "B"
    return "C"


def stage_from_status(status: str | None, score: Any = None) -> str:
    if status in {"已驳回", "默认淘汰"}:
        return "观察暂缓"
    if status in {"已写回飞书", "合作中"}:
        return "已合作跟进中"
    if status in {"已通过", "备选"}:
        return "合格达人待合作"
    number = parse_number(score) or 0
    if number >= 70:
        return "待建联达人"
    return "观察暂缓" if number and number < 70 else "待建联达人"


def status_from_stage(stage: str) -> str:
    return {
        "已合作跟进中": "合作中",
        "合格达人待合作": "已通过",
        "待建联达人": "待审核",
        "观察暂缓": "已驳回",
    }.get(stage, "待审核")


def metric_payload(creator: dict[str, Any]) -> dict[str, Any]:
    return {field: creator.get(field) for field in METRIC_FIELDS}


def summarize_metric_change(previous: dict[str, Any] | None, current: dict[str, Any]) -> dict[str, Any]:
    if not previous:
        return {"type": "initial", "changes": []}
    labels = {
        "followers_count": "粉丝数",
        "quote_price": "报价",
        "natural_cpc": "自然CPC",
        "natural_cpe": "自然CPE",
        "daily_read_median": "日常阅读中位数",
        "daily_interaction_median": "日常互动中位数",
        "cooperation_read_median": "合作阅读中位数",
        "cooperation_interaction_median": "合作互动中位数",
        "overflow_store_unit_price": "外溢进店单价",
        "image_read_unit_price": "图文阅读单价",
        "image_interaction_unit_price": "图文互动单价",
        "video_read_unit_price": "视频阅读单价",
        "video_interaction_unit_price": "视频互动单价",
        "reply_rate_48h": "邀约48h回复率",
        "search_recommend_ratio": "搜索+推荐占比",
        "fans_35_plus_ratio": "35岁以上粉丝占比",
        "cost_30d": "30天外溢进店成本",
        "cost_90d": "90天外溢进店成本",
    }
    changes = []
    for field, label in labels.items():
        old = previous.get(field)
        new = current.get(field)
        if old is None or new is None:
            continue
        try:
            delta = round(float(new) - float(old), 4)
        except (TypeError, ValueError):
            continue
        if delta:
            changes.append({"field": field, "label": label, "from": old, "to": new, "delta": delta})
    return {"type": "update", "changes": changes}


def find_existing(conn: sqlite3.Connection, creator: dict[str, Any]) -> str | None:
    project_is_test = is_test_project_id(creator.get("project_id"))

    def usable_existing_id(candidate_id: str | None) -> str | None:
        if not candidate_id:
            return None
        if not project_is_test and is_test_creator_id(candidate_id):
            return None
        return candidate_id

    checks = [
        ("xiaohongshu_id", creator.get("xiaohongshu_id")),
        ("pgy_blogger_id", creator.get("pgy_blogger_id")),
    ]
    pgy_url = creator.get("pgy_url")
    if pgy_url and "/solar/pre-trade/note/kol" not in pgy_url:
        checks.append(("pgy_url", pgy_url))
    for field, value in checks:
        if value:
            row = conn.execute(
                f"SELECT creator_id FROM creators_global WHERE {field}=?",
                (value,),
            ).fetchone()
            if row:
                existing_id = usable_existing_id(row["creator_id"])
                if existing_id:
                    return existing_id
            row = conn.execute(
                f"SELECT creator_id FROM creators WHERE project_id=? AND {field}=?",
                (creator["project_id"], value),
            ).fetchone()
            if row:
                existing_id = usable_existing_id(row["creator_id"])
                if existing_id:
                    return existing_id
    creator_id = creator.get("creator_id")
    if creator_id:
        row = conn.execute(
            "SELECT creator_id FROM creators_global WHERE creator_id=?",
            (creator_id,),
        ).fetchone()
        if row:
            existing_id = usable_existing_id(row["creator_id"])
            if existing_id:
                return existing_id
        row = conn.execute(
            "SELECT creator_id FROM creators WHERE project_id=? AND creator_id=?",
            (creator["project_id"], creator_id),
        ).fetchone()
        if row:
            existing_id = usable_existing_id(row["creator_id"])
            if existing_id:
                return existing_id
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
            existing_id = usable_existing_id(row["creator_id"])
            if existing_id:
                return existing_id
    return None


def upsert_creator(project_id: str, payload: dict[str, Any], score: bool = True) -> dict[str, Any]:
    init_db()
    creator = normalize_creator(payload, project_id)
    ts = now()
    with connect() as conn:
        ensure_project(conn, project_id)
        existing_id = find_existing(conn, creator)
        creator_id = existing_id or creator["creator_id"]
        project_row = conn.execute(
            "SELECT review_status, pool_stage FROM project_creators WHERE project_id=? AND creator_id=?",
            (project_id, creator_id),
        ).fetchone()
        review = conn.execute("SELECT review_status FROM screening_reviews WHERE creator_id=?", (creator_id,)).fetchone()
        current = conn.execute("SELECT status FROM creators WHERE project_id=? AND creator_id=?", (project_id, creator_id)).fetchone()
        status = project_row["review_status"] if project_row else (current["status"] if review and current else creator["status"])
        existing_legacy = conn.execute("SELECT creator_id FROM creators WHERE creator_id=?", (creator_id,)).fetchone()
        if existing_legacy:
            conn.execute(
                """
                UPDATE creators SET source=?, xiaohongshu_id=?, pgy_blogger_id=?, pgy_url=?, nickname=?,
                creator_type=?, persona_tags=?, ip_city=?, profile_url=?, avatar_url=?, status=?, raw_payload=?, project_id=?, updated_at=?
                WHERE creator_id=?
                """,
                (
                    creator["source"], creator["xiaohongshu_id"], creator["pgy_blogger_id"], creator["pgy_url"],
                    creator["nickname"], creator["creator_type"], creator["persona_tags"], creator["ip_city"],
                    creator["profile_url"], creator["avatar_url"], status, creator["raw_payload"], project_id, ts, creator_id,
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
            INSERT INTO creators_global(creator_id, source, pgy_url, xiaohongshu_id, pgy_blogger_id, nickname,
            creator_type, persona_tags, ip_city, profile_url, avatar_url, raw_payload, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(creator_id) DO UPDATE SET source=excluded.source, pgy_url=excluded.pgy_url,
            xiaohongshu_id=excluded.xiaohongshu_id, pgy_blogger_id=excluded.pgy_blogger_id,
            nickname=excluded.nickname, creator_type=excluded.creator_type, persona_tags=excluded.persona_tags,
            ip_city=excluded.ip_city, profile_url=excluded.profile_url, avatar_url=excluded.avatar_url,
            raw_payload=excluded.raw_payload, updated_at=excluded.updated_at
            """,
            (
                creator_id,
                creator["source"],
                creator["pgy_url"],
                creator["xiaohongshu_id"],
                creator["pgy_blogger_id"],
                creator["nickname"],
                creator["creator_type"],
                creator["persona_tags"],
                creator["ip_city"],
                creator["profile_url"],
                creator["avatar_url"],
                creator["raw_payload"],
                ts,
                ts,
            ),
        )
        pool_stage = project_row["pool_stage"] if project_row else stage_from_status(status)
        conn.execute(
            """
            INSERT INTO project_creators(project_id, creator_id, pool_stage, review_status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(project_id, creator_id) DO UPDATE SET review_status=excluded.review_status,
            pool_stage=excluded.pool_stage, updated_at=excluded.updated_at
            """,
            (project_id, creator_id, pool_stage, status, ts, ts),
        )
        conn.execute(
            f"""
            INSERT INTO creator_metrics(creator_id, {', '.join(METRIC_FIELDS)}, collected_at)
            VALUES ({', '.join(['?'] * (len(METRIC_FIELDS) + 2))})
            ON CONFLICT(creator_id) DO UPDATE SET {', '.join(f'{field}=excluded.{field}' for field in METRIC_FIELDS)},
            collected_at=excluded.collected_at
            """,
            [creator_id, *[creator[field] for field in METRIC_FIELDS], ts],
        )
        previous = row_dict(conn.execute("SELECT * FROM creator_metrics_current WHERE creator_id=?", (creator_id,)).fetchone())
        current_metrics = metric_payload(creator)
        conn.execute(
            f"""
            INSERT INTO creator_metrics_current(creator_id, {', '.join(METRIC_FIELDS)}, collected_at)
            VALUES ({', '.join(['?'] * (len(METRIC_FIELDS) + 2))})
            ON CONFLICT(creator_id) DO UPDATE SET {', '.join(f'{field}=excluded.{field}' for field in METRIC_FIELDS)},
            collected_at=excluded.collected_at
            """,
            [creator_id, *[current_metrics[field] for field in METRIC_FIELDS], ts],
        )
        conn.execute(
            f"""
            INSERT INTO creator_metrics_history(snapshot_id, project_id, creator_id, {', '.join(METRIC_FIELDS)}, change_summary, collected_at)
            VALUES ({', '.join(['?'] * (len(METRIC_FIELDS) + 5))})
            """,
            [
                str(uuid.uuid4()),
                project_id,
                creator_id,
                *[current_metrics[field] for field in METRIC_FIELDS],
                json.dumps(summarize_metric_change(previous, current_metrics), ensure_ascii=False),
                ts,
            ],
        )
        log(conn, project_id, "creator", action, creator.get("nickname") or creator_id, "系统", "达人池已去重入库", "success")
    if score:
        score_creator(project_id, creator_id)
    return get_creator(project_id, creator_id) or {}


def import_csv(project_id: str, path: Path | None = None) -> dict[str, Any]:
    init_db()
    csv_path = path or ROOT / "有道答疑笔5-6月合作_测试项目" / "03_达人池实体表.csv"
    count = 0
    creator_ids = []
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            creator = upsert_creator(project_id, row, score=False)
            creator_ids.append(creator["creator_id"])
            count += 1
    with connect() as conn:
        log(conn, project_id, "import", "导入达人模板", csv_path.name, "系统", f"导入 {count} 条达人记录", "success")
    scoring = score_project(project_id, creator_ids=creator_ids, trigger_source="import")
    return {"imported": count, "scoring": scoring}


def generate_test_creators(project_id: str, desired_count: int | None = None) -> dict[str, Any]:
    project = get_project(project_id) or {}
    target = int(project.get("target_qualified_creator_count") or 10)
    desired = desired_count or max(target * 3, 24)
    existing = list_creators(project_id)
    if len(existing) >= desired:
        return {"generated": 0, "total": len(existing)}

    templates = [
        ("北京升学答疑赵老师", "教育垂类/卖货型", "教师人设/升学规划/初中学习", "北京", 12800, 132000, 1.38, 8.4, 0.62, 0.66, "小升初", "未披露", "升学规划、错题答疑和学习工具推荐"),
        ("上海精英妈妈Lisa", "曝光型", "高知家庭/中产家庭/亲子大孩", "上海", 17600, 215000, 1.72, 11.2, 0.54, 0.59, "初一", "女", "国际学校转轨、家庭学习陪伴和答疑场景"),
        ("海淀初中陪跑爸爸", "曝光型", "普通有娃家庭/初高中学习陪伴", "北京", 9800, 88000, 1.61, 9.6, 0.51, 0.52, "初三", "男", "中考冲刺、家长陪跑和即时答疑需求"),
        ("沪上物理陈老师", "教育垂类/卖货型", "教师人设/高知教育达人", "上海", 14200, 156000, 1.44, 8.9, 0.58, 0.63, "高一", "未披露", "理科学习方法、题目讲解和答疑工具"),
        ("北京胡同陪读妈妈", "曝光型", "普通有娃家庭/话题型亲子", "北京", 11800, 103000, 1.83, 12.8, 0.49, 0.57, "小升初", "女", "胡同家庭、小升初焦虑和学习效率"),
        ("上海住校生日常", "曝光型", "中产家庭/住校生家庭", "上海", 9600, 79000, 1.94, 15.1, 0.45, 0.48, "高一", "男", "住校生周末复盘、自主学习和答疑"),
        ("教辅测评林小北", "教育垂类/卖货型", "学习用品测评/教育卖货型", "其他", 7600, 64000, 1.29, 7.6, 0.64, 0.44, "初二", "女", "教辅工具横评、学习用品转化复盘"),
        ("博士妈妈讲学习", "教育垂类/卖货型", "高知家庭/博士父母/教育达人", "北京", 18800, 245000, 1.68, 10.7, 0.57, 0.68, "高二", "男", "理工科家庭、学习规划和答疑工具深度种草"),
        ("上海中考政策观察", "教育垂类/卖货型", "教育政策解读/高知教育达人", "上海", 16900, 174000, 1.55, 9.9, 0.6, 0.65, "初三", "未披露", "中考政策、升学路径和家长决策"),
        ("北京国际校转轨记", "曝光型", "国际学校/中产家庭/亲子大孩", "北京", 19600, 198000, 1.91, 13.9, 0.47, 0.54, "初一", "女", "国际学校转轨、公立衔接和课后答疑"),
        ("高中数学陪练王老师", "教育垂类/卖货型", "教师人设/高中学习陪伴", "其他", 10500, 92000, 1.47, 8.2, 0.56, 0.5, "高二", "未披露", "高中数学错题、刷题节奏和答疑效率"),
        ("沪漂学区房妈妈", "曝光型", "普通有娃家庭/学区房话题", "上海", 13800, 121000, 1.86, 14.1, 0.46, 0.51, "小升初", "女", "学区房蜗居、家庭教育投入和学习工具"),
        ("初高中英语Grace", "教育垂类/卖货型", "教师人设/英语学习/教育达人", "北京", 12400, 111000, 1.5, 8.8, 0.59, 0.56, "初二", "未披露", "英语学习方法、错题整理和课后答疑"),
        ("陪读家庭研究所", "曝光型", "高知家庭/亲子大孩/中产家庭", "上海", 15800, 137000, 1.77, 12.4, 0.52, 0.58, "高一", "男", "陪读家庭样本、学习效率和工具选择"),
    ]
    existing_ids = {item["creator_id"] for item in existing}
    generated = 0
    existing_numbers = [
        int(match.group(1))
        for item in existing
        for match in [re.search(r"-(\d+)$", str(item.get("creator_id") or ""))]
        if match
    ]
    index = max(existing_numbers, default=0) + 1
    while len(existing) + generated < desired:
        tpl = templates[(index - 1) % len(templates)]
        cycle = (index - 1) // len(templates)
        creator_id = f"GEN-{project_id}-{index:03d}"
        if creator_id in existing_ids:
            index += 1
            continue
        row = {
            "达人ID": creator_id,
            "达人昵称": tpl[0] if cycle == 0 else f"{tpl[0]}{cycle + 1}",
            "蒲公英链接": f"https://pgy.xiaohongshu.com/solar/pre-trade/blogger-detail/{creator_id}",
            "达人类型": tpl[1],
            "人设标签": tpl[2],
            "IP城市": tpl[3],
            "报价": min(19800, tpl[4] + cycle * 300),
            "预算状态": "通过",
            "粉丝数": tpl[5] + cycle * 3500,
            "近30天流量稳定性": "稳定" if index % 6 else "波动",
            "限流风险判断": "低" if index % 7 else "中",
            "合作笔记自然CPC": round(tpl[6] + cycle * 0.03, 2),
            "合作笔记自然CPE": round(tpl[7] + cycle * 0.4, 2),
            "搜索+推荐占比": tpl[8],
            "35岁以上粉丝占比": tpl[9],
            "孩子年龄": "",
            "孩子年级": tpl[10],
            "孩子性别": tpl[11],
            "家庭/教育话题点": tpl[12],
            "30天外溢进店成本": 28 + (index % 6) * 4,
            "90天外溢进店成本": 24 + (index % 6) * 4,
            "当前状态": "待补数据",
            "source": "test_generated",
        }
        upsert_creator(project_id, row, score=False)
        generated += 1
        index += 1
    with connect() as conn:
        log(conn, project_id, "creator", "生成测试达人", PROJECT_NAME, "系统", f"补生成 {generated} 位测试候选达人，当前池不少于 {desired} 位", "success")
    return {"generated": generated, "total": len(list_creators(project_id))}


def list_projects(include_test_projects: bool = False, include_archived: bool = False) -> list[dict[str, Any]]:
    init_db()
    with connect() as conn:
        clauses = []
        if not include_test_projects:
            clauses.append("project_id NOT LIKE 'pytest\\_%' ESCAPE '\\'")
        if not include_archived:
            clauses.append("archived_at IS NULL")
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        projects = rows_dict(conn.execute(f"SELECT * FROM projects {where} ORDER BY archived_at IS NOT NULL, created_at").fetchall())
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
    screening_plan = payload.get("screening_plan")
    if screening_plan is None:
        screening_plan_text = existing.get("screening_plan") if existing else "{}"
    elif isinstance(screening_plan, str):
        screening_plan_text = screening_plan
    else:
        screening_plan_text = json.dumps(screening_plan, ensure_ascii=False)
    with connect() as conn:
        if existing:
            conn.execute(
                "UPDATE projects SET project_name=?, target_qualified_creator_count=?, period_start=?, period_end=?, brief=?, screening_plan=?, updated_at=? WHERE project_id=?",
                (
                    payload.get("project_name") or existing["project_name"],
                    int(payload.get("target_qualified_creator_count") or existing["target_qualified_creator_count"]),
                    payload.get("period_start") or existing.get("period_start"),
                    payload.get("period_end") or existing.get("period_end"),
                    payload.get("brief") or existing.get("brief"),
                    screening_plan_text,
                    ts,
                    project_id,
                ),
            )
        else:
            conn.execute(
                "INSERT INTO projects(project_id, project_name, target_qualified_creator_count, period_start, period_end, brief, screening_plan, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (project_id, payload.get("project_name") or project_id, int(payload.get("target_qualified_creator_count") or 10), payload.get("period_start"), payload.get("period_end"), payload.get("brief") or "", screening_plan_text, ts, ts),
            )
        log(conn, project_id, "project", "保存项目", payload.get("project_name") or project_id, "用户", "立项信息已保存", "success")
    return get_project(project_id) or {}


def archive_project(project_id: str, archived: bool = True) -> dict[str, Any]:
    init_db()
    existing = get_project(project_id)
    if not existing:
        raise KeyError(project_id)
    ts = now()
    with connect() as conn:
        conn.execute(
            "UPDATE projects SET archived_at=?, updated_at=? WHERE project_id=?",
            (ts if archived else None, ts, project_id),
        )
        log(
            conn,
            project_id,
            "project",
            "归档项目" if archived else "取消归档项目",
            existing.get("project_name") or project_id,
            "用户",
            "项目已从默认列表隐藏" if archived else "项目已恢复到默认列表",
            "success",
        )
    return get_project(project_id) or {}


def delete_project(project_id: str) -> dict[str, Any]:
    init_db()
    with connect() as conn:
        project = row_dict(conn.execute("SELECT * FROM projects WHERE project_id=?", (project_id,)).fetchone())
        if not project:
            raise KeyError(project_id)
        creator_ids = [
            row["creator_id"]
            for row in conn.execute("SELECT creator_id FROM project_creators WHERE project_id=?", (project_id,)).fetchall()
        ]
        if not creator_ids:
            creator_ids = [
                row["creator_id"]
                for row in conn.execute("SELECT creator_id FROM creators WHERE project_id=?", (project_id,)).fetchall()
            ]

        project_tables = [
            "operation_logs",
            "collection_batches",
            "feishu_sync_state",
            "project_writeback_settings",
            "project_creator_stage_logs",
            "score_runs",
            "score_feedback",
            "creator_metrics_history",
            "project_creators",
            "creators",
        ]
        for table in project_tables:
            conn.execute(f"DELETE FROM {table} WHERE project_id=?", (project_id,))
        conn.execute("DELETE FROM projects WHERE project_id=?", (project_id,))

        for creator_id in creator_ids:
            still_used = conn.execute(
                "SELECT 1 FROM project_creators WHERE creator_id=? LIMIT 1",
                (creator_id,),
            ).fetchone()
            if not still_used:
                conn.execute("DELETE FROM creator_metrics WHERE creator_id=?", (creator_id,))
                conn.execute("DELETE FROM creator_metrics_current WHERE creator_id=?", (creator_id,))
                conn.execute("DELETE FROM creator_scores WHERE creator_id=?", (creator_id,))
                conn.execute("DELETE FROM screening_reviews WHERE creator_id=?", (creator_id,))
                conn.execute("DELETE FROM creators_global WHERE creator_id=?", (creator_id,))

    export_dir = ROOT / "runtime" / "exports" / project_id
    if export_dir.exists():
        shutil.rmtree(export_dir)
    return {"project_id": project_id, "deleted": True, "creator_count": len(creator_ids)}


def with_project_stats(project: dict[str, Any]) -> dict[str, Any]:
    with connect() as conn:
        pool = conn.execute("SELECT COUNT(*) AS count FROM project_creators WHERE project_id=?", (project["project_id"],)).fetchone()["count"]
        if not pool:
            pool = conn.execute("SELECT COUNT(*) AS count FROM creators WHERE project_id=?", (project["project_id"],)).fetchone()["count"]
        qualified = conn.execute(
            "SELECT COUNT(*) AS count FROM project_creators WHERE project_id=? AND review_status IN ('已通过','已写回飞书','合作中')",
            (project["project_id"],),
        ).fetchone()["count"]
    target = project.get("target_qualified_creator_count") or 10
    project["creator_pool_count"] = pool
    project["qualified_creator_count"] = qualified
    project["qualified_ratio"] = qualified / target if target else 0
    return project


def list_creators(project_id: str, status: str | None = None, q: str | None = None) -> list[dict[str, Any]]:
    init_db()
    where = ["pc.project_id=?"]
    params: list[Any] = [project_id]
    if status:
        where.append("pc.review_status=?")
        params.append(status)
    if q:
        where.append("(g.nickname LIKE ? OR g.persona_tags LIKE ? OR g.ip_city LIKE ?)")
        params.extend([f"%{q}%", f"%{q}%", f"%{q}%"])
    sql = f"""
    SELECT pc.project_id, g.creator_id, g.source, g.xiaohongshu_id, g.pgy_blogger_id, g.pgy_url, g.nickname,
           g.creator_type, g.persona_tags, g.ip_city, g.profile_url, g.avatar_url, g.raw_payload,
           pc.review_status AS status, pc.pool_stage, pc.portfolio_role, pc.owner, pc.note,
           pc.total_score AS project_total_score, pc.tier,
           g.created_at, pc.updated_at, m.*,
           s.total_score, s.base_score, s.bonus_score, s.information_completeness,
           s.initial_tier, s.detail_collection_priority,
           s.budget_score, s.fans_score, s.cpe_score, s.traffic_score,
           s.persona_score, s.content_score, s.recommend_level, s.score_reason, s.cooperation_direction, s.hard_filter_passed,
           r.review_status, r.review_reason, r.reviewer, r.reviewed_at
    FROM project_creators pc
    JOIN creators_global g ON pc.creator_id=g.creator_id
    LEFT JOIN creator_metrics_current m ON g.creator_id=m.creator_id
    LEFT JOIN creator_scores s ON g.creator_id=s.creator_id
    LEFT JOIN screening_reviews r ON g.creator_id=r.creator_id
    WHERE {' AND '.join(where)}
    ORDER BY COALESCE(s.total_score, pc.total_score, 0) DESC, pc.updated_at DESC
    """
    with connect() as conn:
        rows = rows_dict(conn.execute(sql, params).fetchall())
        if rows:
            return rows
        legacy_where = ["c.project_id=?"]
        legacy_params: list[Any] = [project_id]
        if status:
            legacy_where.append("c.status=?")
            legacy_params.append(status)
        if q:
            legacy_where.append("(c.nickname LIKE ? OR c.persona_tags LIKE ? OR c.ip_city LIKE ?)")
            legacy_params.extend([f"%{q}%", f"%{q}%", f"%{q}%"])
        legacy_sql = f"""
        SELECT c.*, m.*, s.total_score, s.base_score, s.bonus_score, s.information_completeness,
               s.initial_tier, s.detail_collection_priority,
               s.budget_score, s.fans_score, s.cpe_score, s.traffic_score,
               s.persona_score, s.content_score, s.recommend_level, s.score_reason, s.cooperation_direction, s.hard_filter_passed,
               r.review_status, r.review_reason, r.reviewer, r.reviewed_at
        FROM creators c
        LEFT JOIN creator_metrics m ON c.creator_id=m.creator_id
        LEFT JOIN creator_scores s ON c.creator_id=s.creator_id
        LEFT JOIN screening_reviews r ON c.creator_id=r.creator_id
        WHERE {' AND '.join(legacy_where)}
        ORDER BY COALESCE(s.total_score, 0) DESC, c.updated_at DESC
        """
        return rows_dict(conn.execute(legacy_sql, legacy_params).fetchall())


def get_creator(project_id: str, creator_id: str) -> dict[str, Any] | None:
    items = list_creators(project_id)
    return next((item for item in items if item["creator_id"] == creator_id), None)


def update_creator(project_id: str, creator_id: str, payload: dict[str, Any], score: bool = True) -> dict[str, Any]:
    existing = get_creator(project_id, creator_id)
    if not existing:
        raise KeyError(creator_id)
    merged = {**existing, **payload, "creator_id": creator_id}
    return upsert_creator(project_id, merged, score=score)


def list_metric_history(project_id: str, creator_id: str, limit: int = 20) -> list[dict[str, Any]]:
    init_db()
    with connect() as conn:
        return rows_dict(
            conn.execute(
                """
                SELECT * FROM creator_metrics_history
                WHERE project_id=? AND creator_id=?
                ORDER BY collected_at DESC
                LIMIT ?
                """,
                (project_id, creator_id, limit),
            ).fetchall()
        )


def list_stage_logs(project_id: str, creator_id: str | None = None) -> list[dict[str, Any]]:
    init_db()
    params: list[Any] = [project_id]
    where = ["project_id=?"]
    if creator_id:
        where.append("creator_id=?")
        params.append(creator_id)
    with connect() as conn:
        return rows_dict(
            conn.execute(
                f"""
                SELECT * FROM project_creator_stage_logs
                WHERE {' AND '.join(where)}
                ORDER BY created_at DESC
                LIMIT 100
                """,
                params,
            ).fetchall()
        )


def list_feishu_sync_state(project_id: str, creator_id: str | None = None) -> list[dict[str, Any]]:
    init_db()
    params: list[Any] = [project_id]
    where = ["project_id=?"]
    if creator_id:
        where.append("creator_id=?")
        params.append(creator_id)
    with connect() as conn:
        return rows_dict(
            conn.execute(
                f"SELECT * FROM feishu_sync_state WHERE {' AND '.join(where)} ORDER BY last_synced_at DESC",
                params,
            ).fetchall()
        )


def record_feishu_sync_state(
    project_id: str,
    creator_id: str,
    table_id: str,
    record_id: str | None,
    direction: str,
    status: str,
    error: str = "",
) -> None:
    init_db()
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO feishu_sync_state(project_id, creator_id, table_id, feishu_record_id, last_synced_at, sync_direction, sync_status, last_error)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(project_id, creator_id, table_id) DO UPDATE SET feishu_record_id=COALESCE(excluded.feishu_record_id, feishu_sync_state.feishu_record_id),
            last_synced_at=excluded.last_synced_at, sync_direction=excluded.sync_direction,
            sync_status=excluded.sync_status, last_error=excluded.last_error
            """,
            (project_id, creator_id, table_id, record_id, now(), direction, status, error),
        )


def update_creator_metrics(project_id: str, creator_id: str, payload: dict[str, Any], operator: str = "用户") -> dict[str, Any]:
    existing = get_creator(project_id, creator_id)
    if not existing:
        raise KeyError(creator_id)
    updated = update_creator(project_id, creator_id, payload)
    history = list_metric_history(project_id, creator_id, 1)
    change_summary = history[0].get("change_summary") if history else "{}"
    with connect() as conn:
        log(conn, project_id, "metrics", "更新达人指标", creator_id, operator, change_summary or "指标已更新并写入历史快照", "success")
    updated["latest_change_summary"] = json.loads(change_summary or "{}")
    return updated


def change_creator_stage(
    project_id: str,
    creator_id: str,
    stage: str,
    reason: str = "",
    operator: str = "用户",
) -> dict[str, Any]:
    if stage not in POOL_STAGES:
        raise ValueError("invalid stage")
    ts = now()
    with connect() as conn:
        previous = conn.execute(
            "SELECT pool_stage, review_status FROM project_creators WHERE project_id=? AND creator_id=?",
            (project_id, creator_id),
        ).fetchone()
        if not previous:
            raise KeyError(creator_id)
        status = status_from_stage(stage)
        conn.execute(
            """
            UPDATE project_creators SET pool_stage=?, review_status=?, review_reason=?, reviewer=?, reviewed_at=?, updated_at=?
            WHERE project_id=? AND creator_id=?
            """,
            (stage, status, reason, operator, ts, ts, project_id, creator_id),
        )
        conn.execute("UPDATE creators SET status=?, updated_at=? WHERE project_id=? AND creator_id=?", (status, ts, project_id, creator_id))
        conn.execute(
            """
            INSERT INTO screening_reviews(creator_id, review_status, review_reason, reviewer, reviewed_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(creator_id) DO UPDATE SET review_status=excluded.review_status,
            review_reason=excluded.review_reason, reviewer=excluded.reviewer, reviewed_at=excluded.reviewed_at
            """,
            (creator_id, status, reason, operator, ts),
        )
        conn.execute(
            """
            INSERT INTO project_creator_stage_logs(log_id, project_id, creator_id, from_stage, to_stage, from_status, to_status, operator, reason, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(uuid.uuid4()),
                project_id,
                creator_id,
                previous["pool_stage"],
                stage,
                previous["review_status"],
                status,
                operator,
                reason,
                ts,
            ),
        )
        log(conn, project_id, "stage", "更新达人池阶段", creator_id, operator, reason or f"移动到{stage}", "success")
    return get_creator(project_id, creator_id) or {}


def creator_pool(project_id: str) -> dict[str, Any]:
    project = get_project(project_id)
    if not project:
        raise KeyError(project_id)
    creators = list_creators(project_id)
    groups = {stage: [] for stage in POOL_STAGES}
    for creator in creators:
        stage = creator.get("pool_stage") or stage_from_status(creator.get("status"), creator.get("total_score"))
        if stage not in groups:
            stage = "待建联达人"
        groups[stage].append(creator)
    for items in groups.values():
        items.sort(key=lambda item: float(item.get("total_score") or 0), reverse=True)
    stats = {
        "total": len(creators),
        "avg_score": round(sum(float(item.get("total_score") or 0) for item in creators) / len(creators), 2) if creators else 0,
        "by_stage": {stage: len(items) for stage, items in groups.items()},
        "qualified": len(groups["已合作跟进中"]) + len(groups["合格达人待合作"]),
    }
    return {"project": project, "groups": groups, "stats": stats, "updated_at": now()}


def creator_pool_detail(project_id: str, creator_id: str) -> dict[str, Any] | None:
    creator = get_creator(project_id, creator_id)
    if not creator:
        return None
    return {
        "creator": creator,
        "metrics_current": {field: creator.get(field) for field in METRIC_FIELDS},
        "history": list_metric_history(project_id, creator_id),
        "stage_logs": list_stage_logs(project_id, creator_id),
        "feishu_sync_state": list_feishu_sync_state(project_id, creator_id),
        "outreach_records": [],
    }


def export_creator_pool_csv(project_id: str) -> Path:
    pool = creator_pool(project_id)
    export_dir = ROOT / "runtime" / "exports" / project_id
    export_dir.mkdir(parents=True, exist_ok=True)
    path = export_dir / f"creator-pool-{datetime.now().strftime('%Y%m%d%H%M%S')}.csv"
    columns = [
        "creator_id",
        "nickname",
        "pool_stage",
        "status",
        "total_score",
        "base_score",
        "bonus_score",
        "information_completeness",
        "initial_tier",
        "detail_collection_priority",
        "tier",
        "pgy_url",
        "creator_type",
        "persona_tags",
        "ip_city",
        "followers_count",
        "quote_price",
        "video_quote_price",
        "natural_cpc",
        "natural_cpe",
        "daily_exposure_median",
        "daily_read_median",
        "daily_interaction_median",
        "daily_thousand_like_note_ratio",
        "daily_hundred_like_note_ratio",
        "image_daily_exposure_median",
        "image_daily_read_median",
        "image_daily_interaction_median",
        "image_daily_thousand_like_note_ratio",
        "image_daily_hundred_like_note_ratio",
        "video_daily_exposure_median",
        "video_daily_read_median",
        "video_daily_interaction_median",
        "video_daily_thousand_like_note_ratio",
        "video_daily_hundred_like_note_ratio",
        "video_completion_rate",
        "cooperation_exposure_median",
        "cooperation_read_median",
        "cooperation_interaction_median",
        "overflow_store_median",
        "overflow_store_unit_price",
        "image_cpm",
        "image_read_unit_price",
        "image_interaction_unit_price",
        "video_cpm",
        "video_read_unit_price",
        "video_interaction_unit_price",
        "active_fans_ratio",
        "fans_growth_ratio",
        "read_fans_ratio",
        "interaction_fans_ratio",
        "order_fans_ratio",
        "reply_rate_48h",
        "active_days_7d",
        "search_recommend_ratio",
        "fans_35_plus_ratio",
        "child_age",
        "child_grade",
        "child_gender",
        "topic_point",
        "cost_30d",
        "cost_90d",
        "review_reason",
        "reviewer",
        "updated_at",
    ]
    rows = [creator for items in pool["groups"].values() for creator in items]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in columns})
    with connect() as conn:
        log(conn, project_id, "export", "导出达人池CSV", path.name, "系统", f"导出 {len(rows)} 条达人池记录", "success")
    return path


def merge_feishu_rows(project_id: str, rows: list[dict[str, Any]], table_id: str = "") -> dict[str, Any]:
    init_db()
    success = 0
    failed = 0
    with connect() as conn:
        for row in rows:
            creator_id = str(row.get("达人ID") or row.get("creator_id") or "")
            if not creator_id:
                pgy_url = row.get("蒲公英链接")
                nickname = row.get("达人昵称")
                existing = None
                if pgy_url:
                    existing = conn.execute("SELECT creator_id FROM creators_global WHERE pgy_url=?", (pgy_url,)).fetchone()
                if not existing and nickname:
                    existing = conn.execute("SELECT creator_id FROM creators_global WHERE nickname=?", (nickname,)).fetchone()
                creator_id = existing["creator_id"] if existing else ""
            if not creator_id:
                failed += 1
                continue
            current = conn.execute(
                "SELECT project_id FROM project_creators WHERE project_id=? AND creator_id=?",
                (project_id, creator_id),
            ).fetchone()
            if not current:
                failed += 1
                continue
            owner = row.get("负责人") or row.get("owner") or ""
            note_parts = [
                row.get("备注") or "",
                row.get("建联状态") or "",
                row.get("合作状态") or "",
                row.get("档期") or "",
                row.get("商务确认信息") or "",
            ]
            note = "；".join(str(item) for item in note_parts if item)
            conn.execute(
                """
                UPDATE project_creators SET owner=COALESCE(NULLIF(?, ''), owner),
                note=COALESCE(NULLIF(?, ''), note), updated_at=?
                WHERE project_id=? AND creator_id=?
                """,
                (owner, note, now(), project_id, creator_id),
            )
            record_feishu_sync_state(project_id, creator_id, table_id or "unknown", str(row.get("_record_id") or row.get("_row_number") or ""), "pull", "success")
            success += 1
        log(conn, project_id, "feishu", "飞书读取合并", table_id or "unknown", "系统", f"成功合并 {success} 条，失败 {failed} 条", "success" if not failed else "warning")
    return {"success": success, "failed": failed}


def _text_blob(creator: dict[str, Any]) -> str:
    raw_payload = creator.get("raw_payload") or ""
    if isinstance(raw_payload, dict):
        raw_payload = json.dumps(raw_payload, ensure_ascii=False)
    return " ".join(
        str(creator.get(key) or "")
        for key in ("nickname", "creator_type", "persona_tags", "topic_point", "child_age", "child_grade", "ip_city")
    ) + f" {raw_payload}"


def _contains_any(text: str, keywords: list[str]) -> bool:
    return any(keyword and keyword in text for keyword in keywords)


def _score_information_completeness(creator: dict[str, Any]) -> float:
    key_groups = [
        ("pgy_url",),
        ("quote_price",),
        ("followers_count",),
        ("creator_type", "persona_tags"),
        ("ip_city",),
        ("fans_35_plus_ratio",),
        ("natural_cpc", "natural_cpe"),
        ("search_recommend_ratio",),
        ("child_age", "child_grade", "topic_point"),
        ("traffic_stability", "rate_limit_risk"),
        ("daily_read_median", "daily_interaction_median"),
        ("cooperation_read_median", "cooperation_interaction_median"),
        ("image_read_unit_price", "image_interaction_unit_price", "video_read_unit_price", "video_interaction_unit_price"),
        ("active_fans_ratio", "interaction_fans_ratio"),
    ]
    known = 0
    for keys in key_groups:
        if any(creator.get(key) not in (None, "", "待填", "待核", "待评估", "-") for key in keys):
            known += 1
    return round(known / len(key_groups), 2)


def _initial_tier(total_score: Any, hard_pass: bool = True) -> str:
    if not hard_pass:
        return "Pass"
    score = parse_number(total_score) or 0
    if score >= 100:
        return "S"
    if score >= 90:
        return "A"
    if score >= 80:
        return "B+"
    if score >= 70:
        return "B"
    return "C"


def _detail_collection_priority(total_score: Any, bonus_score: Any, hard_pass: bool = True) -> str:
    if not hard_pass:
        return "不补采"
    score = parse_number(total_score) or 0
    bonus = parse_number(bonus_score) or 0
    if score >= 100:
        return "必须补采"
    if score >= 90:
        return "优先补采"
    if score >= 80 and bonus >= 8:
        return "高潜补采"
    if score >= 70:
        return "暂缓补采"
    return "不补采"


def _recommend_level(total_score: Any, hard_pass: bool = True) -> str:
    if not hard_pass:
        return "不推荐"
    score = parse_number(total_score) or 0
    if score >= 100:
        return "强推荐"
    if score >= 90:
        return "推荐"
    if score >= 80:
        return "备选"
    return "不推荐"


def _score_bonus(creator: dict[str, Any]) -> tuple[float, list[str]]:
    text = _text_blob(creator)
    city = str(creator.get("ip_city") or "")
    quote = creator.get("quote_price")
    creator_type = str(creator.get("creator_type") or "")
    bonus = 0.0
    reasons: list[str] = []
    if _contains_any(text, ["博士", "硕士", "高知", "教师", "老师", "医生", "专家", "从业者", "研究员"]):
        bonus += 5
        reasons.append("稀缺/专业人设")
    if _contains_any(text, ["学区房", "胡同", "中产", "国际学校", "住校", "升学", "小升初", "初中", "高中", "备考"]):
        bonus += 4
        reasons.append("强话题家庭或强场景")
    if _contains_any(city, ["北京", "上海"]):
        bonus += 3
        reasons.append(f"{city}IP")
    elif _contains_any(city, ["广州", "深圳", "杭州", "南京", "成都", "苏州", "武汉"]):
        bonus += 1.5
        reasons.append(f"{city}城市优势")
    if _contains_any(text, ["讨论", "争议", "观点", "政策", "规划", "避坑", "经验", "干货"]):
        bonus += 3
        reasons.append("内容具备讨论度")
    if quote is not None and quote <= 8000:
        bonus += 3
        reasons.append("低成本潜力")
    elif quote is not None and quote <= 12000:
        bonus += 1.5
        reasons.append("报价相对友好")
    if _contains_any(creator_type, ["曝光", "垂类", "卖货", "转化", "测评", "KOC", "KOL"]):
        bonus += 2
        reasons.append("组合补位价值")
    return round(min(20, bonus), 2), reasons


def score_values(creator: dict[str, Any]) -> dict[str, Any]:
    quote = creator.get("quote_price")
    fans35 = creator.get("fans_35_plus_ratio")
    cpc = creator.get("natural_cpc")
    cpe = creator.get("natural_cpe")
    search = creator.get("search_recommend_ratio")
    risk = str(creator.get("rate_limit_risk") or "")
    stability = str(creator.get("traffic_stability") or "")
    text = _text_blob(creator)
    has_pgy = bool(creator.get("pgy_url") and creator.get("pgy_url") != "待填")

    hard_issues = []
    if quote is not None and quote > 20000:
        hard_issues.append("报价超过2万元")
    if fans35 is not None and fans35 < 0.4:
        hard_issues.append("35岁以上粉丝占比低于40%")
    if _contains_any(risk, ["高风险", "严重", "违规", "疑似限流"]):
        hard_issues.append("存在明确高风险信号")
    hard_pass = not hard_issues

    persona = 18
    if _contains_any(text, ["教育", "学习", "亲子", "家庭", "母婴", "成长", "知识", "教师", "老师", "测评", "生活方式"]):
        persona += 8
    if _contains_any(text, ["低质", "搬运", "无关", "娱乐八卦"]):
        persona -= 8
    persona = max(0, min(30, persona))

    family = 10
    if _contains_any(text, ["孩子", "家长", "妈妈", "爸爸", "小升初", "初中", "高中", "大孩", "升学", "备考"]):
        family += 7
    if _contains_any(text, ["使用场景", "学习场景", "真实家庭", "陪读", "作业"]):
        family += 3
    family = max(0, min(20, family))

    fans = 10 if fans35 is None else 15 if fans35 >= 0.5 else 13 if fans35 >= 0.4 else 4

    traffic = 9 if search is None else 15 if search >= 0.55 else 13 if search >= 0.45 else 11 if search >= 0.4 else 6
    if _contains_any(stability, ["稳定", "良好"]):
        traffic += 1
    if _contains_any(stability, ["波动", "下滑", "异常"]) or _contains_any(risk, ["中风险", "限流"]):
        traffic -= 4
    traffic = max(0, min(15, traffic))

    efficiency = 10 if quote is None else 10 if quote <= 12000 else 8 if quote <= 18000 else 6 if quote <= 20000 else 0
    if cpc is not None:
        efficiency -= 2 if cpc >= 2 else 0
        efficiency += 1 if cpc < 1.5 else 0
    if cpe is not None:
        efficiency -= 3 if cpe >= 20 else 1 if cpe >= 10 else 0
        efficiency += 1 if cpe < 10 else 0
    efficiency = max(0, min(10, efficiency))

    execution = 6
    if has_pgy:
        execution += 2
    if quote is None or quote <= 20000:
        execution += 1
    if _contains_any(text, ["种草", "测评", "好物", "工具", "合作", "开箱", "体验"]):
        execution += 1
    execution = max(0, min(10, execution))

    base = round(persona + family + fans + traffic + efficiency + execution, 2)
    bonus, bonus_reasons = _score_bonus(creator)
    total = round(min(120, base + bonus), 2)
    completeness = _score_information_completeness(creator)
    tier = _initial_tier(total, hard_pass)
    priority = _detail_collection_priority(total, bonus, hard_pass)

    reasons: list[str] = []
    if hard_issues:
        reasons.extend(hard_issues)
    if not has_pgy:
        reasons.append("缺少蒲公英链接，暂按已采集信息初评")
    if fans35 is None:
        reasons.append("粉丝年龄画像待补")
    if cpc is None and cpe is None:
        reasons.append("CPC/CPE待补")
    if search is None:
        reasons.append("搜索+推荐占比待补")
    if bonus_reasons:
        reasons.append(f"加成：{'、'.join(bonus_reasons[:3])}")
    if not reasons:
        reasons.append("基础信息匹配，适合进入项目初筛排序")

    level = _recommend_level(total, hard_pass)
    return {
        "total_score": total,
        "base_score": base,
        "bonus_score": bonus,
        "information_completeness": completeness,
        "initial_tier": tier,
        "detail_collection_priority": priority,
        "budget_score": efficiency,
        "fans_score": fans,
        "cpe_score": efficiency,
        "traffic_score": traffic,
        "persona_score": persona,
        "content_score": family,
        "hard_filter_passed": 1 if hard_pass else 0,
        "recommend_level": level,
        "score_reason": "；".join(reasons),
        "cooperation_direction": _default_cooperation_direction(creator, level),
    }


def _project_screening_plan(project_id: str) -> dict[str, Any]:
    project = get_project(project_id) or {}
    screening_plan = project.get("screening_plan")
    if isinstance(screening_plan, str):
        try:
            screening_plan = json.loads(screening_plan)
        except json.JSONDecodeError:
            screening_plan = {}
    return screening_plan if isinstance(screening_plan, dict) else {}


def _project_hard_filter_issues(project_id: str, creator: dict[str, Any]) -> list[str]:
    screening_plan = _project_screening_plan(project_id)
    scoring_criteria = screening_plan.get("scoringCriteria") if isinstance(screening_plan.get("scoringCriteria"), dict) else {}
    hard_filters = (
        screening_plan.get("scoringHardFilters")
        or scoring_criteria.get("hard_rules")
        or screening_plan.get("hardFilters")
        or []
    )
    if not hard_filters:
        return []
    issues: list[str] = []
    text_blob = _text_blob(creator)
    for item in hard_filters:
        if not isinstance(item, dict) or item.get("required") is False:
            continue
        field = str(item.get("field") or item.get("standard") or "").strip()
        condition = str(item.get("condition") or "").strip()
        value = str(item.get("value") or "").strip()
        rule_text = f"{field} {condition} {value}".lower()
        label = " ".join(part for part in [field, condition, value] if part)
        if "蒲公英" in rule_text and not creator.get("pgy_url"):
            issues.append(f"{label}：缺少蒲公英链接")
        if any(keyword in rule_text for keyword in ["报价", "预算", "合作价格", "平台价格"]):
            threshold = _threshold_from_text(value, "quote")
            quote = parse_number(creator.get("quote_price"))
            if threshold is not None and quote is not None and quote > threshold:
                issues.append(f"{label}：报价 {quote:g} 超过 {threshold:g}")
        if any(keyword in rule_text for keyword in ["35", "34", "粉丝年龄", "宝妈", "家长"]):
            threshold = _threshold_from_text(value, "fans35")
            fans_ratio = ratio(creator.get("fans_35_plus_ratio"))
            if threshold is not None and fans_ratio is not None and fans_ratio < threshold:
                issues.append(f"{label}：35岁以上粉丝占比 {fans_ratio:.0%} 低于 {threshold:.0%}")
        if "cpc" in rule_text:
            threshold = _threshold_from_text(value, "cpc")
            cpc = parse_number(creator.get("natural_cpc"))
            if threshold is not None and cpc is not None and cpc >= threshold:
                issues.append(f"{label}：CPC {cpc:g} 未低于 {threshold:g}")
        if "cpe" in rule_text:
            threshold = _threshold_from_text(value, "cpe")
            cpe = parse_number(creator.get("natural_cpe"))
            if threshold is not None and cpe is not None and cpe >= threshold:
                issues.append(f"{label}：CPE {cpe:g} 未低于 {threshold:g}")
        if any(keyword in rule_text for keyword in ["搜索+推荐", "搜索推荐"]):
            threshold = _threshold_from_text(value, "search")
            search_ratio = ratio(creator.get("search_recommend_ratio"))
            if threshold is not None and search_ratio is not None and search_ratio <= threshold:
                issues.append(f"{label}：搜索+推荐占比 {search_ratio:.0%} 未超过 {threshold:.0%}")
        if any(keyword in rule_text for keyword in ["限流", "违规", "流量稳定", "异常"]):
            risk_text = f"{creator.get('rate_limit_risk') or ''} {creator.get('traffic_stability') or ''}"
            if any(keyword in risk_text for keyword in ["高", "限流", "违规", "异常"]):
                issues.append(f"{label}：存在限流/异常流量风险")
        if condition in {"包含", "匹配", "优先", "约等于"} and value and value not in text_blob:
            values = _expand_rule_values(_split_rule_values(value))
            if values and not any(part in text_blob for part in values):
                issues.append(f"{label}：未识别到匹配信息")
        if condition in {"不包含", "规避"} and value:
            values = _split_rule_values(value)
            if values and any(part in text_blob for part in values):
                issues.append(f"{label}：命中规避项")
    return issues


def generate_test_stage_score(project_id: str, creator: dict[str, Any]) -> tuple[dict[str, Any], str]:
    score = score_values(creator)
    issues = _project_hard_filter_issues(project_id, creator)
    if issues:
        score["hard_filter_passed"] = 0
        score["initial_tier"] = _initial_tier(score["total_score"], False)
        score["detail_collection_priority"] = _detail_collection_priority(score["total_score"], score.get("bonus_score", 0), False)
        score["recommend_level"] = _recommend_level(score["total_score"], False)
        score["score_reason"] = "；".join([*issues, score["score_reason"]])
    score["score_reason"] = f"【通用初筛】{score['score_reason']}"
    return score, "generated"


def _clamp_score(value: Any, default: float = 0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = default
    return max(0, min(100, number))


def _clamp_total_score(value: Any, default: float = 0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = default
    return max(0, min(120, number))


def _weighted_component(score_100: Any, weight: float) -> float:
    return round(_clamp_score(score_100) * weight / 100, 2)


def _default_cooperation_direction(creator: dict[str, Any], recommend_level: str | None = None) -> str:
    creator_type = str(creator.get("creator_type") or "")
    tags = f"{creator.get('persona_tags') or ''} {creator.get('topic_point') or ''}"
    level = recommend_level or ""
    if "不推荐" in level:
        return "暂不合作，补充关键数据后复核"
    if "卖货" in creator_type or any(word in tags for word in ["测评", "教辅", "工具", "答疑"]):
        return "产品种草/测评转化，突出答疑笔功能场景"
    if any(word in tags for word in ["升学", "政策", "规划", "教师", "老师"]):
        return "教育场景深度内容，围绕学习规划和答疑效率"
    if any(word in tags for word in ["亲子", "家庭", "陪读", "中产", "高知"]):
        return "亲子家庭场景种草，突出家长陪伴和孩子自主学习"
    if "曝光" in creator_type:
        return "品牌曝光合作，优先图文笔记验证自然流量"
    return "合作笔记试投，验证内容适配度与自然流量效率"


def _extract_cooperation_direction(result: dict[str, Any], creator: dict[str, Any], recommend_level: str) -> str:
    value = (
        result.get("cooperationDirection")
        or result.get("cooperation_direction")
        or result.get("portfolioRole")
        or result.get("portfolio_role")
        or result.get("cooperationType")
    )
    if isinstance(value, list):
        value = "；".join(str(item) for item in value if item)
    value = str(value or "").strip()
    return value or _default_cooperation_direction(creator, recommend_level)


def _normalize_llm_score(result: dict[str, Any], fallback: dict[str, Any], creator: dict[str, Any] | None = None) -> dict[str, Any]:
    dimensions = result.get("dimensionScores") or result.get("scores") or {}
    weights = {"budget": 10, "fans": 15, "cpe": 10, "engagement": 15, "persona": 30, "content": 20}
    if dimensions:
        component_scores = {
            "budget_score": _weighted_component(dimensions.get("budget"), weights["budget"]),
            "fans_score": _weighted_component(dimensions.get("fans"), weights["fans"]),
            "cpe_score": _weighted_component(dimensions.get("cpe"), weights["cpe"]),
            "traffic_score": _weighted_component(dimensions.get("engagement") or dimensions.get("traffic"), weights["engagement"]),
            "persona_score": _weighted_component(dimensions.get("persona"), weights["persona"]),
            "content_score": _weighted_component(dimensions.get("content"), weights["content"]),
        }
    else:
        component_scores = {key: fallback[key] for key in ("budget_score", "fans_score", "cpe_score", "traffic_score", "persona_score", "content_score")}
    component_total = round(sum(component_scores.values()), 2)
    base_score = _clamp_score(
        result.get("baseScore") or result.get("base_score"),
        fallback.get("base_score") or component_total,
    )
    bonus_score = max(
        0,
        min(
            20,
            parse_number(result.get("bonusScore") or result.get("bonus_score"))
            if result.get("bonusScore") is not None or result.get("bonus_score") is not None
            else (fallback.get("bonus_score") or 0),
        ),
    )
    total = _clamp_total_score(
        result.get("totalScore") or result.get("total_score"),
        fallback.get("total_score") or (base_score + bonus_score),
    )
    hard_filter_passed = result.get("hardFilterPassed")
    if hard_filter_passed is None:
        hard_filter_passed = fallback["hard_filter_passed"]
    reasons = result.get("reason") or result.get("scoreReason") or result.get("score_reason") or fallback["score_reason"]
    if isinstance(reasons, list):
        reasons = "；".join(str(item) for item in reasons if item)
    hard_pass_bool = bool(hard_filter_passed)
    recommend_level = result.get("recommendLevel") or result.get("recommend_level") or _recommend_level(total, hard_pass_bool)
    completeness = parse_number(result.get("informationCompleteness") or result.get("information_completeness"))
    if completeness is None:
        completeness = fallback.get("information_completeness") or (_score_information_completeness(creator) if creator else 0)
    if completeness > 1:
        completeness = completeness / 100
    completeness = max(0, min(1, completeness))
    initial_tier = str(result.get("initialTier") or result.get("initial_tier") or _initial_tier(total, hard_pass_bool))
    detail_priority = str(
        result.get("detailCollectionPriority")
        or result.get("detail_collection_priority")
        or _detail_collection_priority(total, bonus_score, hard_pass_bool)
    )
    cooperation_direction = _extract_cooperation_direction(result, creator or {}, str(recommend_level))
    return {
        "total_score": round(total, 2),
        "base_score": round(base_score, 2),
        "bonus_score": round(bonus_score, 2),
        "information_completeness": round(completeness, 2),
        "initial_tier": initial_tier,
        "detail_collection_priority": detail_priority,
        **component_scores,
        "hard_filter_passed": 1 if hard_pass_bool else 0,
        "recommend_level": str(recommend_level),
        "score_reason": f"【大模型分析】{str(reasons).strip()}",
        "cooperation_direction": cooperation_direction,
    }


LLM_BATCH_CONTEXT_LIMIT_CHARS = 850_000
LLM_BATCH_MAX_CREATORS = 80


def _creator_score_payload(creator: dict[str, Any]) -> dict[str, Any]:
    return {
        "creator_id": creator.get("creator_id"),
        "nickname": creator.get("nickname"),
        "creator_type": creator.get("creator_type"),
        "persona_tags": creator.get("persona_tags"),
        "topic_point": creator.get("topic_point"),
        "ip_city": creator.get("ip_city"),
        "child_grade": creator.get("child_grade"),
        "child_age": creator.get("child_age"),
        "followers_count": creator.get("followers_count"),
        "quote_price": creator.get("quote_price"),
        "natural_cpc": creator.get("natural_cpc"),
        "natural_cpe": creator.get("natural_cpe"),
        "daily_read_median": creator.get("daily_read_median"),
        "daily_interaction_median": creator.get("daily_interaction_median"),
        "cooperation_read_median": creator.get("cooperation_read_median"),
        "cooperation_interaction_median": creator.get("cooperation_interaction_median"),
        "image_read_unit_price": creator.get("image_read_unit_price"),
        "image_interaction_unit_price": creator.get("image_interaction_unit_price"),
        "video_read_unit_price": creator.get("video_read_unit_price"),
        "video_interaction_unit_price": creator.get("video_interaction_unit_price"),
        "active_fans_ratio": creator.get("active_fans_ratio"),
        "interaction_fans_ratio": creator.get("interaction_fans_ratio"),
        "reply_rate_48h": creator.get("reply_rate_48h"),
        "search_recommend_ratio": creator.get("search_recommend_ratio"),
        "fans_35_plus_ratio": creator.get("fans_35_plus_ratio"),
        "traffic_stability": creator.get("traffic_stability"),
        "rate_limit_risk": creator.get("rate_limit_risk"),
        "pgy_url": creator.get("pgy_url"),
        "raw_payload": creator.get("raw_payload"),
    }


def _score_batch_payload(project_id: str, creators: list[dict[str, Any]]) -> dict[str, Any]:
    project = get_project(project_id) or {}
    screening_plan = project.get("screening_plan")
    if isinstance(screening_plan, str):
        try:
            screening_plan = json.loads(screening_plan)
        except json.JSONDecodeError:
            screening_plan = {}
    if not isinstance(screening_plan, dict):
        screening_plan = {}
    return {
        "project": {
            "project_id": project_id,
            "project_name": project.get("project_name") or PROJECT_NAME,
            "brief": project.get("brief") or "教育/亲子大孩/高知家庭达人，聚焦有道答疑笔5-6月合作。",
            "target_qualified_creator_count": project.get("target_qualified_creator_count"),
            "scoringCriteria": screening_plan.get("scoringCriteria") or {},
            "scoringHardFilters": screening_plan.get("scoringHardFilters") or (screening_plan.get("scoringCriteria") or {}).get("hard_rules") or screening_plan.get("hardFilters") or [],
            "hardFilters": screening_plan.get("scoringHardFilters") or (screening_plan.get("scoringCriteria") or {}).get("hard_rules") or screening_plan.get("hardFilters") or [],
            "scoringWeights": screening_plan.get("scoringWeights") or {},
            "collectionSchemeSummary": [
                {
                    "scheme_id": scheme.get("scheme_id"),
                    "name": scheme.get("name"),
                    "goal": scheme.get("goal"),
                }
                for scheme in ((screening_plan.get("pgyCollectionPlan") or {}).get("schemes") or [])
                if isinstance(scheme, dict)
            ],
        },
        "creators": [_creator_score_payload(creator) for creator in creators],
        "requiredSchema": {
            "results": [
                {
                    "creator_id": "必须原样返回",
                    "baseScore": "0-100 基础分，只评估该达人是否适配当前项目，不因信息缺失直接打很低",
                    "bonusScore": "0-20 加成分，只奖励稀缺人设、强话题、城市/受众/性价比/组合价值等亮点",
                    "totalScore": "0-120 初筛总分，等于 baseScore + bonusScore",
                    "informationCompleteness": "0-1，关键初筛字段的信息完整度；未知字段不直接淘汰，但要说明待补",
                    "initialTier": "S|A|B+|B|C|Pass；S≥100，A=90-99，B+=80-89，B=70-79，C<70，硬性不符为Pass",
                    "detailCollectionPriority": "必须补采|优先补采|高潜补采|暂缓补采|不补采；只让高分或高潜达人进入详情页补采",
                    "dimensionScores": {
                        "budget": "0-100 预算/报价匹配，对应基础分中的成本效率部分",
                        "fans": "0-100 粉丝画像/目标受众匹配",
                        "cpe": "0-100 成本效率/CPC/CPE/转化成本",
                        "engagement": "0-100 流量质量、互动质量与稳定性",
                        "persona": "0-100 人设与当前项目 Brief 匹配",
                        "content": "0-100 内容风格、内容场景与可植入度",
                    },
                    "hardFilterPassed": "boolean，是否没有命中当前项目明确硬性淘汰项；未知项不要当成硬性不符",
                    "recommendLevel": "强推荐|推荐|备选|不推荐",
                    "reason": "120字以内，说明基础分依据、加成依据、缺失待补字段与主要风险",
                    "cooperationDirection": "80字以内，给出适合该达人的合作方向/内容角度/投放角色",
                }
            ]
        },
    }


def _chunk_creators_for_llm(project_id: str, creators: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    chunks: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    for creator in creators:
        candidate = [*current, creator]
        size = len(json.dumps(_score_batch_payload(project_id, candidate), ensure_ascii=False))
        if current and (size > LLM_BATCH_CONTEXT_LIMIT_CHARS or len(candidate) > LLM_BATCH_MAX_CREATORS):
            chunks.append(current)
            current = [creator]
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks


def score_values_batch_with_llm(project_id: str, creators: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    system_prompt = (
        "你是广告投放达人筛选策略专家。请基于每个项目自己的 Brief、采集后评分标准 scoringCriteria 和达人资料做综合判断。"
        "所有项目都使用同一套初筛评分协议：基础分 baseScore 满分100，加成分 bonusScore 满分20，总分 totalScore 满分120。"
        "基础分评估项目适配度，未知字段只标记待补采并影响 informationCompleteness，不要因为信息不全把大部分候选人打成不及格；"
        "加成分只奖励稀缺人设、强话题、城市/人群优势、讨论度、低成本潜力和组合补位价值。"
        "请输出 initialTier 和 detailCollectionPriority，用于决定哪些高分/高潜达人进入详情页补采。"
        "不要把当前项目 Brief 写死成有道答疑笔；不同项目必须按传入 Brief 和 scoringCriteria 适配。"
        "蒲公英 collectionSchemeSummary 只用于理解达人来源，不得把页面筛选条件直接当作最终评分结论。"
    )
    user_payload = _score_batch_payload(project_id, creators)
    result = chat_json(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"请只输出符合 requiredSchema 的 JSON，results 数量必须等于 creators 数量：\n{json.dumps(user_payload, ensure_ascii=False)}"},
        ]
    )
    raw_results = result.get("results") or result.get("creators") or result.get("scores") or []
    if isinstance(raw_results, dict):
        raw_results = list(raw_results.values())
    normalized: dict[str, dict[str, Any]] = {}
    by_id = {str(creator.get("creator_id")): creator for creator in creators}
    for item in raw_results:
        if not isinstance(item, dict):
            continue
        creator_id = str(item.get("creator_id") or item.get("creatorId") or "")
        creator = by_id.get(creator_id)
        if not creator:
            continue
        normalized[creator_id] = _normalize_llm_score(item, score_values(creator), creator)
    if len(normalized) != len(creators):
        missing = [str(creator.get("creator_id")) for creator in creators if str(creator.get("creator_id")) not in normalized]
        raise RuntimeError(f"模型批量评分结果缺少达人: {', '.join(missing[:5])}")
    return normalized


def score_values_with_llm(project_id: str, creator: dict[str, Any]) -> tuple[dict[str, Any], str]:
    result = score_values_batch_with_llm(project_id, [creator])
    return result[str(creator["creator_id"])], "llm"


def _persist_creator_score(
    project_id: str,
    creator: dict[str, Any],
    score: dict[str, Any],
    source: str,
    batch_id: str,
    trigger_source: str,
) -> dict[str, Any]:
    creator_id = str(creator["creator_id"])
    ts = now()
    cooperation_direction = score.get("cooperation_direction") or _default_cooperation_direction(creator, score.get("recommend_level"))
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO creator_scores(creator_id, total_score, base_score, bonus_score, information_completeness,
            initial_tier, detail_collection_priority, budget_score, fans_score, cpe_score, traffic_score,
            persona_score, content_score, hard_filter_passed, recommend_level, score_reason, cooperation_direction, scored_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(creator_id) DO UPDATE SET total_score=excluded.total_score,
            base_score=excluded.base_score, bonus_score=excluded.bonus_score,
            information_completeness=excluded.information_completeness,
            initial_tier=excluded.initial_tier, detail_collection_priority=excluded.detail_collection_priority,
            budget_score=excluded.budget_score,
            fans_score=excluded.fans_score, cpe_score=excluded.cpe_score, traffic_score=excluded.traffic_score,
            persona_score=excluded.persona_score, content_score=excluded.content_score,
            hard_filter_passed=excluded.hard_filter_passed, recommend_level=excluded.recommend_level,
            score_reason=excluded.score_reason, cooperation_direction=excluded.cooperation_direction, scored_at=excluded.scored_at
            """,
            (
                creator_id,
                score["total_score"],
                score.get("base_score", min(float(score["total_score"]), 100)),
                score.get("bonus_score", max(0, float(score["total_score"]) - min(float(score["total_score"]), 100))),
                score.get("information_completeness", _score_information_completeness(creator)),
                score.get("initial_tier", _initial_tier(score["total_score"], bool(score["hard_filter_passed"]))),
                score.get("detail_collection_priority", _detail_collection_priority(score["total_score"], score.get("bonus_score", 0), bool(score["hard_filter_passed"]))),
                score["budget_score"],
                score["fans_score"],
                score["cpe_score"],
                score["traffic_score"],
                score["persona_score"],
                score["content_score"],
                score["hard_filter_passed"],
                score["recommend_level"],
                score["score_reason"],
                cooperation_direction,
                ts,
            ),
        )
        conn.execute(
            """
            INSERT INTO score_runs(run_id, batch_id, project_id, creator_id, trigger_source, score_version, rule_score, llm_score, total_score, llm_result, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(uuid.uuid4()),
                batch_id,
                project_id,
                creator_id,
                trigger_source,
                "youdao-v1",
                score["total_score"] if source in {"rule", "generated"} else None,
                score["total_score"] if source == "llm" else None,
                score["total_score"],
                json.dumps({"source": source, "batch_id": batch_id, **score, "cooperation_direction": cooperation_direction}, ensure_ascii=False),
                ts,
            ),
        )
        conn.execute(
            """
            UPDATE project_creators SET total_score=?, tier=?, pool_stage=?, portfolio_role=?, updated_at=?
            WHERE project_id=? AND creator_id=?
            """,
            (
                score["total_score"],
                tier_from_score(score["total_score"]),
                stage_from_status(creator.get("status"), score["total_score"]),
                cooperation_direction,
                ts,
                project_id,
                creator_id,
            ),
        )
        if creator["status"] == "待补数据" and score["hard_filter_passed"]:
            conn.execute("UPDATE creators SET status='待审核', updated_at=? WHERE creator_id=?", (ts, creator_id))
            conn.execute(
                "UPDATE project_creators SET review_status='待审核', pool_stage=?, updated_at=? WHERE project_id=? AND creator_id=?",
                (stage_from_status("待审核", score["total_score"]), ts, project_id, creator_id),
            )
    scored = get_creator(project_id, creator_id) or {}
    scored["score_source"] = source
    scored["batch_id"] = batch_id
    return scored


def score_creator(
    project_id: str,
    creator_id: str,
    use_llm: bool = True,
    batch_id: str | None = None,
    trigger_source: str = "single",
) -> dict[str, Any]:
    creator = get_creator(project_id, creator_id)
    if not creator:
        raise KeyError(creator_id)
    source = "generated"
    try:
        score, source = score_values_with_llm(project_id, creator) if use_llm else (generate_test_stage_score(project_id, creator)[0], "rule")
    except Exception:
        score, source = generate_test_stage_score(project_id, creator)
    return _persist_creator_score(project_id, creator, score, source, batch_id or str(uuid.uuid4()), trigger_source)


def score_project(
    project_id: str,
    use_llm: bool = True,
    creator_ids: list[str] | None = None,
    trigger_source: str = "manual",
) -> dict[str, Any]:
    all_creators = list_creators(project_id)
    wanted = {str(creator_id) for creator_id in creator_ids} if creator_ids else None
    creators = [creator for creator in all_creators if wanted is None or str(creator.get("creator_id")) in wanted]
    batch_id = str(uuid.uuid4())
    sources = {"llm": 0, "generated": 0, "rule": 0}
    if use_llm and creators:
        for chunk in _chunk_creators_for_llm(project_id, creators):
            try:
                batch_scores = score_values_batch_with_llm(project_id, chunk)
                for creator in chunk:
                    score = batch_scores[str(creator["creator_id"])]
                    scored = _persist_creator_score(project_id, creator, score, "llm", batch_id, trigger_source)
                    sources[scored.get("score_source") or "fallback"] = sources.get(scored.get("score_source") or "fallback", 0) + 1
            except Exception:
                for creator in chunk:
                    score, source = generate_test_stage_score(project_id, creator)
                    scored = _persist_creator_score(project_id, creator, score, source, batch_id, trigger_source)
                    sources[scored.get("score_source") or "fallback"] = sources.get(scored.get("score_source") or "fallback", 0) + 1
    else:
        for creator in creators:
            score, _ = generate_test_stage_score(project_id, creator)
            scored = _persist_creator_score(project_id, creator, score, "rule", batch_id, trigger_source)
            sources[scored.get("score_source") or "fallback"] = sources.get(scored.get("score_source") or "fallback", 0) + 1
    with connect() as conn:
        if sources.get("llm"):
            detail = f"批次 {batch_id} 完成 {len(creators)} 位达人评分，其中 {sources['llm']} 位由大模型分析生成"
            status = "success"
        elif sources.get("generated"):
            detail = f"批次 {batch_id} 完成 {len(creators)} 位达人评分，测试阶段已直接生成筛选结果；API 接入入口保留可测"
            status = "success"
        else:
            detail = f"批次 {batch_id} 完成 {len(creators)} 位达人评分，当前使用规则评分；请配置大模型 API 后重新评分"
            status = "warning"
        log(conn, project_id, "score", "执行评分", PROJECT_NAME, "AI", detail, status)
    return {
        "batch_id": batch_id,
        "scored": len(creators),
        "source": "llm" if sources.get("llm") else ("generated" if sources.get("generated") else "rule"),
        "sources": sources,
        "trigger_source": trigger_source,
    }


def review_creator(project_id: str, creator_id: str, status: str, reason: str = "", reviewer: str = "用户") -> dict[str, Any]:
    if status not in PROJECT_STATUSES:
        raise ValueError("invalid status")
    ts = now()
    with connect() as conn:
        previous = conn.execute(
            "SELECT pool_stage, review_status FROM project_creators WHERE project_id=? AND creator_id=?",
            (project_id, creator_id),
        ).fetchone()
        score = conn.execute("SELECT total_score FROM creator_scores WHERE creator_id=?", (creator_id,)).fetchone()
        next_stage = stage_from_status(status, score["total_score"] if score else None)
        conn.execute("UPDATE creators SET status=?, updated_at=? WHERE project_id=? AND creator_id=?", (status, ts, project_id, creator_id))
        conn.execute(
            """
            INSERT INTO project_creators(project_id, creator_id, pool_stage, review_status, review_reason, reviewer, reviewed_at, total_score, tier, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(project_id, creator_id) DO UPDATE SET pool_stage=excluded.pool_stage,
            review_status=excluded.review_status, review_reason=excluded.review_reason, reviewer=excluded.reviewer,
            reviewed_at=excluded.reviewed_at, total_score=excluded.total_score, tier=excluded.tier, updated_at=excluded.updated_at
            """,
            (
                project_id,
                creator_id,
                next_stage,
                status,
                reason,
                reviewer,
                ts,
                score["total_score"] if score else None,
                tier_from_score(score["total_score"] if score else None),
                ts,
                ts,
            ),
        )
        conn.execute(
            """
            INSERT INTO screening_reviews(creator_id, review_status, review_reason, reviewer, reviewed_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(creator_id) DO UPDATE SET review_status=excluded.review_status,
            review_reason=excluded.review_reason, reviewer=excluded.reviewer, reviewed_at=excluded.reviewed_at
            """,
            (creator_id, status, reason, reviewer, ts),
        )
        if not previous or previous["pool_stage"] != next_stage or previous["review_status"] != status:
            conn.execute(
                """
                INSERT INTO project_creator_stage_logs(log_id, project_id, creator_id, from_stage, to_stage, from_status, to_status, operator, reason, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    project_id,
                    creator_id,
                    previous["pool_stage"] if previous else None,
                    next_stage,
                    previous["review_status"] if previous else None,
                    status,
                    reviewer,
                    reason,
                    ts,
                ),
            )
        log(conn, project_id, "review", f"审核{status}", creator_id, reviewer, reason or f"状态更新为{status}", "success")
    return get_creator(project_id, creator_id) or {}


def _batch_dict(row: sqlite3.Row | None) -> dict[str, Any]:
    data = row_dict(row)
    if not data:
        return {}
    for key, default in {
        "collection_plan": {},
        "applied_filters": [],
        "skipped_filters": [],
        "selected_metrics": [],
        "skipped_metrics": [],
    }.items():
        value = data.get(key)
        if isinstance(value, str):
            try:
                data[key] = json.loads(value) if value else default
            except json.JSONDecodeError:
                data[key] = default
        elif value is None:
            data[key] = default
    return data


def list_batches(project_id: str) -> list[dict[str, Any]]:
    init_db()
    with connect() as conn:
        rows = conn.execute("SELECT * FROM collection_batches WHERE project_id=? ORDER BY started_at DESC", (project_id,)).fetchall()
        return [_batch_dict(row) for row in rows]


def create_batch(project_id: str, source_url: str, status: str = "running") -> str:
    batch_id = str(uuid.uuid4())
    with connect() as conn:
        conn.execute(
            "INSERT INTO collection_batches(batch_id, project_id, source_url, status, started_at) VALUES (?, ?, ?, ?, ?)",
            (batch_id, project_id, source_url, status, now()),
        )
    return batch_id


def _json_text(value: Any, default: Any) -> str:
    payload = default if value is None else value
    return json.dumps(payload, ensure_ascii=False)


def scheme_signature(filters: list[dict[str, Any]]) -> str:
    normalized = [
        {
            "field": str(item.get("field") or ""),
            "value": str(item.get("value") or ""),
            "control_type": str(item.get("control_type") or ""),
            "sub_field": str(item.get("sub_field") or ""),
            "min": item.get("min"),
            "max": item.get("max"),
        }
        for item in filters or []
    ]
    normalized = sorted(normalized, key=lambda item: (item["field"], item["value"], item["sub_field"], item["control_type"]))
    return json.dumps(normalized, ensure_ascii=False, sort_keys=True)


def scheme_count_memory(project_id: str, scheme_id: str, filters: list[dict[str, Any]], limit: int = 12) -> list[dict[str, Any]]:
    init_db()
    signature = scheme_signature(filters)
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT * FROM scheme_count_memory
            WHERE project_id=? AND (scheme_id=? OR signature=?)
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (project_id, scheme_id, signature, limit),
        ).fetchall()
    return rows_dict(rows)


def list_scheme_count_memory(project_id: str, scheme_id: str = "", limit: int = 30) -> list[dict[str, Any]]:
    init_db()
    with connect() as conn:
        if scheme_id:
            rows = conn.execute(
                """
                SELECT * FROM scheme_count_memory
                WHERE project_id=? AND scheme_id=?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (project_id, scheme_id, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT * FROM scheme_count_memory
                WHERE project_id=?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (project_id, limit),
            ).fetchall()
    return rows_dict(rows)


def record_scheme_count_memory(
    project_id: str,
    scheme: dict[str, Any],
    expected: dict[str, Any],
    preflight: dict[str, Any],
    *,
    collected_count: int = 0,
    accepted_count: int = 0,
    rejected_count: int = 0,
) -> dict[str, Any]:
    init_db()
    filters = scheme.get("filters") or []
    memory = {
        "memory_id": str(uuid.uuid4()),
        "project_id": project_id,
        "scheme_id": str(scheme.get("scheme_id") or scheme.get("id") or scheme.get("name") or "scheme"),
        "scheme_name": str(scheme.get("name") or scheme.get("scheme_id") or scheme.get("id") or "scheme"),
        "signature": scheme_signature(filters),
        "filters": filters,
        "expected_min": expected.get("expected_min"),
        "expected_max": expected.get("expected_max"),
        "expected_center": expected.get("expected_center"),
        "predicted_source": expected.get("predicted_source") or "formula",
        "actual_recommend_count": preflight.get("actual_recommend_count"),
        "actual_count_text": preflight.get("actual_count_text") or "",
        "actual_count_is_lower_bound": 1 if preflight.get("actual_count_is_lower_bound") else 0,
        "evaluation_status": (preflight.get("evaluation") or {}).get("status") or "",
        "collected_count": collected_count,
        "accepted_count": accepted_count,
        "rejected_count": rejected_count,
        "created_at": now(),
    }
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO scheme_count_memory(memory_id, project_id, scheme_id, scheme_name, signature, filters,
            expected_min, expected_max, expected_center, predicted_source, actual_recommend_count, actual_count_text,
            actual_count_is_lower_bound, evaluation_status, collected_count, accepted_count, rejected_count, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                memory["memory_id"],
                memory["project_id"],
                memory["scheme_id"],
                memory["scheme_name"],
                memory["signature"],
                _json_text(memory["filters"], []),
                memory["expected_min"],
                memory["expected_max"],
                memory["expected_center"],
                memory["predicted_source"],
                memory["actual_recommend_count"],
                memory["actual_count_text"],
                memory["actual_count_is_lower_bound"],
                memory["evaluation_status"],
                memory["collected_count"],
                memory["accepted_count"],
                memory["rejected_count"],
                memory["created_at"],
            ),
        )
    return memory


def update_scheme_count_memory(memory_id: str, *, accepted_count: int = 0, rejected_count: int = 0, collected_count: int | None = None) -> None:
    init_db()
    assignments = ["accepted_count=?", "rejected_count=?"]
    params: list[Any] = [accepted_count, rejected_count]
    if collected_count is not None:
        assignments.append("collected_count=?")
        params.append(collected_count)
    params.append(memory_id)
    with connect() as conn:
        conn.execute(
            f"UPDATE scheme_count_memory SET {', '.join(assignments)} WHERE memory_id=?",
            params,
        )


def finish_batch(
    batch_id: str,
    status: str,
    total: int,
    success: int,
    failed: int,
    error: str = "",
    *,
    collection_plan: dict[str, Any] | None = None,
    applied_filters: list[dict[str, Any]] | None = None,
    skipped_filters: list[dict[str, Any]] | None = None,
    selected_metrics: list[dict[str, Any]] | None = None,
    skipped_metrics: list[dict[str, Any]] | None = None,
    detail_collection: str = "",
) -> dict[str, Any]:
    with connect() as conn:
        conn.execute(
            """
            UPDATE collection_batches SET status=?, finished_at=?, total_count=?, success_count=?,
            failed_count=?, error_message=?, collection_plan=?, applied_filters=?, skipped_filters=?,
            selected_metrics=?, skipped_metrics=?, detail_collection=? WHERE batch_id=?
            """,
            (
                status,
                now(),
                total,
                success,
                failed,
                error,
                _json_text(collection_plan, {}),
                _json_text(applied_filters, []),
                _json_text(skipped_filters, []),
                _json_text(selected_metrics, []),
                _json_text(skipped_metrics, []),
                detail_collection,
                batch_id,
            ),
        )
        row = conn.execute("SELECT * FROM collection_batches WHERE batch_id=?", (batch_id,)).fetchone()
    return _batch_dict(row)


def list_logs(project_id: str) -> list[dict[str, Any]]:
    init_db()
    with connect() as conn:
        return rows_dict(conn.execute("SELECT * FROM operation_logs WHERE project_id=? ORDER BY created_at DESC LIMIT 200", (project_id,)).fetchall())


def _as_float(value: Any) -> float | None:
    number = parse_number(value)
    return number if number is not None else None


def _wan(value: Any) -> Any:
    number = _as_float(value)
    if number is None:
        return ""
    return round(number / 10000, 2)


def _percent(value: Any) -> str:
    number = ratio(value)
    if number is None:
        return ""
    return f"{round(number * 100, 1):g}%"


def _ratio_sum(*values: Any) -> float | None:
    total = 0.0
    found = False
    for value in values:
        number = ratio(value)
        if number is None:
            continue
        total += number
        found = True
    if not found:
        return None
    return min(total, 1.0)


def _fans_35_plus_ratio(c: dict[str, Any]) -> float | None:
    derived = _ratio_sum(c.get("fans_35_44_ratio"), c.get("fans_44_plus_ratio"))
    if derived is not None:
        return derived
    return ratio(c.get("fans_35_plus_ratio"))


def _fans_25_44_ratio(c: dict[str, Any]) -> float | None:
    return _ratio_sum(c.get("fans_25_34_ratio"), c.get("fans_35_44_ratio"))


def _price_with_service(value: Any) -> Any:
    number = _as_float(value)
    if number is None:
        return ""
    return round(number * 1.1, 2)


def _creator_homepage(c: dict[str, Any]) -> str:
    if c.get("profile_url") and "pgy.xiaohongshu.com" not in str(c.get("profile_url")):
        return str(c.get("profile_url"))
    xhs_id = str(c.get("xiaohongshu_id") or "").strip()
    if xhs_id:
        return f"https://www.xiaohongshu.com/user/profile/{xhs_id}"
    return ""


def _text_blob(c: dict[str, Any]) -> str:
    raw_payload = c.get("raw_payload")
    if isinstance(raw_payload, str):
        raw_text = raw_payload
    else:
        raw_text = json.dumps(raw_payload or {}, ensure_ascii=False)
    return " ".join(
        str(c.get(key) or "")
        for key in ("nickname", "creator_type", "persona_tags", "topic_point", "child_age", "child_grade", "child_gender")
    ) + " " + raw_text[:4000]


def _infer_child_stage(c: dict[str, Any]) -> str:
    existing = str(c.get("child_grade") or c.get("child_age") or "").strip()
    if existing:
        return existing
    text = _text_blob(c)
    for value in ["0-6个月", "6-12个月", "1-3岁", "3-6岁", "6-12岁", "12岁以上", "小升初", "初中", "高中"]:
        if value in text:
            return value
    return "需人工获取"


def _infer_child_gender(c: dict[str, Any]) -> str:
    existing = str(c.get("child_gender") or "").strip()
    if existing:
        return existing
    text = _text_blob(c)
    if any(keyword in text for keyword in ["女儿", "女孩", "女宝", "闺女"]):
        return "女"
    if any(keyword in text for keyword in ["儿子", "男孩", "男宝"]):
        return "男"
    return "需人工获取"


def _tier_label(c: dict[str, Any]) -> str:
    followers = _as_float(c.get("followers_count")) or 0
    if followers > 100000:
        return "tier1"
    if followers >= 50000:
        return "tier2"
    return "tier3"


def _note_type(c: dict[str, Any]) -> str:
    image_quote = _as_float(c.get("quote_price"))
    video_quote = _as_float(c.get("video_quote_price"))
    if image_quote and video_quote:
        return "视频or图文"
    if video_quote:
        return "视频"
    if image_quote:
        return "图文"
    return "合作笔记"


def _enrich_feishu_row(row: dict[str, Any], c: dict[str, Any], sequence: int | None = None) -> dict[str, Any]:
    image_quote = c.get("quote_price") or ""
    video_quote = c.get("video_quote_price") or ""
    followers_w = _wan(c.get("followers_count"))
    liked_w = _wan(c.get("liked_collected_count"))
    fans_35_plus = _fans_35_plus_ratio(c)
    fans_25_44 = _fans_25_44_ratio(c)
    fans_35_44 = ratio(c.get("fans_35_44_ratio"))
    fans_44_plus = ratio(c.get("fans_44_plus_ratio"))
    row.update(
        {
            "日期": datetime.now().strftime("%Y-%m-%d"),
            "序号": row.get("序号") or sequence or "",
            "小红书号": c.get("xiaohongshu_id") or "",
            "主页链接": _creator_homepage(c),
            "达人类型": c.get("creator_type") or row.get("账号类型") or "",
            "账号类型": c.get("creator_type") or row.get("账号类型") or "",
            "粉丝量级": _tier_label(c),
            "达人量级": _tier_label(c),
            "粉丝数": c.get("followers_count") or "",
            "粉丝数/w": followers_w,
            "粉丝量\n（w）": followers_w,
            "粉丝量（w）": followers_w,
            "获赞与收藏": c.get("liked_collected_count") or "",
            "赞藏数/w": liked_w,
            "赞藏量\n（w）": liked_w,
            "赞藏量（w）": liked_w,
            "阅读中位数": c.get("daily_read_median") or "",
            "互动中位数": c.get("daily_interaction_median") or "",
            "曝光中位数": c.get("daily_exposure_median") or "",
            "近30天商单互动中位数": c.get("cooperation_interaction_median") or "",
            "粉丝画像年龄": (
                f"25-34 {_percent(c.get('fans_25_34_ratio'))}；35岁以上 {_percent(fans_35_plus)}".strip("；")
                if c.get("fans_25_34_ratio") or fans_35_plus is not None
                else ""
            ),
            "粉丝女性用户占比": _percent(c.get("female_fans_ratio")),
            "粉丝年龄25-34占比": _percent(c.get("fans_25_34_ratio")),
            "粉丝年龄25-44占比": _percent(fans_25_44),
            "25-44岁粉丝占比": _percent(fans_25_44),
            "25-44岁粉丝占比（25-34+35-44）": _percent(fans_25_44),
            "粉丝年龄34岁以上占比": _percent(fans_35_plus),
            "35岁以上粉丝占比": _percent(fans_35_plus),
            "粉丝年龄34岁以上占比（35-44+44岁以上）": _percent(fans_35_plus),
            "35岁以上粉丝占比（35-44+44岁以上）": _percent(fans_35_plus),
            "粉丝年龄35-44占比": _percent(fans_35_44),
            "粉丝年龄44岁以上占比": _percent(fans_44_plus),
            "孩子年级": _infer_child_stage(c),
            "孩子性别": _infer_child_gender(c),
            "图文报备价": image_quote,
            "图文报备裸价": image_quote,
            "平台报价": image_quote,
            "报价": image_quote,
            "视频报备价": video_quote,
            "视频报备裸价": video_quote,
            "图文执行价\n（含平台服务费）": _price_with_service(image_quote),
            "图文执行价（含平台服务费）": _price_with_service(image_quote),
            "视频执行价\n（含平台服务费）": _price_with_service(video_quote),
            "视频执行价（含平台服务费）": _price_with_service(video_quote),
            "合作价格（含服务费）": _price_with_service(image_quote) or image_quote,
            "视频完播率": _percent(c.get("video_completion_rate")),
            "活跃粉丝占比": _percent(c.get("active_fans_ratio")),
            "预估cpe": c.get("image_interaction_unit_price") or c.get("natural_cpe") or "",
            "预估CPE": c.get("image_interaction_unit_price") or c.get("natural_cpe") or "",
            "预估cpm": c.get("image_cpm") or c.get("video_cpm") or "",
            "预估CPM": c.get("image_cpm") or c.get("video_cpm") or "",
            "CPE": c.get("natural_cpe") or c.get("image_interaction_unit_price") or "",
            "cpe（不超过20，最好10以下）": c.get("natural_cpe") or c.get("image_interaction_unit_price") or "",
            "粉丝画像": c.get("audience_profile_screenshot") or "",
            "粉丝画像截图": c.get("audience_profile_screenshot") or "",
            "笔记类型\n（视频or图文）": _note_type(c),
            "笔记类型（视频or图文）": _note_type(c),
            "合作形式": row.get("合作形式") or _note_type(c),
            "SOLO备注": row.get("SOLO备注") or "",
            "客户备注": row.get("客户备注") or "",
            "没选中的原因": row.get("没选中的原因") or "",
        }
    )
    return row


def standard_feishu_rows(
    project_id: str,
    statuses: list[str] | None = None,
    include_test_creators: bool = False,
) -> list[dict[str, Any]]:
    statuses = statuses or ["已通过", "备选"]
    creators = [
        c for c in list_creators(project_id)
        if c["status"] in statuses and (include_test_creators or not is_test_creator(c))
    ]
    rows = []
    for index, c in enumerate(creators, start=1):
        rows.append(
            _enrich_feishu_row(
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
                "曝光中位数（日常）": c.get("daily_exposure_median") or "",
                "阅读中位数（日常）": c.get("daily_read_median") or "",
                "互动中位数（日常）": c.get("daily_interaction_median") or "",
                "千赞笔记比例": c.get("daily_thousand_like_note_ratio") or "",
                "百赞笔记比例": c.get("daily_hundred_like_note_ratio") or "",
                "曝光中位数（合作）": c.get("cooperation_exposure_median") or "",
                "阅读中位数（合作）": c.get("cooperation_read_median") or "",
                "互动中位数（合作）": c.get("cooperation_interaction_median") or "",
                "外溢进店中位数": c.get("overflow_store_median") or "",
                "外溢进店单价": c.get("overflow_store_unit_price") or "",
                "图文预估CPM价格": c.get("image_cpm") or "",
                "图文预估阅读单价": c.get("image_read_unit_price") or "",
                "图文预估互动单价": c.get("image_interaction_unit_price") or "",
                "视频预估CPM价格": c.get("video_cpm") or "",
                "视频预估阅读单价": c.get("video_read_unit_price") or "",
                "视频预估互动单价": c.get("video_interaction_unit_price") or "",
                "活跃粉丝占比": c.get("active_fans_ratio") or "",
                "粉丝量变化幅度": c.get("fans_growth_ratio") or "",
                "阅读粉丝占比": c.get("read_fans_ratio") or "",
                "互动粉丝占比": c.get("interaction_fans_ratio") or "",
                "邀约48h回复率": c.get("reply_rate_48h") or "",
                "粉丝画像截图": c.get("audience_profile_screenshot") or "",
                "搜索+推荐占比": c.get("search_recommend_ratio") or "",
                "35岁以上粉丝占比": c.get("fans_35_plus_ratio") or "",
                "孩子年龄": c.get("child_age") or "",
                "孩子年级": c.get("child_grade") or "",
                "孩子性别": c.get("child_gender") or "",
                "家庭/教育话题点": c.get("topic_point") or "",
                "30天外溢进店成本": c.get("cost_30d") or "",
                "90天外溢进店成本": c.get("cost_90d") or "",
                "推荐等级": c.get("recommend_level") or "",
                "基础分": c.get("base_score") or "",
                "加成分": c.get("bonus_score") or "",
                "初筛总分": c.get("total_score") or "",
                "信息完整度": c.get("information_completeness") or "",
                "初筛等级": c.get("initial_tier") or c.get("tier") or "",
                "是否进入详情页补采": "是" if c.get("detail_collection_priority") in {"必须补采", "优先补采", "高潜补采"} else "否",
                "补采优先级": c.get("detail_collection_priority") or "",
                "合作方向": c.get("cooperation_direction") or c.get("portfolio_role") or "",
                "当前状态": c.get("status") or "",
                "备注": c.get("score_reason") or "",
            },
            c,
            index,
            )
        )
    return rows


def quality_feishu_rows(
    project_id: str,
    limit: int | None = None,
    min_score: float = 90,
    creator_ids: list[str] | None = None,
    include_test_creators: bool = False,
    rescore: bool = True,
) -> list[dict[str, Any]]:
    project = get_project(project_id) or {}
    target = int(project.get("target_qualified_creator_count") or 10)
    max_rows = limit or target
    wanted = {str(creator_id) for creator_id in creator_ids} if creator_ids else None
    if rescore:
        score_project(project_id, creator_ids=list(wanted) if wanted else None)
    creators = [
        c for c in list_creators(project_id)
        if (wanted is None or str(c.get("creator_id")) in wanted)
        and (include_test_creators or not is_test_creator(c))
        and (c.get("hard_filter_passed") == 1 or c.get("hard_filter_passed") is True)
        and float(c.get("total_score") or 0) >= min_score
        and c.get("recommend_level") in {"强推荐", "推荐", "备选"}
        and c.get("detail_collection_priority") in {"必须补采", "优先补采", "高潜补采", None, ""}
    ]
    rows = []
    for c in creators[:max_rows]:
        rows.append(
            _enrich_feishu_row(
            {
                "序号": len(rows) + 1,
                "账号类型": c.get("creator_type") or "",
                "蒲公英链接": c.get("pgy_url") or "",
                "达人昵称": c.get("nickname") or "",
                "粉丝数/w": round(float(c.get("followers_count") or 0) / 10000, 2) if c.get("followers_count") else "",
                "达人量级\n（1-5wtier3，5-10wtier2，大于10w tier1 ）": "tier1" if float(c.get("followers_count") or 0) > 100000 else "tier2" if float(c.get("followers_count") or 0) >= 50000 else "tier3",
                "赞藏数/w": "",
                "孩子年级": c.get("child_grade") or "",
                "孩子性别": c.get("child_gender") or "",
                "粉丝女性用户占比": "",
                "粉丝年龄25-34占比": "",
                "粉丝年龄34岁以上占比": f"{round(float(c.get('fans_35_plus_ratio') or 0) * 100)}%" if c.get("fans_35_plus_ratio") else "",
                "粉丝画像截图": c.get("audience_profile_screenshot") or "",
                "cpe（不超过20，最好10以下）": c.get("natural_cpe") or "",
                "推荐理由": c.get("score_reason") or "",
                "基础分": c.get("base_score") or "",
                "加成分": c.get("bonus_score") or "",
                "初筛总分": c.get("total_score") or "",
                "信息完整度": c.get("information_completeness") or "",
                "初筛等级": c.get("initial_tier") or c.get("tier") or "",
                "补采优先级": c.get("detail_collection_priority") or "",
                "合作方向": c.get("cooperation_direction") or c.get("portfolio_role") or "",
                "平台报价": c.get("quote_price") or "",
                "合作价格（含服务费）": c.get("quote_price") or "",
                "合作形式": "合作笔记",
                "品牌反馈": "优质候选",
                "品牌备注": f"评分 {c.get('total_score')}，{c.get('recommend_level')}",
                "达人反馈": "",
            },
            c,
            len(rows) + 1,
            )
        )
    return rows
