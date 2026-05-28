from __future__ import annotations

import csv
import copy
import json
import os
import re
import shutil
import sqlite3
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime
from pathlib import Path
from typing import Any

from .config_store import ROOT, project_scoring_config_path, read_json, write_json
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
_PROJECT_DATA_CACHE: ContextVar[dict[str, dict[str, Any] | None] | None] = ContextVar(
    "_PROJECT_DATA_CACHE",
    default=None,
)
_PROJECT_DIRECTION_TERMS_CACHE: ContextVar[dict[str, dict[str, Any]] | None] = ContextVar(
    "_PROJECT_DIRECTION_TERMS_CACHE",
    default=None,
)
_INIT_DB_LOCK = threading.Lock()
_INIT_DB_DONE_PATHS: set[str] = set()

KOC_DEFAULT_SCORING_CONFIG = {
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
    "negative_policy": "冲突内容按占比风险处理，不因单个生活/vlog/旅行关键词直接Pass。",
    "evidence_policy": "一阶段只决定入库/补详情优先级；缺主页、笔记正文、合作笔记或回复率时不得直接强推荐。",
}


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)) or default)
    except (TypeError, ValueError):
        return default


def now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class ClosingConnection(sqlite3.Connection):
    def __exit__(self, exc_type, exc_value, traceback):
        try:
            return super().__exit__(exc_type, exc_value, traceback)
        finally:
            self.close()


def database_path() -> Path:
    configured = os.environ.get("RPA_MCP_SYNC_DB_PATH")
    return Path(configured) if configured else DB_PATH


def _database_path_key() -> str:
    path = database_path()
    try:
        return str(path.resolve())
    except OSError:
        return str(path.absolute())


def connect() -> sqlite3.Connection:
    path = database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(
        path,
        timeout=_int_env("RPA_MCP_SYNC_SQLITE_TIMEOUT_SECONDS", 60),
        factory=ClosingConnection,
    )
    conn.row_factory = sqlite3.Row
    conn.execute(f"PRAGMA busy_timeout={_int_env('RPA_MCP_SYNC_SQLITE_BUSY_TIMEOUT_MS', 60000)}")
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
    except sqlite3.OperationalError:
        pass
    return conn


def _is_sqlite_locked(error: BaseException) -> bool:
    text = str(error).lower()
    return isinstance(error, sqlite3.OperationalError) and (
        "database is locked" in text or "database table is locked" in text
    )


def _run_sqlite_locked_retry(operation, *, attempts: int = 5, base_delay: float = 0.35):
    for attempt in range(attempts):
        try:
            return operation()
        except sqlite3.OperationalError as error:
            if not _is_sqlite_locked(error) or attempt >= attempts - 1:
                raise
            time.sleep(base_delay * (2 ** attempt))


def row_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(row) if row else None


def rows_dict(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
    return [dict(row) for row in rows]


def _ensure_index(conn: sqlite3.Connection, name: str, table: str, columns: str) -> None:
    conn.execute(f"CREATE INDEX IF NOT EXISTS {name} ON {table} ({columns})")


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    if column not in _table_columns(conn, table):
        try:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
        except sqlite3.OperationalError as error:
            if "duplicate column name" not in str(error).lower():
                raise


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
  rule_group_score REAL,
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
  stage1_priority TEXT DEFAULT '',
  stage1_reason TEXT DEFAULT '',
  project_match_status TEXT DEFAULT '',
  project_match_confidence REAL,
  final_recommend_level TEXT DEFAULT '',
  target_content_ratio REAL,
  target_content_evidence TEXT DEFAULT '[]',
  product_scene_ratio REAL,
  product_scene_evidence TEXT DEFAULT '[]',
  conflict_content_ratio REAL,
  conflict_content_categories TEXT DEFAULT '[]',
  risk_control_result TEXT DEFAULT '{}',
  recommended_format TEXT DEFAULT '',
  hard_defects TEXT DEFAULT '[]',
  warning_defects TEXT DEFAULT '[]',
  manual_review_items TEXT DEFAULT '[]',
  evidence_quotes TEXT DEFAULT '[]',
  llm_confidence REAL,
  llm_prompt_version TEXT DEFAULT '',
  llm_schema_version TEXT DEFAULT '',
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
    "rate_limit_risk_reason",
    "natural_cpc",
    "natural_cpe",
    "effective_cpc",
    "effective_cpc_source",
    "effective_cpe",
    "effective_cpe_source",
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
    "search_recommend_review_status",
    "search_recommend_review_note",
    "fans_35_plus_ratio",
    "fans_35_plus_ratio_source",
    "child_age",
    "child_grade",
    "child_grade_confidence",
    "child_grade_evidence",
    "child_gender",
    "topic_point",
    "content_scene_tags",
    "content_scene_evidence",
    "presentation_style_tags",
    "cost_30d",
    "cost_90d",
    "audience_profile_screenshot",
    "audience_age_distribution",
    "audience_gender_distribution",
]

PROJECT_STATUSES = {"待补数据", "待审核", "已通过", "备选", "已驳回", "已废弃", "已写回飞书", "待建联", "已邀约", "合作中"}
SCREENING_STAGE = "筛选工作台"
POOL_STAGES = [SCREENING_STAGE, "已合作跟进中", "合格达人待合作", "待建联达人", "观察暂缓", "废弃达人池"]

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
    path = database_path()
    path_key = _database_path_key()
    if path_key in _INIT_DB_DONE_PATHS and path.exists():
        return

    with _INIT_DB_LOCK:
        if path_key in _INIT_DB_DONE_PATHS and path.exists():
            return
        _init_db_uncached()
        _INIT_DB_DONE_PATHS.add(path_key)


def _init_db_uncached() -> None:
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
        text_metric_fields = {
            "budget_status",
            "traffic_stability",
            "rate_limit_risk",
            "rate_limit_risk_reason",
            "effective_cpc_source",
            "effective_cpe_source",
            "search_recommend_review_status",
            "search_recommend_review_note",
            "fans_35_plus_ratio_source",
            "child_age",
            "child_grade",
            "child_grade_confidence",
            "child_grade_evidence",
            "child_gender",
            "topic_point",
            "content_scene_tags",
            "content_scene_evidence",
            "presentation_style_tags",
        }
        for table in ["creator_metrics", "creator_metrics_current", "creator_metrics_history"]:
            for field in METRIC_FIELDS:
                if field in {"audience_profile_screenshot", "audience_age_distribution", "audience_gender_distribution"}:
                    definition = "TEXT"
                elif field in text_metric_fields:
                    definition = "TEXT"
                else:
                    definition = "REAL"
                _ensure_column(conn, table, field, definition)
        for column, definition in {
            "rule_group_score": "REAL",
            "base_score": "REAL",
            "bonus_score": "REAL",
            "information_completeness": "REAL",
            "initial_tier": "TEXT",
            "detail_collection_priority": "TEXT",
            "stage1_priority": "TEXT DEFAULT ''",
            "stage1_reason": "TEXT DEFAULT ''",
            "project_match_status": "TEXT DEFAULT ''",
            "project_match_confidence": "REAL",
            "final_recommend_level": "TEXT DEFAULT ''",
            "target_content_ratio": "REAL",
            "target_content_evidence": "TEXT DEFAULT '[]'",
            "product_scene_ratio": "REAL",
            "product_scene_evidence": "TEXT DEFAULT '[]'",
            "conflict_content_ratio": "REAL",
            "conflict_content_categories": "TEXT DEFAULT '[]'",
            "risk_control_result": "TEXT DEFAULT '{}'",
            "recommended_format": "TEXT DEFAULT ''",
            "hard_defects": "TEXT DEFAULT '[]'",
            "warning_defects": "TEXT DEFAULT '[]'",
            "manual_review_items": "TEXT DEFAULT '[]'",
            "evidence_quotes": "TEXT DEFAULT '[]'",
            "llm_confidence": "REAL",
            "llm_prompt_version": "TEXT DEFAULT ''",
            "llm_schema_version": "TEXT DEFAULT ''",
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
        _ensure_index(conn, "idx_project_creators_project_status", "project_creators", "project_id, review_status")
        _ensure_index(conn, "idx_project_creators_project_stage", "project_creators", "project_id, pool_stage")
        _ensure_index(conn, "idx_project_creators_project_updated", "project_creators", "project_id, updated_at DESC")
        _ensure_index(conn, "idx_project_creators_project_score", "project_creators", "project_id, total_score DESC")
        _ensure_index(conn, "idx_creator_scores_total", "creator_scores", "total_score DESC")
        _ensure_index(conn, "idx_creators_global_nickname", "creators_global", "nickname")
        _ensure_index(conn, "idx_creators_global_ip_city", "creators_global", "ip_city")
        _ensure_index(conn, "idx_creators_global_pgy_url", "creators_global", "pgy_url")
        _ensure_index(conn, "idx_creators_global_xhs", "creators_global", "xiaohongshu_id")
        _ensure_index(conn, "idx_creators_global_pgy_blogger", "creators_global", "pgy_blogger_id")
        _ensure_index(conn, "idx_creators_legacy_project_status", "creators", "project_id, status")
        _ensure_index(conn, "idx_creators_legacy_project_updated", "creators", "project_id, updated_at DESC")
        _ensure_index(conn, "idx_creators_project_nickname", "creators", "project_id, nickname")
        _ensure_index(conn, "idx_creators_project_pgy_url", "creators", "project_id, pgy_url")
        _ensure_index(conn, "idx_creators_project_xhs", "creators", "project_id, xiaohongshu_id")
        _ensure_index(conn, "idx_creators_project_pgy_blogger", "creators", "project_id, pgy_blogger_id")
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
            ip_city=excluded.ip_city, profile_url=excluded.profile_url,
            avatar_url=COALESCE(NULLIF(excluded.avatar_url, ''), creators_global.avatar_url),
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


CHILD_GRADE_STAGE_MAP = {
    "一年级": "小学低年级",
    "二年级": "小学低年级",
    "三年级": "小学低年级",
    "四年级": "小学高年级",
    "五年级": "小学高年级",
    "六年级": "小学高年级",
    "初一": "初中",
    "初二": "初中",
    "初三": "初中",
    "高一": "高中",
    "高二": "高中",
    "高三": "高中",
    "小升初": "小升初",
}
CHILD_GRADE_KEYWORDS = list(CHILD_GRADE_STAGE_MAP.keys()) + ["初中", "高中", "小学低年级", "小学高年级"]
CONTENT_SCENE_KEYWORDS = [
    ("作业答疑", ["作业", "答疑", "写题", "订正", "作业辅导"]),
    ("错题讲解", ["错题", "题目讲解", "难题", "讲题"]),
    ("提分方法", ["提分", "学习方法", "学习效率", "学习习惯", "复习方法"]),
    ("家长辅导", ["家长辅导", "陪读", "家长减负", "陪学", "辅导孩子"]),
    ("学习规划", ["学习规划", "升学规划", "备考规划", "中考规划", "小升初"]),
    ("学习机/答疑笔测评", ["学习机", "答疑笔", "点读笔", "测评", "对比", "开箱", "实测", "体验"]),
    ("中高考/升学", ["中考", "高考", "升学", "择校", "志愿", "小升初"]),
]
PRESENTATION_STYLE_KEYWORDS = [
    ("清单型", ["清单", "合集", "汇总", "攻略", "模板"]),
    ("经验型", ["经验", "踩坑", "避坑", "建议", "复盘"]),
    ("老师讲解型", ["老师", "讲解", "课堂", "例题", "知识点"]),
    ("测评对比型", ["测评", "对比", "横评", "开箱", "实测", "体验"]),
    ("日常记录型", ["日常", "记录", "周末", "今天", "我家", "我娃"]),
    ("情绪共鸣型", ["焦虑", "崩溃", "破防", "终于", "太难了", "心态"]),
]


def _payload_text_blob(payload: Any, limit: int = 12000) -> str:
    parts: list[str] = []

    def visit(value: Any) -> None:
        if len(" ".join(parts)) >= limit:
            return
        if isinstance(value, str):
            text = re.sub(r"\s+", " ", value).strip()
            if text:
                parts.append(text)
            return
        if isinstance(value, dict):
            for key, item in value.items():
                if key in {"avatar_url", "cover_url", "note_url", "profile_url", "pgy_url", "image_url"}:
                    continue
                visit(item)
            return
        if isinstance(value, list):
            for item in value[:40]:
                visit(item)

    visit(payload)
    return " ".join(parts)[:limit]


def _keyword_evidence_snippets(text: str, keywords: list[str], max_items: int = 3) -> list[str]:
    snippets: list[str] = []
    seen: set[str] = set()
    for keyword in keywords:
        for match in re.finditer(re.escape(keyword), text):
            start = max(0, match.start() - 12)
            end = min(len(text), match.end() + 18)
            snippet = re.sub(r"\s+", " ", text[start:end]).strip(" ，。；;|")
            if not snippet or snippet in seen:
                continue
            seen.add(snippet)
            snippets.append(snippet)
            break
        if len(snippets) >= max_items:
            break
    return snippets


def _derive_child_grade_fields(payload: dict[str, Any], existing_grade: str = "") -> dict[str, str]:
    if existing_grade:
        return {
            "child_grade": existing_grade,
            "child_grade_confidence": "high",
            "child_grade_evidence": existing_grade,
        }
    text = _payload_text_blob(payload)
    explicit_hits = [keyword for keyword in CHILD_GRADE_STAGE_MAP if keyword in text]
    broad_hits = [keyword for keyword in ["初中", "高中", "小学低年级", "小学高年级"] if keyword in text]
    explicit_hits = list(dict.fromkeys(explicit_hits))
    broad_hits = list(dict.fromkeys(broad_hits))
    if explicit_hits:
        stage_hits = list(dict.fromkeys(CHILD_GRADE_STAGE_MAP[item] for item in explicit_hits))
        if len(explicit_hits) == 1:
            grade = explicit_hits[0]
        elif len(stage_hits) == 1:
            grade = stage_hits[0]
        else:
            grade = "多学段"
        confidence = "high" if len(explicit_hits) >= 2 else "medium"
        evidence = "；".join(_keyword_evidence_snippets(text, explicit_hits)) or "；".join(explicit_hits[:3])
        return {
            "child_grade": grade,
            "child_grade_confidence": confidence,
            "child_grade_evidence": evidence,
        }
    if broad_hits:
        evidence = "；".join(_keyword_evidence_snippets(text, broad_hits)) or "；".join(broad_hits[:3])
        return {
            "child_grade": broad_hits[0],
            "child_grade_confidence": "medium",
            "child_grade_evidence": evidence,
        }
    return {
        "child_grade": "",
        "child_grade_confidence": "",
        "child_grade_evidence": "",
    }


def _derive_keyword_tags(text: str, mapping: list[tuple[str, list[str]]], max_items: int = 4) -> tuple[str, str]:
    tags: list[str] = []
    evidence_terms: list[str] = []
    for label, keywords in mapping:
        hits = [keyword for keyword in keywords if keyword in text]
        if not hits:
            continue
        tags.append(label)
        evidence_terms.extend(hits[:2])
        if len(tags) >= max_items:
            break
    evidence = "；".join(_keyword_evidence_snippets(text, list(dict.fromkeys(evidence_terms)), max_items))
    return "、".join(tags[:max_items]), evidence


def _derive_effective_cost_fields(creator: dict[str, Any]) -> dict[str, Any]:
    cpc_candidates = [
        ("natural_cpc", parse_number(creator.get("natural_cpc"))),
        ("image_read_unit_price", parse_number(creator.get("image_read_unit_price"))),
        ("video_read_unit_price", parse_number(creator.get("video_read_unit_price"))),
    ]
    cpe_candidates = [
        ("natural_cpe", parse_number(creator.get("natural_cpe"))),
        ("image_interaction_unit_price", parse_number(creator.get("image_interaction_unit_price"))),
        ("video_interaction_unit_price", parse_number(creator.get("video_interaction_unit_price"))),
    ]
    effective_cpc = next((value for _, value in cpc_candidates if value and value > 0), None)
    effective_cpc_source = next((name for name, value in cpc_candidates if value and value > 0), "")
    effective_cpe = next((value for _, value in cpe_candidates if value and value > 0), None)
    effective_cpe_source = next((name for name, value in cpe_candidates if value and value > 0), "")
    return {
        "effective_cpc": effective_cpc,
        "effective_cpc_source": effective_cpc_source,
        "effective_cpe": effective_cpe,
        "effective_cpe_source": effective_cpe_source,
    }


def _derive_fans_35_plus_fields(creator: dict[str, Any]) -> dict[str, Any]:
    direct = ratio(creator.get("fans_35_plus_ratio"))
    derived = _ratio_sum(creator.get("fans_35_44_ratio"), creator.get("fans_44_plus_ratio"))
    if derived is not None:
        return {
            "fans_35_plus_ratio": derived,
            "fans_35_plus_ratio_source": "derived_35_44_plus_44_plus",
        }
    if direct is not None:
        return {
            "fans_35_plus_ratio": direct,
            "fans_35_plus_ratio_source": "direct_field",
        }
    return {
        "fans_35_plus_ratio": None,
        "fans_35_plus_ratio_source": "",
    }


def _derive_search_review_fields(payload: dict[str, Any], ratio_value: Any) -> dict[str, Any]:
    status = str(payload.get("search_recommend_review_status") or payload.get("搜索推荐复核状态") or "").strip()
    note = str(payload.get("search_recommend_review_note") or payload.get("搜索推荐复核备注") or "").strip()
    if not status:
        status = "已复核" if ratio_value is not None else "待复核"
    if not note:
        note = "已录入真实搜索+推荐占比" if ratio_value is not None else "需人工在蒲公英页面复核搜索+推荐占比"
    return {
        "search_recommend_review_status": status,
        "search_recommend_review_note": note,
    }


def _derive_rate_limit_fields(creator: dict[str, Any]) -> dict[str, str]:
    existing_risk = str(creator.get("rate_limit_risk") or "").strip()
    existing_reason = str(creator.get("rate_limit_risk_reason") or "").strip()
    existing_stability = str(creator.get("traffic_stability") or "").strip()
    if existing_risk and existing_stability and existing_reason:
        return {
            "rate_limit_risk": existing_risk,
            "rate_limit_risk_reason": existing_reason,
            "traffic_stability": existing_stability,
        }
    read_daily = parse_number(creator.get("daily_read_median"))
    read_coop = parse_number(creator.get("cooperation_read_median"))
    interaction_daily = parse_number(creator.get("daily_interaction_median"))
    interaction_coop = parse_number(creator.get("cooperation_interaction_median"))
    growth_ratio = ratio(creator.get("fans_growth_ratio"))
    reasons: list[str] = []
    severe = 0
    moderate = 0
    if read_daily and read_coop:
        read_ratio = read_coop / read_daily if read_daily else None
        if read_ratio is not None and read_ratio < 0.5:
            severe += 1
            reasons.append(f"合作阅读仅为日常的{read_ratio:.0%}")
        elif read_ratio is not None and read_ratio < 0.75:
            moderate += 1
            reasons.append(f"合作阅读低于日常，约{read_ratio:.0%}")
    if interaction_daily and interaction_coop:
        interaction_ratio = interaction_coop / interaction_daily if interaction_daily else None
        if interaction_ratio is not None and interaction_ratio < 0.5:
            severe += 1
            reasons.append(f"合作互动仅为日常的{interaction_ratio:.0%}")
        elif interaction_ratio is not None and interaction_ratio < 0.75:
            moderate += 1
            reasons.append(f"合作互动低于日常，约{interaction_ratio:.0%}")
    if growth_ratio is not None and growth_ratio < -0.05:
        moderate += 1
        reasons.append(f"粉丝增长下滑{growth_ratio:.0%}")
    inferred_risk = existing_risk
    if not inferred_risk:
        if severe >= 2 or (severe >= 1 and moderate >= 1):
            inferred_risk = "高风险"
        elif severe or moderate >= 2:
            inferred_risk = "中风险"
        elif read_daily or interaction_daily or read_coop or interaction_coop:
            inferred_risk = "低风险"
        else:
            inferred_risk = "待补"
    inferred_stability = existing_stability
    if not inferred_stability:
        if inferred_risk == "高风险":
            inferred_stability = "波动较大"
        elif inferred_risk == "中风险":
            inferred_stability = "轻微波动"
        elif inferred_risk == "低风险":
            inferred_stability = "相对稳定"
        else:
            inferred_stability = "待补"
    return {
        "rate_limit_risk": inferred_risk,
        "rate_limit_risk_reason": existing_reason or "；".join(reasons[:3]),
        "traffic_stability": inferred_stability,
    }


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


def _looks_like_price_value(value: Any) -> bool:
    if value in (None, ""):
        return False
    if isinstance(value, (int, float)):
        return True
    text = str(value).strip()
    if not text:
        return False
    if "%" in text:
        return False
    if any(hint in text for hint in ("无接单权限", "暂不接单", "不可合作", "--")):
        return False
    return parse_number(text) is not None


def _first_price_metric(payload: dict[str, Any], *names: str) -> Any:
    for name in names:
        value = payload.get(name)
        if _looks_like_price_value(value):
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


def _creator_raw_payload(creator: dict[str, Any]) -> dict[str, Any]:
    cached = creator.get("_raw_payload_dict")
    if isinstance(cached, dict):
        return cached
    parsed = _parse_payload_json(creator.get("raw_payload"))
    creator["_raw_payload_dict"] = parsed
    return parsed


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
    pgy_blogger_id = str(payload.get("pgy_blogger_id") or "").strip()
    pgy_url = str(payload.get("pgy_url") or payload.get("蒲公英链接") or "").strip()
    if not pgy_blogger_id:
        match = re.search(r"/blogger-detail/([^?/#]+)", pgy_url)
        if match:
            pgy_blogger_id = match.group(1)
    profile_url = str(payload.get("profile_url") or payload.get("主页链接") or "").strip()
    if "pgy.xiaohongshu.com" in profile_url:
        profile_url = ""
    if not profile_url and pgy_blogger_id:
        profile_url = f"https://www.xiaohongshu.com/user/profile/{pgy_blogger_id}"
    creator = {
        "creator_id": str(payload.get("creator_id") or payload.get("达人ID") or uuid.uuid4()),
        "project_id": project_id,
        "source": payload.get("source") or "manual",
        "xiaohongshu_id": payload.get("xiaohongshu_id") or payload.get("小红书号") or "",
        "pgy_blogger_id": pgy_blogger_id,
        "pgy_url": pgy_url,
        "nickname": payload.get("nickname") or payload.get("达人昵称") or "",
        "creator_type": creator_type,
        "persona_tags": payload.get("persona_tags") or payload.get("人设标签") or "",
        "ip_city": payload.get("ip_city") or payload.get("IP城市") or "",
        "profile_url": profile_url,
        "avatar_url": payload.get("avatar_url") or "",
        "status": payload.get("status") or payload.get("当前状态") or "待补数据",
        "raw_payload": json.dumps(payload.get("raw_payload") or payload, ensure_ascii=False),
        "followers_count": parse_number(payload.get("followers_count") or payload.get("粉丝数")),
        "quote_price": parse_number(
            _first_price_metric(
                payload,
                "quote_price",
                "图文报价",
                "图文笔记一口价",
                "图文报备价",
                "图文报备裸价",
                "平台报价",
                "报价",
                "全部报价",
            )
        ),
        "budget_status": payload.get("budget_status") or payload.get("预算状态") or "",
        "traffic_stability": payload.get("traffic_stability") or payload.get("近30天流量稳定性") or "",
        "rate_limit_risk": payload.get("rate_limit_risk") or payload.get("限流风险判断") or "",
        "rate_limit_risk_reason": payload.get("rate_limit_risk_reason") or payload.get("限流风险说明") or "",
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
        "video_quote_price": parse_number(
            _first_price_metric(
                payload,
                "video_quote_price",
                "视频报价",
                "视频笔记一口价",
                "视频报备价",
                "视频报备裸价",
            )
        ),
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
        "fans_35_plus_ratio_source": payload.get("fans_35_plus_ratio_source") or "",
        "child_age": payload.get("child_age") or payload.get("孩子年龄") or "",
        "child_grade": payload.get("child_grade") or payload.get("孩子年级") or "",
        "child_grade_confidence": payload.get("child_grade_confidence") or "",
        "child_grade_evidence": payload.get("child_grade_evidence") or "",
        "child_gender": payload.get("child_gender") or payload.get("孩子性别") or "",
        "topic_point": payload.get("topic_point") or payload.get("家庭/教育话题点") or "",
        "content_scene_tags": payload.get("content_scene_tags") or "",
        "content_scene_evidence": payload.get("content_scene_evidence") or "",
        "presentation_style_tags": payload.get("presentation_style_tags") or "",
        "cost_30d": parse_number(payload.get("cost_30d") or payload.get("30天外溢进店成本")),
        "cost_90d": parse_number(payload.get("cost_90d") or payload.get("90天外溢进店成本")),
        "audience_profile_screenshot": payload.get("audience_profile_screenshot") or payload.get("粉丝画像截图") or "",
        "audience_age_distribution": _json_metric(payload.get("audience_age_distribution") or age_distribution, {"segments": []}),
        "audience_gender_distribution": _json_metric(payload.get("audience_gender_distribution") or gender_distribution, {"segments": []}),
        "effective_cpc": parse_number(payload.get("effective_cpc") or payload.get("阅读单价")),
        "effective_cpc_source": payload.get("effective_cpc_source") or "",
        "effective_cpe": parse_number(payload.get("effective_cpe") or payload.get("互动单价")),
        "effective_cpe_source": payload.get("effective_cpe_source") or "",
        "search_recommend_review_status": payload.get("search_recommend_review_status") or payload.get("搜索推荐复核状态") or "",
        "search_recommend_review_note": payload.get("search_recommend_review_note") or payload.get("搜索推荐复核备注") or "",
    }
    creator.update(_derive_effective_cost_fields(creator))
    creator.update(_derive_fans_35_plus_fields(creator))
    creator.update(_derive_search_review_fields(payload, creator.get("search_recommend_ratio")))
    creator.update(_derive_child_grade_fields(payload, str(creator.get("child_grade") or "").strip()))
    creator.update(_derive_rate_limit_fields(creator))
    text_blob = _payload_text_blob(payload)
    content_scene_tags, content_scene_evidence = _derive_keyword_tags(text_blob, CONTENT_SCENE_KEYWORDS)
    presentation_style_tags, _ = _derive_keyword_tags(text_blob, PRESENTATION_STYLE_KEYWORDS)
    if content_scene_tags and not creator.get("content_scene_tags"):
        creator["content_scene_tags"] = content_scene_tags
    if content_scene_evidence:
        creator["content_scene_evidence"] = content_scene_evidence
    if presentation_style_tags and not creator.get("presentation_style_tags"):
        creator["presentation_style_tags"] = presentation_style_tags
    return creator


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


def normalize_score_tier_key(value: Any, score: Any = None) -> str:
    tier = str(value or "").strip().upper().replace(" ", "")
    if tier in {"S", "A", "B+", "B", "C"}:
        return tier
    if tier in {"S档", "S級", "S级"}:
        return "S"
    if tier in {"A档", "A級", "A级"}:
        return "A"
    if tier in {"B+档", "B＋档", "B+級", "B+级", "B＋級", "B＋级"}:
        return "B+"
    if tier in {"B档", "B級", "B级"}:
        return "B"
    if tier in {"C档", "C級", "C级"}:
        return "C"
    if "未评分" in tier or "待评分" in tier:
        return "未评分"
    if "最高优先级" in tier:
        return "S"
    if "高优先级" in tier and "中高" not in tier:
        return "A"
    if "中高优先级" in tier:
        return "B+"
    if "中优先级" in tier:
        return "B"
    if "低优先级" in tier:
        return "C"
    number = parse_number(score)
    if number is None:
        return ""
    return tier_from_score(number)


def stage_from_status(status: str | None, score: Any = None) -> str:
    if status in {"待补数据", "待审核", "人工复核", None, ""}:
        return SCREENING_STAGE
    if status in {"已废弃", "废弃"}:
        return "废弃达人池"
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
        "废弃达人池": "已废弃",
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
        "effective_cpc": "阅读单价",
        "effective_cpe": "互动单价",
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
        "search_recommend_review_status": "搜索+推荐复核状态",
        "fans_35_plus_ratio": "35岁以上粉丝占比",
        "child_grade": "孩子年级",
        "rate_limit_risk": "流量风险",
        "cost_30d": "30天外溢进店成本",
        "cost_90d": "90天外溢进店成本",
    }
    changes = []
    for field, label in labels.items():
        old = previous.get(field)
        new = current.get(field)
        if old is None or new is None:
            continue
        if str(old).strip() == str(new).strip():
            continue
        try:
            delta = round(float(new) - float(old), 4)
        except (TypeError, ValueError):
            changes.append({"field": field, "label": label, "from": old, "to": new})
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


