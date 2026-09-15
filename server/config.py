"""Environment configuration and the provider seam's settings.

Reads once at import. Nothing here touches the network or constructs a service —
that lets `/api/health` report configuration without needing valid keys.
"""

import os
from dataclasses import dataclass, field
from datetime import date, datetime
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

# The real environment wins over the file. That is how every deployment target
# passes configuration, and it is what lets `LLM_PROVIDER=google uv run ...`
# switch the model for one run without editing .env — which matters for a seam
# whose whole purpose is being switchable.
load_dotenv()

INDIA = ZoneInfo("Asia/Kolkata")


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


# What each provider is asked for when LLM_MODEL says nothing. Per provider,
# because one shared default would mean selecting Google and forgetting the
# model sends an OpenAI model name to Gemini, which fails somewhere far from
# the mistake.
DEFAULT_LLM_MODELS = {"openai": "gpt-5.6-luna", "google": "gemini-3.8-flash"}

# How much each provider's default model is allowed to think before answering.
# Two vocabularies because they are two APIs: OpenAI's `reasoning_effort` and
# Gemini's `thinking_level` share words but not sets, and a value from one
# earns a 400 from the other on the first turn, mid-call. Each set below was
# checked against the model it names, so they are enforced only while that
# model is the one in play — a pinned LLM_MODEL is on its own vocabulary.
#
# gpt-5.6-luna documents none, low, medium, high, xhigh, max. But every turn
# of this agent carries function tools, and on /v1/chat/completions the model
# takes tools at "none" and nothing else — including its own default. Not on
# the model page; learned from the eval suite going 0 for 9 and confirmed
# against OpenAI's forum. Lift when OpenAI does, or when `providers.py` moves
# to the Responses API, which has no such rule.
REASONING_EFFORTS = ("none", "low", "medium", "high", "xhigh", "max")
TOOL_SAFE_EFFORTS = ("none",)

# gemini-3.8-flash takes low, medium, high. It refuses "minimal" — the level
# older Gemini models accepted — and Pipecat 1.10.0 predates 3.8, so it clamps
# nothing and forwards whatever it is given.
THINKING_LEVELS = ("low", "medium", "high")

# Turn detection has two implementations and no third; anything else used to
# fall silently to VAD.
TURN_DETECTIONS = ("smart", "vad")

# What each seam may actually be pointed at. `providers.py` branches on exactly
# these names and raises on anything else — which used to be discovered on the
# first call, in a traceback, after the caller had already joined the room.
# `LLM_PROVIDER=gemini` is the mistake this exists for: a real product's name,
# and not the one the factory branches on.
PROVIDERS: dict[str, tuple[str, ...]] = {
    "LLM_PROVIDER": ("openai", "google"),
    "STT_PROVIDER": ("deepgram", "openai"),
    "TTS_PROVIDER": ("cartesia", "deepgram", "openai"),
}


def _as_of() -> date:
    """The date the plan is made from. Today in India, unless pinned.

    `domain/` never reads a clock, so the date enters the process here and
    nowhere else. The zone is explicit because a server running in UTC is a day
    behind its user for the first five and a half hours of every Indian day, and
    "the fifth" would then mean the wrong fifth. Pinning `AS_OF` makes a run
    reproducible, which is what lets an eval assert on a day of the month.
    """
    value = _env("AS_OF")
    return date.fromisoformat(value) if value else datetime.now(INDIA).date()


