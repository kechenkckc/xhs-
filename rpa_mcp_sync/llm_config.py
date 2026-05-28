from __future__ import annotations

import os
import json
import re
from pathlib import Path
from typing import Any

import requests
import yaml

from .config_store import AI_PROVIDER_PATH

DEFAULT_CONFIG = {
    "protocol": "openai-compatible",
    "base_url": "https://api.openai.com/v1",
    "model": "gpt-4.1-mini",
    "api_key_env": "OPENAI_API_KEY",
    "temperature": 0.2,
    "max_tokens": None,
    "timeout_seconds": 180,
}

PROFILE_KEYS = (
    "protocol",
    "base_url",
    "model",
    "api_key_env",
    "temperature",
    "max_tokens",
    "timeout_seconds",
)
PRIVATE_PROFILE_KEYS = (*PROFILE_KEYS, "api_key")
MAIN_MODEL_KEY = "main_model"
SECONDARY_MODEL_KEY = "secondary_model"


def normalize_base_url(value: Any, protocol: str = "openai-compatible") -> str:
    text = str(value or "").strip()
    if not text:
        text = DEFAULT_CONFIG["base_url"]
    text = re.sub(r"^(https?://)+", lambda match: match.group(0).split("://", 1)[0] + "://", text, flags=re.I)
    if not re.match(r"^https?://", text, flags=re.I):
        text = f"https://{text}"
    return text.rstrip("/")


def _read_raw_config(path: Path = AI_PROVIDER_PATH) -> dict[str, Any]:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _profile_payload(raw: dict[str, Any], key: str) -> dict[str, Any]:
    profile = raw.get(key)
    return profile if isinstance(profile, dict) else {}


def _legacy_payload(raw: dict[str, Any]) -> dict[str, Any]:
    return {key: raw[key] for key in PRIVATE_PROFILE_KEYS if key in raw}


def _normalize_profile(raw: dict[str, Any] | None = None, fallback: dict[str, Any] | None = None) -> dict[str, Any]:
    config = {**DEFAULT_CONFIG, **(fallback or {})}
    for key in PRIVATE_PROFILE_KEYS:
        if raw and key in raw:
            config[key] = raw[key]
    config["base_url"] = normalize_base_url(config.get("base_url"), str(config.get("protocol") or DEFAULT_CONFIG["protocol"]))
    return config


def _private_ai_profiles(path: Path = AI_PROVIDER_PATH) -> dict[str, dict[str, Any]]:
    raw = _read_raw_config(path)
    legacy = _legacy_payload(raw)
    main = _normalize_profile({**legacy, **_profile_payload(raw, MAIN_MODEL_KEY)})
    secondary = _normalize_profile(_profile_payload(raw, SECONDARY_MODEL_KEY), fallback=main)
    return {MAIN_MODEL_KEY: main, SECONDARY_MODEL_KEY: secondary}


def _public_profile(config: dict[str, Any], path: Path, role: str) -> dict[str, Any]:
    inline_key = bool(config.get("api_key"))
    env_key = bool(config.get("api_key_env") and os.getenv(config["api_key_env"]))
    public = {k: v for k, v in config.items() if k != "api_key"}
    public.update(
        {
            "role": role,
            "path": str(path),
            "api_key_configured": inline_key or env_key,
            "api_key_source": "inline" if inline_key else ("env" if env_key else "none"),
            "using_example_config": False,
        }
    )
    return public


def _role_key(role: str | None) -> str:
    text = str(role or MAIN_MODEL_KEY).strip().lower()
    if text in {"secondary", "secondary_model", "scoring", "score", "batch"}:
        return SECONDARY_MODEL_KEY
    return MAIN_MODEL_KEY


def read_ai_config(path: Path = AI_PROVIDER_PATH, role: str | None = None) -> dict[str, Any]:
    profiles = _private_ai_profiles(path)
    if role:
        role_key = _role_key(role)
        return _public_profile(profiles[role_key], path, role_key)
    main_public = _public_profile(profiles[MAIN_MODEL_KEY], path, MAIN_MODEL_KEY)
    secondary_public = _public_profile(profiles[SECONDARY_MODEL_KEY], path, SECONDARY_MODEL_KEY)
    public = dict(main_public)
    public[MAIN_MODEL_KEY] = main_public
    public[SECONDARY_MODEL_KEY] = secondary_public
    public["routing"] = {
        "heavy_tasks": MAIN_MODEL_KEY,
        "brief_parsing": MAIN_MODEL_KEY,
        "field_mapping": MAIN_MODEL_KEY,
        "creator_scoring": SECONDARY_MODEL_KEY,
        "batch_repeated_tasks": SECONDARY_MODEL_KEY,
    }
    return public


def _merge_profile(existing: dict[str, Any], payload: dict[str, Any], keep_existing_api_key: bool) -> dict[str, Any]:
    config = dict(existing)
    for key in PROFILE_KEYS:
        if key in payload:
            config[key] = payload[key]
    if payload.get("api_key"):
        config["api_key"] = payload["api_key"]
    elif not keep_existing_api_key:
        config.pop("api_key", None)
    return _normalize_profile(config)


