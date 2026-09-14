"""The provider seam.

Every STT / TTS / LLM construction goes through here, selected by env. Locked
defaults are Deepgram + Cartesia + OpenAI gpt-5-mini; the seam exists so that
choice stays reversible without touching the pipeline.

Imports are deferred into the factories: importing a Pipecat service pulls its
SDK, and `/api/health` must be answerable without any of them.
"""

from server.config import config


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
    if config.tts_provider == "openai":
        from pipecat.services.openai.tts import OpenAITTSService

        return OpenAITTSService(api_key=config.openai_api_key)
    raise ValueError(f"unknown TTS_PROVIDER: {config.tts_provider!r}")


def make_llm(system_instruction: str):
    """The conversational model. It extracts facts and narrates; it never computes."""
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
    return {
        "llm": f"{config.llm_provider}:{config.llm_model}",
        "stt": config.stt_provider,
        "tts": config.tts_provider,
        "turn_detection": config.turn_detection,
    }
