"""Wiring checks for configuration and the provider seam. No network, no LLM, no audio."""

from fastapi.testclient import TestClient

from server import providers
from server.config import Config
from server.main import app

client = TestClient(app)


def test_health_reports_providers():
    body = client.get("/api/health").json()
    assert body["status"] in {"ok", "needs-config"}
    assert body["providers"]["llm"].startswith("openai:")
    assert body["providers"]["turn_detection"] in {"smart", "vad"}


def test_health_never_leaks_key_material():
    raw = client.get("/api/health").text
    for secret in ("sk-", "DAILY_API_KEY=", "api_key"):
        assert secret not in raw


def test_missing_keys_lists_only_selected_providers():
    cfg = Config(
        llm_provider="openai",
        stt_provider="openai",
        tts_provider="openai",
        daily_api_key="x",
        openai_api_key="",
        deepgram_api_key="",
        cartesia_api_key="",
    )
    # Deepgram and Cartesia are not selected, so their absence is not a problem.
    assert cfg.missing_keys() == ["OPENAI_API_KEY"]


def test_describe_is_key_free():
    assert set(providers.describe()) == {"llm", "stt", "tts", "turn_detection"}