def _profile_for_write(config: dict[str, Any]) -> dict[str, Any]:
    return {key: config.get(key) for key in PRIVATE_PROFILE_KEYS if config.get(key) is not None}


def write_ai_config(payload: dict[str, Any], path: Path = AI_PROVIDER_PATH) -> dict[str, Any]:
    existing = _private_ai_profiles(path)
    keep_existing_api_key = bool(payload.get("keep_existing_api_key", True))

    if isinstance(payload.get(MAIN_MODEL_KEY), dict) or isinstance(payload.get(SECONDARY_MODEL_KEY), dict):
        main_payload = payload.get(MAIN_MODEL_KEY) if isinstance(payload.get(MAIN_MODEL_KEY), dict) else {}
        secondary_payload = payload.get(SECONDARY_MODEL_KEY) if isinstance(payload.get(SECONDARY_MODEL_KEY), dict) else {}
    else:
        main_payload = payload
        secondary_payload = {}

    main = _merge_profile(existing[MAIN_MODEL_KEY], main_payload, keep_existing_api_key)
    secondary = _merge_profile(existing[SECONDARY_MODEL_KEY], secondary_payload, keep_existing_api_key)
    config = {
        **_profile_for_write(main),
        MAIN_MODEL_KEY: _profile_for_write(main),
        SECONDARY_MODEL_KEY: _profile_for_write(secondary),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return read_ai_config(path)


def test_ai_config(payload: dict[str, Any]) -> dict[str, Any]:
    payload = dict(payload or {})
    model_role = payload.pop("model_role", payload.pop("role", MAIN_MODEL_KEY))
    payload.pop(MAIN_MODEL_KEY, None)
    payload.pop(SECONDARY_MODEL_KEY, None)
    saved_config = _private_ai_config(role=model_role)
    config = {**saved_config, **payload}
    config["base_url"] = normalize_base_url(config.get("base_url"), str(config.get("protocol") or DEFAULT_CONFIG["protocol"]))
    if not payload.get("api_key") and saved_config.get("api_key"):
        config["api_key"] = saved_config["api_key"]
    api_key = config.get("api_key") or os.getenv(config.get("api_key_env") or "")
    if not api_key:
        return {"ok": False, "error": "未配置 API Key 或环境变量"}
    base_url = str(config["base_url"]).rstrip("/")
    timeout = int(config.get("timeout_seconds") or 180)
    if config.get("protocol") == "gemini":
        url = f"{base_url}/models?key={api_key}"
        response = requests.get(url, timeout=timeout)
    else:
        url = f"{base_url}/models"
        response = requests.get(url, headers={"Authorization": f"Bearer {api_key}"}, timeout=timeout)
    if response.status_code >= 400:
        return {"ok": False, "error": f"模型服务返回 HTTP {response.status_code}: {response.text[:300]}", "url": url}
    try:
        response.json()
    except ValueError:
        return {"ok": False, "error": f"模型服务未返回 JSON: {response.text[:300]}", "url": url}
    return {"ok": True, "message": "API 连接测试成功", "url": url}


def _private_ai_config(path: Path = AI_PROVIDER_PATH, role: str | None = None) -> dict[str, Any]:
    profiles = _private_ai_profiles(path)
    return profiles[_role_key(role)]


def _extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.S)
        if not match:
            raise
        return json.loads(match.group(0))


def chat_json(messages: list[dict[str, str]], config: dict[str, Any] | None = None) -> dict[str, Any]:
    overrides = dict(config or {})
    model_role = overrides.pop("model_role", overrides.pop("role", MAIN_MODEL_KEY))
    config = {**_private_ai_config(role=model_role), **overrides}
    config["base_url"] = normalize_base_url(config.get("base_url"), str(config.get("protocol") or DEFAULT_CONFIG["protocol"]))
    api_key = config.get("api_key") or os.getenv(config.get("api_key_env") or "")
    if not api_key:
        raise RuntimeError("未配置 API Key 或环境变量，无法调用大模型")
    base_url = str(config["base_url"]).rstrip("/")
    timeout = int(config.get("timeout_seconds") or 180)
    max_tokens = config.get("max_tokens") or 4096
    temperature = float(config.get("temperature") if config.get("temperature") is not None else 0.2)

    if config.get("protocol") == "gemini":
        prompt = "\n\n".join(f"{item.get('role', 'user')}: {item.get('content', '')}" for item in messages)
        url = f"{base_url}/models/{config['model']}:generateContent?key={api_key}"
        response = requests.post(
            url,
            json={
                "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": temperature, "maxOutputTokens": max_tokens},
            },
            timeout=timeout,
        )
        if response.status_code >= 400:
            raise RuntimeError(f"模型服务返回 HTTP {response.status_code}: {response.text[:300]}")
        data = response.json()
        text = data["candidates"][0]["content"]["parts"][0]["text"]
    else:
        url = f"{base_url}/chat/completions"
        response = requests.post(
            url,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": config["model"],
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "response_format": {"type": "json_object"},
            },
            timeout=timeout,
        )
        if response.status_code >= 400:
            raise RuntimeError(f"模型服务返回 HTTP {response.status_code}: {response.text[:300]}")
        text = response.json()["choices"][0]["message"]["content"]
    return _extract_json(text)