def _metrics_changed(previous: dict[str, Any] | None, current_metrics: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    change_summary = summarize_metric_change(previous, current_metrics)
    return (not previous) or bool(change_summary.get("changes")), change_summary


def _write_metrics_history(
    conn: sqlite3.Connection,
    project_id: str,
    creator_id: str,
    current_metrics: dict[str, Any],
    change_summary: dict[str, Any],
    ts: str,
) -> None:
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
            json.dumps(change_summary, ensure_ascii=False),
            ts,
        ],
    )


def _upsert_creator_in_conn(
    conn: sqlite3.Connection,
    project_id: str,
    creator: dict[str, Any],
    ts: str,
) -> dict[str, Any]:
    existing_id = find_existing(conn, creator)
    creator_id = existing_id or creator["creator_id"]
    project_row = conn.execute(
        "SELECT review_status, pool_stage FROM project_creators WHERE project_id=? AND creator_id=?",
        (project_id, creator_id),
    ).fetchone()
    review = conn.execute("SELECT review_status FROM screening_reviews WHERE creator_id=?", (creator_id,)).fetchone()
    current = conn.execute("SELECT status FROM creators WHERE project_id=? AND creator_id=?", (project_id, creator_id)).fetchone()
    status = project_row["review_status"] if project_row else (current["status"] if review and current else creator["status"])
    existing_identity = row_dict(conn.execute(
        "SELECT avatar_url FROM creators_global WHERE creator_id=?",
        (creator_id,),
    ).fetchone())
    avatar_url = creator["avatar_url"] or (existing_identity.get("avatar_url") if existing_identity else "") or ""
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
                creator["profile_url"], avatar_url, status, creator["raw_payload"], project_id, ts, creator_id,
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
                creator["ip_city"], creator["profile_url"], avatar_url, status, creator["raw_payload"], ts, ts,
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
        ip_city=excluded.ip_city, profile_url=excluded.profile_url,
        avatar_url=COALESCE(NULLIF(excluded.avatar_url, ''), creators_global.avatar_url),
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
            avatar_url,
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
    changed, change_summary = _metrics_changed(previous, current_metrics)
    if changed:
        _write_metrics_history(conn, project_id, creator_id, current_metrics, change_summary, ts)
    return {
        "creator_id": creator_id,
        "nickname": creator.get("nickname") or "",
        "action": action,
        "metrics_history_written": changed,
    }


def upsert_creator(project_id: str, payload: dict[str, Any], score: bool = False) -> dict[str, Any]:
    init_db()
    creator = normalize_creator(payload, project_id)
    ts = now()
    with connect() as conn:
        ensure_project(conn, project_id)
        saved = _upsert_creator_in_conn(conn, project_id, creator, ts)
        creator_id = saved["creator_id"]
        log(conn, project_id, "creator", saved["action"], creator.get("nickname") or creator_id, "系统", "候选达人已进入筛选工作台", "success")
    if score:
        score_creator(project_id, creator_id)
    return get_creator(project_id, creator_id) or {}


def bulk_upsert_creators(project_id: str, payloads: list[dict[str, Any]], score: bool = False) -> list[dict[str, Any]]:
    init_db()
    normalized = [normalize_creator(payload, project_id) for payload in (payloads or []) if isinstance(payload, dict)]
    if not normalized:
        return []
    ts = now()
    saved_items: list[dict[str, Any]] = []
    with connect() as conn:
        ensure_project(conn, project_id)
        for creator in normalized:
            saved_items.append(_upsert_creator_in_conn(conn, project_id, creator, ts))
        created = sum(1 for item in saved_items if item.get("action") == "新增达人")
        updated = len(saved_items) - created
        history_count = sum(1 for item in saved_items if item.get("metrics_history_written"))
        sample_names = [str(item.get("nickname") or item.get("creator_id") or "") for item in saved_items[:5]]
        suffix = f"；样例：{'、'.join(sample_names)}" if sample_names else ""
        log(
            conn,
            project_id,
            "creator",
            "批量入库达人",
            project_id,
            "系统",
            f"批量入库 {len(saved_items)} 位达人，新增 {created}，更新 {updated}，指标历史写入 {history_count}{suffix}",
            "success",
        )
    if score:
        creator_ids = [str(item["creator_id"]) for item in saved_items if item.get("creator_id")]
        if creator_ids:
            score_project(project_id, use_llm=False, creator_ids=creator_ids, trigger_source="bulk_upsert")
    return saved_items


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
    scoring = score_project(project_id, use_llm=False, creator_ids=creator_ids, trigger_source="import")
    return {"imported": count, "scoring": scoring}


def generate_test_creators(project_id: str, desired_count: int | None = None) -> dict[str, Any]:
    project = _cached_project(project_id) or {}
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


def _cached_project(project_id: str) -> dict[str, Any] | None:
    cache = _PROJECT_DATA_CACHE.get()
    if cache is not None and project_id in cache:
        project = cache[project_id]
        return dict(project) if project else None
    project = get_project(project_id)
    if cache is not None:
        cache[project_id] = dict(project) if project else None
    return project


PROJECT_SCORING_CONFIG_KEYS = [
    "briefType",
    "projectFitConfig",
    "promotionStrategy",
    "budgetPolicy",
    "formatBudgetPolicy",
    "hardRules",
    "tierPolicy",
    "dataLayerScoring",
    "scoringWeights",
    "scoringHardFilters",
    "scoringCriteria",
    "projectSpecialScoring",
    "kocScoringConfig",
]


def _parse_screening_plan_text(value: str | dict[str, Any] | None) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def _project_scoring_config_payload(
    project_id: str,
    project_name: str,
    brief: str,
    screening_plan: dict[str, Any],
    *,
    updated_at: str,
) -> dict[str, Any]:
    scoring_config = {
        key: copy.deepcopy(screening_plan.get(key))
        for key in PROJECT_SCORING_CONFIG_KEYS
        if screening_plan.get(key) not in (None, "", [], {})
    }
    return {
        "schema_version": 1,
        "project_id": project_id,
        "project_name": project_name,
        "brief_digest": str(brief or "")[:500],
        "updated_at": updated_at,
        "source": "screening_plan_project_config",
        "scoring_engine": "rpa_mcp_sync.creator_store",
        "project_scoring_config": scoring_config,
    }


def write_project_scoring_config_file(project_id: str, project: dict[str, Any], screening_plan: dict[str, Any]) -> None:
    if is_test_project_id(project_id) or not screening_plan:
        return
    write_json(
        project_scoring_config_path(project_id),
        _project_scoring_config_payload(
            project_id,
            str(project.get("project_name") or project_id),
            str(project.get("brief") or ""),
            screening_plan,
            updated_at=str(project.get("updated_at") or now()),
        ),
    )


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
    next_project_name = payload.get("project_name") or (existing["project_name"] if existing else project_id)
    next_brief = payload.get("brief") or (existing.get("brief") if existing else "")
    with connect() as conn:
        if existing:
            conn.execute(
                "UPDATE projects SET project_name=?, target_qualified_creator_count=?, period_start=?, period_end=?, brief=?, screening_plan=?, updated_at=? WHERE project_id=?",
                (
                    next_project_name,
                    int(payload.get("target_qualified_creator_count") or existing["target_qualified_creator_count"]),
                    payload.get("period_start") or existing.get("period_start"),
                    payload.get("period_end") or existing.get("period_end"),
                    next_brief,
                    screening_plan_text,
                    ts,
                    project_id,
                ),
            )
        else:
            conn.execute(
                "INSERT INTO projects(project_id, project_name, target_qualified_creator_count, period_start, period_end, brief, screening_plan, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (project_id, next_project_name, int(payload.get("target_qualified_creator_count") or 10), payload.get("period_start"), payload.get("period_end"), next_brief, screening_plan_text, ts, ts),
            )
        log(conn, project_id, "project", "保存项目", next_project_name, "用户", "立项信息已保存", "success")
    write_project_scoring_config_file(
        project_id,
        {"project_name": next_project_name, "brief": next_brief, "updated_at": ts},
        _parse_screening_plan_text(screening_plan_text),
    )
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
    scoring_config_path = project_scoring_config_path(project_id)
    if scoring_config_path.exists():
        scoring_config_path.unlink()
    return {"project_id": project_id, "deleted": True, "creator_count": len(creator_ids)}


