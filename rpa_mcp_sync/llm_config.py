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
    "timeout_seconds": None,
}


def read_ai_config(path: Path = AI_PROVIDER_PATH) -> dict[str, Any]:
    if not path.exists():
        return {**DEFAULT_CONFIG, "path": str(path), "api_key_configured": False, "api_key_source": "none"}
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    config = {**DEFAULT_CONFIG, **payload}
    inline_key = bool(config.get("api_key"))
    env_key = bool(config.get("api_key_env") and os.getenv(config["api_key_env"]))
    public = {k: v for k, v in config.items() if k != "api_key"}
    public.update(
        {
            "path": str(path),
            "api_key_configured": inline_key or env_key,
            "api_key_source": "inline" if inline_key else ("env" if env_key else "none"),
            "using_example_config": False,
        }
    )
    return public


def write_ai_config(payload: dict[str, Any], path: Path = AI_PROVIDER_PATH) -> dict[str, Any]:
    existing_raw = yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else {}
    existing = existing_raw or {}
    config = {**DEFAULT_CONFIG, **existing}
    for key in ("protocol", "base_url", "model", "api_key_env", "temperature", "max_tokens", "timeout_seconds"):
        if key in payload:
            config[key] = payload[key]
    if payload.get("api_key"):
        config["api_key"] = payload["api_key"]
    elif not payload.get("keep_existing_api_key"):
        config.pop("api_key", None)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return read_ai_config(path)


def test_ai_config(payload: dict[str, Any]) -> dict[str, Any]:
    config = {**DEFAULT_CONFIG, **payload}
    api_key = config.get("api_key") or os.getenv(config.get("api_key_env") or "")
    if not api_key:
        return {"ok": False, "error": "未配置 API Key 或环境变量"}
    base_url = str(config["base_url"]).rstrip("/")
    timeout = int(config.get("timeout_seconds") or 60)
    if config.get("protocol") == "gemini":
        url = f"{base_url}/models?key={api_key}"
        response = requests.get(url, timeout=timeout)
    else:
        url = f"{base_url}/models"
        response = requests.get(url, headers={"Authorization": f"Bearer {api_key}"}, timeout=timeout)
    if response.status_code >= 400:
        return {"ok": False, "error": f"模型服务返回 HTTP {response.status_code}"}
    return {"ok": True, "message": "API 连接测试成功"}


def _private_ai_config(path: Path = AI_PROVIDER_PATH) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else {}
    return {**DEFAULT_CONFIG, **(payload or {})}


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
    config = {**_private_ai_config(), **(config or {})}
    api_key = config.get("api_key") or os.getenv(config.get("api_key_env") or "")
    if not api_key:
        raise RuntimeError("未配置 API Key 或环境变量，无法调用大模型")
    base_url = str(config["base_url"]).rstrip("/")
    timeout = int(config.get("timeout_seconds") or 90)
    max_tokens = config.get("max_tokens") or 1800
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
