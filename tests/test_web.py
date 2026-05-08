from fastapi.testclient import TestClient

from rpa_mcp_sync.config_store import AI_PROVIDER_PATH, feishu_connection_path
from rpa_mcp_sync.web import app


client = TestClient(app)


def test_overview_hides_connection_files():
    response = client.get("/api/overview")
    assert response.status_code == 200
    projects = response.json()["projects"]
    assert projects[0]["project_id"] == "youdao_001"
    assert "feishu.connection" not in str(projects)


def test_save_feishu_connection_masks_secret(tmp_path, monkeypatch):
    project_id = "pytest_mask"
    path = feishu_connection_path(project_id)
    if path.exists():
        path.unlink()
    response = client.post(
        "/api/projects/feishu/connection",
        json={
            "project_id": project_id,
            "feishu_url": "https://example.feishu.cn/wiki/wikiToken123?sheet=sheet123",
            "app_id": "cli_test",
            "app_secret": "secret",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["config"]["app_secret_configured"] is True
    assert "app_secret" not in payload["config"]
    if path.exists():
        path.unlink()


def test_llm_config_roundtrip():
    original = AI_PROVIDER_PATH.read_text(encoding="utf-8") if AI_PROVIDER_PATH.exists() else None
    response = client.post(
        "/api/llm/config",
        json={
            "protocol": "gemini",
            "base_url": "https://generativelanguage.googleapis.com/v1beta",
            "model": "gemini-2.5-flash",
            "api_key_env": "GEMINI_API_KEY",
            "temperature": 0.1,
            "max_tokens": 1000,
            "timeout_seconds": 30,
        },
    )
    assert response.status_code == 200
    assert response.json()["config"]["protocol"] == "gemini"
    if original is None:
        if AI_PROVIDER_PATH.exists():
            AI_PROVIDER_PATH.unlink()
    else:
        AI_PROVIDER_PATH.write_text(original, encoding="utf-8")


def test_optimize_screening_standard_falls_back_without_key():
    original = AI_PROVIDER_PATH.read_text(encoding="utf-8") if AI_PROVIDER_PATH.exists() else None
    if AI_PROVIDER_PATH.exists():
        AI_PROVIDER_PATH.unlink()
    response = client.post(
        "/api/projects/youdao_001/screening-standard/optimize",
        json={
            "brief": "需要教育母婴达人，单个达人报价不超过2万元，35岁以上宝妈粉丝占比高，必须有蒲公英链接。",
            "feishu_fields": [
                {"field_name": "达人昵称"},
                {"field_name": "平台报价"},
                {"field_name": "35岁以上粉丝占比"},
                {"field_name": "蒲公英链接"},
            ],
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "fallback"
    assert payload["screeningPlan"]["scoringWeights"]["budget"] == 20
    assert payload["screeningPlan"]["hardFilters"][0]["feishuField"] == "35岁以上粉丝占比"
    if original is None:
        if AI_PROVIDER_PATH.exists():
            AI_PROVIDER_PATH.unlink()
    else:
        AI_PROVIDER_PATH.write_text(original, encoding="utf-8")