@dataclass(frozen=True)
class Config:
    port: int = int(_env("PORT", "8080"))
    # Pipecat logs at debug by default and is chatty enough to put key material
    # on screen. Anything louder than info is a deliberate act.
    log_level: str = _env("LOG_LEVEL", "INFO").upper()
    as_of: date = field(default_factory=_as_of)

    llm_provider: str = _env("LLM_PROVIDER", "openai")
    stt_provider: str = _env("STT_PROVIDER", "deepgram")
    tts_provider: str = _env("TTS_PROVIDER", "cartesia")

    # Empty means "whatever this provider's default is", resolved below against
    # the provider actually selected rather than against the environment, so
    # constructing a Config directly behaves the same way the app does.
    llm_model: str = field(default_factory=lambda: _env("LLM_MODEL"))

    # Gemini only. Thinking tokens bill at the output rate and are spent on
    # latency; on a voice call both are felt, so the lowest the default model
    # accepts. See THINKING_LEVELS.
    thinking_level: str = _env("GEMINI_THINKING_LEVEL", "low")

    # OpenAI only. Not a latency choice: the only value the API takes with tools
    # on this endpoint, see TOOL_SAFE_EFFORTS. It is also the fast one — 2.3s to
    # a greeting against 3.5s at "low", measured, after a call once spent twelve
    # seconds of silence on a greeting with nothing pinning this at all.
    reasoning_effort: str = _env("OPENAI_REASONING_EFFORT", "none")

    # smart | vad. Smart Turn v3 judges whether an utterance sounds finished;
    # a fixed silence threshold either clips people mid-number or feels slow.
    turn_detection: str = _env("TURN_DETECTION", "smart")
    # Only consulted when turn_detection == "vad". Pipecat's default is 0.2s,
    # which shreds conversations where people pause while recalling a figure.
    vad_stop_secs: float = float(_env("VAD_STOP_SECS", "0.8"))

    daily_api_key: str = field(default_factory=lambda: _env("DAILY_API_KEY"), repr=False)
    openai_api_key: str = field(default_factory=lambda: _env("OPENAI_API_KEY"), repr=False)
    # The Google SDK reads GOOGLE_API_KEY itself, and prefers it over
    # GEMINI_API_KEY when both are set. We pass the key explicitly, but using
    # the name the SDK expects keeps one convention instead of two.
    google_api_key: str = field(default_factory=lambda: _env("GOOGLE_API_KEY"), repr=False)
    deepgram_api_key: str = field(default_factory=lambda: _env("DEEPGRAM_API_KEY"), repr=False)
    cartesia_api_key: str = field(default_factory=lambda: _env("CARTESIA_API_KEY"), repr=False)

    def __post_init__(self) -> None:
        if not self.llm_model:
            object.__setattr__(
                self, "llm_model", DEFAULT_LLM_MODELS.get(self.llm_provider, "")
            )

    def model_mismatch(self) -> str | None:
        """A complaint when `LLM_MODEL` names a model the selected provider cannot serve.

        Only the exact defaults of the other providers are recognised, because
        that is the mistake that actually happens: a model pinned in `.env` for
        one provider, left behind when the provider is switched. Anything
        cleverer would guess at model names and age badly.
        """
        stale = {
            model: provider
            for provider, model in DEFAULT_LLM_MODELS.items()
            if provider != self.llm_provider
        }
        other = stale.get(self.llm_model)
        if other is None:
            return None
        ours = DEFAULT_LLM_MODELS.get(self.llm_provider)
        remedy = (
            f"Clear LLM_MODEL to get {ours!r}"
            if ours
            else "Clear LLM_MODEL, or name one it serves"
        )
        return (
            f"LLM_MODEL is {self.llm_model!r}, which is {other}'s model, but "
            f"LLM_PROVIDER is {self.llm_provider!r}. {remedy}."
        )

    def unknown_providers(self) -> list[str]:
        """Seams pointed at something no factory can build, as plain sentences.

        Reported rather than raised, for the same reason `missing_keys` is: the
        server has to start and `/api/health` has to answer, or the only way to
        learn the name is wrong is to place a call and read a traceback.
        """
        chosen = {
            "LLM_PROVIDER": self.llm_provider,
            "STT_PROVIDER": self.stt_provider,
            "TTS_PROVIDER": self.tts_provider,
        }
        complaints = [
            f"{name}={value!r} is not one of: {', '.join(PROVIDERS[name])}"
            for name, value in chosen.items()
            if value not in PROVIDERS[name]
        ]
        if self.turn_detection not in TURN_DETECTIONS:
            complaints.append(
                f"TURN_DETECTION={self.turn_detection!r} is not one of: "
                f"{', '.join(TURN_DETECTIONS)}"
            )
        # Caught here rather than by the API, because the API catches it on the
        # first turn — mid-call, after the caller has already said hello. Only
        # for the default model: the sets were checked against it and no other.
        if self.llm_model != DEFAULT_LLM_MODELS.get(self.llm_provider):
            return complaints
        if self.llm_provider == "openai":
            if self.reasoning_effort not in REASONING_EFFORTS:
                complaints.append(
                    f"OPENAI_REASONING_EFFORT={self.reasoning_effort!r} is not one of: "
                    f"{', '.join(REASONING_EFFORTS)}"
                )
            elif self.reasoning_effort not in TOOL_SAFE_EFFORTS:
                complaints.append(
                    f"OPENAI_REASONING_EFFORT={self.reasoning_effort!r} is refused alongside "
                    f"function tools on /v1/chat/completions; use one of: "
                    f"{', '.join(TOOL_SAFE_EFFORTS)}"
                )
        if self.llm_provider == "google" and self.thinking_level not in THINKING_LEVELS:
            complaints.append(
                f"GEMINI_THINKING_LEVEL={self.thinking_level!r} is not one of: "
                f"{', '.join(THINKING_LEVELS)}"
            )
        return complaints

    def missing_keys(self) -> list[str]:
        """Required env vars that are absent, given the selected providers."""
        needed = {"DAILY_API_KEY": self.daily_api_key}
        # Any of the three seams can be pointed at OpenAI, so asking only about
        # the model would miss a Gemini conversation transcribed by OpenAI.
        if "openai" in (self.llm_provider, self.stt_provider, self.tts_provider):
            needed["OPENAI_API_KEY"] = self.openai_api_key
        if self.llm_provider == "google":
            needed["GOOGLE_API_KEY"] = self.google_api_key
        # Deepgram serves both seams, and either one alone needs the key — asking
        # only about STT reported a healthy config for a call that had no voice.
        if "deepgram" in (self.stt_provider, self.tts_provider):
            needed["DEEPGRAM_API_KEY"] = self.deepgram_api_key
        if self.tts_provider == "cartesia":
            needed["CARTESIA_API_KEY"] = self.cartesia_api_key
        return sorted(name for name, value in needed.items() if not value)


config = Config()
