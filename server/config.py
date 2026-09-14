"""Environment configuration and the provider seam's settings.

Reads once at import. Nothing here touches the network or constructs a service —
that lets `/api/health` report configuration without needing valid keys.
"""

import os
from dataclasses import dataclass, field
from datetime import date, datetime
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv(override=True)

INDIA = ZoneInfo("Asia/Kolkata")


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


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

    llm_model: str = _env("LLM_MODEL", "gpt-5-mini")

    # smart | vad. Smart Turn v3 judges whether an utterance sounds finished;
    # a fixed silence threshold either clips people mid-number or feels slow.
    turn_detection: str = _env("TURN_DETECTION", "smart")
    # Only consulted when turn_detection == "vad". Pipecat's default is 0.2s,
    # which shreds conversations where people pause while recalling a figure.
    vad_stop_secs: float = float(_env("VAD_STOP_SECS", "0.8"))

    daily_api_key: str = field(default_factory=lambda: _env("DAILY_API_KEY"), repr=False)
    openai_api_key: str = field(default_factory=lambda: _env("OPENAI_API_KEY"), repr=False)
    deepgram_api_key: str = field(default_factory=lambda: _env("DEEPGRAM_API_KEY"), repr=False)
    cartesia_api_key: str = field(default_factory=lambda: _env("CARTESIA_API_KEY"), repr=False)

    def missing_keys(self) -> list[str]:
        """Required env vars that are absent, given the selected providers."""
        needed = {"DAILY_API_KEY": self.daily_api_key}
        if self.llm_provider == "openai":
            needed["OPENAI_API_KEY"] = self.openai_api_key
        if self.stt_provider == "deepgram":
            needed["DEEPGRAM_API_KEY"] = self.deepgram_api_key
        if self.tts_provider == "cartesia":
            needed["CARTESIA_API_KEY"] = self.cartesia_api_key
        return sorted(name for name, value in needed.items() if not value)


config = Config()
