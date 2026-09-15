"""The pipeline, and the one function that runs it.

`build_pipeline` takes the transport as an argument rather than making one, so
the same pipeline runs under Daily in production and under the eval transport in
`pipecat eval`. Inlining a transport here would cost us the eval path, which is
where the prompt actually gets iterated on.

Nothing in this module knows anything about money. It wires the model to the
tools and the session, and the session owns everything that is true.
"""

import logging

from pipecat.frames.frames import LLMRunFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.worker import PipelineWorker
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
)
from pipecat.turns.user_stop import (
    SpeechTimeoutUserTurnStopStrategy,
    TurnAnalyzerUserTurnStopStrategy,
)
from pipecat.turns.user_turn_strategies import UserTurnStrategies
from pipecat.workers.runner import WorkerRunner

from server import providers
from server.prompt import system_prompt
from server.session import Session
from server.tools import TOOLS

log = logging.getLogger("finvoice.bot")


def build_pipeline(transport, session: Session) -> Pipeline:
    """The pipeline for one call. `transport` is whatever we are speaking over."""
    vad, turn_analyzer = providers.make_turn_strategies()
    # The system prompt lives on the service, not in the context, so replacing
    # the context — which is how an eval seeds a conversation — cannot drop it.
    llm = providers.make_llm(system_prompt(session.as_of))
    context = LLMContext(tools=TOOLS)
    aggregators = LLMContextAggregatorPair(
        context,
        user_params=LLMUserAggregatorParams(
            vad_analyzer=vad,
            user_turn_strategies=_turn_strategies(turn_analyzer),
        ),
    )

    @aggregators.assistant().event_handler("on_assistant_turn_stopped")
    async def _next_turn(_aggregator, _message):
        # Facts recorded while the model is answering all belong to the turn that
        # prompted them, so the count moves only once the answer is finished.
        session.turn += 1

    return Pipeline(
        [
            transport.input(),
            providers.make_stt(),
            aggregators.user(),
            llm,
            providers.make_tts(),
            transport.output(),
            # After the output, so the history is what was actually spoken.
            aggregators.assistant(),
        ]
    )


async def run_bot(transport, session: Session) -> None:
    """Run one call to completion. Returns when the pipeline ends."""
    worker = PipelineWorker(build_pipeline(transport, session), app_resources=session)
    # Cards reach the browser as RTVI server messages over the same data channel
    # the call uses, so a card can never arrive from a different state than the
    # sentence being spoken beside it.
    session.publish = worker.rtvi.send_server_message

    @transport.event_handler("on_client_connected")
    async def _on_connected(_transport, _client):
        log.info("client connected; opening the conversation")
        await worker.queue_frames([LLMRunFrame()])

    @transport.event_handler("on_client_disconnected")
    async def _on_disconnected(_transport, _client):
        log.info("client disconnected; ending the call")
        await worker.cancel()

    await WorkerRunner().run(worker)


def _turn_strategies(turn_analyzer) -> UserTurnStrategies:
    """When the user has finished speaking.

    Smart Turn v3 reads the waveform and judges whether the sentence sounds
    finished, which is what this conversation needs: people trail off mid-number
    while recalling a figure, and a silence threshold either cuts them off or
    makes every turn feel slow. The timeout strategy is the fallback when
    TURN_DETECTION is set to vad.
    """
    if turn_analyzer is None:
        return UserTurnStrategies(stop=[SpeechTimeoutUserTurnStopStrategy()])
    return UserTurnStrategies(stop=[TurnAnalyzerUserTurnStopStrategy(turn_analyzer=turn_analyzer)])
