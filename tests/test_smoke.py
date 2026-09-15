"""Wiring checks for configuration and the provider seam. No network, no LLM, no audio."""

import pytest
from fastapi.testclient import TestClient

from server import main, providers
from server.config import Config
from server.main import app

client = TestClient(app)


def test_health_reports_providers():
    body = client.get("/api/health").json()
    assert body["status"] in {"ok", "needs-config"}
    # Whichever model is selected locally; the point is that it is reported.
    assert ":" in body["providers"]["llm"]
    assert body["providers"]["turn_detection"] in {"smart", "vad"}


def test_health_never_leaks_key_material():
    raw = client.get("/api/health").text
    for secret in ("sk-", "AIza", "DAILY_API_KEY=", "api_key"):
        assert secret not in raw


def test_describe_is_key_free():
    described = providers.describe()
    assert {"llm", "stt", "tts", "turn_detection"} <= set(described)
    assert not any("key" in name for name in described)


@pytest.mark.parametrize(
    ("provider", "model"),
    [("openai", "gpt-5-mini"), ("google", "gemini-3.8-flash")],
)
def test_the_model_defaults_to_one_the_selected_provider_actually_serves(provider, model):
    # Selecting Google and forgetting the model must not send an OpenAI model
    # name to Gemini: that fails at the first turn, a long way from the mistake.
    assert Config(llm_provider=provider, llm_model="").llm_model == model


def test_an_explicit_model_is_left_alone():
    cfg = Config(llm_provider="google", llm_model="gemini-3.5-flash-lite")
    assert cfg.llm_model == "gemini-3.5-flash-lite"


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


def test_deepgram_tts_alone_still_needs_the_deepgram_key():
    """Deepgram serves both speech seams, so either one alone requires the key.

    Asking only about STT reported a healthy configuration for a call that then
    had no voice at all — the pipeline blocks connecting a TTS service it has no
    key for, and the worker gives up eighteen seconds later.
    """
    cfg = Config(
        llm_provider="openai",
        stt_provider="openai",
        tts_provider="deepgram",
        daily_api_key="x",
        openai_api_key="x",
        deepgram_api_key="",
        cartesia_api_key="",
    )
    assert cfg.missing_keys() == ["DEEPGRAM_API_KEY"]


def test_a_plausible_wrong_provider_name_is_caught_before_a_call():
    """`gemini` is the product's name; `google` is the one the factory branches on.

    This reached a real caller as a traceback from `make_llm`, eighteen seconds
    after they had joined the room. It is a configuration error, so it is
    reported the way a missing key is: at startup, in `/api/health`, and as a
    503 from `/api/connect` before any room is minted.
    """
    cfg = Config(llm_provider="gemini", daily_api_key="x", google_api_key="x")
    assert cfg.unknown_providers() == ["LLM_PROVIDER='gemini' is not one of: openai, google"]


def test_every_default_provider_is_one_the_factories_know():
    assert Config(daily_api_key="x").unknown_providers() == []


def test_deepgram_tts_does_not_ask_for_cartesia():
    cfg = Config(
        llm_provider="openai",
        stt_provider="deepgram",
        tts_provider="deepgram",
        daily_api_key="x",
        openai_api_key="x",
        deepgram_api_key="x",
        cartesia_api_key="",
    )
    assert cfg.missing_keys() == []


def test_choosing_gemini_asks_for_the_google_key_instead():
    cfg = Config(
        llm_provider="google",
        stt_provider="deepgram",
        tts_provider="cartesia",
        daily_api_key="x",
        google_api_key="",
        deepgram_api_key="d",
        cartesia_api_key="c",
    )
    assert cfg.missing_keys() == ["GOOGLE_API_KEY"]


def test_a_gemini_conversation_transcribed_by_openai_needs_both_keys():
    # The model is only one of three seams that can point at OpenAI, and asking
    # about the model alone used to miss this combination entirely.
    cfg = Config(
        llm_provider="google",
        stt_provider="openai",
        tts_provider="cartesia",
        daily_api_key="x",
        google_api_key="",
        openai_api_key="",
        cartesia_api_key="c",
    )
    assert cfg.missing_keys() == ["GOOGLE_API_KEY", "OPENAI_API_KEY"]


def test_each_provider_builds_the_service_it_names(monkeypatch):
    # Construction only; no request is made, so this needs no key that works.
    from pipecat.services.google.llm import GoogleLLMService
    from pipecat.services.openai.llm import OpenAILLMService

    for provider, expected in (("openai", OpenAILLMService), ("google", GoogleLLMService)):
        # llm_model is passed empty so the local .env cannot decide the outcome.
        cfg = Config(llm_provider=provider, llm_model="", openai_api_key="x", google_api_key="x")
        monkeypatch.setattr(providers, "config", cfg)
        assert isinstance(providers.make_llm("be helpful"), expected)


def test_a_provider_we_do_not_support_fails_loudly(monkeypatch):
    monkeypatch.setattr(providers, "config", Config(llm_provider="anthropic", llm_model=""))
    with pytest.raises(ValueError, match="anthropic"):
        providers.make_llm("be helpful")


def test_a_model_left_pinned_for_the_other_provider_is_called_out():
    # The exact trap the per-provider default exists to avoid: LLM_MODEL pinned
    # in .env for one provider and left behind when the provider is switched.
    cfg = Config(llm_provider="google", llm_model="gpt-5-mini")
    complaint = cfg.model_mismatch()
    assert complaint is not None
    assert "gpt-5-mini" in complaint and "gemini-3.8-flash" in complaint


def test_a_model_the_provider_can_serve_draws_no_complaint():
    assert Config(llm_provider="google", llm_model="gemini-3.5-flash-lite").model_mismatch() is None
    assert Config(llm_provider="google", llm_model="").model_mismatch() is None
    assert Config(llm_provider="openai", llm_model="gpt-4o").model_mismatch() is None


def test_an_unknown_provider_does_not_crash_the_complaint_itself():
    # It has no default of its own to suggest, and building the message must
    # not be the thing that fails.
    assert Config(llm_provider="anthropic", llm_model="gpt-5-mini").model_mismatch()


def test_connecting_without_the_keys_says_which_ones(monkeypatch):
    # The first thing anyone hits with a half-filled .env. It must name the gap
    # rather than fail somewhere inside Daily's REST client, and it must not
    # leave a half-started call behind.
    from types import SimpleNamespace

    monkeypatch.setattr(
        "server.main.config",
        SimpleNamespace(missing_keys=lambda: ["DAILY_API_KEY"], unknown_providers=list),
    )
    with TestClient(app) as configured_client:
        response = configured_client.post("/api/connect")

    assert response.status_code == 503
    assert response.json()["missing_env"] == ["DAILY_API_KEY"]
    assert main._calls == {}


def test_connecting_with_an_unknown_provider_refuses_before_minting_a_room(monkeypatch):
    # The keys are all present and every one of them is valid; the only thing
    # wrong is a name. That used to mint a room, admit the caller, and raise
    # from make_llm once they were already inside it.
    from types import SimpleNamespace

    complaint = "LLM_PROVIDER='gemini' is not one of: openai, google"
    monkeypatch.setattr(
        "server.main.config",
        SimpleNamespace(missing_keys=list, unknown_providers=lambda: [complaint]),
    )
    with TestClient(app) as configured_client:
        response = configured_client.post("/api/connect")

    assert response.status_code == 503
    assert response.json()["misconfigured"] == [complaint]
    assert main._calls == {}
