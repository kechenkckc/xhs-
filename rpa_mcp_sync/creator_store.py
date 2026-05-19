from __future__ import annotations

import csv
import json
import os
import re
import shutil
import sqlite3
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime
from pathlib import Path
from typing import Any

from .config_store import ROOT
from .llm_config import chat_json

DB_PATH = ROOT / "runtime" / "tasks.db"
PROJECT_ID = "youdao_001"
PROJECT_NAME = "有道答疑笔5-6月合作"
_SCORING_BENCHMARK_CACHE: ContextVar[dict[tuple[float, float, int], dict[str, Any] | None] | None] = ContextVar(
    "_SCORING_BENCHMARK_CACHE",
    default=None,
)
_PROJECT_SCREENING_PLAN_CACHE: ContextVar[dict[str, dict[str, Any]] | None] = ContextVar(
    "_PROJECT_SCREENING_PLAN_CACHE",
    default=None,
)


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)) or default)
    except (TypeError, ValueError):
        return default


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
  pool_stage TEXT DEFAULT '筛选工作台',
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
  detail_collection TEXT DEFAULT '',
  progress_stage TEXT DEFAULT '',
  progress_message TEXT DEFAULT ''
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

CREATE TABLE IF NOT EXISTS pgy_filter_whitelist (
  whitelist_id TEXT PRIMARY KEY,
  source TEXT NOT NULL,
  field TEXT NOT NULL,
  value TEXT NOT NULL,
  parent_value TEXT DEFAULT '',
  level INTEGER DEFAULT 1,
  control_type TEXT DEFAULT '',
  is_active INTEGER DEFAULT 1,
  captured_at TEXT DEFAULT '',
  raw_payload TEXT DEFAULT '{}',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE(source, field, value, parent_value)
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

CREATE TABLE IF NOT EXISTS project_handoffs (
  handoff_id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  from_role TEXT NOT NULL,
  to_role TEXT NOT NULL,
  title TEXT NOT NULL,
  summary TEXT DEFAULT '',
  payload TEXT DEFAULT '{}',
  status TEXT DEFAULT 'pending',
  created_by TEXT DEFAULT '用户',
  accepted_by TEXT DEFAULT '',
  return_reason TEXT DEFAULT '',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  accepted_at TEXT
);

CREATE TABLE IF NOT EXISTS project_tasks (
  task_id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  source_handoff_id TEXT DEFAULT '',
  title TEXT NOT NULL,
  description TEXT DEFAULT '',
  role TEXT DEFAULT 'executor',
  owner TEXT DEFAULT '',
  status TEXT DEFAULT 'todo',
  priority TEXT DEFAULT 'medium',
  due_at TEXT DEFAULT '',
  blocked_reason TEXT DEFAULT '',
  deliverables TEXT DEFAULT '[]',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  completed_at TEXT
);

CREATE TABLE IF NOT EXISTS project_assets (
  asset_id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  asset_type TEXT NOT NULL,
  title TEXT NOT NULL,
  payload TEXT DEFAULT '{}',
  created_by TEXT DEFAULT '用户',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
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

PROJECT_STATUSES = {"待补数据", "待审核", "已通过", "备选", "已驳回", "已写回飞书", "待建联", "已邀约", "合作中"}
SCREENING_STAGE = "筛选工作台"
POOL_STAGES = [SCREENING_STAGE, "已合作跟进中", "合格达人待合作", "待建联达人", "观察暂缓"]

MARKET_BENCHMARKS = [
    {"key": "0-3k", "min": 0, "max": 3000, "good_read": 800, "excellent_read": 1200, "quote_good_max": 300, "quote_high_max": 500, "cpm_good_max": 80, "cpc_good_max": 2.0, "cpe_good_max": 20},
    {"key": "3k-10k", "min": 3000, "max": 10000, "good_read": 1500, "excellent_read": 2500, "quote_good_max": 800, "quote_high_max": 1500, "cpm_good_max": 80, "cpc_good_max": 2.0, "cpe_good_max": 20},
    {"key": "1w-5w", "min": 10000, "max": 50000, "good_read": 3000, "excellent_read": 6000, "quote_good_max": 2500, "quote_high_max": 5000, "cpm_good_max": 100, "cpc_good_max": 2.0, "cpe_good_max": 20},
    {"key": "5w-10w", "min": 50000, "max": 100000, "good_read": 6000, "excellent_read": 10000, "quote_good_max": 8000, "quote_high_max": 15000, "cpm_good_max": 120, "cpc_good_max": 2.5, "cpe_good_max": 25},
    {"key": "10w+", "min": 100000, "max": 10**12, "good_read": 10000, "excellent_read": 20000, "quote_good_max": 20000, "quote_high_max": 50000, "cpm_good_max": 150, "cpc_good_max": 3.0, "cpe_good_max": 30},
]


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
            "progress_stage": "TEXT DEFAULT ''",
            "progress_message": "TEXT DEFAULT ''",
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
            "已开启合格达人详情完善后自动写回" if auto_writeback_enabled else "已关闭自动写回，改为手动批量写回",
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


INVALID_CREATOR_TYPE_PATTERNS = [
    "获赞",
    "收藏",
    "邀约",
    "合作报价",
    "一口价",
    "相似的博主",
    "查看更多",
    "粉丝数",
    "阅读中位数",
    "互动中位数",
    "曝光中位数",
]


def sanitize_creator_type(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    compact = re.sub(r"\s+", "", text)
    if len(compact) > 36:
        return ""
    if any(pattern in compact for pattern in INVALID_CREATOR_TYPE_PATTERNS):
        return ""
    if re.search(r"[¥￥]", compact):
        return ""
    if re.search(r"(?:^|/)\d+(?:\.\d+)?(?:w|W|万|%)?(?:/|$)", compact):
        return ""
    return compact


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


def _parse_payload_json(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _audience_distribution_payload(payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    raw = _parse_payload_json(payload.get("raw_payload"))
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
    creator_type = sanitize_creator_type(payload.get("creator_type") or payload.get("达人类型"))
    return {
        "creator_id": str(payload.get("creator_id") or payload.get("达人ID") or uuid.uuid4()),
        "project_id": project_id,
        "source": payload.get("source") or "manual",
        "xiaohongshu_id": payload.get("xiaohongshu_id") or payload.get("小红书号") or "",
        "pgy_blogger_id": payload.get("pgy_blogger_id") or "",
        "pgy_url": payload.get("pgy_url") or payload.get("蒲公英链接") or "",
        "nickname": payload.get("nickname") or payload.get("达人昵称") or "",
        "creator_type": creator_type,
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
    if number >= 95:
        return "S"
    if number >= 80:
        return "A"
    if number >= 75:
        return "B+"
    if number >= 70:
        return "B"
    return "C"


def stage_from_status(status: str | None, score: Any = None) -> str:
    if status in {"待补数据", "待审核", "人工复核", None, ""}:
        return SCREENING_STAGE
    if status in {"已驳回", "默认淘汰"}:
        return "观察暂缓"
    if status in {"已写回飞书", "合作中"}:
        return "已合作跟进中"
    if status in {"已通过", "备选"}:
        return "合格达人待合作"
    if status in {"待建联", "已邀约"}:
        return "待建联达人"
    return SCREENING_STAGE


def status_from_stage(stage: str) -> str:
    return {
        SCREENING_STAGE: "待审核",
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
    if creator.get("nickname") and (creator.get("pgy_url") or creator.get("pgy_blogger_id") or creator.get("xiaohongshu_id")):
        row = conn.execute(
            """
            SELECT creator_id FROM creators
            WHERE project_id=? AND nickname=? AND creator_id LIKE 'pgy:list:%'
            AND COALESCE(pgy_url, '')=''
            ORDER BY updated_at DESC
            LIMIT 1
            """,
            (creator["project_id"], creator["nickname"]),
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
        log(conn, project_id, "creator", action, creator.get("nickname") or creator_id, "系统", "候选达人已进入筛选工作台", "success")
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
        candidates = conn.execute("SELECT COUNT(*) AS count FROM project_creators WHERE project_id=?", (project["project_id"],)).fetchone()["count"]
        if not candidates:
            candidates = conn.execute("SELECT COUNT(*) AS count FROM creators WHERE project_id=?", (project["project_id"],)).fetchone()["count"]
        pool = conn.execute(
            "SELECT COUNT(*) AS count FROM project_creators WHERE project_id=? AND pool_stage<>?",
            (project["project_id"], SCREENING_STAGE),
        ).fetchone()["count"]
        qualified = conn.execute(
            "SELECT COUNT(*) AS count FROM project_creators WHERE project_id=? AND review_status IN ('已通过','已写回飞书','合作中')",
            (project["project_id"],),
        ).fetchone()["count"]
    target = project.get("target_qualified_creator_count") or 10
    project["screening_candidate_count"] = candidates
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
            for row in rows:
                row["creator_type"] = sanitize_creator_type(row.get("creator_type"))
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
        legacy_rows = rows_dict(conn.execute(legacy_sql, legacy_params).fetchall())
        for row in legacy_rows:
            row["creator_type"] = sanitize_creator_type(row.get("creator_type"))
        return legacy_rows


def creator_quality_summary(project_id: str) -> dict[str, Any]:
    creators = list_creators(project_id)

    def present(value: Any) -> bool:
        return bool(str(value or "").strip())

    missing_pgy = [item for item in creators if not present(item.get("pgy_url"))]
    missing_xhs = [item for item in creators if not present(item.get("xiaohongshu_id"))]
    missing_pgy_id = [item for item in creators if not present(item.get("pgy_blogger_id"))]
    fallback_rows = [item for item in creators if str(item.get("creator_id") or "").startswith("pgy:list:")]
    fallback_without_link = [item for item in fallback_rows if not present(item.get("pgy_url"))]
    unscored = [item for item in creators if item.get("total_score") in (None, "")]
    detail_needed = [item for item in creators if needs_detail_completion(item)]

    def sample(items: list[dict[str, Any]], limit: int = 10) -> list[dict[str, Any]]:
        return [
            {
                "creator_id": item.get("creator_id"),
                "nickname": item.get("nickname"),
                "pgy_url": item.get("pgy_url") or "",
                "xiaohongshu_id": item.get("xiaohongshu_id") or "",
                "pgy_blogger_id": item.get("pgy_blogger_id") or "",
                "source": item.get("source") or "",
            }
            for item in items[:limit]
        ]

    total = len(creators)
    return {
        "project_id": project_id,
        "total": total,
        "pgy_url": {
            "present": total - len(missing_pgy),
            "missing": len(missing_pgy),
            "missing_rate": round(len(missing_pgy) / total, 4) if total else 0,
        },
        "xiaohongshu_id": {
            "present": total - len(missing_xhs),
            "missing": len(missing_xhs),
            "missing_rate": round(len(missing_xhs) / total, 4) if total else 0,
        },
        "pgy_blogger_id": {
            "present": total - len(missing_pgy_id),
            "missing": len(missing_pgy_id),
            "missing_rate": round(len(missing_pgy_id) / total, 4) if total else 0,
        },
        "fallback_rows": {
            "total": len(fallback_rows),
            "missing_pgy_url": len(fallback_without_link),
        },
        "scores": {
            "unscored": len(unscored),
            "scored": total - len(unscored),
        },
        "detail_completion": {
            "needed": len(detail_needed),
            "needed_rate": round(len(detail_needed) / total, 4) if total else 0,
            "sample": [
                {
                    "creator_id": item.get("creator_id"),
                    "nickname": item.get("nickname"),
                    "total_score": item.get("total_score"),
                    "initial_tier": item.get("initial_tier") or item.get("tier") or "",
                    "needs": detail_completion_actionable_needs(item),
                    "missing_fields": detail_completion_actionable_missing_fields(item),
                }
                for item in sorted(detail_needed, key=lambda c: parse_number(c.get("total_score")) or 0, reverse=True)[:10]
            ],
        },
        "samples": {
            "missing_pgy_url": sample(missing_pgy),
            "fallback_without_link": sample(fallback_without_link),
        },
    }


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
            stage = SCREENING_STAGE
        groups[stage].append(creator)
    for items in groups.values():
        items.sort(key=lambda item: float(item.get("total_score") or 0), reverse=True)
    pool_creators = [item for stage, items in groups.items() if stage != SCREENING_STAGE for item in items]
    stats = {
        "total": len(pool_creators),
        "screening": len(groups[SCREENING_STAGE]),
        "avg_score": round(sum(float(item.get("total_score") or 0) for item in pool_creators) / len(pool_creators), 2) if pool_creators else 0,
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
    score = parse_number(total_score) or 0
    if score >= 95:
        return "S"
    if score >= 80:
        return "A"
    if score >= 75:
        return "B+"
    if score >= 70:
        return "B"
    return "C"


def _detail_collection_priority(total_score: Any, bonus_score: Any, hard_pass: bool = True) -> str:
    if not hard_pass:
        return "数据暂缓"
    score = parse_number(total_score) or 0
    bonus = parse_number(bonus_score) or 0
    if score >= 95:
        return "最高优先级"
    if score >= 80:
        return "高优先级"
    if score >= 75:
        return "中高优先级"
    if score >= 70:
        return "中优先级"
    return "低优先级"


def _recommend_level(total_score: Any, hard_pass: bool = True) -> str:
    if not hard_pass:
        return "待复核"
    score = parse_number(total_score) or 0
    if score >= 95:
        return "强推荐"
    if score >= 80:
        return "推荐"
    if score >= 70:
        return "备选"
    return "不推荐"


DETAIL_PRIORITY_HIGH_VALUES = {"必须完善", "优先完善", "高潜完善", "最高优先级", "高优先级", "中高优先级", "中优先级"}
DETAIL_COMPLETION_PRIORITY_VALUES = {"必须完善", "优先完善", "高潜完善", "最高优先级", "高优先级", "中高优先级"}
DETAIL_COMPLETION_ACTIONABLE_FIELDS = {"fans_35_plus_ratio", "education_context", "note_cases", "detail_page_evidence"}
DETAIL_COMPLETION_FIELD_NEED_LABELS = {
    "fans_35_plus_ratio": "缺35岁以上粉丝占比",
    "education_context": "缺孩子年龄/年级/教育话题",
    "note_cases": "缺近期/合作笔记案例",
    "detail_page_evidence": "缺达人详情页证据",
}


def detail_completion_needs(creator: dict[str, Any]) -> list[str]:
    needs: list[str] = []

    def positive(*keys: str) -> bool:
        return any((parse_number(creator.get(key)) or 0) > 0 for key in keys)

    def present(*keys: str) -> bool:
        return any(str(creator.get(key) or "").strip() for key in keys)

    if ratio(creator.get("fans_35_plus_ratio")) is None:
        needs.append("缺35岁以上粉丝占比")
    if not positive(
        "daily_read_median",
        "image_daily_read_median",
        "video_daily_read_median",
        "cooperation_read_median",
    ):
        needs.append("缺有效阅读中位数")
    if not positive(
        "daily_interaction_median",
        "image_daily_interaction_median",
        "video_daily_interaction_median",
        "cooperation_interaction_median",
    ):
        needs.append("缺有效互动中位数")
    if not positive("image_cpm", "video_cpm", "image_read_unit_price", "video_read_unit_price", "image_interaction_unit_price", "video_interaction_unit_price"):
        needs.append("缺有效CPM/CPC/CPE")
    if not present("child_age", "child_grade", "topic_point"):
        needs.append("缺孩子年龄/年级/教育话题")

    raw_payload = _parse_payload_json(creator.get("raw_payload"))
    detail = raw_payload.get("detail") if isinstance(raw_payload, dict) else None
    summary = raw_payload.get("detail_collection_summary") if isinstance(raw_payload, dict) else None
    if not isinstance(detail, dict) and not isinstance(summary, dict):
        needs.append("缺达人详情页证据")
    if not _collect_note_cases_from_payload(raw_payload):
        needs.append("缺近期/合作笔记案例")
    return list(dict.fromkeys(needs))


def detail_completion_missing_fields(creator: dict[str, Any]) -> list[str]:
    fields: list[str] = []
    if ratio(creator.get("fans_35_plus_ratio")) is None:
        fields.append("fans_35_plus_ratio")
    for label, keys in {
        "read_median": ("daily_read_median", "image_daily_read_median", "video_daily_read_median", "cooperation_read_median"),
        "interaction_median": ("daily_interaction_median", "image_daily_interaction_median", "video_daily_interaction_median", "cooperation_interaction_median"),
        "cost_efficiency": ("image_cpm", "video_cpm", "image_read_unit_price", "video_read_unit_price", "image_interaction_unit_price", "video_interaction_unit_price"),
    }.items():
        if not any((parse_number(creator.get(key)) or 0) > 0 for key in keys):
            fields.append(label)
    if not any(str(creator.get(key) or "").strip() for key in ("child_age", "child_grade", "topic_point")):
        fields.append("education_context")
    raw_payload = _parse_payload_json(creator.get("raw_payload"))
    if not _collect_note_cases_from_payload(raw_payload):
        fields.append("note_cases")
    if "缺达人详情页证据" in detail_completion_needs(creator):
        fields.append("detail_page_evidence")
    return fields


def detail_completion_actionable_missing_fields(creator: dict[str, Any]) -> list[str]:
    return [field for field in detail_completion_missing_fields(creator) if field in DETAIL_COMPLETION_ACTIONABLE_FIELDS]


def detail_completion_actionable_needs(creator: dict[str, Any]) -> list[str]:
    return [DETAIL_COMPLETION_FIELD_NEED_LABELS[field] for field in detail_completion_actionable_missing_fields(creator)]


def _has_detail_completion_link(creator: dict[str, Any]) -> bool:
    for key in ("pgy_url", "profile_url"):
        value = str(creator.get(key) or "").strip()
        if "/blogger-detail/" in value:
            return True
    return False


def needs_detail_completion(creator: dict[str, Any]) -> bool:
    actionable_fields = detail_completion_actionable_missing_fields(creator)
    if not actionable_fields:
        return False
    if not _has_detail_completion_link(creator):
        return False
    score = parse_number(creator.get("total_score")) or 0
    hard_pass = creator.get("hard_filter_passed") in {1, True, "1"}
    high_priority = creator.get("detail_collection_priority") in DETAIL_COMPLETION_PRIORITY_VALUES
    return hard_pass and (score >= 75 or high_priority)


def cleanup_project_creator_duplicates(project_id: str) -> dict[str, Any]:
    creators = list_creators(project_id)
    identity_groups: dict[str, list[dict[str, Any]]] = {}

    def add_group(key: str, creator: dict[str, Any]) -> None:
        identity_groups.setdefault(key, []).append(creator)

    for creator in creators:
        pgy_url = str(creator.get("pgy_url") or "").strip()
        xhs_id = str(creator.get("xiaohongshu_id") or "").strip()
        blogger_id = str(creator.get("pgy_blogger_id") or "").strip()
        if xhs_id:
            add_group(f"xiaohongshu_id:{xhs_id}", creator)
        if blogger_id:
            add_group(f"pgy_blogger_id:{blogger_id}", creator)
        if pgy_url and "/blogger-detail/" in pgy_url:
            add_group(f"pgy_url:{pgy_url}", creator)

    def canonical_rank(creator: dict[str, Any]) -> tuple[float, float, float, float]:
        creator_id = str(creator.get("creator_id") or "")
        list_penalty = 0.0 if not creator_id.startswith("pgy:list:") else 1.0
        info_score = parse_number(creator.get("information_completeness")) or 0
        total_score = parse_number(creator.get("total_score")) or 0
        actionable_count = len(detail_completion_actionable_missing_fields(creator))
        return (list_penalty, -info_score, -total_score, actionable_count)

    merged_pairs: list[dict[str, Any]] = []
    deleted_ids: list[str] = []
    touched_groups = 0
    removed_ids: set[str] = set()
    init_db()
    with connect() as conn:
        for grouped in identity_groups.values():
            unique_ids = {
                str(item.get("creator_id") or "")
                for item in grouped
                if str(item.get("creator_id") or "") not in removed_ids
            }
            if len(unique_ids) <= 1:
                continue
            touched_groups += 1
            ranked = sorted(
                [item for item in grouped if str(item.get("creator_id") or "") not in removed_ids],
                key=canonical_rank,
            )
            canonical = ranked[0]
            duplicates = ranked[1:]
            canonical_id = str(canonical.get("creator_id") or "")
            for duplicate in duplicates:
                duplicate_id = str(duplicate.get("creator_id") or "")
                if not duplicate_id or duplicate_id == canonical_id:
                    continue
                if duplicate_id in removed_ids:
                    continue
                merged_pairs.append(
                    {
                        "canonical_creator_id": canonical_id,
                        "duplicate_creator_id": duplicate_id,
                        "canonical_nickname": canonical.get("nickname") or "",
                        "duplicate_nickname": duplicate.get("nickname") or "",
                    }
                )
                conn.execute("DELETE FROM project_creators WHERE project_id=? AND creator_id=?", (project_id, duplicate_id))
                conn.execute("DELETE FROM screening_reviews WHERE creator_id=?", (duplicate_id,))
                conn.execute("DELETE FROM creator_scores WHERE creator_id=?", (duplicate_id,))
                conn.execute("DELETE FROM creator_metrics WHERE creator_id=?", (duplicate_id,))
                conn.execute("DELETE FROM creator_metrics_current WHERE creator_id=?", (duplicate_id,))
                conn.execute("DELETE FROM creator_metrics_history WHERE project_id=? AND creator_id=?", (project_id, duplicate_id))
                conn.execute("DELETE FROM feishu_sync_state WHERE project_id=? AND creator_id=?", (project_id, duplicate_id))
                conn.execute("DELETE FROM creators WHERE project_id=? AND creator_id=?", (project_id, duplicate_id))
                deleted_ids.append(duplicate_id)
                removed_ids.add(duplicate_id)
        if deleted_ids:
            log(
                conn,
                project_id,
                "creator",
                "清理重复达人",
                PROJECT_NAME,
                "系统",
                f"清理 {len(deleted_ids)} 条项目内重复达人记录，涉及 {touched_groups} 组",
                "success",
            )
    return {
        "project_id": project_id,
        "duplicate_groups": touched_groups,
        "deleted_count": len(deleted_ids),
        "deleted_creator_ids": deleted_ids,
        "merged_pairs": merged_pairs,
    }


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


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _collect_note_cases_from_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    cases: list[dict[str, Any]] = []
    for key in ("recent_note_cases", "recent_notes", "cooperation_note_cases", "note_cases", "notes"):
        cases.extend(item for item in _as_list(payload.get(key)) if isinstance(item, dict))
    for page in _as_list(payload.get("cooperation_note_case_pages")):
        if isinstance(page, dict):
            cases.extend(item for item in _as_list(page.get("cases")) if isinstance(item, dict))
    for key in ("detail", "raw_payload"):
        nested = payload.get(key)
        if isinstance(nested, dict):
            cases.extend(_collect_note_cases_from_payload(nested))
    return cases


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = round((len(ordered) - 1) * percentile)
    return ordered[max(0, min(len(ordered) - 1, index))]


def _market_benchmark_for_followers(followers: Any) -> dict[str, Any]:
    fans = parse_number(followers) or 0
    for item in MARKET_BENCHMARKS:
        if item["min"] < fans <= item["max"] or (fans == 0 and item["min"] == 0):
            return dict(item)
    return dict(MARKET_BENCHMARKS[-1])


@contextmanager
def _scoring_benchmark_cache() -> Any:
    token = _SCORING_BENCHMARK_CACHE.set({})
    try:
        yield
    finally:
        _SCORING_BENCHMARK_CACHE.reset(token)


@contextmanager
def _scoring_batch_context() -> Any:
    benchmark_token = _SCORING_BENCHMARK_CACHE.set({})
    project_token = _PROJECT_SCREENING_PLAN_CACHE.set({})
    try:
        yield
    finally:
        _PROJECT_SCREENING_PLAN_CACHE.reset(project_token)
        _SCORING_BENCHMARK_CACHE.reset(benchmark_token)


def _read_reference_from_creator(creator: dict[str, Any]) -> float | None:
    values = [
        parse_number(creator.get("cooperation_read_median")),
        parse_number(creator.get("daily_read_median")),
        parse_number(creator.get("image_daily_read_median")),
        parse_number(creator.get("video_daily_read_median")),
    ]
    values = [value for value in values if value is not None and value > 0]
    return max(values) if values else None


def _exposure_reference_from_creator(creator: dict[str, Any]) -> float | None:
    values = [
        parse_number(creator.get("cooperation_exposure_median")),
        parse_number(creator.get("daily_exposure_median")),
        parse_number(creator.get("image_daily_exposure_median")),
        parse_number(creator.get("video_daily_exposure_median")),
    ]
    values = [value for value in values if value is not None and value > 0]
    return max(values) if values else None


def _first_number(*values: Any, positive: bool = False) -> float | None:
    for value in values:
        number = parse_number(value)
        if number is not None and (not positive or number > 0):
            return number
    return None


def _efficiency_metrics(creator: dict[str, Any], read_reference: Any | None = None) -> dict[str, float | None]:
    quote = parse_number(creator.get("quote_price"))
    read = parse_number(read_reference) if read_reference is not None else _read_reference_from_creator(creator)
    exposure = _exposure_reference_from_creator(creator)
    cpm = _first_number(creator.get("image_cpm"), creator.get("video_cpm"), positive=True)
    cpc = _first_number(creator.get("natural_cpc"), creator.get("image_read_unit_price"), creator.get("video_read_unit_price"), positive=True)
    cpe = _first_number(creator.get("natural_cpe"), creator.get("image_interaction_unit_price"), creator.get("video_interaction_unit_price"), positive=True)
    estimated_cpm = quote / exposure * 1000 if quote is not None and exposure else None
    estimated_cpc = quote / read if quote is not None and read else None
    return {
        "quote": quote,
        "read": read,
        "exposure": exposure,
        "cpm": cpm,
        "estimated_cpm": estimated_cpm,
        "cpc": cpc,
        "cpe": cpe,
        "estimated_cpc": estimated_cpc,
    }


def _db_benchmark_for_followers(followers: Any, min_samples: int = 8) -> dict[str, Any] | None:
    market = _market_benchmark_for_followers(followers)
    cache = _SCORING_BENCHMARK_CACHE.get()
    cache_key = (float(market["min"]), float(market["max"]), int(min_samples))
    if cache is not None and cache_key in cache:
        cached = cache[cache_key]
        return dict(cached) if cached else None
    try:
        with connect() as conn:
            rows = rows_dict(
                conn.execute(
                    """
                    SELECT quote_price, natural_cpc, natural_cpe, image_cpm, video_cpm,
                           image_read_unit_price, video_read_unit_price, image_interaction_unit_price, video_interaction_unit_price,
                           daily_read_median, image_daily_read_median, video_daily_read_median, cooperation_read_median
                    FROM creator_metrics_current
                    WHERE followers_count > ? AND followers_count <= ?
                    """,
                    (market["min"], market["max"]),
                ).fetchall()
            )
    except Exception:
        if cache is not None:
            cache[cache_key] = None
        return None
    reads: list[float] = []
    quotes: list[float] = []
    cpms: list[float] = []
    cpcs: list[float] = []
    cpes: list[float] = []
    for row in rows:
        read = _read_reference_from_creator(row)
        quote = parse_number(row.get("quote_price"))
        efficiency = _efficiency_metrics(row, read)
        if read is not None:
            reads.append(read)
        if quote is not None:
            quotes.append(quote)
        if efficiency["cpm"] is not None:
            cpms.append(efficiency["cpm"])
        if efficiency["cpc"] is not None:
            cpcs.append(efficiency["cpc"])
        elif efficiency["estimated_cpc"] is not None:
            cpcs.append(efficiency["estimated_cpc"])
        if efficiency["cpe"] is not None:
            cpes.append(efficiency["cpe"])
    if len(reads) < min_samples and len(quotes) < min_samples:
        if cache is not None:
            cache[cache_key] = None
        return None
    benchmark = dict(market)
    benchmark["source"] = "database"
    benchmark["sample_count"] = len(rows)
    if len(reads) >= min_samples:
        benchmark["good_read"] = round(_percentile(reads, 0.75) or benchmark["good_read"], 2)
        benchmark["excellent_read"] = round(max(benchmark["good_read"], _percentile(reads, 0.9) or benchmark["excellent_read"]), 2)
    if len(quotes) >= min_samples:
        quote_p50 = _percentile(quotes, 0.5) or benchmark["quote_good_max"]
        quote_p75 = _percentile(quotes, 0.75) or benchmark["quote_good_max"]
        benchmark["quote_good_max"] = round(min(benchmark["quote_good_max"], max(quote_p50, quote_p75)), 2)
        benchmark["quote_high_max"] = round(min(benchmark["quote_high_max"], max(benchmark["quote_good_max"] * 2, quote_p75 * 1.5)), 2)
    if len(cpms) >= min_samples:
        benchmark["cpm_good_max"] = round(min(benchmark["cpm_good_max"], _percentile(cpms, 0.5) or benchmark["cpm_good_max"]), 2)
    if len(cpcs) >= min_samples:
        benchmark["cpc_good_max"] = round(min(benchmark["cpc_good_max"], _percentile(cpcs, 0.5) or benchmark["cpc_good_max"]), 2)
    if len(cpes) >= min_samples:
        benchmark["cpe_good_max"] = round(min(benchmark["cpe_good_max"], _percentile(cpes, 0.5) or benchmark["cpe_good_max"]), 2)
    if cache is not None:
        cache[cache_key] = dict(benchmark)
    return benchmark


def _scoring_benchmark_for_creator(creator: dict[str, Any]) -> dict[str, Any]:
    followers = creator.get("followers_count")
    benchmark = _db_benchmark_for_followers(followers)
    if benchmark:
        return benchmark
    market = _market_benchmark_for_followers(followers)
    market["source"] = "market_seed"
    market["sample_count"] = 0
    return market


def _expected_good_read(followers: Any, benchmark: dict[str, Any] | None = None) -> float:
    if benchmark:
        return float(benchmark.get("good_read") or 1000)
    return float(_market_benchmark_for_followers(followers).get("good_read") or 1000)


def _efficiency_profile(creator: dict[str, Any], benchmark: dict[str, Any], read_reference: Any | None = None) -> dict[str, Any]:
    metrics = _efficiency_metrics(creator, read_reference)
    cpm = metrics["cpm"] if metrics["cpm"] is not None else metrics["estimated_cpm"]
    cpc = metrics["cpc"] if metrics["cpc"] is not None else metrics["estimated_cpc"]
    cpe = metrics["cpe"]
    quote = metrics["quote"]
    quote_good_max = float(benchmark.get("quote_good_max") or 0)
    quote_high_max = float(benchmark.get("quote_high_max") or quote_good_max * 2 or 1)
    cpm_good_max = float(benchmark.get("cpm_good_max") or 100)
    cpc_good_max = float(benchmark.get("cpc_good_max") or 2)
    cpe_good_max = float(benchmark.get("cpe_good_max") or 20)
    followers_missing = parse_number(creator.get("followers_count")) is None

    score = 10.0
    reasons: list[str] = []
    good_efficiency = False
    poor_efficiency = False

    if quote is not None and followers_missing:
        reasons.append(f"报价{quote:.0f}待结合粉丝T级与效果容量判断")
    elif quote is not None:
        if quote <= quote_good_max:
            reasons.append(f"报价{quote:.0f}低于量级合理线{quote_good_max:.0f}")
        elif cpm is not None or cpc is not None or cpe is not None:
            reasons.append(f"报价{quote:.0f}需结合效率判断")
        elif quote > quote_high_max:
            score -= 5
            poor_efficiency = True
            reasons.append(f"报价{quote:.0f}高于量级高价线{quote_high_max:.0f}")
        else:
            score -= 2
            reasons.append(f"报价{quote:.0f}高于量级合理线{quote_good_max:.0f}")

    if cpm is not None:
        if cpm <= cpm_good_max:
            score += 2
            good_efficiency = True
            reasons.append(f"CPM {cpm:.1f} 达标")
        elif cpm <= cpm_good_max * 1.5:
            score -= 1
            reasons.append(f"CPM {cpm:.1f} 略高")
        else:
            score -= 5
            poor_efficiency = True
            reasons.append(f"CPM {cpm:.1f} 偏高")

    if cpc is not None:
        if cpc <= cpc_good_max:
            score += 2
            good_efficiency = True
            reasons.append(f"CPC {cpc:.2f} 达标")
        elif cpc <= cpc_good_max * 1.5:
            score -= 1
            reasons.append(f"CPC {cpc:.2f} 略高")
        else:
            score -= 4
            poor_efficiency = True
            reasons.append(f"CPC {cpc:.2f} 偏高")

    if cpe is not None:
        if cpe <= cpe_good_max:
            score += 1
            good_efficiency = True
            reasons.append(f"CPE {cpe:.1f} 达标")
        elif cpe <= cpe_good_max * 1.5:
            score -= 1
            reasons.append(f"CPE {cpe:.1f} 略高")
        else:
            score -= 3
            poor_efficiency = True
            reasons.append(f"CPE {cpe:.1f} 偏高")

    if quote is not None and quote > quote_good_max and good_efficiency:
        reasons.append("报价偏高但效率指标可接受")
    return {
        **metrics,
        "effective_cpm": cpm,
        "effective_cpc": cpc,
        "score": round(max(0, min(12, score)), 2),
        "good_efficiency": good_efficiency,
        "poor_efficiency": poor_efficiency,
        "reasons": reasons,
    }


def _budget_effect_profile(creator: dict[str, Any], benchmark: dict[str, Any] | None = None) -> dict[str, Any]:
    benchmark = benchmark or _scoring_benchmark_for_creator(creator)
    metrics = _efficiency_metrics(creator)
    quote = metrics["quote"]
    cpm = metrics["cpm"] if metrics["cpm"] is not None else metrics["estimated_cpm"]
    cpc = metrics["cpc"] if metrics["cpc"] is not None else metrics["estimated_cpc"]
    cpe = metrics["cpe"]
    estimated_exposure = quote / cpm * 1000 if quote is not None and cpm else None
    estimated_read = quote / cpc if quote is not None and cpc else None
    estimated_interaction = quote / cpe if quote is not None and cpe else None
    return {
        "quote": quote,
        "effective_cpm": cpm,
        "effective_cpc": cpc,
        "effective_cpe": cpe,
        "estimated_exposure": round(estimated_exposure, 2) if estimated_exposure is not None else None,
        "estimated_read": round(estimated_read, 2) if estimated_read is not None else None,
        "estimated_interaction": round(estimated_interaction, 2) if estimated_interaction is not None else None,
        "observed_30d_exposure_median": _exposure_reference_from_creator(creator),
        "observed_30d_read_median": _read_reference_from_creator(creator),
        "observed_30d_interaction_median": _first_number(
            creator.get("cooperation_interaction_median"),
            creator.get("daily_interaction_median"),
            creator.get("image_daily_interaction_median"),
            creator.get("video_daily_interaction_median"),
        ),
        "tier_benchmark": {
            "tier_key": benchmark.get("key"),
            "expected_read": benchmark.get("good_read"),
            "excellent_read": benchmark.get("excellent_read"),
            "quote_good_max": benchmark.get("quote_good_max"),
            "quote_high_max": benchmark.get("quote_high_max"),
            "cpm_good_max": benchmark.get("cpm_good_max"),
            "cpc_good_max": benchmark.get("cpc_good_max"),
            "cpe_good_max": benchmark.get("cpe_good_max"),
            "source": benchmark.get("source"),
            "sample_count": benchmark.get("sample_count"),
        },
    }


def _follower_scale_fit(followers: Any) -> float:
    fans = parse_number(followers)
    if fans is None:
        return 8
    if 3000 <= fans <= 100000:
        return 15
    if 1000 <= fans < 3000 or 100000 < fans <= 200000:
        return 12
    if 500 <= fans < 1000:
        return 8
    return 5


def _precision_fans_fit(creator: dict[str, Any]) -> tuple[float, bool]:
    fans35 = ratio(creator.get("fans_35_plus_ratio"))
    female = ratio(creator.get("female_fans_ratio"))
    text = _text_blob(creator)
    score = 8.0
    if fans35 is not None:
        score = 15 if fans35 >= 0.5 else 13 if fans35 >= 0.4 else 4
    if female is not None and female >= 0.65:
        score = min(15, score + 1)
    if _contains_any(text, ["妈妈", "家长", "宝妈", "陪读", "大孩", "小升初", "初中", "高中"]):
        score = min(15, score + 1)
    return round(score, 2), score >= 13


def _verticality_fit(creator: dict[str, Any]) -> tuple[float, float, bool]:
    text = _text_blob(creator)
    persona = 18
    if _contains_any(text, ["教育", "学习", "亲子", "家庭", "母婴", "成长", "知识", "教师", "老师", "测评", "生活方式"]):
        persona += 8
    if _contains_any(text, ["低质", "搬运", "无关", "娱乐八卦"]):
        persona -= 8
    persona = max(0, min(30, persona))

    content = 10
    if _contains_any(text, ["孩子", "家长", "妈妈", "爸爸", "小升初", "初中", "高中", "大孩", "升学", "备考"]):
        content += 7
    if _contains_any(text, ["使用场景", "学习场景", "真实家庭", "陪读", "作业"]):
        content += 3
    content = max(0, min(20, content))
    return persona, content, persona >= 24 and content >= 17


def _tag_direction_fit(creator: dict[str, Any]) -> dict[str, Any]:
    text = _text_blob(creator)
    raw_payload = _parse_payload_json(creator.get("raw_payload"))
    hint = ""
    if isinstance(raw_payload, dict):
        hint = str(raw_payload.get("cooperation_hint") or "")
    combined = f"{text} {hint}"
    strong_keywords = ["教育", "学习", "K12", "k12", "家庭教育", "小升初", "初中", "高中", "升学", "教辅", "答疑", "作业", "亲子大孩"]
    medium_keywords = ["亲子", "母婴", "家长", "妈妈", "爸爸", "孩子", "学生", "学习工具", "教育工具", "答疑工具", "测评", "好物"]
    weak_keywords = ["3C", "电器", "数码", "智能", "工具", "家居", "家装", "生活记录", "生活方式", "极简", "收纳", "日常", "中产", "家庭"]
    negative_keywords = ["美妆", "护肤", "穿搭", "娱乐", "八卦", "宠物", "美甲", "低幼", "孕期", "辅食"]
    matched: list[str] = []
    score = 6.0
    level = "weak"
    if _contains_any(combined, strong_keywords):
        matched.extend([keyword for keyword in strong_keywords if keyword in combined][:4])
        score = 15.0
        level = "strong"
    elif _contains_any(combined, medium_keywords):
        matched.extend([keyword for keyword in medium_keywords if keyword in combined][:4])
        score = 11.0
        level = "medium"
    elif _contains_any(combined, weak_keywords):
        matched.extend([keyword for keyword in weak_keywords if keyword in combined][:4])
        score = 8.0
        level = "weak"
    if _contains_any(combined, negative_keywords) and not _contains_any(combined, strong_keywords):
        matched.extend([keyword for keyword in negative_keywords if keyword in combined][:3])
        score = min(score, 4.0)
        level = "off"
    return {
        "score": round(max(0, min(15, score)), 2),
        "level": level,
        "matched": list(dict.fromkeys(matched)),
        "cooperation_hint": hint,
    }


def _execution_fit(creator: dict[str, Any]) -> tuple[float, list[str]]:
    score = 0.0
    reasons: list[str] = []
    if creator.get("pgy_url"):
        score += 2
    else:
        reasons.append("缺蒲公英链接")
    if parse_number(creator.get("quote_price")) is not None:
        score += 1.5
    else:
        reasons.append("报价缺失")
    reply = ratio(creator.get("reply_rate_48h"))
    if reply is not None:
        if reply >= 0.8:
            score += 2
            reasons.append("48h回复率优秀")
        elif reply >= 0.6:
            score += 1.5
            reasons.append("48h回复率达标")
        elif reply >= 0.4:
            score += 0.8
            reasons.append("48h回复率一般")
        else:
            reasons.append("48h回复率偏低")
    else:
        score += 1
        reasons.append("48h回复率未进入本轮数据")
    if parse_number(creator.get("followers_count")) is not None:
        score += 0.8
    if creator.get("avatar_url") or creator.get("xiaohongshu_id"):
        score += 0.7
    return round(max(0, min(5, score)), 2), reasons


def _recent_note_data_profile(creator: dict[str, Any]) -> dict[str, Any]:
    raw_payload = _parse_payload_json(creator.get("raw_payload"))
    note_cases = _collect_note_cases_from_payload(raw_payload)
    reads: list[float] = []
    interactions: list[float] = []
    for item in note_cases:
        read = parse_number(item.get("read_count") or item.get("readCount") or item.get("read"))
        if read is not None and read > 0:
            reads.append(read)
        interaction_values = [
            parse_number(item.get("like_count") or item.get("likeCount") or item.get("likes")),
            parse_number(item.get("save_count") or item.get("saveCount") or item.get("saves")),
            parse_number(item.get("comment_count") or item.get("commentCount") or item.get("comments")),
            parse_number(item.get("share_count") or item.get("shareCount") or item.get("shares")),
        ]
        interaction = sum(value for value in interaction_values if value is not None)
        if interaction:
            interactions.append(interaction)

    has_recent_notes = bool(reads)
    source = "recent_notes" if has_recent_notes else ""
    if not reads:
        for key in ("cooperation_read_median", "daily_read_median", "image_daily_read_median", "video_daily_read_median"):
            read = parse_number(creator.get(key))
            if read is not None and read > 0:
                reads.append(read)
        source = "median_metrics" if reads else ""
    if not interactions:
        for key in ("cooperation_interaction_median", "daily_interaction_median", "image_daily_interaction_median", "video_daily_interaction_median"):
            interaction = parse_number(creator.get(key))
            if interaction is not None and interaction > 0:
                interactions.append(interaction)

    followers = parse_number(creator.get("followers_count"))
    benchmark = _scoring_benchmark_for_creator(creator)
    expected = _expected_good_read(followers, benchmark)
    median_read = _median(reads)
    avg_read = round(sum(reads) / len(reads), 2) if reads else None
    max_read = max(reads) if reads else None
    avg_interaction = round(sum(interactions) / len(interactions), 2) if interactions else None
    read_fans_ratio = median_read / followers if median_read is not None and followers else None

    best_read = max(value for value in [median_read, avg_read, max_read] if value is not None) if reads else 0
    if not reads:
        data_score = 7.0
    elif median_read >= expected * 1.5 or avg_read >= expected * 1.5 or max_read >= expected * 2:
        data_score = 30.0
    elif median_read >= expected or avg_read >= expected or max_read >= expected * 1.5:
        data_score = 24.0
    elif median_read >= expected * 0.6 or avg_read >= expected * 0.6 or max_read >= expected:
        data_score = 16.0
    elif max_read >= expected * 0.5:
        data_score = 10.0
    else:
        data_score = 4.0
    if avg_interaction is not None and avg_interaction >= 50:
        data_score = min(30, data_score + 2)
    if source == "median_metrics":
        data_score = min(24, data_score)

    good_data = bool(reads) and data_score >= 24
    weak_recent_data = has_recent_notes and data_score < 16
    return {
        "source": source,
        "benchmark": benchmark,
        "has_recent_notes": has_recent_notes,
        "expected_read": expected,
        "median_read": median_read,
        "avg_read": avg_read,
        "max_read": max_read,
        "best_read": best_read,
        "avg_interaction": avg_interaction,
        "read_fans_ratio": read_fans_ratio,
        "data_score": round(data_score, 2),
        "good_data": good_data,
        "weak_recent_data": weak_recent_data,
    }


def _apply_quality_gate(total: float, profile: dict[str, Any], reasons: list[str], creator: dict[str, Any] | None = None, direction_profile: dict[str, Any] | None = None) -> float:
    efficiency = profile.get("efficiency") if isinstance(profile.get("efficiency"), dict) else {}
    if creator is not None:
        fans35 = ratio(creator.get("fans_35_plus_ratio"))
        if fans35 is not None and fans35 < 0.4 and total > 69:
            reasons.append("35岁以上粉丝占比低于40%，初评最高C档")
            return 69.0
        if fans35 is None and total > 94:
            reasons.append("缺少35岁以上粉丝占比，初评暂不进入S档")
            total = 94.0
    if efficiency.get("poor_efficiency") and total > 84:
        reasons.append("CPM/CPC/CPE效率偏差，高分封顶到A档观察")
        total = 84.0
    if profile["weak_recent_data"]:
        reasons.append("近期笔记阅读未达较好数据，高分封顶到B档")
        if total > 79:
            total = 79.0
    if profile.get("source") and not profile["good_data"] and total > 79:
        reasons.append("缺少较好阅读数据支撑，初筛最高B+档")
        total = 79.0
    if not profile.get("source") and total > 79:
        reasons.append("缺少阅读/互动核心数据，初筛最高B+档")
        total = 79.0
    if direction_profile and direction_profile.get("level") in {"weak", "off"} and total > 79:
        reasons.append("类目/标签仅弱相关，初筛最高B+档")
        total = 79.0
    return total


def score_values(creator: dict[str, Any]) -> dict[str, Any]:
    quote = creator.get("quote_price")
    fans35 = creator.get("fans_35_plus_ratio")
    cpc = creator.get("natural_cpc")
    cpe = creator.get("natural_cpe")
    search = creator.get("search_recommend_ratio")
    risk = str(creator.get("rate_limit_risk") or "")
    stability = str(creator.get("traffic_stability") or "")
    text = _text_blob(creator)
    data_profile = _recent_note_data_profile(creator)
    efficiency_profile = _efficiency_profile(creator, data_profile["benchmark"], data_profile.get("median_read") or data_profile.get("avg_read"))
    data_profile["efficiency"] = efficiency_profile

    hard_issues = []
    if quote is not None and quote > 20000:
        hard_issues.append("报价超过2万元")
    if fans35 is not None and fans35 < 0.4:
        hard_issues.append("35岁以上粉丝占比低于40%")
    if _contains_any(risk, ["高风险", "严重", "违规", "疑似限流"]):
        hard_issues.append("存在明确高风险信号")
    hard_pass = not hard_issues

    precision_fans, precise_fans = _precision_fans_fit(creator)
    audience_score = round(precision_fans / 15 * 25, 2)

    traffic = round(min(25, data_profile["data_score"] / 30 * 25), 2)
    if search is not None:
        traffic += 3 if search >= 0.55 else 2 if search >= 0.45 else 1 if search >= 0.4 else -4
    if _contains_any(stability, ["稳定", "良好"]):
        traffic += 1.5
    if _contains_any(stability, ["波动", "下滑", "异常"]) or _contains_any(risk, ["中风险", "限流"]):
        traffic -= 5
    traffic = max(0, min(25, traffic))

    efficiency = round(float(efficiency_profile["score"] or 0) / 12 * 25, 2)
    if cpc is not None:
        efficiency -= 5 if cpc >= 2 else 0
        efficiency += 2 if cpc < 1.5 else 0
    if cpe is not None:
        efficiency -= 6 if cpe >= 20 else 2 if cpe >= 10 else 0
        efficiency += 2 if cpe < 10 else 0
    cpe_efficiency = max(0, min(25, efficiency))

    direction_profile = _tag_direction_fit(creator)
    direction_score = float(direction_profile["score"])
    execution_score, execution_reasons = _execution_fit(creator)

    base = round(audience_score + traffic + cpe_efficiency + direction_score + execution_score, 2)

    bonus = 0.0
    bonus_reasons: list[str] = []
    if data_profile["good_data"] and precise_fans:
        bonus += 2
        bonus_reasons.append("人群画像与阅读数据同时达标")
    if efficiency_profile.get("good_efficiency") and data_profile["good_data"]:
        bonus += 2
        bonus_reasons.append("成本效率和流量质量同时较好")
    if direction_profile["level"] == "strong" and data_profile["good_data"]:
        bonus += 1
        bonus_reasons.append("强相关方向且数据有支撑")
    total = round(min(100, base + bonus), 2)
    completeness = _score_information_completeness(creator)
    tier = _initial_tier(total, hard_pass)
    priority = _detail_collection_priority(total, bonus, hard_pass)

    reasons: list[str] = []
    if hard_issues:
        reasons.extend(hard_issues)
    if fans35 is None:
        reasons.append("粉丝年龄画像未进入本轮数据判断")
    if cpc is None and cpe is None:
        reasons.append("CPC/CPE未进入本轮数据判断")
    if search is None:
        reasons.append("搜索+推荐占比未进入本轮数据判断")
    if efficiency_profile["reasons"]:
        reasons.append(f"效率判断：{'、'.join(efficiency_profile['reasons'][:4])}")
    if data_profile["source"]:
        reads = []
        if data_profile["median_read"] is not None:
            reads.append(f"中位阅读{data_profile['median_read']:.0f}")
        if data_profile["avg_read"] is not None:
            reads.append(f"均读{data_profile['avg_read']:.0f}")
        if data_profile["max_read"] is not None:
            reads.append(f"最高阅读{data_profile['max_read']:.0f}")
        reasons.append(f"近期/合作数据：{'、'.join(reads)}，达标线{data_profile['expected_read']:.0f}")
    else:
        reasons.append("近30天阅读数据未进入本轮数据判断")

    matched_tags = direction_profile.get("matched") or []
    if matched_tags:
        reasons.append(f"方向弱证据：{direction_profile['level']}，命中{'、'.join(matched_tags[:4])}")
    elif direction_profile.get("cooperation_hint"):
        reasons.append(f"期待合作行业：{direction_profile['cooperation_hint']}")
    if execution_reasons:
        reasons.append(f"执行确定性：{'、'.join(execution_reasons[:3])}")
    if data_profile["good_data"] and precise_fans and direction_profile["level"] in {"strong", "medium"}:
        reasons.append("A档候选依据：人群达标、阅读/互动有支撑、方向相关")
    total = round(_apply_quality_gate(total, data_profile, reasons, creator, direction_profile), 2)
    if hard_pass and total < 70 and not data_profile["weak_recent_data"] and not efficiency_profile["poor_efficiency"]:
        total = 70.0
        reasons.append("未发现已确认硬伤，数据证据不足时按B档观察，不因缺字段直接低分")
    tier = _initial_tier(total, hard_pass)
    priority = _detail_collection_priority(total, bonus, hard_pass)
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
        "budget_score": round(execution_score / 5 * 15, 2),
        "fans_score": round(audience_score / 25 * 5, 2),
        "cpe_score": round(cpe_efficiency / 25 * 20, 2),
        "traffic_score": round(traffic / 25 * 30, 2),
        "persona_score": round(direction_score / 15 * 20, 2),
        "content_score": round(bonus / 5 * 10, 2),
        "hard_filter_passed": 1 if hard_pass else 0,
        "recommend_level": level,
        "score_reason": "；".join(reasons),
        "cooperation_direction": _default_cooperation_direction(creator, level),
    }


def _project_screening_plan(project_id: str) -> dict[str, Any]:
    cache = _PROJECT_SCREENING_PLAN_CACHE.get()
    if cache is not None and project_id in cache:
        return cache[project_id]
    project = get_project(project_id) or {}
    screening_plan = project.get("screening_plan")
    if isinstance(screening_plan, str):
        try:
            screening_plan = json.loads(screening_plan)
        except json.JSONDecodeError:
            screening_plan = {}
    plan = screening_plan if isinstance(screening_plan, dict) else {}
    if cache is not None:
        cache[project_id] = plan
    return plan


def _project_hard_filter_issues(project_id: str, creator: dict[str, Any]) -> list[str]:
    raw_payload = _parse_payload_json(creator.get("raw_payload"))
    collection_issues = raw_payload.get("collection_hard_filter_issues")
    if isinstance(collection_issues, list) and collection_issues:
        return list(dict.fromkeys(str(item) for item in collection_issues if item))
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
    category_items: list[dict[str, Any]] = []
    for item in hard_filters:
        if not isinstance(item, dict) or item.get("required") is False:
            continue
        field = str(item.get("field") or item.get("standard") or "").strip()
        condition = str(item.get("condition") or "").strip()
        value = str(item.get("value") or "").strip()
        rule_text = f"{field} {condition} {value}".lower()
        label = " ".join(part for part in [field, condition, value] if part)
        if "蒲公英" in rule_text and not creator.get("pgy_url"):
            continue
        if field == "博主类目":
            category_items.append(item)
            continue
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
    if category_items:
        if not any(_project_blogger_category_match(text_blob, item) for item in category_items):
            category_labels = " / ".join(dict.fromkeys(_project_blogger_category_label(item) for item in category_items))
            issues.append(f"博主类目：未命中 {category_labels}")
    return list(dict.fromkeys(issues))


def _project_blogger_category_label(item: dict[str, Any]) -> str:
    value = str(item.get("value") or item.get("standard") or "").strip()
    sub_value = str(item.get("sub_value") or item.get("subValue") or "").strip()
    return f"{value}-{sub_value}" if sub_value else value


def _project_blogger_category_match_terms(item: dict[str, Any]) -> list[str]:
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


def _project_blogger_category_match(text_blob: str, item: dict[str, Any]) -> bool:
    lowered = text_blob.lower()
    return any(keyword.lower() in lowered for keyword in _project_blogger_category_match_terms(item))


def generate_test_stage_score(project_id: str, creator: dict[str, Any]) -> tuple[dict[str, Any], str]:
    score = score_values(creator)
    issues = _project_hard_filter_issues(project_id, creator)
    if issues:
        score["hard_filter_passed"] = 0
        score["initial_tier"] = _initial_tier(score["total_score"], True)
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
        return "暂不进入高优先级，保留明确风险和数据短板"
    if any(word in tags for word in ["升学", "政策", "规划", "教师", "老师", "高知", "陪读"]):
        return "高优先级详情完善，重点核验主页简介、笔记标题、文案与长期教育场景"
    if "卖货" in creator_type or any(word in tags for word in ["测评", "教辅", "工具", "答疑"]):
        return "高优先级详情完善，重点核验内容质量与数据效果是否支撑报价"
    if any(word in tags for word in ["亲子", "家庭", "妈妈", "家长"]):
        return "详情完善后判断真实家庭教育场景与内容调性"
    return "按数据层级进入后续详情完善与内容质量判断"


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
    weights = {"budget": 15, "fans": 5, "cpe": 20, "engagement": 30, "persona": 20, "content": 10}
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
    raw_bonus = (
        parse_number(result.get("bonusScore") or result.get("bonus_score"))
        if result.get("bonusScore") is not None or result.get("bonus_score") is not None
        else (fallback.get("bonus_score") or 0)
    )
    bonus_score = max(0, min(5, raw_bonus if raw_bonus is not None else 0))
    total = _clamp_total_score(
        result.get("totalScore") or result.get("total_score"),
        fallback.get("total_score") or (base_score + bonus_score),
    )
    total = min(total, 100)
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
    if initial_tier not in {"S", "A", "B+", "B", "C"}:
        initial_tier = _initial_tier(total, True)
    detail_priority = str(
        result.get("detailCollectionPriority")
        or result.get("detail_collection_priority")
        or _detail_collection_priority(total, bonus_score, hard_pass_bool)
    )
    gate_reasons: list[str] = []
    if creator:
        data_profile = _recent_note_data_profile(creator)
        data_profile["efficiency"] = _efficiency_profile(creator, data_profile["benchmark"], data_profile.get("median_read") or data_profile.get("avg_read"))
        total = _apply_quality_gate(total, data_profile, gate_reasons, creator, _tag_direction_fit(creator))
        if gate_reasons:
            reasons = "；".join([str(reasons).strip(), *gate_reasons])
        initial_tier = _initial_tier(total, hard_pass_bool)
        detail_priority = _detail_collection_priority(total, bonus_score, hard_pass_bool)
        recommend_level = _recommend_level(total, hard_pass_bool)
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
LLM_BATCH_MAX_CREATORS = 6
LLM_SCORE_MAX_WORKERS = max(1, _int_env("LLM_SCORE_MAX_WORKERS", 8))


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
        "daily_exposure_median": creator.get("daily_exposure_median"),
        "daily_interaction_median": creator.get("daily_interaction_median"),
        "image_daily_exposure_median": creator.get("image_daily_exposure_median"),
        "image_daily_read_median": creator.get("image_daily_read_median"),
        "image_daily_interaction_median": creator.get("image_daily_interaction_median"),
        "video_daily_exposure_median": creator.get("video_daily_exposure_median"),
        "video_daily_read_median": creator.get("video_daily_read_median"),
        "video_daily_interaction_median": creator.get("video_daily_interaction_median"),
        "video_completion_rate": creator.get("video_completion_rate"),
        "cooperation_exposure_median": creator.get("cooperation_exposure_median"),
        "cooperation_read_median": creator.get("cooperation_read_median"),
        "cooperation_interaction_median": creator.get("cooperation_interaction_median"),
        "image_cpm": creator.get("image_cpm"),
        "image_read_unit_price": creator.get("image_read_unit_price"),
        "image_interaction_unit_price": creator.get("image_interaction_unit_price"),
        "video_cpm": creator.get("video_cpm"),
        "video_read_unit_price": creator.get("video_read_unit_price"),
        "video_interaction_unit_price": creator.get("video_interaction_unit_price"),
        "liked_collected_count": creator.get("liked_collected_count"),
        "active_fans_ratio": creator.get("active_fans_ratio"),
        "interaction_fans_ratio": creator.get("interaction_fans_ratio"),
        "reply_rate_48h": creator.get("reply_rate_48h"),
        "search_recommend_ratio": creator.get("search_recommend_ratio"),
        "fans_35_plus_ratio": creator.get("fans_35_plus_ratio"),
        "traffic_stability": creator.get("traffic_stability"),
        "rate_limit_risk": creator.get("rate_limit_risk"),
        "pgy_url": creator.get("pgy_url"),
        "raw_payload": creator.get("raw_payload"),
        "machine_data_profile": _budget_effect_profile(creator),
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
    scoring_criteria = screening_plan.get("scoringCriteria") if isinstance(screening_plan.get("scoringCriteria"), dict) else {}
    budget_policy = screening_plan.get("budgetPolicy") or scoring_criteria.get("budget_policy") or {}
    data_layer = screening_plan.get("dataLayerScoring") or scoring_criteria.get("data_layer_scoring") or {}
    tier_policy = screening_plan.get("tierPolicy") or scoring_criteria.get("tier_policy") or {}
    return {
        "project": {
            "project_id": project_id,
            "project_name": project.get("project_name") or PROJECT_NAME,
            "brief": project.get("brief") or "教育/亲子大孩/高知家庭达人，聚焦有道答疑笔5-6月合作。",
            "target_qualified_creator_count": project.get("target_qualified_creator_count"),
            "budgetPolicy": budget_policy,
            "scoringCriteria": scoring_criteria,
            "dataLayerScoring": data_layer,
            "tierPolicy": tier_policy,
            "scoringHardFilters": screening_plan.get("scoringHardFilters") or (screening_plan.get("scoringCriteria") or {}).get("hard_rules") or screening_plan.get("hardFilters") or [],
            "hardFilters": screening_plan.get("scoringHardFilters") or (screening_plan.get("scoringCriteria") or {}).get("hard_rules") or screening_plan.get("hardFilters") or [],
            "scoringWeights": screening_plan.get("scoringWeights") or {},
            "scoringProtocol": [
                "初评分只使用稳定入库字段，主公式抓5类：35岁以上粉丝占比、阅读/互动中位数、报价与阅读/互动单价、类目/标签/期待合作行业、执行确定性。",
                "粉丝量只作为T级比较坐标，不作为高权重加分项；阅读/互动必须按同T级基准判断。",
                "报价不是越低越好，必须结合报价能换来的阅读/互动总量、CPM/CPC/CPE效率、单达人参考预算和硬上限判断。",
                "类目、个人标签、期待合作行业只是弱方向证据；没有主页简介、详情页、笔记标题/正文时，不得直接判定高知/教师/大孩家长等强人设。",
                "缺蒲公英链接、缺字段、缺近期笔记正文是采集/证据状态，不是达人质量问题，不得作为硬性淘汰原因。",
                "只有已确认的报价超硬上限、同T级近30天数据明显低于基准、已确认异常/违规/限流，才能作为明确风险。",
                "封顶规则必须执行：35岁以上粉丝占比低于40%最高C；缺35岁以上粉丝占比、缺阅读/互动核心数据、成本效率差或标签弱相关，暂不进入A档。",
            ],
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
                    "dataLayer": "S|A|B|C；基于35岁以上粉丝占比、阅读/互动中位数、报价与CPC/CPE、T级基准得到的数据层级",
                    "baseScore": "0-100 初筛基础分；只使用稳定入库字段，优先人群、流量、成本效率、标签方向、执行确定性",
                    "bonusScore": "0-5 微加分；只奖励人群画像、数据表现、成本效率和方向匹配同时成立，不因低价或标签单独加高分",
                    "totalScore": "0-100 初筛总分，等于 baseScore + bonusScore 后封顶",
                    "informationCompleteness": "0-1，当前可用证据完整度；低完整度只影响置信度和后续详情完善优先级，不等于达人质量差",
                    "initialTier": "S|A|B+|B|C；S=95-100证据充分标杆，A=80-94初筛高潜，B+=75-79次高潜，B=70-74备选观察，C<70低优先级；硬性不符也必须保留分数档位，不要输出Pass",
                    "detailCollectionPriority": "最高优先级|高优先级|中高优先级|中优先级|低优先级|数据暂缓；只让数据层级高或高潜达人进入详情页完善内容/人设信息，硬性不符用数据暂缓",
                    "dimensionScores": {
                        "budget": "0-100 执行确定性：蒲公英链接、报价完整、48h回复率、基础身份完整度",
                        "fans": "0-100 目标人群匹配：核心看35岁以上粉丝占比，粉丝量只作T级坐标",
                        "cpe": "0-100 成本效率：报价、阅读单价/CPC、互动单价/CPE，CPM只作辅助",
                        "engagement": "0-100 真实流量质量：阅读中位数、互动中位数，需与同T级基准比较",
                        "persona": "0-100 内容方向弱匹配：博主类目、内容标签、个人标签、期待合作行业；不得当成强人设",
                        "content": "0-100 微加分：人群、数据、效率、方向同时成立才给高分",
                    },
                    "hardFilterPassed": "boolean，只基于已确认事实判断；未知项、缺蒲公英链接、缺字段不得当成硬性不符",
                    "recommendLevel": "强推荐|推荐|备选|不推荐|继续观察",
                    "reason": "260字以内，按【人群画像】【阅读互动】【成本效率】【产品内容场景/风险】四段输出。必须先识别项目里的具体产品，再判断笔记内容和呈现方式是否能自然承接该产品；例如有道点读笔要看亲子阅读、英语跟读、查词发音、孩子自主阅读等场景，有道答疑笔要看作业答疑、错题讲解、孩子自主学习、家长辅导减负等场景。必须写明报价、阅读/互动中位数、CPC/CPE或阅读/互动单价、T级比较结论；标签和期待合作只能写弱证据。",
                    "cooperationDirection": "80字以内，非评分依据；只说明后续详情完善或审核重点，不要用曝光/测评/转化角色影响分数",
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
        "你是广告投放达人初筛评分专家。请按少字段核心初评分机制评分，不要做大而全加权。"
        "主公式只看五类稳定入库数据：目标人群匹配、真实流量质量、成本效率、内容方向弱匹配、执行确定性。"
        "目标人群核心看35岁以上粉丝占比；真实流量核心看阅读中位数和互动中位数；成本效率核心看报价、阅读单价/CPC、互动单价/CPE。"
        "粉丝量只作为T级比较坐标，不是高权重得分项；报价不是越低越好，必须判断这笔预算能换来的阅读/互动总量。"
        "所有项目使用 baseScore 100、bonusScore 5、totalScore 100；加成只给人群、数据、效率、方向同时成立。"
        "缺蒲公英链接、缺字段、缺近期笔记正文属于证据/采集状态，不是达人质量问题，不得作为硬性淘汰或低分原因。"
        "只有已确认的报价超硬上限、同T级近30天数据明显低于基准、已确认异常/违规/限流，才能作为明确风险。"
        "类目、个人标签、期待合作行业只是弱方向证据；没有主页简介、详情页、笔记标题/正文时，不得直接判定高知/教师/大孩家长等强人设。"
        "必须先从项目名称、brief和scoringCriteria识别具体产品，再围绕产品本身判断内容适配，不要只按教育/母婴大类下结论。"
        "例如有道点读笔重点看亲子阅读、英语跟读、查词发音、孩子自主阅读和家长陪伴呈现；有道答疑笔重点看作业答疑、错题讲解、孩子自主学习和家长辅导减负呈现。"
        "短板必须分析笔记内容主题和呈现方式，指出是否缺少产品使用过程、孩子反馈、家长视角或使用前后对比。"
        "必须执行封顶：35岁以上粉丝占比低于40%最高C；缺阅读/互动核心数据、阅读表现不佳或标签弱相关，初筛最高B+；缺35岁以上粉丝占比不得进入S。"
        "不要把达人是否适合曝光、测评、转化种草作为评分依据；达人质量好才值得推进，怎么推是后续执行策略。"
        "请输出 initialTier 和 detailCollectionPriority，用于决定哪些数据层级高或高潜达人进入详情页完善信息。"
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


def _score_llm_chunks_parallel(
    project_id: str,
    chunks: list[list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    if not chunks:
        return []
    max_workers = max(1, min(LLM_SCORE_MAX_WORKERS, len(chunks)))
    results: list[dict[str, Any] | None] = [None] * len(chunks)

    def run_chunk(chunk: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        with _scoring_batch_context():
            return score_values_batch_with_llm(project_id, chunk)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(run_chunk, chunk): (index, chunk)
            for index, chunk in enumerate(chunks)
        }
        for future in as_completed(futures):
            index, chunk = futures[future]
            try:
                results[index] = {"ok": True, "chunk": chunk, "scores": future.result()}
            except Exception as error:
                results[index] = {"ok": False, "chunk": chunk, "error": error}
    return [result for result in results if result is not None]


def _persist_creator_score(
    project_id: str,
    creator: dict[str, Any],
    score: dict[str, Any],
    source: str,
    batch_id: str,
    trigger_source: str,
    fetch_scored: bool = True,
    conn: sqlite3.Connection | None = None,
) -> dict[str, Any]:
    creator_id = str(creator["creator_id"])
    ts = now()
    cooperation_direction = score.get("cooperation_direction") or _default_cooperation_direction(creator, score.get("recommend_level"))
    def write(handle: sqlite3.Connection) -> None:
        handle.execute(
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
        handle.execute(
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
        handle.execute(
            """
            UPDATE project_creators SET total_score=?, tier=?, pool_stage=?, portfolio_role=?, updated_at=?
            WHERE project_id=? AND creator_id=?
            """,
            (
                score["total_score"],
                tier_from_score(score["total_score"]),
                stage_from_status(creator.get("status")),
                cooperation_direction,
                ts,
                project_id,
                creator_id,
            ),
        )
        if creator["status"] == "待补数据":
            handle.execute("UPDATE creators SET status='待审核', updated_at=? WHERE creator_id=?", (ts, creator_id))
            handle.execute(
                "UPDATE project_creators SET review_status='待审核', pool_stage=?, updated_at=? WHERE project_id=? AND creator_id=?",
                (stage_from_status("待审核"), ts, project_id, creator_id),
            )
    if conn is None:
        with connect() as write_conn:
            write(write_conn)
    else:
        write(conn)
    if fetch_scored:
        scored = get_creator(project_id, creator_id) or {}
    else:
        scored = dict(creator)
    scored["score_source"] = source
    scored["batch_id"] = batch_id
    scored["total_score"] = score.get("total_score")
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
    with _scoring_batch_context():
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
    llm_errors: list[str] = []
    llm_chunk_results: list[dict[str, Any]] = []
    chunks = _chunk_creators_for_llm(project_id, creators) if use_llm and creators else []
    if chunks:
        llm_chunk_results = _score_llm_chunks_parallel(project_id, chunks)
    with _scoring_batch_context(), connect() as conn:
        if use_llm and creators:
            for chunk_result in llm_chunk_results:
                chunk = chunk_result["chunk"]
                if chunk_result.get("ok"):
                    batch_scores = chunk_result["scores"]
                    for creator in chunk:
                        score = batch_scores[str(creator["creator_id"])]
                        scored = _persist_creator_score(project_id, creator, score, "llm", batch_id, trigger_source, fetch_scored=False, conn=conn)
                        sources[scored.get("score_source") or "fallback"] = sources.get(scored.get("score_source") or "fallback", 0) + 1
                else:
                    error = chunk_result.get("error")
                    llm_errors.append(str(error)[:300])
                    for creator in chunk:
                        score, source = generate_test_stage_score(project_id, creator)
                        scored = _persist_creator_score(project_id, creator, score, source, batch_id, trigger_source, fetch_scored=False, conn=conn)
                        sources[scored.get("score_source") or "fallback"] = sources.get(scored.get("score_source") or "fallback", 0) + 1
        else:
            for creator in creators:
                score, _ = generate_test_stage_score(project_id, creator)
                scored = _persist_creator_score(project_id, creator, score, "rule", batch_id, trigger_source, fetch_scored=False, conn=conn)
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
        "llm_errors": llm_errors,
        "message": detail,
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


def update_batch_progress(
    batch_id: str,
    *,
    stage: str = "",
    message: str = "",
    total_count: int | None = None,
    success_count: int | None = None,
    failed_count: int | None = None,
) -> dict[str, Any]:
    assignments = []
    params: list[Any] = []
    if stage:
        assignments.append("progress_stage=?")
        params.append(stage)
    if message:
        assignments.append("progress_message=?")
        params.append(message)
    if total_count is not None:
        assignments.append("total_count=?")
        params.append(total_count)
    if success_count is not None:
        assignments.append("success_count=?")
        params.append(success_count)
    if failed_count is not None:
        assignments.append("failed_count=?")
        params.append(failed_count)
    if not assignments:
        with connect() as conn:
            row = conn.execute("SELECT * FROM collection_batches WHERE batch_id=?", (batch_id,)).fetchone()
        return _batch_dict(row)
    params.append(batch_id)
    with connect() as conn:
        conn.execute(f"UPDATE collection_batches SET {', '.join(assignments)} WHERE batch_id=?", params)
        row = conn.execute("SELECT * FROM collection_batches WHERE batch_id=?", (batch_id,)).fetchone()
    return _batch_dict(row)


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
            selected_metrics=?, skipped_metrics=?, detail_collection=?, progress_stage=?, progress_message=? WHERE batch_id=?
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
                status,
                "采集完成" if status == "success" else error,
                batch_id,
            ),
        )
        row = conn.execute("SELECT * FROM collection_batches WHERE batch_id=?", (batch_id,)).fetchone()
    return _batch_dict(row)


def list_logs(project_id: str) -> list[dict[str, Any]]:
    init_db()
    with connect() as conn:
        return rows_dict(conn.execute("SELECT * FROM operation_logs WHERE project_id=? ORDER BY created_at DESC LIMIT 200", (project_id,)).fetchall())


def _json_value(value: Any, default: Any) -> Any:
    if value in (None, ""):
        return default
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default


def _handoff_dict(row: sqlite3.Row) -> dict[str, Any]:
    item = dict(row)
    item["payload"] = _json_value(item.get("payload"), {})
    return item


def _task_dict(row: sqlite3.Row) -> dict[str, Any]:
    item = dict(row)
    item["deliverables"] = _json_value(item.get("deliverables"), [])
    return item


def list_handoffs(project_id: str, to_role: str | None = None, from_role: str | None = None) -> list[dict[str, Any]]:
    init_db()
    where = ["project_id=?"]
    params: list[Any] = [project_id]
    if to_role:
        where.append("to_role=?")
        params.append(to_role)
    if from_role:
        where.append("from_role=?")
        params.append(from_role)
    with connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM project_handoffs WHERE {' AND '.join(where)} ORDER BY created_at DESC",
            params,
        ).fetchall()
    return [_handoff_dict(row) for row in rows]


def create_handoff(project_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    init_db()
    ts = now()
    handoff_id = payload.get("handoff_id") or str(uuid.uuid4())
    from_role = payload.get("from_role") or "planner"
    to_role = payload.get("to_role") or "executor"
    title = payload.get("title") or "项目交接单"
    summary = payload.get("summary") or ""
    body = payload.get("payload") or {}
    with connect() as conn:
        ensure_project(conn, project_id)
        conn.execute(
            """
            INSERT INTO project_handoffs(
              handoff_id, project_id, from_role, to_role, title, summary, payload,
              status, created_by, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                handoff_id,
                project_id,
                from_role,
                to_role,
                title,
                summary,
                _json_text(body, {}),
                payload.get("status") or "pending",
                payload.get("created_by") or "用户",
                ts,
                ts,
            ),
        )
        log(conn, project_id, "handoff", "提交交接", title, payload.get("created_by") or "用户", f"{from_role} -> {to_role}: {summary}", "success")
    return get_handoff(project_id, handoff_id) or {}


def get_handoff(project_id: str, handoff_id: str) -> dict[str, Any] | None:
    init_db()
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM project_handoffs WHERE project_id=? AND handoff_id=?",
            (project_id, handoff_id),
        ).fetchone()
    return _handoff_dict(row) if row else None


def update_handoff_status(
    project_id: str,
    handoff_id: str,
    status: str,
    *,
    operator: str = "用户",
    return_reason: str = "",
) -> dict[str, Any]:
    init_db()
    existing = get_handoff(project_id, handoff_id)
    if not existing:
        raise KeyError(handoff_id)
    ts = now()
    accepted_at = ts if status in {"accepted", "in_progress", "completed"} and not existing.get("accepted_at") else existing.get("accepted_at")
    with connect() as conn:
        conn.execute(
            """
            UPDATE project_handoffs
            SET status=?, accepted_by=?, return_reason=?, accepted_at=?, updated_at=?
            WHERE project_id=? AND handoff_id=?
            """,
            (status, operator if status != "returned" else existing.get("accepted_by") or "", return_reason, accepted_at, ts, project_id, handoff_id),
        )
        action = "退回交接" if status == "returned" else "接收交接"
        detail = return_reason or f"交接状态更新为 {status}"
        log(conn, project_id, "handoff", action, existing.get("title") or handoff_id, operator, detail, "success")
    return get_handoff(project_id, handoff_id) or {}


def list_tasks(project_id: str, role: str | None = None, status: str | None = None) -> list[dict[str, Any]]:
    init_db()
    where = ["project_id=?"]
    params: list[Any] = [project_id]
    if role:
        where.append("role=?")
        params.append(role)
    if status:
        where.append("status=?")
        params.append(status)
    with connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM project_tasks WHERE {' AND '.join(where)} ORDER BY created_at DESC",
            params,
        ).fetchall()
    return [_task_dict(row) for row in rows]


def create_task(project_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    init_db()
    ts = now()
    task_id = payload.get("task_id") or str(uuid.uuid4())
    with connect() as conn:
        ensure_project(conn, project_id)
        conn.execute(
            """
            INSERT INTO project_tasks(
              task_id, project_id, source_handoff_id, title, description, role,
              owner, status, priority, due_at, blocked_reason, deliverables,
              created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                task_id,
                project_id,
                payload.get("source_handoff_id") or "",
                payload.get("title") or "未命名任务",
                payload.get("description") or "",
                payload.get("role") or "executor",
                payload.get("owner") or "",
                payload.get("status") or "todo",
                payload.get("priority") or "medium",
                payload.get("due_at") or "",
                payload.get("blocked_reason") or "",
                _json_text(payload.get("deliverables"), []),
                ts,
                ts,
            ),
        )
        log(conn, project_id, "task", "创建任务", payload.get("title") or task_id, payload.get("operator") or "用户", payload.get("description") or "任务已创建", "success")
    return get_task(project_id, task_id) or {}


def get_task(project_id: str, task_id: str) -> dict[str, Any] | None:
    init_db()
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM project_tasks WHERE project_id=? AND task_id=?",
            (project_id, task_id),
        ).fetchone()
    return _task_dict(row) if row else None


def update_task(project_id: str, task_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    init_db()
    existing = get_task(project_id, task_id)
    if not existing:
        raise KeyError(task_id)
    allowed = {
        "title",
        "description",
        "role",
        "owner",
        "status",
        "priority",
        "due_at",
        "blocked_reason",
    }
    fields = [key for key in allowed if key in payload]
    assignments = [f"{key}=?" for key in fields]
    values = [payload[key] for key in fields]
    if "deliverables" in payload:
        assignments.append("deliverables=?")
        values.append(_json_text(payload.get("deliverables"), []))
    completed_at = now() if payload.get("status") == "done" and not existing.get("completed_at") else existing.get("completed_at")
    assignments.extend(["completed_at=?", "updated_at=?"])
    values.extend([completed_at, now(), project_id, task_id])
    with connect() as conn:
        conn.execute(
            f"UPDATE project_tasks SET {', '.join(assignments)} WHERE project_id=? AND task_id=?",
            values,
        )
        log(conn, project_id, "task", "更新任务", existing.get("title") or task_id, payload.get("operator") or "用户", f"状态更新为 {payload.get('status') or existing.get('status')}", "success")
    return get_task(project_id, task_id) or {}


def create_tasks_from_handoff(project_id: str, handoff_id: str, operator: str = "用户") -> list[dict[str, Any]]:
    handoff = get_handoff(project_id, handoff_id)
    if not handoff:
        raise KeyError(handoff_id)
    body = handoff.get("payload") or {}
    suggestions = body.get("execution_tasks") or body.get("tasks") or []
    if not suggestions:
        suggestions = [
            {"title": f"拆解{handoff.get('title')}", "description": handoff.get("summary") or "", "priority": "high"},
            {"title": "确认交付物与时间节点", "description": "基于交接单补齐负责人、截止时间和验收口径。", "priority": "medium"},
        ]
    tasks = []
    for item in suggestions:
        tasks.append(
            create_task(
                project_id,
                {
                    "source_handoff_id": handoff_id,
                    "title": item.get("title") or item.get("name") or "交接生成任务",
                    "description": item.get("description") or item.get("note") or handoff.get("summary") or "",
                    "role": "executor",
                    "owner": item.get("owner") or "",
                    "status": item.get("status") or "todo",
                    "priority": item.get("priority") or "medium",
                    "due_at": item.get("due_at") or item.get("deadline") or "",
                    "operator": operator,
                },
            )
        )
    update_handoff_status(project_id, handoff_id, "in_progress", operator=operator)
    return tasks


def list_assets(project_id: str, asset_type: str | None = None) -> list[dict[str, Any]]:
    init_db()
    where = ["project_id=?"]
    params: list[Any] = [project_id]
    if asset_type:
        where.append("asset_type=?")
        params.append(asset_type)
    with connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM project_assets WHERE {' AND '.join(where)} ORDER BY created_at DESC",
            params,
        ).fetchall()
    assets = rows_dict(rows)
    for asset in assets:
        asset["payload"] = _json_value(asset.get("payload"), {})
    return assets


def create_asset(project_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    init_db()
    ts = now()
    asset_id = payload.get("asset_id") or str(uuid.uuid4())
    with connect() as conn:
        ensure_project(conn, project_id)
        conn.execute(
            """
            INSERT INTO project_assets(asset_id, project_id, asset_type, title, payload, created_by, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                asset_id,
                project_id,
                payload.get("asset_type") or "document",
                payload.get("title") or "未命名资产",
                _json_text(payload.get("payload"), {}),
                payload.get("created_by") or "用户",
                ts,
                ts,
            ),
        )
        log(conn, project_id, "asset", "保存资产", payload.get("title") or asset_id, payload.get("created_by") or "用户", payload.get("asset_type") or "document", "success")
    assets = [asset for asset in list_assets(project_id) if asset.get("asset_id") == asset_id]
    return assets[0] if assets else {}


def project_metrics(project_id: str) -> dict[str, Any]:
    project = get_project(project_id)
    if not project:
        raise KeyError(project_id)
    handoffs = list_handoffs(project_id)
    tasks = list_tasks(project_id)
    assets = list_assets(project_id)
    logs = list_logs(project_id)
    creator_pool_count = int(project.get("creator_pool_count") or 0)
    screening_candidate_count = int(project.get("screening_candidate_count") or 0)
    qualified_count = int(project.get("qualified_creator_count") or 0)
    task_total = len(tasks)
    task_done = len([task for task in tasks if task.get("status") == "done"])
    blocked = len([task for task in tasks if task.get("status") == "blocked"])
    pending_handoffs = len([item for item in handoffs if item.get("status") == "pending"])
    returned_handoffs = len([item for item in handoffs if item.get("status") == "returned"])
    brief_assets = len([asset for asset in assets if asset.get("asset_type") == "brief"])
    strategy_assets = len([asset for asset in assets if asset.get("asset_type") == "strategy"])
    strategy_score = min(100, 35 + brief_assets * 25 + strategy_assets * 25)
    execution_score = 100 if task_total == 0 else round((task_done / task_total) * 100)
    creator_score = min(100, round((qualified_count / max(int(project.get("target_qualified_creator_count") or 10), 1)) * 100))
    risk_penalty = blocked * 12 + pending_handoffs * 5 + returned_handoffs * 8
    health_score = max(0, min(100, round((strategy_score + execution_score + creator_score + 75) / 4 - risk_penalty)))
    return {
        "project_id": project_id,
        "project": project,
        "summary": {
            "health_score": health_score,
            "strategy_score": strategy_score,
            "execution_score": execution_score,
            "creator_pool_score": creator_score,
            "task_total": task_total,
            "task_done": task_done,
            "blocked_tasks": blocked,
            "pending_handoffs": pending_handoffs,
            "returned_handoffs": returned_handoffs,
            "asset_count": len(assets),
            "timeline_count": len(logs),
            "creator_pool_count": creator_pool_count,
            "screening_candidate_count": screening_candidate_count,
            "qualified_creator_count": qualified_count,
        },
        "role_efficiency": {
            "planner": {"brief_assets": brief_assets, "strategy_assets": strategy_assets, "handoffs": len([item for item in handoffs if item.get("from_role") == "planner"])},
            "executor": {"task_completion_rate": execution_score, "blocked_tasks": blocked, "tasks": task_total},
            "screening": {"candidate_count": screening_candidate_count, "qualified_count": qualified_count, "qualified_rate": creator_score},
        },
        "risks": [
            *[
                {
                    "risk_id": task.get("task_id"),
                    "project_id": project_id,
                    "title": task.get("blocked_reason") or f"{task.get('title')} 阻塞",
                    "type": "任务阻塞",
                    "level": "high",
                    "status": "handling",
                    "source_id": task.get("task_id"),
                }
                for task in tasks
                if task.get("status") == "blocked"
            ],
            *[
                {
                    "risk_id": item.get("handoff_id"),
                    "project_id": project_id,
                    "title": item.get("return_reason") or f"{item.get('title')} 被退回",
                    "type": "交接阻塞",
                    "level": "medium",
                    "status": "tracking",
                    "source_id": item.get("handoff_id"),
                }
                for item in handoffs
                if item.get("status") == "returned"
            ],
        ],
    }


def management_overview() -> dict[str, Any]:
    projects = list_projects(include_archived=True)
    project_items = []
    all_risks = []
    for project in projects:
        metrics = project_metrics(project["project_id"])
        summary = metrics["summary"]
        project_items.append({"project": project, "metrics": summary})
        all_risks.extend(metrics["risks"])
    active = [item for item in project_items if not item["project"].get("archived_at")]
    completed = [item for item in project_items if item["project"].get("archived_at")]
    warn = [item for item in active if item["metrics"]["health_score"] < 60 or item["metrics"]["blocked_tasks"] > 0]
    return {
        "projects": project_items,
        "overview": {
            "project_total": len(project_items),
            "active_projects": len(active),
            "warning_projects": len(warn),
            "completed_projects": len(completed),
            "asset_total": sum(item["metrics"]["asset_count"] for item in project_items),
            "task_total": sum(item["metrics"]["task_total"] for item in project_items),
            "pending_handoffs": sum(item["metrics"]["pending_handoffs"] for item in project_items),
            "average_health": round(sum(item["metrics"]["health_score"] for item in project_items) / max(len(project_items), 1), 1),
        },
        "risks": all_risks,
    }


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
                "是否进入详情页完善": "是" if c.get("detail_collection_priority") in DETAIL_PRIORITY_HIGH_VALUES else "否",
                "详情完善优先级": c.get("detail_collection_priority") or "",
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
    min_score: float = 70,
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
        and c.get("detail_collection_priority") in {*DETAIL_PRIORITY_HIGH_VALUES, None, ""}
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
                "详情完善优先级": c.get("detail_collection_priority") or "",
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