def with_project_stats(project: dict[str, Any]) -> dict[str, Any]:
    with connect() as conn:
        candidates = conn.execute("SELECT COUNT(*) AS count FROM project_creators WHERE project_id=?", (project["project_id"],)).fetchone()["count"]
        if not candidates:
            candidates = conn.execute("SELECT COUNT(*) AS count FROM creators WHERE project_id=?", (project["project_id"],)).fetchone()["count"]
        pool = conn.execute(
            "SELECT COUNT(*) AS count FROM project_creators WHERE project_id=? AND pool_stage NOT IN (?, ?)",
            (project["project_id"], SCREENING_STAGE, "废弃达人池"),
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


def list_creators(
    project_id: str,
    status: str | None = None,
    pool_stage: str | None = None,
    exclude_pool_stage: str | None = None,
    q: str | None = None,
    include_raw: bool = True,
    creator_id: str | None = None,
    creator_ids: list[str] | None = None,
    limit: int | None = None,
    offset: int = 0,
) -> list[dict[str, Any]]:
    init_db()
    where = ["pc.project_id=?"]
    params: list[Any] = [project_id]
    if creator_id:
        where.append("pc.creator_id=?")
        params.append(creator_id)
    ids = [str(item) for item in (creator_ids or []) if str(item or "").strip()]
    if ids:
        placeholders = ", ".join("?" for _ in ids)
        where.append(f"pc.creator_id IN ({placeholders})")
        params.extend(ids)
    if status:
        where.append("pc.review_status=?")
        params.append(status)
    if pool_stage:
        where.append("pc.pool_stage=?")
        params.append(pool_stage)
    if exclude_pool_stage:
        where.append("COALESCE(pc.pool_stage, '')<>?")
        params.append(exclude_pool_stage)
    if q:
        where.append("(g.nickname LIKE ? OR g.persona_tags LIKE ? OR g.ip_city LIKE ?)")
        params.extend([f"%{q}%", f"%{q}%", f"%{q}%"])
    raw_payload_select = "g.raw_payload" if include_raw else "'{}' AS raw_payload"
    paging_sql = ""
    if limit is not None:
        paging_sql = " LIMIT ? OFFSET ?"
    sql = f"""
    SELECT pc.project_id, g.creator_id, g.source, g.xiaohongshu_id, g.pgy_blogger_id, g.pgy_url, g.nickname,
           g.creator_type, g.persona_tags, g.ip_city, g.profile_url, g.avatar_url, {raw_payload_select},
           pc.review_status AS status, pc.pool_stage, pc.portfolio_role, pc.owner, pc.note,
           pc.total_score AS project_total_score, pc.tier,
           g.created_at, pc.updated_at, m.*,
           s.total_score, s.rule_group_score, s.base_score, s.bonus_score, s.information_completeness,
           s.initial_tier, s.detail_collection_priority,
           s.budget_score, s.fans_score, s.cpe_score, s.traffic_score,
           s.persona_score, s.content_score, s.recommend_level, s.score_reason, s.cooperation_direction,
           s.stage1_priority, s.stage1_reason, s.project_match_status, s.project_match_confidence,
           s.final_recommend_level, s.target_content_ratio, s.target_content_evidence,
           s.product_scene_ratio, s.product_scene_evidence, s.conflict_content_ratio,
           s.conflict_content_categories, s.risk_control_result, s.recommended_format,
           s.hard_defects, s.warning_defects,
           s.manual_review_items, s.evidence_quotes, s.llm_confidence, s.llm_prompt_version, s.llm_schema_version,
           s.hard_filter_passed,
           r.review_status, r.review_reason, r.reviewer, r.reviewed_at
    FROM project_creators pc
    JOIN creators_global g ON pc.creator_id=g.creator_id
    LEFT JOIN creator_metrics_current m ON g.creator_id=m.creator_id
    LEFT JOIN creator_scores s ON g.creator_id=s.creator_id
    LEFT JOIN screening_reviews r ON g.creator_id=r.creator_id
    WHERE {' AND '.join(where)}
    ORDER BY COALESCE(s.total_score, pc.total_score, 0) DESC, pc.updated_at DESC
    {paging_sql}
    """
    query_params = [*params]
    if limit is not None:
        query_params.extend([limit, max(0, offset)])
    with connect() as conn:
        rows = rows_dict(conn.execute(sql, query_params).fetchall())
        if rows:
            with _scoring_batch_context():
                for row in rows:
                    row["creator_type"] = sanitize_creator_type(row.get("creator_type"))
                    row.update(_creator_stage_derivatives(row, project_id))
            return rows
        legacy_where = ["c.project_id=?"]
        legacy_params: list[Any] = [project_id]
        if creator_id:
            legacy_where.append("c.creator_id=?")
            legacy_params.append(creator_id)
        if ids:
            placeholders = ", ".join("?" for _ in ids)
            legacy_where.append(f"c.creator_id IN ({placeholders})")
            legacy_params.extend(ids)
        if status:
            legacy_where.append("c.status=?")
            legacy_params.append(status)
        if pool_stage:
            legacy_where.append("c.status=?")
            legacy_params.append(pool_stage)
        if exclude_pool_stage:
            legacy_where.append("c.status<>?")
            legacy_params.append(exclude_pool_stage)
        if q:
            legacy_where.append("(c.nickname LIKE ? OR c.persona_tags LIKE ? OR c.ip_city LIKE ?)")
            legacy_params.extend([f"%{q}%", f"%{q}%", f"%{q}%"])
        legacy_raw_payload_select = "c.raw_payload" if include_raw else "'{}' AS raw_payload"
        legacy_paging_sql = paging_sql
        legacy_sql = f"""
        SELECT c.project_id, c.creator_id, c.source, c.xiaohongshu_id, c.pgy_url, c.nickname,
               c.creator_type, c.persona_tags, c.ip_city, c.profile_url, c.avatar_url, c.status,
               c.created_at, c.updated_at, {legacy_raw_payload_select},
               m.*, s.total_score, s.rule_group_score, s.base_score, s.bonus_score, s.information_completeness,
               s.initial_tier, s.detail_collection_priority,
               s.budget_score, s.fans_score, s.cpe_score, s.traffic_score,
               s.persona_score, s.content_score, s.recommend_level, s.score_reason, s.cooperation_direction,
               s.stage1_priority, s.stage1_reason, s.project_match_status, s.project_match_confidence,
               s.final_recommend_level, s.target_content_ratio, s.target_content_evidence,
               s.product_scene_ratio, s.product_scene_evidence, s.conflict_content_ratio,
               s.conflict_content_categories, s.risk_control_result, s.recommended_format,
               s.hard_defects, s.warning_defects,
               s.manual_review_items, s.evidence_quotes, s.llm_confidence, s.llm_prompt_version, s.llm_schema_version,
               s.hard_filter_passed,
               r.review_status, r.review_reason, r.reviewer, r.reviewed_at
        FROM creators c
        LEFT JOIN creator_metrics m ON c.creator_id=m.creator_id
        LEFT JOIN creator_scores s ON c.creator_id=s.creator_id
        LEFT JOIN screening_reviews r ON c.creator_id=r.creator_id
        WHERE {' AND '.join(legacy_where)}
        ORDER BY COALESCE(s.total_score, 0) DESC, c.updated_at DESC
        {legacy_paging_sql}
        """
        legacy_query_params = [*legacy_params]
        if limit is not None:
            legacy_query_params.extend([limit, max(0, offset)])
        legacy_rows = rows_dict(conn.execute(legacy_sql, legacy_query_params).fetchall())
        with _scoring_batch_context():
            for row in legacy_rows:
                row["creator_type"] = sanitize_creator_type(row.get("creator_type"))
                row.update(_creator_stage_derivatives(row, project_id))
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
    items = list_creators(project_id, creator_id=creator_id)
    return next((item for item in items if item["creator_id"] == creator_id), None)


def _list_creators_for_scoring(project_id: str, creator_ids: list[str] | None = None) -> list[dict[str, Any]]:
    init_db()
    wanted_ids = list(dict.fromkeys(str(item) for item in (creator_ids or []) if str(item or "").strip()))
    where = ["pc.project_id=?"]
    params: list[Any] = [project_id]
    if wanted_ids:
        placeholders = ", ".join("?" for _ in wanted_ids)
        where.append(f"pc.creator_id IN ({placeholders})")
        params.extend(wanted_ids)
    sql = f"""
    SELECT pc.project_id, g.creator_id, g.source, g.xiaohongshu_id, g.pgy_blogger_id, g.pgy_url, g.nickname,
           g.creator_type, g.persona_tags, g.ip_city, g.profile_url, g.avatar_url, g.raw_payload,
           pc.review_status AS status, pc.pool_stage, pc.portfolio_role, pc.owner, pc.note,
           pc.total_score AS project_total_score, pc.tier,
           g.created_at, pc.updated_at, m.*
    FROM project_creators pc
    JOIN creators_global g ON pc.creator_id=g.creator_id
    LEFT JOIN creator_metrics_current m ON g.creator_id=m.creator_id
    WHERE {' AND '.join(where)}
    ORDER BY pc.updated_at DESC
    """
    legacy_where = ["c.project_id=?"]
    legacy_params: list[Any] = [project_id]
    if wanted_ids:
        placeholders = ", ".join("?" for _ in wanted_ids)
        legacy_where.append(f"c.creator_id IN ({placeholders})")
        legacy_params.extend(wanted_ids)
    legacy_sql = f"""
    SELECT c.project_id, c.creator_id, c.source, c.xiaohongshu_id, c.pgy_url, c.nickname,
           c.creator_type, c.persona_tags, c.ip_city, c.profile_url, c.avatar_url, c.status,
           c.created_at, c.updated_at, c.raw_payload, m.*
    FROM creators c
    LEFT JOIN creator_metrics m ON c.creator_id=m.creator_id
    WHERE {' AND '.join(legacy_where)}
    ORDER BY c.updated_at DESC
    """
    with connect() as conn:
        rows = rows_dict(conn.execute(sql, params).fetchall())
        if not rows:
            rows = rows_dict(conn.execute(legacy_sql, legacy_params).fetchall())
    for row in rows:
        row["creator_type"] = sanitize_creator_type(row.get("creator_type"))
    if wanted_ids:
        order = {creator_id: index for index, creator_id in enumerate(wanted_ids)}
        rows.sort(key=lambda item: order.get(str(item.get("creator_id")), len(order)))
    return rows


def _get_creator_for_scoring(project_id: str, creator_id: str) -> dict[str, Any] | None:
    rows = _list_creators_for_scoring(project_id, [creator_id])
    return rows[0] if rows else None


def count_creators(project_id: str, status: str | None = None, q: str | None = None) -> int:
    init_db()
    where = ["pc.project_id=?"]
    params: list[Any] = [project_id]
    if status:
        where.append("pc.review_status=?")
        params.append(status)
    if q:
        where.append("(g.nickname LIKE ? OR g.persona_tags LIKE ? OR g.ip_city LIKE ?)")
        params.extend([f"%{q}%", f"%{q}%", f"%{q}%"])
    with connect() as conn:
        count = conn.execute(
            f"""
            SELECT COUNT(*) AS count
            FROM project_creators pc
            JOIN creators_global g ON pc.creator_id=g.creator_id
            WHERE {' AND '.join(where)}
            """,
            params,
        ).fetchone()["count"]
        if count:
            return int(count)
        legacy_where = ["c.project_id=?"]
        legacy_params: list[Any] = [project_id]
        if status:
            legacy_where.append("c.status=?")
            legacy_params.append(status)
        if q:
            legacy_where.append("(c.nickname LIKE ? OR c.persona_tags LIKE ? OR c.ip_city LIKE ?)")
            legacy_params.extend([f"%{q}%", f"%{q}%", f"%{q}%"])
        return int(conn.execute(
            f"SELECT COUNT(*) AS count FROM creators c WHERE {' AND '.join(legacy_where)}",
            legacy_params,
        ).fetchone()["count"])


def creator_screening_stats(project_id: str) -> dict[str, Any]:
    init_db()
    excluded_statuses = ("已通过", "已写回飞书", "已驳回", "默认淘汰", "已废弃", "备选")
    placeholders = ", ".join("?" for _ in excluded_statuses)

    with connect() as conn:
        rows = rows_dict(
            conn.execute(
                f"""
                SELECT COALESCE(s.total_score, pc.total_score) AS tier_score,
                       COUNT(*) AS count
                FROM project_creators pc
                LEFT JOIN creator_scores s ON pc.creator_id=s.creator_id
                WHERE pc.project_id=?
                  AND COALESCE(pc.review_status, '') NOT IN ({placeholders})
                GROUP BY COALESCE(s.total_score, pc.total_score)
                """,
                [project_id, *excluded_statuses],
            ).fetchall()
        )
        status_rows = rows_dict(
            conn.execute(
                """
                SELECT COALESCE(review_status, '待审核') AS status, COUNT(*) AS count
                FROM project_creators
                WHERE project_id=?
                GROUP BY COALESCE(review_status, '待审核')
                """,
                (project_id,),
            ).fetchall()
        )
        if not rows and not status_rows:
            legacy_rows = rows_dict(
                conn.execute(
                    f"""
                    SELECT s.total_score AS tier_score,
                           COUNT(*) AS count
                    FROM creators c
                    LEFT JOIN creator_scores s ON c.creator_id=s.creator_id
                    WHERE c.project_id=?
                      AND COALESCE(c.status, '') NOT IN ({placeholders})
                    GROUP BY s.total_score
                    """,
                    [project_id, *excluded_statuses],
                ).fetchall()
            )
            rows = legacy_rows
            status_rows = rows_dict(
                conn.execute(
                    """
                    SELECT COALESCE(status, '待审核') AS status, COUNT(*) AS count
                    FROM creators
                    WHERE project_id=?
                    GROUP BY COALESCE(status, '待审核')
                    """,
                    (project_id,),
                ).fetchall()
            )

    tiers = {"S": 0, "A": 0, "B+": 0, "B": 0, "C": 0, "未评分": 0}
    for row in rows:
        tier = normalize_score_tier_key("", row.get("tier_score")) or "未评分"
        tiers[tier] = tiers.get(tier, 0) + int(row.get("count") or 0)
    statuses = {str(row.get("status") or "待审核"): int(row.get("count") or 0) for row in status_rows}
    screening_total = sum(tiers.values())
    return {
        "project_id": project_id,
        "total": screening_total,
        "tiers": tiers,
        "statuses": statuses,
        "passed": sum(statuses.get(status, 0) for status in ("已通过", "已写回飞书")),
        "rejected": sum(statuses.get(status, 0) for status in ("已驳回", "默认淘汰")),
        "discarded": statuses.get("已废弃", 0),
        "backup": statuses.get("备选", 0),
        "review": statuses.get("人工复核", 0),
        "pending": screening_total - statuses.get("人工复核", 0),
    }


_LIGHT_CREATOR_FIELDS = {
    "project_id",
    "creator_id",
    "source",
    "xiaohongshu_id",
    "pgy_blogger_id",
    "pgy_url",
    "nickname",
    "creator_type",
    "persona_tags",
    "ip_city",
    "avatar_url",
    "raw_payload",
    "status",
    "pool_stage",
    "portfolio_role",
    "owner",
    "note",
    "project_total_score",
    "tier",
    "created_at",
    "updated_at",
    "collected_at",
    "followers_count",
    "quote_price",
    "budget_status",
    "traffic_stability",
    "rate_limit_risk",
    "rate_limit_risk_reason",
    "natural_cpc",
    "natural_cpe",
    "effective_cpc",
    "effective_cpc_source",
    "effective_cpe",
    "effective_cpe_source",
    "daily_exposure_median",
    "daily_read_median",
    "daily_interaction_median",
    "cooperation_exposure_median",
    "cooperation_read_median",
    "cooperation_interaction_median",
    "search_recommend_ratio",
    "search_recommend_review_status",
    "search_recommend_review_note",
    "fans_35_plus_ratio",
    "fans_35_plus_ratio_source",
    "child_age",
    "child_grade",
    "child_grade_confidence",
    "child_grade_evidence",
    "child_gender",
    "topic_point",
    "content_scene_tags",
    "content_scene_evidence",
    "presentation_style_tags",
    "cost_30d",
    "cost_90d",
    "total_score",
    "rule_group_score",
    "base_score",
    "bonus_score",
    "information_completeness",
    "initial_tier",
    "detail_collection_priority",
    "budget_score",
    "fans_score",
    "cpe_score",
    "traffic_score",
    "persona_score",
    "content_score",
    "recommend_level",
    "score_reason",
    "cooperation_direction",
    "stage1_priority",
    "stage1_reason",
    "project_match_status",
    "project_match_confidence",
    "final_recommend_level",
    "target_content_ratio",
    "target_content_evidence",
    "product_scene_ratio",
    "product_scene_evidence",
    "conflict_content_ratio",
    "conflict_content_categories",
    "risk_control_result",
    "recommended_format",
    "hard_defects",
    "warning_defects",
    "manual_review_items",
    "evidence_quotes",
    "llm_confidence",
    "llm_prompt_version",
    "llm_schema_version",
    "hard_filter_passed",
    "review_status",
    "review_reason",
    "reviewer",
    "reviewed_at",
}


def compact_creator_for_list(creator: dict[str, Any]) -> dict[str, Any]:
    if creator.get("project_id"):
        with _scoring_batch_context():
            creator = {**creator, **_creator_stage_derivatives(creator, str(creator.get("project_id")))}
    result = {key: creator.get(key) for key in _LIGHT_CREATOR_FIELDS if key in creator}
    display_score = result.get("total_score")
    if display_score in (None, ""):
        display_score = result.get("project_total_score")
    normalized_tier = normalize_score_tier_key("", display_score) or normalize_score_tier_key(
        result.get("initial_tier") or result.get("tier") or result.get("detail_collection_priority"),
    )
    if normalized_tier:
        result["initial_tier"] = normalized_tier
    if result.get("score_reason"):
        result["score_reason"] = str(result["score_reason"])[:420]
    if result.get("cooperation_direction"):
        result["cooperation_direction"] = str(result["cooperation_direction"])[:160]
    if result.get("review_reason"):
        result["review_reason"] = str(result["review_reason"])[:220]
    if result.get("manual_review_items"):
        result["manual_review_items"] = str(result["manual_review_items"])[:320]
    if result.get("evidence_quotes"):
        result["evidence_quotes"] = str(result["evidence_quotes"])[:320]
    if result.get("hard_defects"):
        result["hard_defects"] = str(result["hard_defects"])[:1200]
    if result.get("warning_defects"):
        result["warning_defects"] = str(result["warning_defects"])[:1200]
    return result


def update_creator(project_id: str, creator_id: str, payload: dict[str, Any], score: bool = False) -> dict[str, Any]:
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


def backfill_creator_derived_fields(
    project_id: str,
    creator_ids: list[str] | None = None,
    *,
    rescore: bool = True,
    use_llm: bool = False,
    operator: str = "系统",
) -> dict[str, Any]:
    init_db()
    wanted = {str(item) for item in creator_ids} if creator_ids else None
    creators = [
        creator for creator in list_creators(project_id)
        if wanted is None or str(creator.get("creator_id")) in wanted
    ]
    if not creators:
        return {"project_id": project_id, "backfilled": 0, "rescored": 0, "creator_ids": []}

    ts = now()
    updated_ids: list[str] = []
    with connect() as conn:
        for creator in creators:
            creator_id = str(creator.get("creator_id") or "")
            raw_payload = _parse_payload_json(creator.get("raw_payload"))
            normalized = normalize_creator({**creator, "raw_payload": raw_payload}, project_id)
            current_metrics = metric_payload(normalized)
            previous = row_dict(conn.execute("SELECT * FROM creator_metrics_current WHERE creator_id=?", (creator_id,)).fetchone())
            conn.execute(
                f"""
                INSERT INTO creator_metrics(creator_id, {', '.join(METRIC_FIELDS)}, collected_at)
                VALUES ({', '.join(['?'] * (len(METRIC_FIELDS) + 2))})
                ON CONFLICT(creator_id) DO UPDATE SET {', '.join(f'{field}=excluded.{field}' for field in METRIC_FIELDS)},
                collected_at=excluded.collected_at
                """,
                [creator_id, *[current_metrics[field] for field in METRIC_FIELDS], ts],
            )
            conn.execute(
                f"""
                INSERT INTO creator_metrics_current(creator_id, {', '.join(METRIC_FIELDS)}, collected_at)
                VALUES ({', '.join(['?'] * (len(METRIC_FIELDS) + 2))})
                ON CONFLICT(creator_id) DO UPDATE SET {', '.join(f'{field}=excluded.{field}' for field in METRIC_FIELDS)},
                collected_at=excluded.collected_at
                """,
                [creator_id, *[current_metrics[field] for field in METRIC_FIELDS], ts],
            )
            changed, change_summary = _metrics_changed(previous, current_metrics)
            if changed:
                _write_metrics_history(conn, project_id, creator_id, current_metrics, change_summary, ts)
            updated_ids.append(creator_id)
        log(
            conn,
            project_id,
            "metrics",
            "回填派生字段",
            project_id,
            operator,
            f"回填 {len(updated_ids)} 位达人：阅读单价/互动单价、35+、孩子年级、流量风险、搜推复核状态",
            "success",
        )
    rescored = 0
    if rescore and updated_ids:
        result = score_project(project_id, creator_ids=updated_ids, use_llm=use_llm, trigger_source="derived_backfill")
        rescored = int(result.get("scored") or 0)
    return {
        "project_id": project_id,
        "backfilled": len(updated_ids),
        "rescored": rescored,
        "creator_ids": updated_ids,
    }


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


def creator_pool(project_id: str, include_screening: bool = True) -> dict[str, Any]:
    project = get_project(project_id)
    if not project:
        raise KeyError(project_id)
    creators = list_creators(
        project_id,
        include_raw=False,
        exclude_pool_stage=None if include_screening else SCREENING_STAGE,
    )
    groups = {stage: [] for stage in POOL_STAGES}
    for creator in creators:
        stage = creator.get("pool_stage") or stage_from_status(creator.get("status"), creator.get("total_score"))
        if stage not in groups:
            stage = SCREENING_STAGE
        groups[stage].append(creator)
    for items in groups.values():
        items.sort(key=lambda item: float(item.get("total_score") or 0), reverse=True)
    pool_creators = [item for stage, items in groups.items() if stage not in {SCREENING_STAGE, "废弃达人池"} for item in items]
    stats = {
        "total": len(pool_creators),
        "screening": len(groups[SCREENING_STAGE]),
        "avg_score": round(sum(float(item.get("total_score") or 0) for item in pool_creators) / len(pool_creators), 2) if pool_creators else 0,
        "by_stage": {stage: len(items) for stage, items in groups.items()},
        "qualified": len(groups["已合作跟进中"]) + len(groups["合格达人待合作"]),
        "discarded": len(groups["废弃达人池"]),
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
        "effective_cpc",
        "effective_cpe",
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
        "search_recommend_review_status",
        "fans_35_plus_ratio",
        "child_age",
        "child_grade",
        "child_grade_confidence",
        "child_grade_evidence",
        "child_gender",
        "topic_point",
        "content_scene_tags",
        "presentation_style_tags",
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
    cached = creator.get("_text_blob")
    if isinstance(cached, str):
        return cached
    raw_payload = creator.get("raw_payload") or ""
    if isinstance(raw_payload, dict):
        raw_payload = json.dumps(raw_payload, ensure_ascii=False)
    text = " ".join(
        str(creator.get(key) or "")
        for key in ("nickname", "creator_type", "persona_tags", "topic_point", "child_age", "child_grade", "ip_city")
    ) + f" {raw_payload}"
    creator["_text_blob"] = text
    return text


def _identity_text_blob(creator: dict[str, Any], *, include_notes: bool = True) -> str:
    raw_payload = _creator_raw_payload(creator)
    parts = [
        creator.get("nickname"),
        creator.get("creator_type"),
        creator.get("persona_tags"),
        creator.get("topic_point"),
        creator.get("child_age"),
        creator.get("child_grade"),
        creator.get("ip_city"),
    ]
    if isinstance(raw_payload, dict):
        for key in ("blogger_profile", "personal_intro", "profile_intro", "signature", "bio"):
            parts.append(raw_payload.get(key))
        detail = raw_payload.get("detail")
        if isinstance(detail, dict):
            for key in ("blogger_profile", "personal_intro", "profile_intro", "signature", "bio"):
                parts.append(detail.get(key))
        if include_notes:
            for note in _collect_note_cases_from_payload(raw_payload)[:12]:
                if isinstance(note, dict):
                    parts.extend([note.get("title"), note.get("content"), note.get("summary")])
    return " ".join(str(item or "") for item in parts)


def _contains_any(text: str, keywords: list[str]) -> bool:
    return any(keyword and keyword in text for keyword in keywords)


OVERSEAS_STUDY_BACKGROUND_KEYWORDS = [
    "留学",
    "留学生",
    "留子",
    "海外",
    "国外",
    "美国",
    "英国",
    "韩国",
    "日本",
    "欧洲",
    "美本",
    "英本",
    "海本",
    "澳洲",
    "澳大利亚",
    "加拿大",
    "新加坡",
    "港澳",
    "港校",
    "国际学校",
    "海外教育",
    "海外华人",
    "study abroad",
    "overseas",
    "international student",
]


def _has_overseas_study_background(creator: dict[str, Any], direction_profile: dict[str, Any] | None = None) -> bool:
    matched = " ".join(str(item) for item in ((direction_profile or {}).get("matched") or []))
    text = f"{matched} {_identity_text_blob(creator)}".lower()
    explicit_text = " ".join(
        str(creator.get(key) or "")
        for key in ("nickname", "creator_type", "persona_tags", "ip_city", "topic_point")
    ).lower()
    explicit_hits = [
        "留学", "留学生", "留子", "留学教育", "海外华人", "美本", "英本", "海本",
        "美国", "英国", "澳洲", "澳大利亚", "加拿大", "新加坡", "韩国", "日本", "法国",
        "德国", "荷兰", "芬兰", "比利时", "马来西亚", "中国 香港", "港校",
        "study abroad", "overseas", "international student",
    ]
    note_identity_hits = [
        "留学", "留学生", "留子", "海外留学", "国外上课", "海外课堂", "国际学校", "港校",
        "assignment", "essay", "final", "lecture",
    ]
    return _contains_any(explicit_text, explicit_hits) or _contains_any(text, note_identity_hits)


def _project_special_scoring_config(project_id: str | None) -> dict[str, Any]:
    if not project_id:
        return {}
    plan = _project_screening_plan(project_id)
    config = plan.get("projectSpecialScoring") or plan.get("specialScoringPolicy") or plan.get("project_scoring_policy")
    return config if isinstance(config, dict) and config.get("enabled", True) is not False else {}


def _has_project_special_scoring(project_id: str | None) -> bool:
    return bool(_project_special_scoring_config(project_id))


def _project_special_scoring_profile(
    creator: dict[str, Any],
    config: dict[str, Any],
    direction_profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    text = _identity_text_blob(creator).lower()
    matched = " ".join(str(item) for item in ((direction_profile or {}).get("matched") or [])).lower()
    combined = f"{matched} {text}"
    identity_config = config.get("identity") if isinstance(config.get("identity"), dict) else {}
    scene_config = config.get("scene") if isinstance(config.get("scene"), dict) else {}
    negative_config = config.get("negative") if isinstance(config.get("negative"), dict) else {}
    identity_fields = identity_config.get("fields") or ["nickname", "creator_type", "persona_tags", "ip_city", "topic_point"]
    explicit_text = " ".join(
        str(creator.get(key) or "")
        for key in identity_fields
    ).lower()
    explicit_overseas_hits = [
        keyword for keyword in (identity_config.get("keywords") or [])
        if keyword.lower() in explicit_text
    ]
    note_overseas_hits = [
        keyword for keyword in (identity_config.get("evidence_keywords") or [])
        if keyword.lower() in combined
    ]
    overseas_hits = list(dict.fromkeys([*explicit_overseas_hits, *note_overseas_hits]))
    study_hits = [keyword for keyword in (scene_config.get("keywords") or []) if keyword.lower() in combined]
    negative_hits = [keyword for keyword in (negative_config.get("keywords") or []) if keyword.lower() in combined]
    return {
        "overseas_hits": list(dict.fromkeys(overseas_hits))[:5],
        "study_hits": list(dict.fromkeys(study_hits))[:6],
        "negative_hits": list(dict.fromkeys(negative_hits))[:4],
        "overseas": bool(overseas_hits),
        "study": bool(study_hits),
        "brief_tag_hit_count": len(set(overseas_hits[:5] + study_hits[:6])),
    }


def _score_information_completeness(creator: dict[str, Any]) -> float:
    key_groups = [
        ("pgy_url",),
        ("quote_price",),
        ("followers_count",),
        ("creator_type", "persona_tags"),
        ("ip_city",),
        ("fans_35_plus_ratio",),
        ("effective_cpc", "effective_cpe", "natural_cpc", "natural_cpe"),
        ("search_recommend_review_status",),
        ("child_age", "child_grade", "topic_point"),
        ("traffic_stability", "rate_limit_risk", "rate_limit_risk_reason"),
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


def min_priority_label(value: str, cap: str) -> str:
    order = {
        "数据暂缓": 0,
        "低优先级": 1,
        "中优先级": 2,
        "中高优先级": 3,
        "高优先级": 4,
        "最高优先级": 5,
    }
    value_text = str(value or "低优先级")
    cap_text = str(cap or "低优先级")
    if order.get(value_text, 1) <= order.get(cap_text, 1):
        return value_text
    return cap_text


def _initial_rule_group_score(
    base_score: Any,
    bonus_score: Any,
    information_completeness: Any,
    hard_pass: bool = True,
) -> float:
    """Score used only for first-pass grouping before detail evidence gates."""
    if not hard_pass:
        return min(parse_number(base_score) or 0, 69.0)
    base = parse_number(base_score) or 0
    bonus = parse_number(bonus_score) or 0
    completeness = parse_number(information_completeness) or 0
    if completeness > 1:
        completeness = completeness / 100
    group_score = base + bonus
    if completeness >= 0.72:
        group_score += 2
    elif completeness >= 0.55:
        group_score += 1
    return round(max(0, min(100, group_score)), 2)


def _initial_rule_tier_and_priority(
    creator: dict[str, Any],
    group_score: float,
    bonus_score: Any,
    hard_pass: bool,
    data_profile: dict[str, Any],
    efficiency_profile: dict[str, Any],
    direction_profile: dict[str, Any],
) -> tuple[str, str]:
    if not hard_pass:
        return "C", "数据暂缓"
    matched = " ".join(str(item) for item in (direction_profile.get("matched") or []))
    weak_generic_hit = any(keyword in matched for keyword in ["记录", "vlog", "日常", "生活"])
    tier_score = group_score
    if not data_profile.get("good_data"):
        tier_score = min(tier_score, 84)
    if not efficiency_profile.get("good_efficiency"):
        tier_score = min(tier_score, 89)
    if direction_profile.get("level") != "strong":
        tier_score = min(tier_score, 84)
    if weak_generic_hit:
        tier_score = min(tier_score, 84)
    tier = _initial_tier(tier_score, True)
    priority = _detail_collection_priority(tier_score, bonus_score, True)
    return tier, priority


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
DETAIL_COMPLETION_ACTIONABLE_FIELDS = {"education_context", "note_cases", "detail_page_evidence"}
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

    raw_payload = _creator_raw_payload(creator)
    detail = raw_payload.get("detail") if isinstance(raw_payload, dict) else None
    summary = raw_payload.get("detail_collection_summary") if isinstance(raw_payload, dict) else None
    if not isinstance(detail, dict) and not isinstance(summary, dict):
        needs.append("缺达人详情页证据")
    if not _collect_note_cases_from_payload(raw_payload):
        needs.append("缺近期/合作笔记案例")
    return list(dict.fromkeys(needs))


def detail_completion_missing_fields(creator: dict[str, Any]) -> list[str]:
    fields: list[str] = []
    for label, keys in {
        "read_median": ("daily_read_median", "image_daily_read_median", "video_daily_read_median", "cooperation_read_median"),
        "interaction_median": ("daily_interaction_median", "image_daily_interaction_median", "video_daily_interaction_median", "cooperation_interaction_median"),
        "cost_efficiency": ("image_cpm", "video_cpm", "image_read_unit_price", "video_read_unit_price", "image_interaction_unit_price", "video_interaction_unit_price"),
    }.items():
        if not any((parse_number(creator.get(key)) or 0) > 0 for key in keys):
            fields.append(label)
    if not any(str(creator.get(key) or "").strip() for key in ("child_age", "child_grade", "topic_point")):
        fields.append("education_context")
    raw_payload = _creator_raw_payload(creator)
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
    init_db()
    with connect() as conn:
        migrate_legacy_creators(conn)
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
    project_data_token = _PROJECT_DATA_CACHE.set({})
    direction_terms_token = _PROJECT_DIRECTION_TERMS_CACHE.set({})
    try:
        yield
    finally:
        _PROJECT_DIRECTION_TERMS_CACHE.reset(direction_terms_token)
        _PROJECT_DATA_CACHE.reset(project_data_token)
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


def _interaction_reference_from_creator(creator: dict[str, Any]) -> float | None:
    values = [
        parse_number(creator.get("cooperation_interaction_median")),
        parse_number(creator.get("daily_interaction_median")),
        parse_number(creator.get("image_daily_interaction_median")),
        parse_number(creator.get("video_daily_interaction_median")),
    ]
    values = [value for value in values if value is not None and value > 0]
    return max(values) if values else None


def _has_cooperation_note_metrics(creator: dict[str, Any]) -> bool:
    metric_keys = (
        "cooperation_exposure_median",
        "cooperation_read_median",
        "cooperation_interaction_median",
        "natural_cpc",
        "natural_cpe",
    )
    has_metric = any((parse_number(creator.get(key)) or 0) > 0 for key in metric_keys)
    if not has_metric:
        return False
    raw_payload = _creator_raw_payload(creator)
    performance = raw_payload.get("data_performance") if isinstance(raw_payload, dict) else None
    if not isinstance(performance, dict):
        return True
    cooperation = performance.get("cooperation") if isinstance(performance.get("cooperation"), dict) else {}
    for mode in ("scale", "cost"):
        metrics = cooperation.get(mode, {}).get("metrics", {}) if isinstance(cooperation.get(mode), dict) else {}
        if isinstance(metrics, dict) and any((parse_number(value) or 0) > 0 for value in metrics.values()):
            return True
    return False


def _apply_missing_cooperation_note_data_gate(
    total: float,
    creator: dict[str, Any],
    reasons: list[str],
    *,
    cap: float = 79.0,
) -> bool:
    if _has_cooperation_note_metrics(creator):
        return False
    if total > cap:
        reasons.append("缺合作笔记核心数据，系统级下调初筛优先级：详情优先级最高中优先级，需补合作笔记数据后再上调")
    else:
        reasons.append("缺合作笔记核心数据，优先级下调，需补合作笔记数据")
    return True


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
    interaction = _interaction_reference_from_creator(creator)
    cpm = _first_number(creator.get("image_cpm"), creator.get("video_cpm"), positive=True)
    cpc = _first_number(creator.get("effective_cpc"), creator.get("natural_cpc"), creator.get("image_read_unit_price"), creator.get("video_read_unit_price"), positive=True)
    cpe = _first_number(creator.get("effective_cpe"), creator.get("natural_cpe"), creator.get("image_interaction_unit_price"), creator.get("video_interaction_unit_price"), positive=True)
    estimated_cpm = quote / exposure * 1000 if quote is not None and exposure else None
    estimated_cpc = quote / read if quote is not None and read else None
    estimated_cpe = quote / interaction if quote is not None and interaction else None
    return {
        "quote": quote,
        "read": read,
        "exposure": exposure,
        "interaction": interaction,
        "cpm": cpm,
        "estimated_cpm": estimated_cpm,
        "cpc": cpc,
        "cpe": cpe,
        "estimated_cpc": estimated_cpc,
        "estimated_cpe": estimated_cpe,
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
        elif efficiency["estimated_cpe"] is not None:
            cpes.append(efficiency["estimated_cpe"])
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
    cpe = metrics["cpe"] if metrics["cpe"] is not None else metrics["estimated_cpe"]
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
    strong_metrics = [
        cpm is not None and cpm <= cpm_good_max,
        cpc is not None and cpc <= cpc_good_max,
        cpe is not None and cpe <= cpe_good_max,
    ]
    return {
        **metrics,
        "effective_cpm": cpm,
        "effective_cpc": cpc,
        "score": round(max(0, min(12, score)), 2),
        "good_efficiency": good_efficiency,
        "excellent_efficiency": sum(1 for item in strong_metrics if item) >= 2,
        "poor_efficiency": poor_efficiency,
        "reasons": reasons,
    }


def _budget_effect_profile(creator: dict[str, Any], benchmark: dict[str, Any] | None = None) -> dict[str, Any]:
    benchmark = benchmark or _scoring_benchmark_for_creator(creator)
    metrics = _efficiency_metrics(creator)
    quote = metrics["quote"]
    cpm = metrics["cpm"] if metrics["cpm"] is not None else metrics["estimated_cpm"]
    cpc = metrics["cpc"] if metrics["cpc"] is not None else metrics["estimated_cpc"]
    cpe = metrics["cpe"] if metrics["cpe"] is not None else metrics["estimated_cpe"]
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
    female = ratio(creator.get("female_fans_ratio"))
    text = _text_blob(creator)
    score = 12.0
    if female is not None and female >= 0.65:
        score = min(15, score + 1)
    if _contains_any(text, ["妈妈", "家长", "宝妈", "陪读", "大孩", "小升初", "初中", "高中"]):
        score = min(15, score + 1)
    return round(score, 2), False


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
    raw_payload = _creator_raw_payload(creator)
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
        elif reply >= 0.5:
            score += 0.8
            reasons.append("48h回复率一般")
        else:
            reasons.append("48h回复率低于50%，基础筛选扣分")
    else:
        score += 1
        reasons.append("48h回复率未进入本轮数据")
    if parse_number(creator.get("followers_count")) is not None:
        score += 0.8
    if creator.get("avatar_url") or creator.get("xiaohongshu_id"):
        score += 0.7
    return round(max(0, min(5, score)), 2), reasons


def _recent_note_data_profile(creator: dict[str, Any]) -> dict[str, Any]:
    raw_payload = _creator_raw_payload(creator)
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
    strong_interaction = avg_interaction is not None and avg_interaction >= 80
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
        "excellent_data": bool(good_data and strong_interaction and best_read >= expected),
        "weak_recent_data": weak_recent_data,
    }


DEFAULT_SCORING_WEIGHTS = {"budget": 15, "fans": 5, "cpe": 20, "engagement": 30, "persona": 20, "content": 10}


def _project_scoring_weights(project_id: str | None) -> dict[str, float]:
    plan = _project_screening_plan(project_id) if project_id else {}
    scoring_criteria = plan.get("scoringCriteria") if isinstance(plan.get("scoringCriteria"), dict) else {}
    raw = plan.get("scoringWeights") or scoring_criteria.get("dimension_weights") or {}
    weights: dict[str, float] = {}
    aliases = {
        "traffic": "engagement",
        "engagement_score": "engagement",
        "cost": "cpe",
        "efficiency": "cpe",
        "audience": "fans",
        "fan": "fans",
    }
    if isinstance(raw, dict):
        for key, value in raw.items():
            normalized_key = aliases.get(str(key), str(key))
            if normalized_key not in DEFAULT_SCORING_WEIGHTS:
                continue
            number = parse_number(value)
            if number is not None and number > 0:
                weights[normalized_key] = float(number)
    if not weights:
        weights = dict(DEFAULT_SCORING_WEIGHTS)
    for key, default in DEFAULT_SCORING_WEIGHTS.items():
        weights.setdefault(key, float(default))
    total = sum(weights.values())
    if total <= 0:
        return dict(DEFAULT_SCORING_WEIGHTS)
    return {key: round(value / total * 100, 4) for key, value in weights.items()}


def _weighted_component(raw_100: Any, weight: float) -> float:
    return round(_clamp_score(raw_100) * weight / 100, 2)


def _project_hard_filters(project_id: str | None) -> list[dict[str, Any]]:
    if not project_id:
        return []
    plan = _project_screening_plan(project_id)
    scoring_criteria = plan.get("scoringCriteria") if isinstance(plan.get("scoringCriteria"), dict) else {}
    hard_filters = plan.get("scoringHardFilters") or scoring_criteria.get("hard_rules") or plan.get("hardFilters") or []
    return [item for item in hard_filters if isinstance(item, dict)]


def _project_rule_mentions(project_id: str | None, keywords: list[str]) -> bool:
    lowered_keywords = [keyword.lower() for keyword in keywords]
    for item in _project_hard_filters(project_id):
        text = " ".join(str(item.get(key) or "") for key in ("field", "standard", "condition", "value", "label", "feishuField")).lower()
        if any(keyword in text for keyword in lowered_keywords):
            return True
    return False


def _project_metric_threshold(project_id: str | None, metric: str) -> float | None:
    if not project_id:
        return None
    for item in _project_hard_filters(project_id):
        text = " ".join(str(item.get(key) or "") for key in ("field", "standard", "condition", "value", "label", "feishuField"))
        lowered = text.lower()
        if metric == "quote" and any(keyword in lowered for keyword in ["报价", "预算", "合作价格", "平台价格"]):
            value = _threshold_from_text(text, "quote")
        elif metric == "fans35" and any(keyword in lowered for keyword in ["35", "34", "粉丝年龄", "宝妈", "家长"]):
            value = _threshold_from_text(text, "fans35")
        elif metric == "cpc" and "cpc" in lowered:
            value = _threshold_from_text(text, "cpc")
        elif metric == "cpe" and "cpe" in lowered:
            value = _threshold_from_text(text, "cpe")
        else:
            value = None
        if value is not None:
            return value
    return None


def _rule_targets_quote(field: str, condition: str, value: str, item: dict[str, Any]) -> bool:
    field_text = " ".join(
        str(item.get(key) or "")
        for key in ("field", "standard", "label", "feishuField", "pgyField", "subField", "sub_field")
    )
    text = f"{field_text} {condition} {value}"
    if any(keyword in field_text for keyword in ["报价", "价格", "合作价", "平台价", "达人预算", "单达人预算", "执行价"]):
        return True
    if any(keyword in text for keyword in ["¥", "￥", "元以内", "不高于", "不超过"]) and not any(keyword in text.lower() for keyword in ["cpc", "cpe", "cpm", "阅读", "互动", "曝光", "近30天"]):
        return True
    return False


def _collect_project_terms(value: Any, *, limit: int = 80) -> list[str]:
    terms: list[str] = []
    blocked_generic_terms = {
        "记录",
        "vlog",
        "视频",
        "日常",
        "生活",
        "生活记录",
        "大学",
        "大学教育",
        "教程",
        "测评",
        "经验",
        "学习",
        "教育",
        "学生",
        "产品",
        "工具",
    }

    def add(text: Any) -> None:
        for part in re.split(r"[、,，;；/|\\n\\r\\t ]+", str(text or "")):
            part = part.strip(" ：:。.!！?？()（）[]【】")
            lowered = part.lower()
            has_chinese = bool(re.search(r"[\u4e00-\u9fff]", part))
            if (
                2 <= len(part) <= 24
                and part not in terms
                and not lowered.startswith(("http", "www"))
                and "." not in lowered
                and lowered not in {"com", "cn", "pgy", "xiaohongshu", "solar", "trade", "blogger", "detail"}
                and part not in blocked_generic_terms
                and (has_chinese or len(part) >= 4)
            ):
                terms.append(part)

    def visit(item: Any) -> None:
        if len(terms) >= limit:
            return
        if isinstance(item, str):
            add(item)
        elif isinstance(item, dict):
            for key, child in item.items():
                if str(key) in {"id", "scheme_id", "created_at", "updated_at"}:
                    continue
                visit(child)
        elif isinstance(item, list):
            for child in item[:30]:
                visit(child)

    visit(value)
    return terms[:limit]


def _project_direction_fit(creator: dict[str, Any], project_id: str | None) -> dict[str, Any]:
    if not project_id:
        return _tag_direction_fit(creator)
    plan = _project_screening_plan(project_id)
    if not plan:
        return _tag_direction_fit(creator)
    terms_cache = _PROJECT_DIRECTION_TERMS_CACHE.get()
    cached_terms = terms_cache.get(project_id) if terms_cache is not None else None
    if cached_terms is None:
        project_fit = plan.get("projectFitConfig") if isinstance(plan.get("projectFitConfig"), dict) else {}
        promotion = plan.get("promotionStrategy") if isinstance(plan.get("promotionStrategy"), dict) else {}
        scoring_criteria = plan.get("scoringCriteria") if isinstance(plan.get("scoringCriteria"), dict) else {}
        project = _cached_project(project_id) or {}
        cached_terms = {
            "positive": _collect_project_terms(
                {
                    "brief": project.get("brief"),
                    "promotion": promotion,
                    "project_fit": {
                        "preferred_content_scenes": project_fit.get("preferred_content_scenes"),
                        "preferred_presentation_styles": project_fit.get("preferred_presentation_styles"),
                        "target_grade_keywords": project_fit.get("target_grade_keywords"),
                        "parent_decision_keywords": project_fit.get("parent_decision_keywords"),
                    },
                    "scoring": {
                        "post_score_rules": scoring_criteria.get("post_score_rules"),
                        "manual_review_rules": scoring_criteria.get("manual_review_rules"),
                        "hard_rules": scoring_criteria.get("hard_rules"),
                    },
                }
            ),
            "negative": _collect_project_terms(
                {
                    "discouraged": project_fit.get("discouraged_keywords"),
                    "negative": scoring_criteria.get("negative_constraints") or plan.get("negativeConstraints"),
                },
                limit=40,
            ),
            "summary": str((promotion.get("summary") if isinstance(promotion, dict) else "") or ""),
        }
        if terms_cache is not None:
            terms_cache[project_id] = cached_terms
    positive_terms = cached_terms.get("positive") or []
    negative_terms = cached_terms.get("negative") or []
    text = _text_blob(creator).lower()
    positive_hits = [term for term in positive_terms if term.lower() in text]
    negative_hits = [term for term in negative_terms if term.lower() in text]
    if negative_hits:
        score = 3.0
        level = "off"
    elif len(positive_hits) >= 3:
        score = 15.0
        level = "strong"
    elif positive_hits:
        score = 11.0
        level = "medium"
    else:
        score = 8.0
        level = "neutral"
    return {
        "score": round(max(0, min(15, score)), 2),
        "level": level,
        "matched": list(dict.fromkeys([*positive_hits[:5], *negative_hits[:3]])),
        "cooperation_hint": str(cached_terms.get("summary") or ""),
    }


FALLBACK_BENCHMARK_MIN_SAMPLES = 5
BATCH_DEFECT_LOW_METRIC_RATIO = 0.5
BATCH_DEFECT_HIGH_COST_RATIO = 1.5


def _creator_follower_bucket(creator: dict[str, Any]) -> str:
    followers = parse_number(creator.get("followers_count")) or 0
    return str(_market_benchmark_for_followers(followers).get("key") or "unknown")


def _creator_category_bucket(creator: dict[str, Any]) -> str:
    text = " ".join(
        str(creator.get(key) or "")
        for key in ("creator_type", "persona_tags", "content_scene_tags", "topic_point")
    )
    if any(keyword in text for keyword in ["教育", "学习", "升学", "教辅", "答疑", "作业", "老师"]):
        return "教育"
    if any(keyword in text for keyword in ["母婴", "亲子", "育儿", "妈妈", "宝宝", "家庭"]):
        return "母婴"
    if any(keyword in text for keyword in ["美妆", "护肤", "彩妆", "成分"]):
        return "美妆护肤"
    if any(keyword in text for keyword in ["家居", "家装", "收纳", "装修"]):
        return "家居家装"
    if any(keyword in text for keyword in ["数码", "科技", "AI", "智能", "电子"]):
        return "数码科技"
    return "通用"


def _creator_read_metric(creator: dict[str, Any]) -> float | None:
    return _read_reference_from_creator(creator)


def _creator_interaction_metric(creator: dict[str, Any]) -> float | None:
    return _interaction_reference_from_creator(creator)


def _creator_cpm_metric(creator: dict[str, Any]) -> float | None:
    metrics = _efficiency_metrics(creator, _creator_read_metric(creator))
    value = metrics.get("cpm") if metrics.get("cpm") is not None else metrics.get("estimated_cpm")
    return float(value) if value is not None and value > 0 else None


def _creator_cpe_metric(creator: dict[str, Any]) -> float | None:
    metrics = _efficiency_metrics(creator, _creator_read_metric(creator))
    value = metrics.get("cpe") if metrics.get("cpe") is not None else metrics.get("estimated_cpe")
    return float(value) if value is not None and value > 0 else None


def _creator_quote_metric(creator: dict[str, Any]) -> float | None:
    value = parse_number(creator.get("quote_price"))
    return float(value) if value is not None and value > 0 else None


_DEFECT_METRIC_GETTERS = {
    "read": _creator_read_metric,
    "interaction": _creator_interaction_metric,
    "cpm": _creator_cpm_metric,
    "cpe": _creator_cpe_metric,
    "quote": _creator_quote_metric,
}


def _benchmark_stats_for_items(items: list[dict[str, Any]]) -> dict[str, Any]:
    stats: dict[str, Any] = {"sample_count": len(items)}
    for key, getter in _DEFECT_METRIC_GETTERS.items():
        values = [getter(item) for item in items]
        values = [float(value) for value in values if value is not None and value > 0]
        stats[f"{key}_sample_count"] = len(values)
        stats[f"{key}_median"] = round(_median(values), 4) if values else None
        stats[f"{key}_p75"] = round(_percentile(values, 0.75), 4) if values else None
        stats[f"{key}_p90"] = round(_percentile(values, 0.9), 4) if values else None
    return stats


def _batch_defect_benchmarks(creators: list[dict[str, Any]]) -> dict[str, dict[tuple[str, ...], dict[str, Any]]]:
    groups: dict[str, dict[tuple[str, ...], list[dict[str, Any]]]] = {
        "category_bucket": {},
        "bucket": {},
        "global": {("global",): creators},
    }
    for creator in creators:
        category = _creator_category_bucket(creator)
        bucket = _creator_follower_bucket(creator)
        groups["category_bucket"].setdefault((category, bucket), []).append(creator)
        groups["bucket"].setdefault((bucket,), []).append(creator)
    return {
        level: {key: _benchmark_stats_for_items(items) for key, items in level_groups.items()}
        for level, level_groups in groups.items()
    }


def _select_batch_benchmark(
    creator: dict[str, Any],
    benchmarks: dict[str, dict[tuple[str, ...], dict[str, Any]]],
    metric: str,
) -> tuple[dict[str, Any], str]:
    category = _creator_category_bucket(creator)
    bucket = _creator_follower_bucket(creator)
    candidates = [
        ("category_bucket", (category, bucket)),
        ("bucket", (bucket,)),
        ("global", ("global",)),
    ]
    count_key = f"{metric}_sample_count"
    value_key = f"{metric}_median"
    for level, key in candidates:
        stats = benchmarks.get(level, {}).get(key)
        if stats and stats.get(value_key) is not None and int(stats.get(count_key) or 0) >= FALLBACK_BENCHMARK_MIN_SAMPLES:
            return stats, level
    for level, key in candidates:
        stats = benchmarks.get(level, {}).get(key)
        if stats and stats.get(value_key) is not None:
            return stats, level
    market = _market_benchmark_for_followers(creator.get("followers_count"))
    return {
        "sample_count": 0,
        "read_median": market.get("good_read"),
        "interaction_median": None,
        "cpm_median": market.get("cpm_good_max"),
        "cpe_median": market.get("cpe_good_max"),
        "quote_median": market.get("quote_good_max"),
    }, "market_seed"


def _defect_record(
    code: str,
    level: str,
    message: str,
    field: str,
    value: Any = None,
    threshold: Any = None,
    benchmark: Any = None,
    benchmark_level: str = "",
) -> dict[str, Any]:
    record = {
        "code": code,
        "level": level,
        "message": message,
        "field": field,
    }
    if value is not None:
        record["value"] = round(float(value), 4) if isinstance(value, (int, float)) else value
    if threshold is not None:
        record["threshold"] = round(float(threshold), 4) if isinstance(threshold, (int, float)) else threshold
    if benchmark is not None:
        record["benchmark"] = round(float(benchmark), 4) if isinstance(benchmark, (int, float)) else benchmark
    if benchmark_level:
        record["benchmark_level"] = benchmark_level
    return record


def _project_tag_match_defect(project_id: str, creator: dict[str, Any]) -> dict[str, Any] | None:
    profile = _project_direction_fit(creator, project_id)
    if profile.get("level") != "neutral":
        return None
    plan = _project_screening_plan(project_id)
    project_fit = plan.get("projectFitConfig") if isinstance(plan.get("projectFitConfig"), dict) else {}
    has_direction_config = bool(project_fit or plan.get("promotionStrategy") or plan.get("scoringCriteria"))
    if not has_direction_config:
        return None
    return _defect_record(
        "PROJECT_TAG_DIRECTION_MISMATCH",
        "major",
        "达人标签和内容方向未命中当前项目推广方向",
        "persona_tags",
        value=creator.get("persona_tags") or creator.get("creator_type") or "",
        threshold="至少命中1个项目方向词",
        benchmark=profile.get("cooperation_hint") or "",
    )


def _system_defects_for_creator(
    project_id: str,
    creator: dict[str, Any],
    benchmarks: dict[str, dict[tuple[str, ...], dict[str, Any]]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    hard: list[dict[str, Any]] = []
    warning: list[dict[str, Any]] = []

    reply = ratio(creator.get("reply_rate_48h"))
    if reply is not None and reply < LOW_REPLY_RATE_SCREENING_THRESHOLD:
        hard.append(_defect_record(
            "LOW_48H_REPLY_RATE",
            "critical",
            "48h回复率低于50%，沟通响应风险高",
            "reply_rate_48h",
            value=reply,
            threshold=LOW_REPLY_RATE_SCREENING_THRESHOLD,
        ))

    read = _creator_read_metric(creator)
    read_stats, read_level = _select_batch_benchmark(creator, benchmarks, "read")
    read_benchmark = parse_number(read_stats.get("read_median"))
    if read is not None and read_benchmark is not None and read < read_benchmark * BATCH_DEFECT_LOW_METRIC_RATIO:
        hard.append(_defect_record(
            "LOW_READ_MEDIAN",
            "major",
            "阅读中位数低于同层级中位数50%",
            "daily_read_median",
            value=read,
            threshold=read_benchmark * BATCH_DEFECT_LOW_METRIC_RATIO,
            benchmark=read_benchmark,
            benchmark_level=read_level,
        ))

    interaction = _creator_interaction_metric(creator)
    interaction_stats, interaction_level = _select_batch_benchmark(creator, benchmarks, "interaction")
    interaction_benchmark = parse_number(interaction_stats.get("interaction_median"))
    if interaction is not None and interaction_benchmark is not None and interaction < interaction_benchmark * BATCH_DEFECT_LOW_METRIC_RATIO:
        hard.append(_defect_record(
            "LOW_INTERACTION_MEDIAN",
            "major",
            "互动中位数低于同层级中位数50%",
            "daily_interaction_median",
            value=interaction,
            threshold=interaction_benchmark * BATCH_DEFECT_LOW_METRIC_RATIO,
            benchmark=interaction_benchmark,
            benchmark_level=interaction_level,
        ))

    cpm = _creator_cpm_metric(creator)
    cpm_stats, cpm_level = _select_batch_benchmark(creator, benchmarks, "cpm")
    cpm_benchmark = parse_number(cpm_stats.get("cpm_median"))
    if cpm is not None and cpm_benchmark is not None and cpm > cpm_benchmark * BATCH_DEFECT_HIGH_COST_RATIO:
        hard.append(_defect_record(
            "HIGH_CPM",
            "major",
            "CPM高于同层级中位数1.5倍",
            "image_cpm",
            value=cpm,
            threshold=cpm_benchmark * BATCH_DEFECT_HIGH_COST_RATIO,
            benchmark=cpm_benchmark,
            benchmark_level=cpm_level,
        ))

    cpe = _creator_cpe_metric(creator)
    cpe_stats, cpe_level = _select_batch_benchmark(creator, benchmarks, "cpe")
    cpe_benchmark = parse_number(cpe_stats.get("cpe_median"))
    if cpe is not None and cpe_benchmark is not None and cpe > cpe_benchmark * BATCH_DEFECT_HIGH_COST_RATIO:
        hard.append(_defect_record(
            "HIGH_CPE",
            "major",
            "CPE高于同层级中位数1.5倍",
            "effective_cpe",
            value=cpe,
            threshold=cpe_benchmark * BATCH_DEFECT_HIGH_COST_RATIO,
            benchmark=cpe_benchmark,
            benchmark_level=cpe_level,
        ))

    direction_defect = _project_tag_match_defect(project_id, creator)
    if direction_defect:
        hard.append(direction_defect)

    active_days = parse_number(creator.get("active_days_7d"))
    if active_days is not None and active_days < 1:
        warning.append(_defect_record(
            "LOW_RECENT_ACTIVITY",
            "warning",
            "近7天活跃天数不足，需复核账号近期活跃度",
            "active_days_7d",
            value=active_days,
            threshold=1,
        ))

    followers = parse_number(creator.get("followers_count"))
    if followers and read is not None:
        reach_rate = read / followers
        if followers >= 10000 and reach_rate < 0.01:
            warning.append(_defect_record(
                "LOW_FAN_REACH_RATE",
                "warning",
                "粉丝量与阅读触达不匹配，阅读/粉丝低于1%",
                "read_fans_ratio",
                value=reach_rate,
                threshold=0.01,
            ))

    if creator.get("rate_limit_risk") and not _contains_any(str(creator.get("rate_limit_risk")), ["无", "低风险"]):
        warning.append(_defect_record(
            "TRAFFIC_RISK_SIGNAL",
            "warning",
            "存在限流或异常流量风险字段",
            "rate_limit_risk",
            value=creator.get("rate_limit_risk"),
        ))

    missing = []
    for field in ("daily_read_median", "cooperation_read_median"):
        if parse_number(creator.get(field)) is not None:
            break
    else:
        missing.append("阅读中位数")
    for field in ("daily_interaction_median", "cooperation_interaction_median"):
        if parse_number(creator.get(field)) is not None:
            break
    else:
        missing.append("互动中位数")
    if ratio(creator.get("reply_rate_48h")) is None:
        missing.append("48h回复率")
    if missing:
        warning.append(_defect_record(
            "SCORING_DATA_INCOMPLETE",
            "warning",
            f"核心评分字段缺失：{'、'.join(missing)}",
            "data_completeness",
            value="、".join(missing),
        ))

    unique_hard = {item["code"]: item for item in hard}
    unique_warning = {item["code"]: item for item in warning if item["code"] not in unique_hard}
    return list(unique_hard.values()), list(unique_warning.values())


def _attach_system_defects(
    project_id: str,
    scored_items: list[tuple[dict[str, Any], dict[str, Any], str]],
    benchmarks: dict[str, dict[tuple[str, ...], dict[str, Any]]] | None = None,
) -> tuple[int, int]:
    benchmarks = benchmarks or _batch_defect_benchmarks([creator for creator, _, _ in scored_items])
    hard_count = 0
    warning_count = 0
    for creator, score, _ in scored_items:
        hard_defects, warning_defects = _system_defects_for_creator(project_id, creator, benchmarks)
        score["hard_defects"] = hard_defects
        score["warning_defects"] = warning_defects
        hard_count += len(hard_defects)
        warning_count += len(warning_defects)
        if hard_defects and score.get("hard_filter_passed") != 0:
            score["hard_filter_passed"] = 0
            score["recommend_level"] = _recommend_level(score.get("total_score") or 0, False)
            messages = [item["message"] for item in hard_defects[:4]]
            score["score_reason"] = "；".join([*messages, str(score.get("score_reason") or "")])
    return hard_count, warning_count


def _project_audience_fit(creator: dict[str, Any], project_id: str | None) -> tuple[float, bool]:
    if not project_id:
        return _precision_fans_fit(creator)
    plan = _project_screening_plan(project_id)
    threshold = _project_metric_threshold(project_id, "fans35")
    fans35 = ratio(creator.get("fans_35_plus_ratio"))
    score = 12.0 if not plan else 15.0
    precise = False
    if threshold is not None:
        if fans35 is None:
            score = 12.0
        elif fans35 >= threshold:
            score = 23.0
            precise = True
        else:
            score = 8.0
    direction = _project_direction_fit(creator, project_id)
    if direction["level"] == "strong":
        score = min(25, score + 2)
        precise = True
    elif direction["level"] == "medium":
        score = min(25, score + 1)
    elif direction["level"] == "off":
        score = min(score, 6)
    return round(max(0, min(25, score)), 2), precise


def _apply_quality_gate(
    total: float,
    profile: dict[str, Any],
    reasons: list[str],
    creator: dict[str, Any] | None = None,
    direction_profile: dict[str, Any] | None = None,
    project_id: str | None = None,
) -> float:
    efficiency = profile.get("efficiency") if isinstance(profile.get("efficiency"), dict) else {}
    if creator is not None:
        fans35 = ratio(creator.get("fans_35_plus_ratio"))
        fans35_threshold = _project_metric_threshold(project_id, "fans35") if project_id else None
        if fans35_threshold is not None:
            if fans35 is not None and fans35 < fans35_threshold and total > 69:
                reasons.append(f"项目粉丝年龄硬条件未达标，初评最高C档")
                return 69.0
            if fans35 is None and total > 94:
                reasons.append("项目要求粉丝年龄画像，但当前缺少该字段，初评暂不进入S档")
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
        reasons.append("项目方向匹配较弱，初筛最高B+档")
        total = 79.0
    return total


LOW_REPLY_RATE_SCREENING_THRESHOLD = 0.5
LOW_REPLY_RATE_SCREENING_PENALTY = 8.0
LOW_REPLY_RATE_SCREENING_CAP = 84.0


def _apply_low_reply_rate_gate(
    total: float,
    creator: dict[str, Any] | None,
    reasons: list[str],
    threshold: float | None = None,
) -> tuple[float, bool]:
    if creator is None:
        return total, False
    threshold = threshold if threshold is not None else LOW_REPLY_RATE_SCREENING_THRESHOLD
    reply = ratio(creator.get("reply_rate_48h"))
    if reply is None or reply >= threshold:
        return total, False
    total = max(0.0, total - LOW_REPLY_RATE_SCREENING_PENALTY)
    if total > LOW_REPLY_RATE_SCREENING_CAP:
        reasons.append(f"48h回复率低于{threshold:.0%}，基础筛选扣8分，高分封顶到A档观察")
        total = LOW_REPLY_RATE_SCREENING_CAP
    else:
        reasons.append(f"48h回复率低于{threshold:.0%}，基础筛选扣8分")
    return total, True


def _apply_project_special_scoring(
    total: float,
    creator: dict[str, Any],
    data_profile: dict[str, Any],
    efficiency_profile: dict[str, Any],
    direction_profile: dict[str, Any],
    reasons: list[str],
    project_id: str | None,
    hard_pass: bool,
) -> float:
    config = _project_special_scoring_config(project_id)
    if not hard_pass or not config:
        return total
    label = str(config.get("label") or "项目专属")
    identity_config = config.get("identity") if isinstance(config.get("identity"), dict) else {}
    scene_config = config.get("scene") if isinstance(config.get("scene"), dict) else {}
    data_config = config.get("data") if isinstance(config.get("data"), dict) else {}
    efficiency_config = config.get("efficiency") if isinstance(config.get("efficiency"), dict) else {}
    tier_rules = config.get("tier_rules") if isinstance(config.get("tier_rules"), dict) else {}
    negative_config = config.get("negative") if isinstance(config.get("negative"), dict) else {}
    brief_profile = _project_special_scoring_profile(creator, config, direction_profile)
    read = data_profile.get("median_read") or data_profile.get("avg_read")
    interaction = data_profile.get("avg_interaction")
    expected_read = float(data_profile.get("expected_read") or 0)
    read_ratio = (float(read) / expected_read) if read is not None and expected_read > 0 else 0
    metric_reasons: list[str] = []
    if read is not None:
        metric_reasons.append(f"平均/中位阅读{read:.0f}")
    if interaction is not None:
        metric_reasons.append(f"平均互动{interaction:.0f}")
    if efficiency_profile.get("effective_cpc") is not None:
        metric_reasons.append(f"CPC {float(efficiency_profile['effective_cpc']):.2f}")
    if efficiency_profile.get("effective_cpe") is not None:
        metric_reasons.append(f"CPE {float(efficiency_profile['effective_cpe']):.1f}")
    if efficiency_profile.get("effective_cpm") is not None:
        metric_reasons.append(f"CPM {float(efficiency_profile['effective_cpm']):.1f}")

    identity_points = float(identity_config.get("points") or 0) if brief_profile["overseas"] else 0
    scene_points = 0
    if brief_profile["study"]:
        max_keyword_hits = int(scene_config.get("max_keyword_hits") or 4)
        scene_points = float(scene_config.get("base_points") or 0) + min(len(brief_profile["study_hits"]), max_keyword_hits) * float(scene_config.get("points_per_hit") or 0)
    scene_max = float(scene_config.get("max_points") or scene_points or 0)
    direction_bonus = scene_config.get("direction_bonus") if isinstance(scene_config.get("direction_bonus"), dict) else {}
    if direction_profile.get("level") == "strong":
        scene_points += float(direction_bonus.get("strong") or 0)
    elif direction_profile.get("level") == "medium":
        scene_points += float(direction_bonus.get("medium") or 0)
    scene_points = min(scene_max, scene_points) if scene_max else scene_points

    data_points = 0
    if data_profile.get("excellent_data"):
        data_points = float(data_config.get("excellent_points") or 0)
    elif data_profile.get("good_data"):
        data_points = float(data_config.get("good_points") or 0)
    else:
        for rule in data_config.get("read_ratio_points") or []:
            if isinstance(rule, dict) and read_ratio >= float(rule.get("min") or 0):
                data_points = float(rule.get("points") or 0)
                break
    if interaction is not None:
        for rule in data_config.get("interaction_bonus") or []:
            if isinstance(rule, dict) and interaction >= float(rule.get("min") or 0):
                data_points += float(rule.get("points") or 0)
                break
    data_points = min(float(data_config.get("max_points") or data_points or 0), data_points) if data_config.get("max_points") is not None else data_points

    efficiency_points = 0
    if efficiency_profile.get("excellent_efficiency"):
        efficiency_points = float(efficiency_config.get("excellent_points") or 0)
    elif efficiency_profile.get("good_efficiency"):
        efficiency_points = float(efficiency_config.get("good_points") or 0)
    elif metric_reasons:
        efficiency_points = float(efficiency_config.get("fallback_points") or 0)
    efficiency_points = min(float(efficiency_config.get("max_points") or efficiency_points or 0), efficiency_points) if efficiency_config.get("max_points") is not None else efficiency_points

    priority_score = identity_points + scene_points + data_points + efficiency_points
    if brief_profile["overseas"]:
        reasons.append(f"{label}优先级1：命中{identity_config.get('name') or '身份背景'}（{'、'.join(brief_profile['overseas_hits'][:3])}）")
    if brief_profile["study"]:
        reasons.append(f"{label}优先级2：命中{scene_config.get('name') or 'Brief场景'}（{'、'.join(brief_profile['study_hits'][:4])}）")
    if data_profile.get("excellent_data") and efficiency_profile.get("excellent_efficiency"):
        reasons.append(f"{label}优先级3：平均阅读、互动及CPC/CPE/CPM综合数据优秀")
    elif metric_reasons:
        reasons.append(f"{label}综合数据：{'、'.join(metric_reasons[:5])}")

    reasons.append(
        f"{label}优先级积分：身份{identity_points:g}/{float(identity_config.get('points') or 0):g}，场景{scene_points:g}/{float(scene_config.get('max_points') or 0):g}，数据{data_points:g}/{float(data_config.get('max_points') or 0):g}，效率{efficiency_points:g}/{float(efficiency_config.get('max_points') or 0):g}，合计{priority_score:g}/100"
    )

    s_requirements_pass = True
    if tier_rules.get("require_identity_for_s", True) and not brief_profile["overseas"]:
        s_requirements_pass = False
    if tier_rules.get("require_scene_for_s", True) and not brief_profile["study"]:
        s_requirements_pass = False
    if tier_rules.get("require_good_data_for_s", True) and not data_profile.get("good_data"):
        s_requirements_pass = False
    if tier_rules.get("require_good_efficiency_for_s", True) and not efficiency_profile.get("good_efficiency"):
        s_requirements_pass = False
    if s_requirements_pass and priority_score >= float(tier_rules.get("s_min_priority_score") or 85):
        high_min = float(tier_rules.get("s_high_priority_score") or 10**9)
        total = max(total, float(tier_rules.get("s_high_score") or tier_rules.get("s_score") or 95) if priority_score >= high_min else float(tier_rules.get("s_score") or 95))
        reasons.append(f"{label}S档依据：身份、Brief场景、数据效率累计达标")
    elif priority_score >= float(tier_rules.get("a_min_priority_score") or 10**9):
        total = max(total, float(tier_rules.get("a_score") or 88))
    elif priority_score >= float(tier_rules.get("b_plus_min_priority_score") or 10**9):
        total = max(total, float(tier_rules.get("b_plus_score") or 80))
    elif priority_score >= float(tier_rules.get("b_min_priority_score") or 10**9):
        total = max(total, float(tier_rules.get("b_score") or 75))

    if brief_profile["negative_hits"] and not brief_profile["study"]:
        total = min(total, float(negative_config.get("cap_without_scene") or 84))
        reasons.append(f"{label}风险：命中{'、'.join(brief_profile['negative_hits'][:3])}，核心场景需复核")
    if not brief_profile["overseas"]:
        no_identity_cap = tier_rules.get("no_identity_cap")
        if no_identity_cap is not None and total > float(no_identity_cap):
            reasons.append(f"{label}身份优先级：未识别{identity_config.get('name') or '身份背景'}，最高按A档高潜备选")
            total = float(no_identity_cap)
    elif priority_score < float(tier_rules.get("s_min_priority_score") or 85) and total >= 95:
        identity_only_cap = tier_rules.get("identity_only_s_cap")
        if identity_only_cap is not None:
            reasons.append(f"{label}S档未达：仅身份背景不足以进入S，需叠加Brief场景和综合数据")
            total = min(total, float(identity_only_cap))
    return round(min(100, total), 2)


def _split_semantic_tags(value: Any) -> list[str]:
    text = str(value or "").strip()
    if not text:
        return []
    return [item.strip() for item in re.split(r"[、,，;；/|]+", text) if item.strip()]


def _project_fit_config(project_id: str | None) -> dict[str, Any]:
    if not project_id:
        return {}
    plan = _project_screening_plan(project_id)
    config = plan.get("projectFitConfig")
    if not isinstance(config, dict):
        config = {}
    adjusted = dict(config)
    special = _project_special_scoring_config(project_id)
    patch = special.get("project_fit_config_patch") if isinstance(special.get("project_fit_config_patch"), dict) else {}
    for key in ("preferred_content_scenes", "preferred_presentation_styles", "discouraged_keywords"):
        if patch.get(key):
            adjusted[key] = list(dict.fromkeys([*(adjusted.get(key) or []), *patch.get(key)]))
    for key in ("target_grade_keywords", "parent_decision_keywords"):
        if patch.get(key):
            adjusted[key] = list(patch.get(key))
    return adjusted


def _project_fit_signal_profile(creator: dict[str, Any], project_fit_config: dict[str, Any]) -> dict[str, Any]:
    if not project_fit_config:
        return {
            "scene_hits": [],
            "style_hits": [],
            "grade_hits": [],
            "parent_hits": [],
            "negative_hits": [],
            "recent_note_count": 0,
            "evidence_score": 0.0,
        }
    text_blob = _text_blob(creator).lower()
    content_tags = set(_split_semantic_tags(creator.get("content_scene_tags")))
    style_tags = set(_split_semantic_tags(creator.get("presentation_style_tags")))
    raw_payload = _creator_raw_payload(creator)
    recent_notes = raw_payload.get("recent_notes") if isinstance(raw_payload.get("recent_notes"), list) else []
    cooperation_cases = raw_payload.get("cooperation_note_cases") if isinstance(raw_payload.get("cooperation_note_cases"), list) else []

    preferred_scenes = [str(item).strip() for item in (project_fit_config.get("preferred_content_scenes") or []) if str(item).strip()]
    preferred_styles = [str(item).strip() for item in (project_fit_config.get("preferred_presentation_styles") or []) if str(item).strip()]
    grade_keywords = [str(item).strip() for item in (project_fit_config.get("target_grade_keywords") or []) if str(item).strip()]
    parent_keywords = [str(item).strip() for item in (project_fit_config.get("parent_decision_keywords") or []) if str(item).strip()]
    discouraged_keywords = [str(item).strip() for item in (project_fit_config.get("discouraged_keywords") or []) if str(item).strip()]

    scene_hits = [item for item in preferred_scenes if item in content_tags or item.lower() in text_blob]
    style_hits = [item for item in preferred_styles if item in style_tags or item.lower() in text_blob]
    grade_hits = [item for item in grade_keywords if item.lower() in text_blob]
    parent_hits = [item for item in parent_keywords if item.lower() in text_blob]
    negative_hits = [item for item in discouraged_keywords if item.lower() in text_blob]
    recent_note_count = sum(
        1
        for item in [*recent_notes, *cooperation_cases]
        if isinstance(item, dict) and (str(item.get("title") or "").strip() or str(item.get("content") or "").strip())
    )
    evidence_rules = project_fit_config.get("evidence_rules") if isinstance(project_fit_config.get("evidence_rules"), dict) else {}
    min_notes = int(evidence_rules.get("minimum_recent_note_count_for_high_score") or 2)
    evidence_signals = [
        bool(scene_hits),
        bool(style_hits),
        bool(grade_hits),
        bool(parent_hits),
        recent_note_count >= min_notes,
        bool(str(creator.get("child_grade") or "").strip()),
    ]
    evidence_score = round(sum(1 for item in evidence_signals if item) / len(evidence_signals), 3) if evidence_signals else 0.0
    return {
        "scene_hits": list(dict.fromkeys(scene_hits)),
        "style_hits": list(dict.fromkeys(style_hits)),
        "grade_hits": list(dict.fromkeys(grade_hits)),
        "parent_hits": list(dict.fromkeys(parent_hits)),
        "negative_hits": list(dict.fromkeys(negative_hits)),
        "recent_note_count": recent_note_count,
        "evidence_score": evidence_score,
    }


def _apply_project_fit_gate(
    total: float,
    creator: dict[str, Any],
    project_fit_config: dict[str, Any],
    reasons: list[str],
) -> float:
    if not project_fit_config:
        return total
    evidence_rules = project_fit_config.get("evidence_rules") if isinstance(project_fit_config.get("evidence_rules"), dict) else {}
    profile = _project_fit_signal_profile(creator, project_fit_config)
    scene_hits = profile["scene_hits"]
    style_hits = profile["style_hits"]
    negative_hits = profile["negative_hits"]
    has_grade_or_parent_evidence = bool(profile["grade_hits"] or profile["parent_hits"])
    min_notes = int(evidence_rules.get("minimum_recent_note_count_for_high_score") or 2)
    insufficient_cap = float(evidence_rules.get("insufficient_evidence_max_score") or 84)
    weak_scene_cap = float(evidence_rules.get("weak_scene_match_max_score") or 79)
    negative_cap = float(evidence_rules.get("negative_hit_max_score") or 74)

    if scene_hits:
        if total < 100:
            total = min(100, total + 1.5)
        reasons.append(f"项目场景匹配：命中{'、'.join(scene_hits[:3])}")
    if style_hits:
        if total < 100:
            total = min(100, total + 0.5)
        reasons.append(f"内容呈现匹配：命中{'、'.join(style_hits[:2])}")
    if negative_hits and total > negative_cap:
        reasons.append(f"命中项目降权内容：{'、'.join(negative_hits[:3])}")
        total = negative_cap
    if evidence_rules.get("require_scene_evidence_for_a_tier") and not scene_hits:
        reasons.append("缺少与当前产品场景直接匹配的内容证据，高分封顶到B+档")
        if total > weak_scene_cap:
            total = weak_scene_cap
    if evidence_rules.get("require_grade_or_parent_evidence_for_s_tier") and not has_grade_or_parent_evidence:
        reasons.append("缺少目标学段或家长决策者证据，暂不进入A档以上")
        if total > insufficient_cap:
            total = insufficient_cap
    if profile["recent_note_count"] < min_notes:
        reasons.append(f"近期可用笔记证据少于{min_notes}条，暂不进入A档以上")
        if total > insufficient_cap:
            total = insufficient_cap
    if profile["evidence_score"] < 0.34:
        reasons.append("项目证据充分度偏低，暂不进入A档以上")
        if total > insufficient_cap:
            total = insufficient_cap
    return round(total, 2)


def score_values(creator: dict[str, Any], project_id: str | None = None) -> dict[str, Any]:
    quote = creator.get("quote_price")
    fans35 = _fans_35_plus_ratio(creator)
    cpc = _first_number(creator.get("effective_cpc"), creator.get("natural_cpc"), positive=True)
    cpe = _first_number(creator.get("effective_cpe"), creator.get("natural_cpe"), positive=True)
    search_review_status = str(creator.get("search_recommend_review_status") or "")
    risk = str(creator.get("rate_limit_risk") or "")
    stability = str(creator.get("traffic_stability") or "")
    text = _text_blob(creator)
    data_profile = _recent_note_data_profile(creator)
    efficiency_profile = _efficiency_profile(creator, data_profile["benchmark"], data_profile.get("median_read") or data_profile.get("avg_read"))
    data_profile["efficiency"] = efficiency_profile
    stage_derivatives = _creator_stage_derivatives(creator, project_id)
    is_koc_project = _is_koc_project(project_id)
    hard_rules = _project_hard_rules_config(project_id)

    hard_issues = _project_hard_filter_issues(project_id, creator) if project_id else []
    if (not project_id or _project_rule_mentions(project_id, ["限流", "违规", "流量稳定", "异常"])) and _contains_any(risk, ["高风险", "严重", "违规", "疑似限流"]):
        hard_issues.append("存在明确高风险信号")
    hard_issues = list(dict.fromkeys(hard_issues))
    hard_pass = not hard_issues

    weights = _project_scoring_weights(project_id)
    audience_score, precise_fans = _project_audience_fit(creator, project_id)

    traffic = round(min(25, data_profile["data_score"] / 30 * 25), 2)
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

    direction_profile = _project_direction_fit(creator, project_id)
    direction_score = float(direction_profile["score"])
    execution_score, execution_reasons = _execution_fit(creator)

    component_scores = {
        "budget_score": _weighted_component(execution_score / 5 * 100, weights["budget"]),
        "fans_score": _weighted_component(audience_score / 25 * 100, weights["fans"]),
        "cpe_score": _weighted_component(cpe_efficiency / 25 * 100, weights["cpe"]),
        "traffic_score": _weighted_component(traffic / 25 * 100, weights["engagement"]),
        "persona_score": _weighted_component(direction_score / 15 * 100, weights["persona"]),
        "content_score": _weighted_component((5 if direction_profile["level"] == "strong" else 3 if direction_profile["level"] == "medium" else 1) / 5 * 100, weights["content"]),
    }
    base = round(sum(component_scores.values()), 2)

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
    group_score = _initial_rule_group_score(base, bonus, completeness, hard_pass)
    tier, priority = _initial_rule_tier_and_priority(creator, group_score, bonus, hard_pass, data_profile, efficiency_profile, direction_profile)

    reasons: list[str] = []
    if hard_issues:
        reasons.extend(hard_issues)
    if _project_metric_threshold(project_id, "fans35") is not None and fans35 is None:
        reasons.append("粉丝年龄画像未进入本轮数据判断")
    if cpc is None and cpe is None:
        reasons.append("CPC/CPE未进入本轮数据判断")
    if _project_rule_mentions(project_id, ["搜索+推荐", "搜索推荐"]) and search_review_status != "已复核":
        reasons.append("搜索+推荐占比待人工复核，不进入自动评分")
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
    if stage_derivatives.get("format_budget_fit") and stage_derivatives.get("format_budget_fit") != "待核":
        reasons.append(
            "形态预算："
            f"{stage_derivatives.get('format_budget_fit')}，"
            f"{stage_derivatives.get('image_quote_status')}，"
            f"{stage_derivatives.get('video_quote_status')}"
        )
    if stage_derivatives.get("dominant_note_format") and stage_derivatives.get("dominant_note_format") != "待补":
        reasons.append(f"近期/合作笔记形态：{stage_derivatives.get('dominant_note_format')}")
    if stage_derivatives.get("commercial_order_signal") in {"有商单证据", "疑似有商单"}:
        reasons.append(f"商单证据：{stage_derivatives.get('commercial_order_signal')}")
    if stage_derivatives.get("detail_need_reason"):
        reasons.append(f"一阶段状态：{stage_derivatives.get('stage_one_status')}，{stage_derivatives.get('detail_need_reason')}")
    if data_profile["good_data"] and precise_fans and direction_profile["level"] in {"strong", "medium"}:
        reasons.append("A档候选依据：人群达标、阅读/互动有支撑、方向相关")
    total = _apply_project_fit_gate(total, creator, _project_fit_config(project_id), reasons)
    total = round(_apply_quality_gate(total, data_profile, reasons, creator, direction_profile, project_id), 2)
    total = _apply_project_special_scoring(total, creator, data_profile, efficiency_profile, direction_profile, reasons, project_id, hard_pass)
    missing_cooperation_data_gate = _apply_missing_cooperation_note_data_gate(total, creator, reasons)
    if hard_pass and total < 70 and not data_profile["weak_recent_data"] and not efficiency_profile["poor_efficiency"]:
        total = 70.0
        reasons.append("未发现已确认硬伤，数据证据不足时按B档观察，不因缺字段直接低分")
    tier, priority = _initial_rule_tier_and_priority(creator, group_score, bonus, hard_pass, data_profile, efficiency_profile, direction_profile)
    if hard_pass and _has_project_special_scoring(project_id):
        tier = _initial_tier(total, hard_pass)
        priority = _detail_collection_priority(total, bonus, hard_pass)
    if stage_derivatives.get("format_budget_fit") == "均超预算" and not stage_derivatives.get("premium_exception_passed"):
        if total > 69:
            reasons.append("项目形态预算硬条件未达标，初评最高C档")
            total = 69.0
        hard_pass = False
        tier = _initial_tier(total, hard_pass)
        priority = _detail_collection_priority(total, bonus, hard_pass)
    elif stage_derivatives.get("premium_exception_passed"):
        reasons.append(f"预算溢价例外：{stage_derivatives.get('premium_exception_reason')}，进入补详情复核")
        if total < 75:
            total = 75.0
        hard_pass = True
        tier = _initial_tier(total, hard_pass)
        priority = "高优先级"
    total, low_reply_gate_applied = _apply_low_reply_rate_gate(
        total,
        creator,
        reasons,
        ratio(hard_rules.get("reply_rate_min")) if hard_rules else None,
    )
    total = round(total, 2)
    if low_reply_gate_applied:
        hard_pass = False
        tier = _initial_tier(total, hard_pass)
        priority = _detail_collection_priority(total, bonus, hard_pass)
    if missing_cooperation_data_gate:
        priority = min_priority_label(_detail_collection_priority(total, bonus, hard_pass), "中优先级")
    koc_profile: dict[str, Any] = {}
    if is_koc_project:
        koc_profile = _koc_final_profile(creator, project_id, stage_derivatives, data_profile, efficiency_profile)
        status = str(koc_profile.get("project_match_status") or "")
        if koc_profile.get("stage1_priority"):
            reasons.append(f"KOC一阶段：{koc_profile.get('stage1_priority')}，{koc_profile.get('stage1_reason')}")
        target_ratio = koc_profile.get("target_content_ratio")
        scene_ratio = koc_profile.get("product_scene_ratio")
        conflict_ratio = koc_profile.get("conflict_content_ratio")
        ratio_parts = []
        if target_ratio is not None:
            ratio_parts.append(f"学习/目标内容占比{target_ratio:.0%}")
        if scene_ratio is not None:
            ratio_parts.append(f"产品场景占比{scene_ratio:.0%}")
        if conflict_ratio is not None:
            ratio_parts.append(f"冲突内容占比{conflict_ratio:.0%}")
        if ratio_parts:
            reasons.append(f"KOC内容结构：{'、'.join(ratio_parts)}")
        risk_result = koc_profile.get("risk_control_result") if isinstance(koc_profile.get("risk_control_result"), dict) else {}
        if risk_result.get("hard"):
            reasons.append(f"KOC硬风险：{'、'.join(risk_result['hard'][:3])}")
        if risk_result.get("missing"):
            reasons.append(f"KOC待补证据：{'、'.join(risk_result['missing'][:4])}")
        if status == "Pass":
            hard_pass = False
            total = min(total, 69.0)
            reasons.append("KOC二阶段：硬性条件未达标，最终Pass")
        elif status == "不推荐":
            hard_pass = False
            total = min(total, 74.0)
            reasons.append("KOC二阶段：内容/数据/身份综合不足，最终不推荐")
        elif status == "待人工确认":
            total = min(total, 84.0)
            reasons.append("KOC二阶段：关键证据不足，需人工确认后再推荐")
        elif status == "备选":
            total = min(total, 79.0)
            reasons.append("KOC二阶段：可做备选，不直接强推")
        elif status == "推荐":
            total = max(total, 80.0)
            reasons.append("KOC二阶段：预算、数据和内容证据基本匹配")
        elif status == "强推荐":
            total = max(total, 90.0)
            reasons.append("KOC二阶段：预算、数据、留学身份和学习场景证据同时达标")
        total = round(total, 2)
        tier = _initial_tier(total, hard_pass)
        if status in {"待人工确认", "备选"}:
            priority_cap = "中优先级" if status == "待人工确认" else "中高优先级"
            priority = min_priority_label(_detail_collection_priority(total, bonus, hard_pass), priority_cap)
        else:
            priority = _detail_collection_priority(total, bonus, hard_pass)
    if missing_cooperation_data_gate:
        priority = min_priority_label(priority, "中优先级")
    if group_score > total:
        reasons.append(f"规则初筛分组：{group_score:.1f}分，{tier}档/{priority}；最终推荐分受详情证据充分度约束")
    if bonus_reasons:
        reasons.append(f"加成：{'、'.join(bonus_reasons[:3])}")
    if not reasons:
        reasons.append("基础信息匹配，适合进入项目初筛排序")

    level = str(koc_profile.get("final_recommend_level") or _recommend_level(total, hard_pass))
    return {
        "total_score": total,
        "rule_group_score": group_score,
        "base_score": base,
        "bonus_score": bonus,
        "information_completeness": completeness,
        "initial_tier": tier,
        "detail_collection_priority": priority,
        **component_scores,
        "hard_filter_passed": 1 if hard_pass else 0,
        "recommend_level": level,
        "score_reason": "；".join(reasons),
        "cooperation_direction": _default_cooperation_direction(creator, level),
        "stage1_priority": koc_profile.get("stage1_priority") or "",
        "stage1_reason": koc_profile.get("stage1_reason") or "",
        "project_match_status": koc_profile.get("project_match_status") or "",
        "project_match_confidence": koc_profile.get("project_match_confidence"),
        "final_recommend_level": koc_profile.get("final_recommend_level") or level,
        "target_content_ratio": koc_profile.get("target_content_ratio"),
        "target_content_evidence": koc_profile.get("target_content_evidence") or [],
        "product_scene_ratio": koc_profile.get("product_scene_ratio"),
        "product_scene_evidence": koc_profile.get("product_scene_evidence") or [],
        "conflict_content_ratio": koc_profile.get("conflict_content_ratio"),
        "conflict_content_categories": koc_profile.get("conflict_content_categories") or [],
        "risk_control_result": koc_profile.get("risk_control_result") or {},
        "recommended_format": koc_profile.get("recommended_format") or "",
    }


def _project_screening_plan(project_id: str) -> dict[str, Any]:
    cache = _PROJECT_SCREENING_PLAN_CACHE.get()
    if cache is not None and project_id in cache:
        return cache[project_id]
    project = _cached_project(project_id) or {}
    screening_plan = project.get("screening_plan")
    if isinstance(screening_plan, str):
        try:
            screening_plan = json.loads(screening_plan)
        except json.JSONDecodeError:
            screening_plan = {}
    plan = screening_plan if isinstance(screening_plan, dict) else {}
    if not is_test_project_id(project_id):
        file_payload = read_json(project_scoring_config_path(project_id), {})
        file_config = file_payload.get("project_scoring_config") if isinstance(file_payload, dict) else {}
        if isinstance(file_config, dict) and file_config:
            plan = {**plan, **copy.deepcopy(file_config)}
    if cache is not None:
        cache[project_id] = plan
    return plan


def _project_format_budget_policy(project_id: str | None) -> dict[str, Any]:
    if not project_id:
        return {}
    plan = _project_screening_plan(project_id)
    scoring_criteria = plan.get("scoringCriteria") if isinstance(plan.get("scoringCriteria"), dict) else {}
    policy = plan.get("formatBudgetPolicy") or scoring_criteria.get("format_budget_policy") or {}
    return policy if isinstance(policy, dict) else {}


def _project_hard_rules_config(project_id: str | None) -> dict[str, Any]:
    if not project_id:
        return {}
    plan = _project_screening_plan(project_id)
    scoring_criteria = plan.get("scoringCriteria") if isinstance(plan.get("scoringCriteria"), dict) else {}
    rules = plan.get("hardRules") or scoring_criteria.get("project_hard_rules") or {}
    return rules if isinstance(rules, dict) else {}


def _project_koc_scoring_config(project_id: str | None) -> dict[str, Any]:
    if not project_id:
        return copy.deepcopy(KOC_DEFAULT_SCORING_CONFIG)
    plan = _project_screening_plan(project_id)
    source = plan.get("kocScoringConfig") if isinstance(plan.get("kocScoringConfig"), dict) else {}
    result = copy.deepcopy(KOC_DEFAULT_SCORING_CONFIG)
    for key, value in source.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = {**result[key], **{sub_key: sub_val for sub_key, sub_val in value.items() if sub_val not in (None, "")}}
        elif value not in (None, "", [], {}):
            result[key] = value
    result["enabled"] = result.get("enabled") is not False
    return result


def _koc_config_number(config: dict[str, Any], section: str, key: str, default: float) -> float:
    source = config.get(section) if isinstance(config.get(section), dict) else {}
    value = parse_number(source.get(key))
    return float(value) if value is not None else float(default)


def _is_koc_project(project_id: str | None) -> bool:
    if not project_id:
        return False
    plan = _project_screening_plan(project_id)
    project_fit = plan.get("projectFitConfig") if isinstance(plan.get("projectFitConfig"), dict) else {}
    values = [
        plan.get("is_koc_project"),
        project_fit.get("is_koc_project"),
        plan.get("project_delivery_type"),
        project_fit.get("project_delivery_type"),
        plan.get("creator_matrix_type"),
        project_fit.get("creator_matrix_type"),
    ]
    if any(value is True for value in values):
        return True
    text = " ".join(str(value or "") for value in values).lower()
    if "koc" in text:
        return True
    project = _cached_project(project_id) or {}
    brief = str(project.get("brief") or "").lower()
    return bool(re.search(r"\bkoc\b|达人量级[^，。；;\n]*koc|预算[^，。；;\n]*koc", brief))


def _quote_status(value: Any, cap: Any, label: str) -> str:
    price = parse_number(value)
    threshold = parse_number(cap)
    if price is None:
        return f"{label}待核"
    if threshold is None:
        return f"{label}已采集"
    return f"{label}预算内" if price <= threshold else f"{label}超预算"


def _note_case_format(item: dict[str, Any]) -> str:
    values = [
        item.get("note_type"),
        item.get("noteType"),
        item.get("type"),
        item.get("media_type"),
        item.get("mediaType"),
        item.get("笔记类型"),
    ]
    for value in values:
        text = str(value or "").strip().lower()
        if not text:
            continue
        if text in {"2", "video"} or "视频" in text:
            return "视频"
        if text in {"1", "image", "photo"} or "图文" in text or "图片" in text:
            return "图文"
    if item.get("isVideo") is True or item.get("is_video") is True:
        return "视频"
    if item.get("isVideo") is False or item.get("is_video") is False:
        return "图文"
    text_blob = json.dumps(item, ensure_ascii=False)
    if "视频笔记" in text_blob:
        return "视频"
    if "图文笔记" in text_blob:
        return "图文"
    return ""


def _note_format_counts(creator: dict[str, Any]) -> dict[str, Any]:
    raw_payload = _creator_raw_payload(creator)
    cases = _collect_note_cases_from_payload(raw_payload)
    counts = {"图文": 0, "视频": 0, "unknown": 0}
    for item in cases:
        note_format = _note_case_format(item)
        if note_format in {"图文", "视频"}:
            counts[note_format] += 1
        else:
            counts["unknown"] += 1
    for key in ("note_type", "noteType", "笔记类型"):
        note_format = _note_case_format({key: creator.get(key) or raw_payload.get(key)})
        if note_format in {"图文", "视频"}:
            counts[note_format] += 1
    text_blob = json.dumps(raw_payload, ensure_ascii=False)
    counts["视频"] += len(re.findall(r"视频笔记", text_blob))
    counts["图文"] += len(re.findall(r"图文笔记", text_blob))
    total_known = counts["图文"] + counts["视频"]
    if total_known < 3:
        dominant = "待补"
    elif counts["视频"] / total_known >= 0.6:
        dominant = "视频为主"
    elif counts["图文"] / total_known >= 0.6:
        dominant = "图文为主"
    else:
        dominant = "混合"
    return {**counts, "known_total": total_known, "dominant": dominant}


def _note_case_date(item: dict[str, Any]) -> datetime | None:
    for key in ("publish_time", "publishTime", "create_time", "createTime", "date", "created_at", "发布时间"):
        value = item.get(key)
        if value in (None, ""):
            continue
        if isinstance(value, (int, float)):
            timestamp = float(value)
            if timestamp > 10_000_000_000:
                timestamp /= 1000
            try:
                return datetime.fromtimestamp(timestamp)
            except (OSError, ValueError):
                continue
        text = str(value).strip()
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y/%m/%d", "%m-%d"):
            try:
                parsed = datetime.strptime(text[:19] if fmt.endswith("%S") else text[:10], fmt)
                if fmt == "%m-%d":
                    parsed = parsed.replace(year=datetime.now().year)
                return parsed
            except ValueError:
                continue
    return None


def _latest_note_date(creator: dict[str, Any]) -> datetime | None:
    raw_payload = _creator_raw_payload(creator)
    dates = [_note_case_date(item) for item in _collect_note_cases_from_payload(raw_payload)]
    return max((item for item in dates if item is not None), default=None)


def _like_counts_from_notes(creator: dict[str, Any]) -> list[dict[str, Any]]:
    raw_payload = _creator_raw_payload(creator)
    result = []
    for item in _collect_note_cases_from_payload(raw_payload):
        like = parse_number(item.get("like_count") or item.get("likeCount") or item.get("likes") or item.get("liked_count") or item.get("点赞数"))
        if like is None:
            continue
        result.append({"like_count": like, "date": _note_case_date(item)})
    return result


def _note_text(item: dict[str, Any]) -> str:
    return " ".join(
        str(item.get(key) or "")
        for key in (
            "title",
            "note_title",
            "display_title",
            "content",
            "desc",
            "description",
            "summary",
            "正文",
            "标题",
        )
    )


def _normalize_keyword_list(value: Any) -> list[str]:
    if value in (None, ""):
        return []
    if isinstance(value, str):
        value = [part.strip() for part in re.split(r"[、,，;；/|\n\r\t]+", value) if part.strip()]
    if not isinstance(value, list):
        value = [value]
    result: list[str] = []
    for item in value:
        text = str(item or "").strip()
        if text and text not in result:
            result.append(text)
    return result


KOC_DEFAULT_STUDY_KEYWORDS = [
    "学习",
    "上课",
    "听课",
    "课堂",
    "课程",
    "笔记",
    "复习",
    "备考",
    "考试",
    "期末",
    "final",
    "essay",
    "assignment",
    "lecture",
    "论文",
    "作业",
    "专业",
    "学校",
    "自习",
    "图书馆",
    "gpa",
    "presentation",
    "seminar",
    "港硕",
    "留学",
]

KOC_DEFAULT_PRODUCT_SCENE_KEYWORDS = [
    "听课",
    "课堂",
    "lecture",
    "课程",
    "录音",
    "转写",
    "翻译",
    "总结",
    "笔记",
    "复盘",
    "课后",
    "学习效率",
    "效率工具",
]

KOC_DEFAULT_CONFLICT_KEYWORDS = [
    "纯vlog",
    "vlog",
    "旅行",
    "旅游",
    "探店",
    "穿搭",
    "美妆",
    "护肤",
    "情绪",
    "情侣",
    "日常流水账",
    "纯生活",
    "吃喝玩乐",
]


def _koc_project_keywords(project_id: str | None) -> dict[str, list[str]]:
    plan = _project_screening_plan(project_id) if project_id else {}
    project_fit = plan.get("projectFitConfig") if isinstance(plan.get("projectFitConfig"), dict) else {}
    special = _project_special_scoring_config(project_id)
    patch = special.get("project_fit_config_patch") if isinstance(special.get("project_fit_config_patch"), dict) else {}
    scene_config = special.get("scene") if isinstance(special.get("scene"), dict) else {}
    negative_config = special.get("negative") if isinstance(special.get("negative"), dict) else {}
    hard_rules = _project_hard_rules_config(project_id)
    koc_config = plan.get("kocScoringConfig") if isinstance(plan.get("kocScoringConfig"), dict) else {}
    return {
        "target": list(dict.fromkeys([
            *KOC_DEFAULT_STUDY_KEYWORDS,
            *_normalize_keyword_list(project_fit.get("target_content_keywords")),
            *_normalize_keyword_list(scene_config.get("keywords")),
            *_normalize_keyword_list(hard_rules.get("target_content_keywords")),
            *_normalize_keyword_list(koc_config.get("target_content_keywords")),
        ])),
        "product_scene": list(dict.fromkeys([
            *KOC_DEFAULT_PRODUCT_SCENE_KEYWORDS,
            *_normalize_keyword_list(project_fit.get("preferred_content_scenes")),
            *_normalize_keyword_list(patch.get("preferred_content_scenes")),
            *_normalize_keyword_list(koc_config.get("product_scene_keywords")),
        ])),
        "conflict": list(dict.fromkeys([
            *KOC_DEFAULT_CONFLICT_KEYWORDS,
            *_normalize_keyword_list(project_fit.get("discouraged_keywords")),
            *_normalize_keyword_list(patch.get("discouraged_keywords")),
            *_normalize_keyword_list(negative_config.get("keywords")),
            *_normalize_keyword_list(koc_config.get("conflict_content_keywords")),
        ])),
    }


def _note_keyword_ratio(cases: list[dict[str, Any]], keywords: list[str]) -> tuple[float | None, list[str]]:
    if not cases:
        return None, []
    evidence: list[str] = []
    hits = 0
    lowered_keywords = [keyword.lower() for keyword in keywords if str(keyword or "").strip()]
    for item in cases:
        text = _note_text(item)
        lowered = text.lower()
        matched = [keyword for keyword in lowered_keywords if keyword and keyword in lowered]
        if matched:
            hits += 1
            title = str(item.get("title") or item.get("note_title") or item.get("display_title") or text).strip()
            if title:
                evidence.append(f"{title[:60]}｜命中{', '.join(matched[:3])}")
    return round(hits / len(cases), 4), evidence[:8]


def _koc_content_profiles(creator: dict[str, Any], project_id: str | None) -> dict[str, Any]:
    raw_payload = _creator_raw_payload(creator)
    cases = _collect_note_cases_from_payload(raw_payload)
    keywords = _koc_project_keywords(project_id)
    target_ratio, target_evidence = _note_keyword_ratio(cases, keywords["target"])
    scene_ratio, scene_evidence = _note_keyword_ratio(cases, keywords["product_scene"])
    conflict_ratio, conflict_evidence = _note_keyword_ratio(cases, keywords["conflict"])
    categories = []
    for evidence in conflict_evidence:
        for keyword in keywords["conflict"]:
            if keyword.lower() in evidence.lower() and keyword not in categories:
                categories.append(keyword)
    return {
        "target_content_ratio": target_ratio,
        "target_content_evidence": target_evidence,
        "product_scene_ratio": scene_ratio,
        "product_scene_evidence": scene_evidence,
        "conflict_content_ratio": conflict_ratio,
        "conflict_content_categories": categories[:8],
        "note_sample_count": len(cases),
    }


def _commercial_order_signal(creator: dict[str, Any]) -> str:
    raw_payload = _creator_raw_payload(creator)
    cooperation_cases = raw_payload.get("cooperation_note_cases") if isinstance(raw_payload.get("cooperation_note_cases"), list) else []
    if cooperation_cases:
        return "有商单证据"
    text = _text_blob(creator)
    if any(keyword in text for keyword in ["合作笔记", "商单", "品牌合作", "蒲公英合作"]):
        return "疑似有商单"
    return "待补"


def _creator_no_order_permission_signal(creator: dict[str, Any], raw_payload: dict[str, Any] | None = None) -> str:
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
        return "无接单权限"
    return ""


def _recent_update_status(creator: dict[str, Any], days: Any) -> str:
    window = parse_number(days)
    if window is None:
        return "未配置"
    latest = _latest_note_date(creator)
    if latest is None:
        return "待补"
    age_days = (datetime.now() - latest).days
    return f"近{int(window)}天有更新" if age_days <= window else "疑似断更"


def _low_like_risk(creator: dict[str, Any], threshold: Any, ignore_same_day: bool = True) -> str:
    limit = parse_number(threshold)
    if limit is None:
        return "未配置"
    counts = _like_counts_from_notes(creator)
    if not counts:
        return "待补"
    today = datetime.now().date()
    risky = []
    for item in counts:
        date = item.get("date")
        if ignore_same_day and isinstance(date, datetime) and date.date() == today:
            continue
        if float(item["like_count"]) < limit:
            risky.append(item)
    return "低赞风险" if risky else "无明显风险"


def _low_like_risk_profile(creator: dict[str, Any], threshold: Any, ignore_same_day: bool = True) -> dict[str, Any]:
    limit = parse_number(threshold)
    counts = _like_counts_from_notes(creator)
    if limit is None:
        return {"status": "未配置", "sample_count": len(counts), "low_count": 0, "ratio": None, "level": "none"}
    if not counts:
        return {"status": "待补", "sample_count": 0, "low_count": 0, "ratio": None, "level": "missing"}
    today = datetime.now().date()
    valid = []
    for item in counts:
        date = item.get("date")
        if ignore_same_day and isinstance(date, datetime) and date.date() == today:
            continue
        valid.append(item)
    if not valid:
        return {"status": "待补", "sample_count": 0, "low_count": 0, "ratio": None, "level": "missing"}
    low = [item for item in valid if float(item["like_count"]) < limit]
    low_ratio = len(low) / len(valid)
    if len(valid) >= 5 and low_ratio >= 0.5:
        level = "hard"
        status = "高低赞风险"
    elif low:
        level = "warning"
        status = "低赞风险"
    else:
        level = "none"
        status = "无明显风险"
    return {
        "status": status,
        "sample_count": len(valid),
        "low_count": len(low),
        "ratio": round(low_ratio, 4),
        "threshold": limit,
        "level": level,
    }


def _format_budget_fit(creator: dict[str, Any], policy: dict[str, Any]) -> tuple[str, str, str]:
    image_cap = policy.get("image_quote_cap") or policy.get("single_creator_budget_cap")
    video_cap = policy.get("video_quote_cap") or policy.get("single_creator_budget_cap")
    image_status = _quote_status(creator.get("quote_price"), image_cap, "图文")
    video_status = _quote_status(creator.get("video_quote_price"), video_cap, "视频")
    allowed = [str(item) for item in (policy.get("allowed_formats") or [])]
    if not allowed:
        allowed = ["图文"]
    image_ok = image_status == "图文预算内"
    video_ok = video_status == "视频预算内"
    image_known = "待核" not in image_status
    video_known = "待核" not in video_status
    image_over = image_status == "图文超预算"
    video_over = video_status == "视频超预算"
    image_has_cap = parse_number(image_cap) is not None
    video_has_cap = parse_number(video_cap) is not None
    if "图文" in allowed and "视频" in allowed:
        if image_ok and video_ok:
            fit = "推荐形态预算匹配"
        elif image_ok and video_over:
            fit = "仅图文可投"
        elif video_ok and image_over:
            fit = "仅视频可投"
        elif image_over and video_over:
            fit = "均超预算"
        else:
            fit = "待核"
    elif "视频" in allowed:
        fit = "推荐形态预算匹配" if video_ok else ("均超预算" if video_over and video_has_cap else "待核")
    else:
        fit = "推荐形态预算匹配" if image_ok else ("均超预算" if image_over and image_has_cap else "待核")
    return image_status, video_status, fit


def _best_project_data_value(creator: dict[str, Any]) -> float | None:
    values = [
        parse_number(creator.get("daily_read_median")),
        parse_number(creator.get("image_daily_read_median")),
        parse_number(creator.get("video_daily_read_median")),
        parse_number(creator.get("cooperation_read_median")),
    ]
    raw_payload = _creator_raw_payload(creator)
    for item in _collect_note_cases_from_payload(raw_payload):
        read = parse_number(item.get("read_count") or item.get("readCount") or item.get("read"))
        if read is not None:
            values.append(read)
    numeric = [value for value in values if value is not None and value > 0]
    return max(numeric) if numeric else None


def _premium_exception_profile(creator: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    exception_policy = policy.get("premium_exception_policy") if isinstance(policy.get("premium_exception_policy"), dict) else {}
    if exception_policy.get("enabled") is False:
        return {"passed": False, "reason": "溢价例外未启用"}
    multiplier = parse_number(exception_policy.get("max_budget_multiplier")) or 1.5
    top_percent = parse_number(exception_policy.get("data_top_percent")) or 5
    percentile = max(0.5, min(0.99, 1 - top_percent / 100))
    benchmark = _scoring_benchmark_for_creator(creator)
    top_read = parse_number(benchmark.get("top_read"))
    if top_read is None:
        excellent = parse_number(benchmark.get("excellent_read"))
        good = parse_number(benchmark.get("good_read"))
        top_read = excellent or (good * 1.5 if good is not None else None)
    best_read = _best_project_data_value(creator)
    data_pass = bool(best_read is not None and top_read is not None and best_read >= top_read)
    image_cap = parse_number(policy.get("image_quote_cap") or policy.get("single_creator_budget_cap"))
    video_cap = parse_number(policy.get("video_quote_cap") or policy.get("single_creator_budget_cap"))
    image_quote = parse_number(creator.get("quote_price"))
    video_quote = parse_number(creator.get("video_quote_price"))
    quote_options = []
    if image_cap is not None and image_quote is not None:
        quote_options.append(("图文", image_quote, image_cap))
    if video_cap is not None and video_quote is not None:
        quote_options.append(("视频", video_quote, video_cap))
    within_multiplier = [
        label
        for label, quote, cap in quote_options
        if cap < quote <= cap * multiplier
    ]
    passed = data_pass and bool(within_multiplier)
    reason = (
        f"数据达前{top_percent:g}%线，最佳阅读{best_read:.0f}≥{top_read:.0f}，"
        f"{'、'.join(within_multiplier) or '无形态'}报价不超过预算{multiplier:g}倍"
        if passed and best_read is not None and top_read is not None
        else ""
    )
    return {
        "passed": passed,
        "reason": reason or "未满足高性价比溢价例外",
        "best_read": best_read,
        "top_read_threshold": top_read,
        "data_top_percent": top_percent,
        "max_budget_multiplier": multiplier,
        "formats": within_multiplier,
        "percentile": percentile,
    }


def _koc_stage1_profile(
    creator: dict[str, Any],
    project_id: str | None,
    data_profile: dict[str, Any] | None = None,
    efficiency_profile: dict[str, Any] | None = None,
) -> dict[str, str]:
    if not _is_koc_project(project_id):
        return {"stage1_priority": "", "stage1_reason": ""}
    data_profile = data_profile or _recent_note_data_profile(creator)
    efficiency_profile = efficiency_profile or _efficiency_profile(
        creator,
        data_profile.get("benchmark") or {},
        data_profile.get("median_read") or data_profile.get("avg_read"),
    )
    policy = _project_format_budget_policy(project_id)
    image_status, video_status, budget_fit = _format_budget_fit(creator, policy)
    quote = min(
        [
            value
            for value in (
                parse_number(creator.get("quote_price")),
                parse_number(creator.get("video_quote_price")),
            )
            if value is not None
        ],
        default=None,
    )
    read = data_profile.get("median_read") or data_profile.get("avg_read") or _creator_read_metric(creator)
    interaction = data_profile.get("avg_interaction") or _creator_interaction_metric(creator)
    cpe = parse_number(efficiency_profile.get("effective_cpe")) or _creator_cpe_metric(creator)
    overseas = _has_overseas_study_background(creator)
    stage_derivatives = _creator_stage_derivatives(creator, project_id)
    return _koc_stage1_profile_from_metrics(
        creator,
        project_id,
        stage_derivatives,
        read=read,
        interaction=interaction,
        cpe=cpe,
        overseas=overseas,
    )


def _koc_stage1_profile_from_metrics(
    creator: dict[str, Any],
    project_id: str | None,
    stage_derivatives: dict[str, Any],
    *,
    read: Any = None,
    interaction: Any = None,
    cpe: Any = None,
    overseas: bool = False,
) -> dict[str, str]:
    if not _is_koc_project(project_id):
        return {"stage1_priority": "", "stage1_reason": ""}
    koc_config = _project_koc_scoring_config(project_id)
    budget_accept_max = _koc_config_number(koc_config, "stage1_thresholds", "budget_accept_max", 1000)
    read_priority_min = _koc_config_number(koc_config, "stage1_thresholds", "read_priority_min", 1000)
    interaction_priority_min = _koc_config_number(koc_config, "stage1_thresholds", "interaction_priority_min", 100)
    cpe_priority_max = _koc_config_number(koc_config, "stage1_thresholds", "cpe_priority_max", 7)
    image_status = str(stage_derivatives.get("image_quote_status") or "")
    video_status = str(stage_derivatives.get("video_quote_status") or "")
    budget_fit = str(stage_derivatives.get("format_budget_fit") or "待核")
    quote = min(
        [
            value
            for value in (
                parse_number(creator.get("quote_price")),
                parse_number(creator.get("video_quote_price")),
            )
            if value is not None
        ],
        default=None,
    )
    signals = []
    weak = []
    if quote is not None and quote <= budget_accept_max:
        signals.append(f"报价{quote:g}≤{budget_accept_max:g}")
    else:
        weak.append(f"报价待补或超{budget_accept_max:g}")
    if read is not None and read >= read_priority_min:
        signals.append(f"阅读{read:.0f}≥{read_priority_min:g}")
    else:
        weak.append(f"阅读未达{read_priority_min:g}或待补")
    if interaction is not None and interaction >= interaction_priority_min:
        signals.append(f"互动{interaction:.0f}≥{interaction_priority_min:g}")
    else:
        weak.append(f"互动未达{interaction_priority_min:g}或待补")
    if cpe is not None and cpe <= cpe_priority_max:
        signals.append(f"CPE{cpe:.2f}≤{cpe_priority_max:g}")
    elif cpe is not None:
        weak.append(f"CPE{cpe:.2f}偏高")
    else:
        weak.append("CPE待补")
    if overseas:
        signals.append("有留学/海外弱证据")
    else:
        weak.append("留学/海外证据待补")
    if budget_fit == "均超预算":
        priority = "不入库"
    elif len(signals) >= 4:
        priority = "P0"
    elif len(signals) >= 3:
        priority = "P1"
    elif len(signals) >= 2:
        priority = "P2"
    else:
        priority = "P3"
    if not _has_cooperation_note_metrics(creator) and priority in {"P0", "P1"}:
        priority = "P2"
        weak.insert(0, "缺合作笔记核心数据，P级最高P2")
    return {
        "stage1_priority": priority,
        "stage1_reason": "；".join([*signals, *weak[:3], f"预算状态{budget_fit}", image_status, video_status]),
    }


def _recommended_format_from_budget(stage_derivatives: dict[str, Any], policy: dict[str, Any]) -> str:
    preferred = str(policy.get("preferred_format") or "").strip()
    budget_fit = stage_derivatives.get("format_budget_fit")
    if budget_fit == "均超预算":
        return "不推荐"
    if budget_fit == "仅图文可投":
        return "图文"
    if budget_fit == "仅视频可投":
        return "视频"
    if budget_fit == "推荐形态预算匹配":
        return preferred if preferred in {"图文", "视频"} else "均可"
    return "待补"


def _koc_risk_control_result(
    creator: dict[str, Any],
    project_id: str | None,
    stage_derivatives: dict[str, Any],
    content_profile: dict[str, Any],
) -> dict[str, Any]:
    hard_rules = _project_hard_rules_config(project_id)
    hard: list[str] = []
    warning: list[str] = []
    missing: list[str] = []
    if stage_derivatives.get("format_budget_fit") == "均超预算" and not stage_derivatives.get("premium_exception_passed"):
        hard.append("图文/视频报价均超预算")
    reply_min = ratio(hard_rules.get("reply_rate_min"))
    reply = ratio(creator.get("reply_rate_48h"))
    if reply_min is not None and reply is not None and reply < reply_min:
        hard.append(f"48h回复率{reply:.0%}低于{reply_min:.0%}")
    if reply_min is not None and reply is None:
        missing.append("48h回复率")
    if hard_rules.get("must_have_commercial_order") and stage_derivatives.get("commercial_order_signal") == "待补":
        missing.append("商单证据")
    if stage_derivatives.get("recent_update_status") == "疑似断更":
        hard.append("近期未更新")
    elif stage_derivatives.get("recent_update_status") == "待补":
        missing.append("近期更新")
    low_like = _low_like_risk_profile(
        creator,
        hard_rules.get("low_like_threshold"),
        hard_rules.get("ignore_low_like_if_same_day") is not False,
    )
    if low_like.get("level") == "hard":
        hard.append("近期低赞比例较高")
    elif low_like.get("level") == "warning":
        warning.append("存在少量低赞笔记")
    elif low_like.get("level") == "missing":
        missing.append("近期点赞数据")
    required_ratio = ratio(hard_rules.get("must_have_study_content_ratio"))
    target_ratio = content_profile.get("target_content_ratio")
    if required_ratio is not None:
        if target_ratio is None:
            missing.append("学习类内容占比")
        elif target_ratio < required_ratio:
            hard.append(f"学习类内容占比{target_ratio:.0%}低于{required_ratio:.0%}")
    if hard_rules.get("must_have_study_abroad_trace") and not _has_overseas_study_background(creator):
        missing.append("留学/海外身份痕迹")
    conflict_ratio = content_profile.get("conflict_content_ratio")
    koc_config = _project_koc_scoring_config(project_id)
    conflict_warning_ratio = _koc_config_number(koc_config, "detail_stage_rules", "conflict_warning_ratio", 0.5)
    conflict_target_floor = _koc_config_number(koc_config, "detail_stage_rules", "conflict_is_hard_only_when_target_below", 0.5)
    if conflict_ratio is not None and conflict_ratio >= conflict_warning_ratio and (target_ratio is None or target_ratio < conflict_target_floor):
        warning.append("近期内容偏生活/vlog，需要人工确认非纯vlog")
    return {
        "hard": list(dict.fromkeys(hard)),
        "warning": list(dict.fromkeys(warning)),
        "missing": list(dict.fromkeys(missing)),
        "low_like": low_like,
    }


def _koc_final_profile(
    creator: dict[str, Any],
    project_id: str | None,
    stage_derivatives: dict[str, Any],
    data_profile: dict[str, Any],
    efficiency_profile: dict[str, Any],
) -> dict[str, Any]:
    content_profile = _koc_content_profiles(creator, project_id)
    risk_result = _koc_risk_control_result(creator, project_id, stage_derivatives, content_profile)
    read = data_profile.get("median_read") or data_profile.get("avg_read") or _creator_read_metric(creator)
    interaction = data_profile.get("avg_interaction") or _creator_interaction_metric(creator)
    cpe = parse_number(efficiency_profile.get("effective_cpe")) or _creator_cpe_metric(creator)
    overseas = _has_overseas_study_background(creator)
    stage1 = _koc_stage1_profile_from_metrics(
        creator,
        project_id,
        stage_derivatives,
        read=read,
        interaction=interaction,
        cpe=cpe,
        overseas=overseas,
    )
    policy = _project_format_budget_policy(project_id)
    hard_rules = _project_hard_rules_config(project_id)
    koc_config = _project_koc_scoring_config(project_id)
    target_required = (
        ratio(hard_rules.get("must_have_study_content_ratio"))
        or _koc_config_number(koc_config, "detail_stage_rules", "target_content_required_ratio", 0.5)
    )
    minimum_sample = _koc_config_number(koc_config, "detail_stage_rules", "minimum_sample_for_decision", 5)
    scene_strong_ratio = _koc_config_number(koc_config, "detail_stage_rules", "product_scene_strong_ratio", 0.25)
    good_read_min = _koc_config_number(koc_config, "final_match_thresholds", "good_read_min", 1000)
    good_interaction_min = _koc_config_number(koc_config, "final_match_thresholds", "good_interaction_min", 100)
    good_cpe_max = _koc_config_number(koc_config, "final_match_thresholds", "good_cpe_max", 7)
    strong_read_min = _koc_config_number(koc_config, "final_match_thresholds", "strong_read_min", 2400)
    strong_interaction_min = _koc_config_number(koc_config, "final_match_thresholds", "strong_interaction_min", 274)
    strong_cpe_max = _koc_config_number(koc_config, "final_match_thresholds", "strong_cpe_max", 3.8)
    target_ratio = content_profile.get("target_content_ratio")
    scene_ratio = content_profile.get("product_scene_ratio")
    missing_cooperation_note_data = not _has_cooperation_note_metrics(creator)
    evidence_missing = bool(risk_result["missing"]) or target_ratio is None or content_profile.get("note_sample_count", 0) < minimum_sample
    strong_data = bool(
        read is not None
        and read >= strong_read_min
        and interaction is not None
        and interaction >= strong_interaction_min
        and (cpe is None or cpe <= strong_cpe_max)
    )
    good_data = bool(
        read is not None
        and read >= good_read_min
        and interaction is not None
        and interaction >= good_interaction_min
        and (cpe is None or cpe <= good_cpe_max)
    )
    if risk_result["hard"]:
        status = "Pass"
        confidence = 0.88
    elif missing_cooperation_note_data:
        status = "待人工确认" if target_ratio is None or content_profile.get("note_sample_count", 0) < minimum_sample else "备选"
        confidence = 0.58
        risk_result["missing"] = list(dict.fromkeys([*risk_result.get("missing", []), "合作笔记核心数据"]))
    elif evidence_missing:
        status = "待人工确认"
        confidence = 0.55
    elif overseas and target_ratio >= target_required and good_data and stage_derivatives.get("format_budget_fit") != "待核":
        status = "强推荐" if strong_data and (scene_ratio or 0) >= scene_strong_ratio and not risk_result["warning"] else "推荐"
        confidence = 0.82 if status == "强推荐" else 0.74
    elif target_ratio is not None and target_ratio >= target_required and good_data:
        status = "备选"
        confidence = 0.66
    else:
        status = "不推荐"
        confidence = 0.74
    return {
        **stage1,
        "project_match_status": status,
        "project_match_confidence": confidence,
        "final_recommend_level": status,
        "recommended_format": _recommended_format_from_budget(stage_derivatives, policy),
        "risk_control_result": risk_result,
        **content_profile,
    }


def _creator_stage_derivatives(creator: dict[str, Any], project_id: str | None = None) -> dict[str, Any]:
    cache_key = str(project_id or "")
    cache = creator.get("_stage_derivatives_cache")
    if isinstance(cache, dict) and cache_key in cache:
        return dict(cache[cache_key])
    policy = _project_format_budget_policy(project_id)
    hard_rules = _project_hard_rules_config(project_id)
    image_status, video_status, budget_fit = _format_budget_fit(creator, policy)
    premium_exception = _premium_exception_profile(creator, policy) if policy else {"passed": False, "reason": ""}
    note_counts = _note_format_counts(creator)
    commercial_signal = _commercial_order_signal(creator)
    recent_status = _recent_update_status(creator, hard_rules.get("recent_update_days"))
    low_like_risk = _low_like_risk(
        creator,
        hard_rules.get("low_like_threshold"),
        hard_rules.get("ignore_low_like_if_same_day") is not False,
    )
    reply = ratio(creator.get("reply_rate_48h"))
    reply_min = ratio(hard_rules.get("reply_rate_min"))
    pass_reasons: list[str] = []
    detail_reasons: list[str] = []
    if reply_min is not None and reply is not None and reply < reply_min:
        pass_reasons.append(f"48h回复率{reply:.0%}低于{reply_min:.0%}")
    if budget_fit == "均超预算" and not premium_exception.get("passed"):
        pass_reasons.append("图文/视频报价均超预算")
    elif budget_fit == "均超预算" and premium_exception.get("passed"):
        detail_reasons.append(f"高性价比溢价例外：{premium_exception.get('reason')}")
    if _creator_no_order_permission_signal(creator, _creator_raw_payload(creator)):
        pass_reasons.append("无接单权限")
    if recent_status == "疑似断更":
        pass_reasons.append("近期未更新")
    if low_like_risk == "低赞风险":
        pass_reasons.append("近期笔记存在低赞风险")
    if hard_rules.get("must_have_commercial_order") and commercial_signal == "待补":
        detail_reasons.append("需补商单证据")
    if note_counts["dominant"] == "待补":
        detail_reasons.append("需补近期笔记形态")
    if budget_fit == "待核":
        detail_reasons.append("需补报价/合作形态")
    if recent_status == "待补":
        detail_reasons.append("需补近期更新")
    if low_like_risk == "待补":
        detail_reasons.append("需补近期点赞数据")
    if pass_reasons:
        stage_status = "一阶段Pass"
    elif detail_reasons:
        stage_status = "优先补全"
    else:
        stage_status = "可补全"
    result = {
        "image_quote_status": image_status,
        "video_quote_status": video_status,
        "format_budget_fit": budget_fit,
        "premium_exception_passed": bool(premium_exception.get("passed")),
        "premium_exception_reason": premium_exception.get("reason") or "",
        "dominant_note_format": note_counts["dominant"],
        "note_format_counts": json.dumps(note_counts, ensure_ascii=False),
        "commercial_order_signal": commercial_signal,
        "recent_update_status": recent_status,
        "low_like_risk": low_like_risk,
        "stage_one_status": stage_status,
        "detail_need_reason": "；".join([*pass_reasons, *detail_reasons]),
    }
    if not isinstance(cache, dict):
        cache = {}
        creator["_stage_derivatives_cache"] = cache
    cache[cache_key] = dict(result)
    return result


def _project_hard_filter_issues(project_id: str, creator: dict[str, Any]) -> list[str]:
    raw_payload = _creator_raw_payload(creator)
    collection_issues = raw_payload.get("collection_hard_filter_issues")
    if isinstance(collection_issues, list) and collection_issues:
        issues = [
            str(item)
            for item in collection_issues
            if item and not re.search(r"近30天.*报价\s*\d+(?:\.\d+)?\s*超过\s*30", str(item))
        ]
        issues = list(dict.fromkeys(issues))
    else:
        issues = []
    permission_text = json.dumps(
        {
            "order_permission_status": creator.get("order_permission_status"),
            "raw_order_permission_status": raw_payload.get("order_permission_status") if isinstance(raw_payload, dict) else "",
            "raw_table": raw_payload.get("raw_table") if isinstance(raw_payload, dict) else "",
            "text": raw_payload.get("text") if isinstance(raw_payload, dict) else "",
            "detail_text": raw_payload.get("detail_text") if isinstance(raw_payload, dict) else "",
            "list_api_kol": raw_payload.get("list_api_kol") if isinstance(raw_payload, dict) else "",
        },
        ensure_ascii=False,
    )
    permission_compact = re.sub(r"\s+", "", permission_text)
    if any(hint in permission_compact for hint in ["无接单权限", "暂无接单权限", "不可接单", "不能接单", "暂不接单", "未开通接单"]):
        issues.append("接单权限：蒲公英显示无接单权限，无法发起合作")
        issues = list(dict.fromkeys(issues))
    stage_derivatives = _creator_stage_derivatives(creator, project_id)
    hard_rules_config = _project_hard_rules_config(project_id)
    if stage_derivatives.get("format_budget_fit") == "均超预算" and not stage_derivatives.get("premium_exception_passed"):
        issues.append("形态预算：图文/视频报价均超过项目预算")
    reply_min = ratio(hard_rules_config.get("reply_rate_min"))
    reply = ratio(creator.get("reply_rate_48h"))
    if reply_min is not None and reply is not None and reply < reply_min:
        issues.append(f"48h回复率：{reply:.0%}低于项目下限{reply_min:.0%}")
    screening_plan = _project_screening_plan(project_id)
    scoring_criteria = screening_plan.get("scoringCriteria") if isinstance(screening_plan.get("scoringCriteria"), dict) else {}
    hard_filters = (
        screening_plan.get("scoringHardFilters")
        or scoring_criteria.get("hard_rules")
        or screening_plan.get("hardFilters")
        or []
    )
    if not hard_filters:
        return issues
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
        ignored_keywords = _project_special_scoring_config(project_id).get("ignore_hard_filter_keywords") or []
        if ignored_keywords and any(str(keyword).lower() in rule_text for keyword in ignored_keywords):
            continue
        if field == "博主类目":
            category_items.append(item)
            continue
        if _rule_targets_quote(field, condition, value, item):
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
            cpc = _first_number(creator.get("effective_cpc"), creator.get("natural_cpc"), positive=True)
            if threshold is not None and cpc is not None and cpc >= threshold:
                issues.append(f"{label}：CPC {cpc:g} 未低于 {threshold:g}")
        if "cpe" in rule_text:
            threshold = _threshold_from_text(value, "cpe")
            cpe = _first_number(creator.get("effective_cpe"), creator.get("natural_cpe"), positive=True)
            if threshold is not None and cpe is not None and cpe >= threshold:
                issues.append(f"{label}：CPE {cpe:g} 未低于 {threshold:g}")
        if any(keyword in rule_text for keyword in ["搜索+推荐", "搜索推荐"]):
            review_status = str(creator.get("search_recommend_review_status") or "")
            if review_status != "已复核":
                issues.append(f"{label}：搜索+推荐占比待人工复核")
        if any(keyword in rule_text for keyword in ["限流", "违规", "流量稳定", "异常"]):
            risk_text = f"{creator.get('rate_limit_risk') or ''} {creator.get('traffic_stability') or ''}"
            if any(keyword in risk_text for keyword in ["高", "限流", "违规", "异常"]):
                issues.append(f"{label}：存在限流/异常流量风险")
        if condition in {"包含", "匹配", "优先", "约等于"} and value and value not in text_blob:
            if any(keyword in rule_text for keyword in ["粉丝年龄", "35", "34"]) and ratio(creator.get("fans_35_plus_ratio")) is None:
                continue
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


def generate_test_stage_score(
    project_id: str,
    creator: dict[str, Any],
    *,
    check_hard_issues: bool = True,
) -> tuple[dict[str, Any], str]:
    score = score_values(creator, project_id=project_id)
    issues = _project_hard_filter_issues(project_id, creator) if check_hard_issues else []
    if issues:
        score["hard_filter_passed"] = 0
        score["initial_tier"] = _initial_tier(score["total_score"], True)
        score["detail_collection_priority"] = _detail_collection_priority(score["total_score"], score.get("bonus_score", 0), False)
        score["recommend_level"] = _recommend_level(score["total_score"], False)
        score["score_reason"] = "；".join([*issues, score["score_reason"]])
    if _is_koc_project(project_id) and score.get("final_recommend_level"):
        score["recommend_level"] = score.get("final_recommend_level")
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


def _normalize_structured_list(value: Any, limit: int = 8) -> list[str]:
    if value in (None, ""):
        return []
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return []
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError:
            parsed = [item.strip() for item in re.split(r"[；;\n]+", stripped) if item.strip()]
        value = parsed
    if isinstance(value, dict):
        value = list(value.values())
    if not isinstance(value, list):
        value = [value]
    result: list[str] = []
    for item in value:
        if isinstance(item, dict):
            text = str(
                item.get("text")
                or item.get("summary")
                or item.get("item")
                or item.get("evidence")
                or item.get("reason")
                or item
            ).strip()
        else:
            text = str(item).strip()
        if text and text not in result:
            result.append(text[:260])
        if len(result) >= limit:
            break
    return result


def _normalize_llm_score(
    result: dict[str, Any],
    fallback: dict[str, Any],
    creator: dict[str, Any] | None = None,
    project_id: str | None = None,
) -> dict[str, Any]:
    dimensions = result.get("dimensionScores") or result.get("scores") or {}
    weights = _project_scoring_weights(project_id)
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
        efficiency_profile = data_profile["efficiency"]
        direction_profile = _project_direction_fit(creator, project_id)
        total = _apply_project_fit_gate(total, creator, _project_fit_config(project_id), gate_reasons)
        total = _apply_quality_gate(total, data_profile, gate_reasons, creator, direction_profile, project_id)
        total = _apply_project_special_scoring(total, creator, data_profile, efficiency_profile, direction_profile, gate_reasons, project_id, hard_pass_bool)
        stage_derivatives = _creator_stage_derivatives(creator, project_id)
        if stage_derivatives.get("format_budget_fit") == "均超预算" and not stage_derivatives.get("premium_exception_passed"):
            total = min(total, 69.0)
            hard_pass_bool = False
            gate_reasons.append("形态预算：图文/视频报价均超过项目预算，初评最高C档")
        elif stage_derivatives.get("premium_exception_passed"):
            hard_pass_bool = True
            gate_reasons.append(f"预算溢价例外：{stage_derivatives.get('premium_exception_reason')}，进入补详情复核")
        elif stage_derivatives.get("format_budget_fit") in {"仅图文可投", "仅视频可投"}:
            gate_reasons.append(f"形态预算：{stage_derivatives.get('format_budget_fit')}，推荐形态需受限")
        if gate_reasons:
            reasons = "；".join([str(reasons).strip(), *gate_reasons])
        initial_tier = _initial_tier(total, hard_pass_bool)
        detail_priority = _detail_collection_priority(total, bonus_score, hard_pass_bool)
        if hard_pass_bool and _has_project_special_scoring(project_id):
            initial_tier = _initial_tier(total, hard_pass_bool)
            detail_priority = _detail_collection_priority(total, bonus_score, hard_pass_bool)
        low_reply_reasons: list[str] = []
        total, low_reply_gate_applied = _apply_low_reply_rate_gate(
            total,
            creator,
            low_reply_reasons,
            ratio(_project_hard_rules_config(project_id).get("reply_rate_min")),
        )
        if low_reply_reasons:
            reasons = "；".join([str(reasons).strip(), *low_reply_reasons])
        if low_reply_gate_applied:
            hard_pass_bool = False
            initial_tier = _initial_tier(total, hard_pass_bool)
            detail_priority = _detail_collection_priority(total, bonus_score, hard_pass_bool)
        recommend_level = _recommend_level(total, hard_pass_bool)
    cooperation_direction = _extract_cooperation_direction(result, creator or {}, str(recommend_level))
    manual_review_items = _normalize_structured_list(result.get("manualReviewItems") or result.get("manual_review_items") or [])
    evidence_quotes = _normalize_structured_list(result.get("evidenceQuotes") or result.get("evidence_quotes") or [], limit=5)
    project_match_status = str(result.get("projectMatchStatus") or result.get("project_match_status") or "").strip()
    format_budget_status = str(result.get("formatBudgetStatus") or result.get("format_budget_status") or "").strip()
    recommended_format = str(result.get("recommendedFormat") or result.get("recommended_format") or "").strip()
    implantability = str(result.get("implantability") or "").strip()
    hard_rule_results = _normalize_structured_list(result.get("hardRuleResults") or result.get("hard_rule_results") or [], limit=8)
    stage_summary = []
    if project_match_status:
        stage_summary.append(f"二阶段审号：{project_match_status}")
    if recommended_format or format_budget_status:
        stage_summary.append(f"推荐形态：{recommended_format or '待补'}，{format_budget_status or '待核'}")
    if implantability:
        stage_summary.append(f"植入空间：{implantability}")
    if hard_rule_results:
        stage_summary.append(f"硬性条件：{'；'.join(hard_rule_results[:3])}")
    if stage_summary:
        reasons = "；".join([str(reasons).strip(), *stage_summary])
    llm_confidence = parse_number(result.get("confidence") or result.get("llmConfidence") or result.get("llm_confidence"))
    koc_profile: dict[str, Any] = {}
    if creator and _is_koc_project(project_id):
        data_profile = _recent_note_data_profile(creator)
        efficiency_profile = _efficiency_profile(
            creator,
            data_profile.get("benchmark") or {},
            data_profile.get("median_read") or data_profile.get("avg_read"),
        )
        stage_derivatives = _creator_stage_derivatives(creator, project_id)
        koc_profile = _koc_final_profile(creator, project_id, stage_derivatives, data_profile, efficiency_profile)
        status = str(
            result.get("projectMatchStatus")
            or result.get("project_match_status")
            or koc_profile.get("project_match_status")
            or ""
        ).strip()
        if status in {"Pass", "不推荐"}:
            hard_pass_bool = False
            total = min(total, 69.0 if status == "Pass" else 74.0)
        elif status == "待人工确认":
            total = min(total, 84.0)
        elif status == "备选":
            total = min(total, 79.0)
        elif status == "推荐":
            total = max(total, 80.0)
        elif status == "强推荐":
            total = max(total, 90.0)
        initial_tier = _initial_tier(total, hard_pass_bool)
        detail_priority = _detail_collection_priority(total, bonus_score, hard_pass_bool)
        if status == "待人工确认":
            detail_priority = min_priority_label(detail_priority, "中优先级")
        elif status == "备选":
            detail_priority = min_priority_label(detail_priority, "中高优先级")
        recommend_level = status or recommend_level
        koc_summary = []
        if koc_profile.get("stage1_priority"):
            koc_summary.append(f"KOC一阶段：{koc_profile.get('stage1_priority')}，{koc_profile.get('stage1_reason')}")
        if koc_profile.get("project_match_status"):
            koc_summary.append(f"KOC二阶段：{koc_profile.get('project_match_status')}")
        if koc_summary:
            reasons = "；".join([str(reasons).strip(), *koc_summary])
    return {
        "total_score": round(total, 2),
        "rule_group_score": fallback.get("rule_group_score") or fallback.get("base_score") or round(total, 2),
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
        "manual_review_items": manual_review_items,
        "evidence_quotes": evidence_quotes,
        "llm_confidence": llm_confidence,
        "llm_prompt_version": str(result.get("promptVersion") or result.get("prompt_version") or ""),
        "llm_schema_version": str(result.get("schemaVersion") or result.get("schema_version") or ""),
        "stage1_priority": str(result.get("stage1Priority") or result.get("stage1_priority") or koc_profile.get("stage1_priority") or ""),
        "stage1_reason": str(result.get("stage1Reason") or result.get("stage1_reason") or koc_profile.get("stage1_reason") or ""),
        "project_match_status": str(result.get("projectMatchStatus") or result.get("project_match_status") or koc_profile.get("project_match_status") or ""),
        "project_match_confidence": parse_number(result.get("projectMatchConfidence") or result.get("project_match_confidence")) or koc_profile.get("project_match_confidence"),
        "final_recommend_level": str(result.get("finalRecommendLevel") or result.get("final_recommend_level") or koc_profile.get("final_recommend_level") or recommend_level),
        "target_content_ratio": parse_number(result.get("studyContentRatioEstimate") or result.get("target_content_ratio")) if (result.get("studyContentRatioEstimate") or result.get("target_content_ratio")) not in (None, "", "待补") else koc_profile.get("target_content_ratio"),
        "target_content_evidence": koc_profile.get("target_content_evidence") or [],
        "product_scene_ratio": koc_profile.get("product_scene_ratio"),
        "product_scene_evidence": koc_profile.get("product_scene_evidence") or [],
        "conflict_content_ratio": koc_profile.get("conflict_content_ratio"),
        "conflict_content_categories": koc_profile.get("conflict_content_categories") or [],
        "risk_control_result": koc_profile.get("risk_control_result") or {},
        "recommended_format": str(result.get("recommendedFormat") or result.get("recommended_format") or koc_profile.get("recommended_format") or ""),
    }


LLM_BATCH_CONTEXT_LIMIT_CHARS = 850_000
LLM_BATCH_MAX_CREATORS = max(1, _int_env("LLM_BATCH_MAX_CREATORS", 1))
LLM_SCORE_MAX_WORKERS = max(1, _int_env("LLM_SCORE_MAX_WORKERS", 50))
LLM_SCORE_RETRY_ATTEMPTS = max(1, _int_env("LLM_SCORE_RETRY_ATTEMPTS", 2))


def _creator_score_payload(creator: dict[str, Any], project_id: str | None = None) -> dict[str, Any]:
    stage_derivatives = _creator_stage_derivatives(creator, project_id)
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
        "video_quote_price": creator.get("video_quote_price"),
        "stage_derivatives": stage_derivatives,
        "image_quote_status": stage_derivatives.get("image_quote_status"),
        "video_quote_status": stage_derivatives.get("video_quote_status"),
        "format_budget_fit": stage_derivatives.get("format_budget_fit"),
        "premium_exception_passed": stage_derivatives.get("premium_exception_passed"),
        "premium_exception_reason": stage_derivatives.get("premium_exception_reason"),
        "dominant_note_format": stage_derivatives.get("dominant_note_format"),
        "commercial_order_signal": stage_derivatives.get("commercial_order_signal"),
        "recent_update_status": stage_derivatives.get("recent_update_status"),
        "low_like_risk": stage_derivatives.get("low_like_risk"),
        "stage_one_status": stage_derivatives.get("stage_one_status"),
        "detail_need_reason": stage_derivatives.get("detail_need_reason"),
        "effective_cpc": creator.get("effective_cpc"),
        "effective_cpc_source": creator.get("effective_cpc_source"),
        "effective_cpe": creator.get("effective_cpe"),
        "effective_cpe_source": creator.get("effective_cpe_source"),
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
        "fans_35_plus_ratio": creator.get("fans_35_plus_ratio"),
        "fans_35_plus_ratio_source": creator.get("fans_35_plus_ratio_source"),
        "traffic_stability": creator.get("traffic_stability"),
        "rate_limit_risk": creator.get("rate_limit_risk"),
        "rate_limit_risk_reason": creator.get("rate_limit_risk_reason"),
        "child_grade_confidence": creator.get("child_grade_confidence"),
        "child_grade_evidence": creator.get("child_grade_evidence"),
        "content_scene_tags": creator.get("content_scene_tags"),
        "presentation_style_tags": creator.get("presentation_style_tags"),
        "search_recommend_review_status": creator.get("search_recommend_review_status"),
        "search_recommend_review_note": creator.get("search_recommend_review_note"),
        "pgy_url": creator.get("pgy_url"),
        "raw_payload": creator.get("raw_payload"),
        "machine_data_profile": _budget_effect_profile(creator),
    }


def _score_batch_payload(project_id: str, creators: list[dict[str, Any]]) -> dict[str, Any]:
    project = _cached_project(project_id) or {}
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
    format_budget_policy = screening_plan.get("formatBudgetPolicy") or scoring_criteria.get("format_budget_policy") or {}
    hard_rules = screening_plan.get("hardRules") or scoring_criteria.get("project_hard_rules") or {}
    data_layer = screening_plan.get("dataLayerScoring") or scoring_criteria.get("data_layer_scoring") or {}
    tier_policy = screening_plan.get("tierPolicy") or scoring_criteria.get("tier_policy") or {}
    return {
        "project": {
            "project_id": project_id,
            "project_name": project.get("project_name") or PROJECT_NAME,
            "brief": project.get("brief") or "当前项目 Brief",
            "target_qualified_creator_count": project.get("target_qualified_creator_count"),
            "projectFitConfig": screening_plan.get("projectFitConfig") if isinstance(screening_plan.get("projectFitConfig"), dict) else {},
            "promotionStrategy": screening_plan.get("promotionStrategy") if isinstance(screening_plan.get("promotionStrategy"), dict) else {},
            "budgetPolicy": budget_policy,
            "formatBudgetPolicy": format_budget_policy if isinstance(format_budget_policy, dict) else {},
            "hardRules": hard_rules if isinstance(hard_rules, dict) else {},
            "scoringCriteria": scoring_criteria,
            "dataLayerScoring": data_layer,
            "tierPolicy": tier_policy,
            "scoringHardFilters": screening_plan.get("scoringHardFilters") or (screening_plan.get("scoringCriteria") or {}).get("hard_rules") or screening_plan.get("hardFilters") or [],
            "hardFilters": screening_plan.get("scoringHardFilters") or (screening_plan.get("scoringCriteria") or {}).get("hard_rules") or screening_plan.get("hardFilters") or [],
            "scoringWeights": screening_plan.get("scoringWeights") or {},
            "scoringExecutionPolicy": {
                "prompt_version": "creator-score-v2-20260519",
                "schema_version": "creator-score-structured-v2",
                "search_recommend_ratio_policy": "manual_review_only",
                "model_role": "辅助解释和有限加减权，不替代规则事实层",
            },
            "scoringProtocol": [
                "仅当 projectFitConfig.is_koc_project=true、项目配置显式选择KOC，或Brief明确提到KOC时，才启用KOC通用评分结构；不得因为预算低于2000元自动套用KOC结构。",
                "KOC项目分两阶段：一阶段只判断入库/补详情优先级，不直接给强推荐；二阶段必须结合主页、简介、近期笔记标题/正文、数据和风险控制后输出最终推荐。",
                "初评分只使用稳定入库字段，主公式抓5类：目标人群匹配、阅读/互动中位数、报价与阅读/互动单价、内容方向/卖点承接、执行确定性。",
                "粉丝量只作为T级比较坐标，不作为高权重加分项；阅读/互动必须按同T级基准判断。",
                "报价不是越低越好，必须结合报价能换来的阅读/互动总量、CPM/CPC/CPE效率、单达人参考预算和硬上限判断。",
                "类目、个人标签、期待合作行业只是弱方向证据；没有主页简介、详情页、笔记标题/正文时，不得直接判定高知/教师/大孩家长等强人设。",
                "缺蒲公英链接、缺字段、缺近期笔记正文是采集/证据状态，不是达人质量问题，不得作为硬性淘汰原因。",
                "只有已确认的报价超硬上限、同T级近30天数据明显低于基准、已确认异常/违规/限流，才能作为明确风险。",
                "搜索+推荐占比属于人工复核事实字段，未复核前不得自动加分、扣分或淘汰。",
                "封顶规则必须来自当前 Brief 的明确硬性条件和 scoringCriteria；不得把某个历史项目的人群阈值套到所有项目。",
                "必须结合 promotionStrategy 和 projectFitConfig 判断产品场景、目标用户/决策者、核心卖点、内容调性和转化场景；证据不足时输出 insufficient_evidence 含义的结论，不要硬猜。",
                "必须读取 formatBudgetPolicy：图文报价用 quote_price，视频报价用 video_quote_price；推荐视频时必须校验视频预算，视频超预算但图文预算内只能推荐图文。",
                "若 formatBudgetPolicy.premium_exception_policy 启用，数据达到同量级前5%且报价不超过预算1.5倍的高性价比达人，不因超预算直接Pass，应进入补详情/人工复核。",
                "必须读取 hardRules：回复率、是否接过商单、近期更新、低赞风险、身份/内容占比要求都只能基于已采集或补全后的证据判断；缺字段输出待补/低置信，不要硬猜。",
                "近期合作笔记形态要结合 note_type、noteType、isVideo、视频笔记/图文笔记文本和 stage_derivatives.dominant_note_format 判断。",
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
        "creators": [_creator_score_payload(creator, project_id) for creator in creators],
        "requiredSchema": {
            "results": [
                {
                    "creator_id": "必须原样返回",
                    "stage1Priority": "仅KOC项目需要：P0|P1|P2|P3|不入库；一阶段入库/补详情优先级，不等于最终推荐。",
                    "stage1Reason": "仅KOC项目需要：用预算、阅读、互动、CPE、身份弱证据说明一阶段判断。",
                    "dataLayer": "S|A|B|C；基于目标人群匹配、阅读/互动中位数、报价与CPC/CPE、T级基准得到的数据层级",
                    "baseScore": "0-100 初筛基础分；只使用稳定入库字段，优先目标人群、流量、成本效率、内容方向/卖点承接、执行确定性",
                    "bonusScore": "0-5 微加分；只奖励人群画像、数据表现、成本效率和方向匹配同时成立，不因低价或标签单独加高分",
                    "totalScore": "0-100 初筛总分，等于 baseScore + bonusScore 后封顶",
                    "informationCompleteness": "0-1，当前可用证据完整度；低完整度只影响置信度和后续详情完善优先级，不等于达人质量差",
                    "initialTier": "S|A|B+|B|C；S=95-100证据充分标杆，A=80-94初筛高潜，B+=75-79次高潜，B=70-74备选观察，C<70低优先级；硬性不符也必须保留分数档位，不要输出Pass",
                    "detailCollectionPriority": "最高优先级|高优先级|中高优先级|中优先级|低优先级|数据暂缓；只让数据层级高或高潜达人进入详情页完善内容/人设信息，硬性不符用数据暂缓",
                    "projectMatchStatus": "强推荐|推荐|备选|待人工确认|不推荐|Pass；二阶段审号结论。KOC项目证据不足时输出待人工确认或备选，不得仅凭总分强推荐",
                    "projectMatchConfidence": "0-1，项目匹配置信度；KOC项目缺主页/笔记正文/身份证据时低于0.7",
                    "finalRecommendLevel": "强推荐|推荐|备选|待人工确认|不推荐|Pass；最终对项目可执行推荐结论",
                    "hardRuleResults": [{"rule": "项目硬性条件", "status": "通过|不通过|待补", "evidence": "依据字段/标题/主页/详情证据"}],
                    "studyContentRatioEstimate": "0-1或待补；按项目目标内容占比要求估算，例如学习类内容50%以上",
                    "dominantNoteFormat": "图文为主|视频为主|混合|待补",
                    "recommendedFormat": "图文|视频|均可|不推荐|待补",
                    "formatBudgetStatus": "推荐形态预算匹配|仅图文可投|仅视频可投|均超预算|待核",
                    "implantability": "高|中|低|待补；是否有自然植入空间，必须引用内容/人设/近期笔记证据",
                    "dimensionScores": {
                        "budget": "0-100 执行确定性：蒲公英链接、报价完整、48h回复率、基础身份完整度",
                        "fans": "0-100 目标人群匹配：结合 promotionStrategy 判断使用者/决策者/受众是否匹配；粉丝量只作T级坐标",
                        "cpe": "0-100 成本效率：报价、阅读单价/CPC、互动单价/CPE，CPM只作辅助",
                        "engagement": "0-100 真实流量质量：阅读中位数、互动中位数，需与同T级基准比较",
                        "persona": "0-100 内容方向弱匹配：博主类目、内容标签、个人标签、期待合作行业；不得当成强人设",
                        "content": "0-100 微加分：人群、数据、效率、方向同时成立才给高分",
                    },
                    "hardFilterPassed": "boolean，只基于已确认事实判断；未知项、缺蒲公英链接、缺字段不得当成硬性不符",
                    "recommendLevel": "强推荐|推荐|备选|不推荐|继续观察",
                    "reason": "260字以内，按【目标人群】【阅读互动】【成本效率】【产品内容场景/风险】四段输出。必须先结合 promotionStrategy 识别项目里的具体产品、目标用户、决策者、核心卖点和转化场景，再判断笔记内容和呈现方式是否能自然承接该产品。必须写明报价、阅读/互动中位数、阅读单价/互动单价或CPC/CPE、T级比较结论；标签和期待合作只能写弱证据。不要判断搜索+推荐占比，只能把它列为人工复核项。",
                    "cooperationDirection": "80字以内，非评分依据；只说明后续详情完善或审核重点，不要用曝光/测评/转化角色影响分数",
                    "manualReviewItems": ["需要人工确认的事项，例如搜索+推荐占比、强人设真伪、特殊家庭背景等"],
                    "evidenceQuotes": ["最多3条证据摘要，引用笔记标题/内容要点，不要长引文"],
                    "confidence": "0-1，对当前结论的置信度；证据不足时必须低于0.7",
                    "promptVersion": "creator-score-v2-20260519",
                    "schemaVersion": "creator-score-structured-v2",
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
        "目标人群必须结合 promotionStrategy 判断当前项目的真实使用者、决策者和受众画像；真实流量核心看阅读中位数和互动中位数；成本效率核心看报价、阅读单价/CPC、互动单价/CPE。"
        "粉丝量只作为T级比较坐标，不是高权重得分项；报价不是越低越好，必须判断这笔预算能换来的阅读/互动总量。"
        "所有项目使用 baseScore 100、bonusScore 5、totalScore 100；加成只给人群、数据、效率、方向同时成立。"
        "缺蒲公英链接、缺字段、缺近期笔记正文属于证据/采集状态，不是达人质量问题，不得作为硬性淘汰或低分原因。"
        "只有已确认的报价超硬上限、同T级近30天数据明显低于基准、已确认异常/违规/限流，才能作为明确风险。"
        "类目、个人标签、期待合作行业只是弱方向证据；没有主页简介、详情页、笔记标题/正文时，不得直接判定高知/教师/大孩家长等强人设。"
        "必须先从项目名称、brief、promotionStrategy和scoringCriteria识别具体产品，再围绕产品定位、核心卖点、内容场景和转化路径判断内容适配，不要只按宽类目下结论。"
        "短板必须分析笔记内容主题和呈现方式，指出是否缺少产品使用过程、目标用户反馈、决策者视角、核心卖点承接或使用前后对比。"
        "搜索+推荐占比属于人工复核项，不得用模型猜测，不得把 search_recommend_review_status != 已复核 当成负向评分。"
        "必须执行封顶：缺当前 Brief 明确硬性画像证据、缺阅读/互动核心数据、成本效率差或内容方向弱相关，初筛不得进入强推荐；不得把某个历史项目的人群阈值套到所有项目。"
        "不要把达人是否适合曝光、测评、转化种草作为评分依据；达人质量好才值得推进，怎么推是后续执行策略。"
        "请输出 initialTier 和 detailCollectionPriority，用于决定哪些数据层级高或高潜达人进入详情页完善信息。"
        "不要把当前项目 Brief 写死成任何历史项目；不同项目必须按传入 Brief、promotionStrategy 和 scoringCriteria 适配。"
        "蒲公英 collectionSchemeSummary 只用于理解达人来源，不得把页面筛选条件直接当作最终评分结论。"
        "必须输出 confidence、manualReviewItems、evidenceQuotes、promptVersion、schemaVersion；证据不足时要明确降低 confidence。"
    )
    user_payload = _score_batch_payload(project_id, creators)
    result = chat_json(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"请只输出符合 requiredSchema 的 JSON，results 数量必须等于 creators 数量：\n{json.dumps(user_payload, ensure_ascii=False)}"},
        ],
        config={"model_role": "secondary"},
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
        normalized[creator_id] = _normalize_llm_score(item, score_values(creator, project_id=project_id), creator, project_id=project_id)
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
        last_error: Exception | None = None
        for _ in range(LLM_SCORE_RETRY_ATTEMPTS):
            try:
                with _scoring_batch_context():
                    return score_values_batch_with_llm(project_id, chunk)
            except Exception as error:
                last_error = error
        raise last_error or RuntimeError("模型评分失败")

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
    hard_defects = score.get("hard_defects") if isinstance(score.get("hard_defects"), list) else []
    warning_defects = score.get("warning_defects") if isinstance(score.get("warning_defects"), list) else []
    manual_review_items = _normalize_structured_list(score.get("manual_review_items") or score.get("manualReviewItems") or [])
    evidence_quotes = _normalize_structured_list(score.get("evidence_quotes") or score.get("evidenceQuotes") or [], limit=5)
    llm_confidence = parse_number(score.get("llm_confidence") or score.get("llmConfidence"))
    llm_prompt_version = str(score.get("llm_prompt_version") or score.get("promptVersion") or "")
    llm_schema_version = str(score.get("llm_schema_version") or score.get("schemaVersion") or "")
    target_content_evidence = score.get("target_content_evidence")
    product_scene_evidence = score.get("product_scene_evidence")
    conflict_content_categories = score.get("conflict_content_categories")
    risk_control_result = score.get("risk_control_result")
    if not isinstance(target_content_evidence, list):
        target_content_evidence = _normalize_structured_list(target_content_evidence or [])
    if not isinstance(product_scene_evidence, list):
        product_scene_evidence = _normalize_structured_list(product_scene_evidence or [])
    if not isinstance(conflict_content_categories, list):
        conflict_content_categories = _normalize_structured_list(conflict_content_categories or [])
    if not isinstance(risk_control_result, dict):
        risk_control_result = {}
    def write(handle: sqlite3.Connection) -> None:
        handle.execute(
            """
            INSERT INTO creator_scores(creator_id, total_score, rule_group_score, base_score, bonus_score, information_completeness,
            initial_tier, detail_collection_priority, budget_score, fans_score, cpe_score, traffic_score,
            persona_score, content_score, hard_filter_passed, recommend_level, score_reason, cooperation_direction,
            stage1_priority, stage1_reason, project_match_status, project_match_confidence, final_recommend_level,
            target_content_ratio, target_content_evidence, product_scene_ratio, product_scene_evidence,
            conflict_content_ratio, conflict_content_categories, risk_control_result, recommended_format,
            hard_defects, warning_defects, manual_review_items, evidence_quotes, llm_confidence, llm_prompt_version, llm_schema_version, scored_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(creator_id) DO UPDATE SET total_score=excluded.total_score,
            rule_group_score=excluded.rule_group_score,
            base_score=excluded.base_score, bonus_score=excluded.bonus_score,
            information_completeness=excluded.information_completeness,
            initial_tier=excluded.initial_tier, detail_collection_priority=excluded.detail_collection_priority,
            budget_score=excluded.budget_score,
            fans_score=excluded.fans_score, cpe_score=excluded.cpe_score, traffic_score=excluded.traffic_score,
            persona_score=excluded.persona_score, content_score=excluded.content_score,
            hard_filter_passed=excluded.hard_filter_passed, recommend_level=excluded.recommend_level,
            score_reason=excluded.score_reason, cooperation_direction=excluded.cooperation_direction,
            stage1_priority=excluded.stage1_priority, stage1_reason=excluded.stage1_reason,
            project_match_status=excluded.project_match_status, project_match_confidence=excluded.project_match_confidence,
            final_recommend_level=excluded.final_recommend_level,
            target_content_ratio=excluded.target_content_ratio, target_content_evidence=excluded.target_content_evidence,
            product_scene_ratio=excluded.product_scene_ratio, product_scene_evidence=excluded.product_scene_evidence,
            conflict_content_ratio=excluded.conflict_content_ratio, conflict_content_categories=excluded.conflict_content_categories,
            risk_control_result=excluded.risk_control_result, recommended_format=excluded.recommended_format,
            hard_defects=excluded.hard_defects, warning_defects=excluded.warning_defects,
            manual_review_items=excluded.manual_review_items, evidence_quotes=excluded.evidence_quotes,
            llm_confidence=excluded.llm_confidence, llm_prompt_version=excluded.llm_prompt_version,
            llm_schema_version=excluded.llm_schema_version, scored_at=excluded.scored_at
            """,
            (
                creator_id,
                score["total_score"],
                score.get("rule_group_score", score.get("total_score")),
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
                score.get("stage1_priority") or "",
                score.get("stage1_reason") or "",
                score.get("project_match_status") or "",
                parse_number(score.get("project_match_confidence")),
                score.get("final_recommend_level") or score.get("recommend_level") or "",
                parse_number(score.get("target_content_ratio")),
                json.dumps(target_content_evidence, ensure_ascii=False),
                parse_number(score.get("product_scene_ratio")),
                json.dumps(product_scene_evidence, ensure_ascii=False),
                parse_number(score.get("conflict_content_ratio")),
                json.dumps(conflict_content_categories, ensure_ascii=False),
                json.dumps(risk_control_result, ensure_ascii=False),
                score.get("recommended_format") or "",
                json.dumps(hard_defects, ensure_ascii=False),
                json.dumps(warning_defects, ensure_ascii=False),
                json.dumps(manual_review_items, ensure_ascii=False),
                json.dumps(evidence_quotes, ensure_ascii=False),
                llm_confidence,
                llm_prompt_version,
                llm_schema_version,
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
        scored = {**dict(creator), **score, "cooperation_direction": cooperation_direction}
    scored["score_source"] = source
    scored["batch_id"] = batch_id
    scored["total_score"] = score.get("total_score")
    return scored


def _persist_creator_scores_bulk(
    project_id: str,
    scored_items: list[tuple[dict[str, Any], dict[str, Any], str]],
    batch_id: str,
    trigger_source: str,
    conn: sqlite3.Connection,
) -> None:
    for creator, score, source in scored_items:
        _persist_creator_score(
            project_id,
            creator,
            score,
            source,
            batch_id,
            trigger_source,
            fetch_scored=False,
            conn=conn,
        )


def score_creator(
    project_id: str,
    creator_id: str,
    use_llm: bool = False,
    batch_id: str | None = None,
    trigger_source: str = "single",
    fallback_on_llm_error: bool = True,
) -> dict[str, Any]:
    creator = _get_creator_for_scoring(project_id, creator_id)
    if not creator:
        raise KeyError(creator_id)
    source = "generated"
    with _scoring_batch_context():
        try:
            score, source = score_values_with_llm(project_id, creator) if use_llm else (generate_test_stage_score(project_id, creator, check_hard_issues=False)[0], "rule")
        except Exception:
            if use_llm and not fallback_on_llm_error:
                raise
            score, source = generate_test_stage_score(project_id, creator, check_hard_issues=False)
        _attach_system_defects(project_id, [(creator, score, source)])
    return _persist_creator_score(
        project_id,
        creator,
        score,
        source,
        batch_id or str(uuid.uuid4()),
        trigger_source,
        fetch_scored=False,
    )


def score_project(
    project_id: str,
    use_llm: bool = False,
    creator_ids: list[str] | None = None,
    trigger_source: str = "manual",
    fallback_on_llm_error: bool = True,
) -> dict[str, Any]:
    wanted_ids = list(dict.fromkeys(str(creator_id) for creator_id in (creator_ids or []) if str(creator_id or "").strip()))
    creators = _list_creators_for_scoring(project_id, wanted_ids or None)
    batch_id = str(uuid.uuid4())
    sources = {"llm": 0, "generated": 0, "rule": 0}
    llm_errors: list[str] = []
    llm_chunk_results: list[dict[str, Any]] = []
    defect_summary = {"hard_defects": 0, "warning_defects": 0, "creators_with_hard_defects": 0}
    chunks = _chunk_creators_for_llm(project_id, creators) if use_llm and creators else []
    if chunks:
        llm_chunk_results = _score_llm_chunks_parallel(project_id, chunks)
        failed_chunks = [result for result in llm_chunk_results if not result.get("ok")]
        if failed_chunks and not fallback_on_llm_error:
            failed_creator_ids = [
                str(creator.get("creator_id"))
                for result in failed_chunks
                for creator in (result.get("chunk") or [])
            ]
            error_samples = [str(result.get("error"))[:180] for result in failed_chunks[:3]]
            raise RuntimeError(
                f"大模型评分失败 {len(failed_creator_ids)}/{len(creators)} 位，请检查模型配置或网络；"
                f"失败达人：{', '.join(failed_creator_ids[:10])}；错误：{' | '.join(error_samples)}"
            )
    def write_scores() -> None:
        sources.clear()
        sources.update({"llm": 0, "generated": 0, "rule": 0})
        llm_errors.clear()
        defect_summary.update({"hard_defects": 0, "warning_defects": 0, "creators_with_hard_defects": 0})
        benchmarks = _batch_defect_benchmarks(creators)

        def persist_scored_items(conn: sqlite3.Connection, scored_items: list[tuple[dict[str, Any], dict[str, Any], str]]) -> None:
            hard_count, warning_count = _attach_system_defects(project_id, scored_items, benchmarks)
            defect_summary["hard_defects"] += hard_count
            defect_summary["warning_defects"] += warning_count
            defect_summary["creators_with_hard_defects"] += sum(1 for _, score, _ in scored_items if score.get("hard_defects"))
            _persist_creator_scores_bulk(project_id, scored_items, batch_id, trigger_source, conn)
            for _, _, source in scored_items:
                sources[source] = sources.get(source, 0) + 1

        with _scoring_batch_context(), connect() as conn:
            if use_llm and creators:
                for chunk_result in llm_chunk_results:
                    chunk = chunk_result["chunk"]
                    if chunk_result.get("ok"):
                        batch_scores = chunk_result["scores"]
                        scored_items = [(creator, batch_scores[str(creator["creator_id"])], "llm") for creator in chunk]
                        persist_scored_items(conn, scored_items)
                    else:
                        error = chunk_result.get("error")
                        llm_errors.append(str(error)[:300])
                        scored_items = [(creator, *generate_test_stage_score(project_id, creator, check_hard_issues=False)) for creator in chunk]
                        persist_scored_items(conn, scored_items)
            else:
                scored_items = [(creator, generate_test_stage_score(project_id, creator, check_hard_issues=False)[0], "rule") for creator in creators]
                persist_scored_items(conn, scored_items)

    _run_sqlite_locked_retry(write_scores)
    if sources.get("llm"):
        detail = f"批次 {batch_id} 完成 {len(creators)} 位达人评分，其中 {sources['llm']} 位由大模型分析生成"
        status = "success"
    elif sources.get("generated"):
        detail = f"批次 {batch_id} 完成 {len(creators)} 位达人评分，测试阶段已直接生成筛选结果；API 接入入口保留可测"
        status = "success"
    else:
        detail = f"批次 {batch_id} 完成 {len(creators)} 位达人评分，当前使用规则评分；请配置大模型 API 后重新评分"
        status = "warning"

    def write_score_log() -> None:
        with connect() as conn:
            log(conn, project_id, "score", "执行评分", PROJECT_NAME, "AI", detail, status)

    _run_sqlite_locked_retry(write_score_log)
    return {
        "batch_id": batch_id,
        "scored": len(creators),
        "source": "llm" if sources.get("llm") else ("generated" if sources.get("generated") else "rule"),
        "sources": sources,
        "defects": defect_summary,
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


def list_batches(project_id: str, status: str | None = None, limit: int | None = None) -> list[dict[str, Any]]:
    init_db()
    with connect() as conn:
        where = ["project_id=?"]
        params: list[Any] = [project_id]
        if status:
            where.append("status=?")
            params.append(status)
        sql = f"SELECT * FROM collection_batches WHERE {' AND '.join(where)} ORDER BY started_at DESC"
        if limit is not None:
            sql += " LIMIT ?"
            params.append(max(1, int(limit)))
        rows = conn.execute(sql, params).fetchall()
        return [_batch_dict(row) for row in rows]


def get_batch(batch_id: str) -> dict[str, Any]:
    init_db()
    with connect() as conn:
        row = conn.execute("SELECT * FROM collection_batches WHERE batch_id=?", (batch_id,)).fetchone()
    return _batch_dict(row)


def create_batch(project_id: str, source_url: str, status: str = "running") -> str:
    batch_id = str(uuid.uuid4())
    with connect() as conn:
        conn.execute(
            "INSERT INTO collection_batches(batch_id, project_id, source_url, status, started_at) VALUES (?, ?, ?, ?, ?)",
            (batch_id, project_id, source_url, status, now()),
        )
    return batch_id


def close_stale_running_batches(message: str) -> int:
    init_db()
    with connect() as conn:
        rows = conn.execute("SELECT * FROM collection_batches WHERE status='running'").fetchall()
        for row in rows:
            batch = _batch_dict(row)
            conn.execute(
                """
                UPDATE collection_batches
                SET status='stopped', finished_at=?, error_message=?, progress_stage='stopped', progress_message=?
                WHERE batch_id=?
                """,
                (now(), message, message, batch["batch_id"]),
            )
    return len(rows)


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
    profile_url = str(c.get("profile_url") or "").strip()
    if profile_url and "pgy.xiaohongshu.com" not in profile_url:
        return profile_url
    pgy_blogger_id = str(c.get("pgy_blogger_id") or "").strip()
    if not pgy_blogger_id:
        match = re.search(r"/blogger-detail/([^?/#]+)", str(c.get("pgy_url") or ""))
        if match:
            pgy_blogger_id = match.group(1)
    if pgy_blogger_id:
        return f"https://www.xiaohongshu.com/user/profile/{pgy_blogger_id}"
    xhs_id = str(c.get("xiaohongshu_id") or "").strip()
    if xhs_id and not xhs_id.isdigit():
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


def _compact_reason_parts(parts: list[str], limit: int = 360) -> str:
    text = "；".join(dict.fromkeys([str(part).strip("；; ") for part in parts if str(part).strip("；; ")]))
    return text[:limit]


def _creator_project_promotion_reason(project_id: str, c: dict[str, Any]) -> str:
    project_fit = _project_fit_config(project_id)
    profile = _project_fit_signal_profile(c, project_fit) if project_fit else {}
    parts: list[str] = []
    scene_hits = profile.get("scene_hits") or []
    style_hits = profile.get("style_hits") or []
    audience_hits = list(dict.fromkeys([*(profile.get("grade_hits") or []), *(profile.get("parent_hits") or [])]))

    if scene_hits:
        parts.append(f"内容场景契合项目推广：命中{'、'.join(scene_hits[:3])}")
    if style_hits:
        parts.append(f"表达方式适配：{'、'.join(style_hits[:2])}")
    if audience_hits:
        parts.append(f"目标人群/决策链路相关：{'、'.join(audience_hits[:3])}")

    topic = str(c.get("topic_point") or "").strip()
    if topic and not scene_hits:
        parts.append(f"内容话题可承接推广：{topic[:80]}")
    direction = str(c.get("cooperation_direction") or c.get("portfolio_role") or "").strip()
    if direction:
        parts.append(f"建议合作方向：{direction[:80]}")

    score = c.get("total_score")
    level = str(c.get("recommend_level") or "").strip()
    if score or level:
        parts.append(f"推荐结论：{level or '候选'}{f'，评分{score}' if score else ''}")

    if not parts:
        tags = "、".join([item for item in _split_semantic_tags(c.get("persona_tags"))[:3] if item])
        if tags:
            parts.append(f"达人标签与项目推广方向存在可验证交集：{tags}")
        else:
            parts.append("达人基础数据进入候选池，需结合详情页内容证据复核具体推广契合点")
    return _compact_reason_parts(parts)


def _feishu_recommendation_reason(project_id: str, c: dict[str, Any]) -> str:
    score_reason = str(c.get("score_reason") or "").strip()
    promotion_reason = _creator_project_promotion_reason(project_id, c)
    if score_reason and promotion_reason:
        return f"{score_reason}\n推荐理由：{promotion_reason}"[:760]
    return (score_reason or f"推荐理由：{promotion_reason}")[:760]


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
            "图文报价": image_quote,
            "图文笔记一口价": image_quote,
            "平台报价": image_quote,
            "报价": image_quote,
            "视频报备价": video_quote,
            "视频报备裸价": video_quote,
            "视频报价": video_quote,
            "视频笔记一口价": video_quote,
            "图文执行价\n（含平台服务费）": _price_with_service(image_quote),
            "图文执行价（含平台服务费）": _price_with_service(image_quote),
            "视频执行价\n（含平台服务费）": _price_with_service(video_quote),
            "视频执行价（含平台服务费）": _price_with_service(video_quote),
            "合作价格（含服务费）": _price_with_service(image_quote) or image_quote,
            "视频完播率": _percent(c.get("video_completion_rate")),
            "活跃粉丝占比": _percent(c.get("active_fans_ratio")),
            "预估cpe": c.get("effective_cpe") or c.get("image_interaction_unit_price") or c.get("natural_cpe") or "",
            "预估CPE": c.get("effective_cpe") or c.get("image_interaction_unit_price") or c.get("natural_cpe") or "",
            "预估cpm": c.get("image_cpm") or c.get("video_cpm") or "",
            "预估CPM": c.get("image_cpm") or c.get("video_cpm") or "",
            "阅读单价": c.get("effective_cpc") or c.get("natural_cpc") or c.get("image_read_unit_price") or c.get("video_read_unit_price") or "",
            "互动单价": c.get("effective_cpe") or c.get("natural_cpe") or c.get("image_interaction_unit_price") or c.get("video_interaction_unit_price") or "",
            "CPE": c.get("effective_cpe") or c.get("natural_cpe") or c.get("image_interaction_unit_price") or "",
            "cpe（不超过20，最好10以下）": c.get("effective_cpe") or c.get("natural_cpe") or c.get("image_interaction_unit_price") or "",
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
        recommendation_reason = _feishu_recommendation_reason(project_id, c)
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
                "阅读单价": c.get("effective_cpc") or "",
                "互动单价": c.get("effective_cpe") or "",
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
                "搜索推荐复核状态": c.get("search_recommend_review_status") or "",
                "搜索推荐复核备注": c.get("search_recommend_review_note") or "",
                "35岁以上粉丝占比": c.get("fans_35_plus_ratio") or "",
                "孩子年龄": c.get("child_age") or "",
                "孩子年级": c.get("child_grade") or "",
                "孩子年级置信度": c.get("child_grade_confidence") or "",
                "孩子年级证据": c.get("child_grade_evidence") or "",
                "孩子性别": c.get("child_gender") or "",
                "家庭/教育话题点": c.get("topic_point") or "",
                "内容场景标签": c.get("content_scene_tags") or "",
                "内容场景证据": c.get("content_scene_evidence") or "",
                "呈现方式标签": c.get("presentation_style_tags") or "",
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
                "推荐理由": recommendation_reason,
                "推荐理由/项目契合点": recommendation_reason,
                "项目推广契合点": _creator_project_promotion_reason(project_id, c),
                "达人契合该项目推广的地方": _creator_project_promotion_reason(project_id, c),
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
        recommendation_reason = _feishu_recommendation_reason(project_id, c)
        promotion_reason = _creator_project_promotion_reason(project_id, c)
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
                "cpe（不超过20，最好10以下）": c.get("effective_cpe") or c.get("natural_cpe") or "",
                "推荐理由": recommendation_reason,
                "推荐理由/项目契合点": recommendation_reason,
                "项目推广契合点": promotion_reason,
                "达人契合该项目推广的地方": promotion_reason,
                "基础分": c.get("base_score") or "",
                "加成分": c.get("bonus_score") or "",
                "初筛总分": c.get("total_score") or "",
                "信息完整度": c.get("information_completeness") or "",
                "初筛等级": c.get("initial_tier") or c.get("tier") or "",
                "详情完善优先级": c.get("detail_collection_priority") or "",
                "合作方向": c.get("cooperation_direction") or c.get("portfolio_role") or "",
                "平台报价": c.get("quote_price") or "",
                "图文报价": c.get("quote_price") or "",
                "图文笔记一口价": c.get("quote_price") or "",
                "视频报价": c.get("video_quote_price") or "",
                "视频笔记一口价": c.get("video_quote_price") or "",
                "合作价格（含服务费）": _price_with_service(c.get("quote_price")) or c.get("quote_price") or "",
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
