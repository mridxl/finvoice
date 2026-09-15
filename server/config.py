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

# Reasoning efforts `gpt-5.6-luna` documents, in its own order. Checked against
# OpenAI's model page rather than assumed: the set is per-model, and it does not
# include "minimal" — naming it after the Gemini setting would earn a 400 on the
# first turn, which is the failure this list exists to prevent.
REASONING_EFFORTS = ("none", "low", "medium", "high", "xhigh", "max")

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

    # Gemini only. Gemini 3 models think before answering, and thinking tokens
    # are billed at the output rate as well as spent on latency — on a voice
    # call both are felt, so the lowest a model will accept is what we want.
    #
    # "low", not "minimal": gemini-3.8-flash and gemini-3.7-flash both reject
    # MINIMAL with a 400. Pipecat 1.10.0 clamps only 3.7 (it predates 3.8), so
    # it will happily send a level the model refuses — which is why this is a
    # setting, and why its default is the one the default model actually takes.
    thinking_level: str = _env("GEMINI_THINKING_LEVEL", "low")

    # OpenAI's half of the same problem, and it had no control at all until a
    # call spent twelve seconds of silence producing a greeting. GPT-5 models
    # reason before answering and default to "medium".
    #
    # "low", not "none": OpenAI's own guidance puts tool use and multi-step
    # decisions — which is the whole of this agent — under "low", and reserves
    # "none" for classification and retrieval. Drop it to "none" if the silence
    # still costs more than the judgement is worth.
    reasoning_effort: str = _env("OPENAI_REASONING_EFFORT", "low")

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
        # Caught here rather than by the API, because the API catches it on the
        # first turn — mid-call, after the caller has already said hello.
        if self.llm_provider == "openai" and self.reasoning_effort not in REASONING_EFFORTS:
            complaints.append(
                f"OPENAI_REASONING_EFFORT={self.reasoning_effort!r} is not one of: "
                f"{', '.join(REASONING_EFFORTS)}"
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
