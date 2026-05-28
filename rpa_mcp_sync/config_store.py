from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = ROOT / "config"
PROJECT_CONFIG_DIR = CONFIG_DIR / "projects"
AI_PROVIDER_PATH = CONFIG_DIR / "ai_provider.yaml"


def ensure_dirs() -> None:
    PROJECT_CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def feishu_connection_path(project_id: str) -> Path:
    safe_id = "".join(ch for ch in project_id if ch.isalnum() or ch in "_-")
    return PROJECT_CONFIG_DIR / f"{safe_id}.feishu.connection.json"


def project_scoring_config_path(project_id: str) -> Path:
    safe_id = "".join(ch for ch in project_id if ch.isalnum() or ch in "_-")
    return PROJECT_CONFIG_DIR / f"{safe_id}.scoring.config.json"


def public_feishu_config(config: dict[str, Any]) -> dict[str, Any]:
    result = dict(config)
    result.pop("app_secret", None)
    result.pop("field_mapping_cache", None)
    result["app_secret_configured"] = bool(config.get("app_secret"))
    return result
