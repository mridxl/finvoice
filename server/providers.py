"""The provider seam.

Every STT / TTS / LLM construction goes through here, selected by env. Defaults
are Deepgram + Cartesia + OpenAI gpt-5-mini, with Gemini as the other model
option; the seam exists so that choice stays reversible without touching the
pipeline, which is the whole reason swapping the model is an env var rather than
a rewrite.

Imports are deferred into the factories: importing a Pipecat service pulls its
SDK, and `/api/health` must be answerable without any of them.
"""

import logging

from server.config import config

log = logging.getLogger("finvoice.providers")


def make_stt():
    """Streaming speech-to-text."""
    if config.stt_provider == "deepgram":
        from pipecat.services.deepgram.stt import DeepgramSTTService

        return DeepgramSTTService(api_key=config.deepgram_api_key)
    if config.stt_provider == "openai":
        from pipecat.services.openai.stt import OpenAISTTService

        return OpenAISTTService(api_key=config.openai_api_key)
    raise ValueError(f"unknown STT_PROVIDER: {config.stt_provider!r}")


def make_tts():
    """Streaming text-to-speech."""
    if config.tts_provider == "cartesia":
        from pipecat.services.cartesia.tts import CartesiaTTSService

        return CartesiaTTSService(
            api_key=config.cartesia_api_key,
            settings=CartesiaTTSService.Settings(
                voice="86e30c1d-714b-4074-a1f2-1cb6b552fb49",
            ),
        )
    if config.tts_provider == "deepgram":
        from pipecat.services.deepgram.tts import DeepgramTTSService

        # Aura 2, streaming over a websocket like Cartesia, so interruption
        # still works. Named explicitly rather than left to the service default
        # so the voice is a decision in the repo and not a vendor's.
        return DeepgramTTSService(
            api_key=config.deepgram_api_key,
            settings=DeepgramTTSService.Settings(voice="aura-2-helena-en"),
        )
    if config.tts_provider == "openai":
        from pipecat.services.openai.tts import OpenAITTSService

        return OpenAITTSService(api_key=config.openai_api_key)
    raise ValueError(f"unknown TTS_PROVIDER: {config.tts_provider!r}")


def make_llm(system_instruction: str):
    """The conversational model. It extracts facts and narrates; it never computes."""
    # Said here rather than at startup so both the server and the eval bot get
    # it, and said rather than raised so /api/health still answers.
    if (complaint := config.model_mismatch()) is not None:
        log.warning("%s", complaint)

    if config.llm_provider == "openai":
        from pipecat.services.openai.llm import OpenAILLMService

        return OpenAILLMService(
            api_key=config.openai_api_key,
            settings=OpenAILLMService.Settings(
                model=config.llm_model,
                # The prompt lives on the service rather than in the context, so
                # replacing the context cannot drop it. An eval seeds a
                # conversation exactly that way.
                system_instruction=system_instruction,
            ),
        )
    if config.llm_provider == "google":
        from pipecat.services.google.llm import GoogleLLMService

        return GoogleLLMService(
            api_key=config.google_api_key,
            settings=GoogleLLMService.Settings(
                model=config.llm_model,
                system_instruction=system_instruction,
                # Set rather than left to the model's own default: Gemini 3
                # thinks before it answers, and on a voice call that time is
                # silence the user is listening to.
                thinking=GoogleLLMService.ThinkingConfig(thinking_level=config.thinking_level),
            ),
        )
    raise ValueError(f"unknown LLM_PROVIDER: {config.llm_provider!r}")


def make_turn_strategies():
    """End-of-turn detection for the user aggregator.

    Smart Turn v3 reads the waveform and judges whether the utterance sounds
    finished. That matters here because people pause mid-sentence while recalling
    a figure, and a fixed silence threshold cannot both tolerate that and stay
    responsive.
    """
    from pipecat.audio.vad.silero import SileroVADAnalyzer

    vad = SileroVADAnalyzer()
    if config.turn_detection != "smart":
        from pipecat.audio.vad.vad_analyzer import VADParams

        return SileroVADAnalyzer(params=VADParams(stop_secs=config.vad_stop_secs)), None

    from pipecat.audio.turn.smart_turn.local_smart_turn_v3 import LocalSmartTurnAnalyzerV3

    return vad, LocalSmartTurnAnalyzerV3()


def describe() -> dict[str, str]:
    """Selected providers, for /api/health. Never includes key material."""
    described = {
        "llm": f"{config.llm_provider}:{config.llm_model}",
        "stt": config.stt_provider,
        "tts": config.tts_provider,
        "turn_detection": config.turn_detection,
    }
    if config.llm_provider == "google":
        described["thinking"] = config.thinking_level
    return described
