"""Run the bot over the eval transport: text in, text out, no audio.

This is the same pipeline the call uses. The transport is a WebSocket server
speaking RTVI that `pipecat eval` connects to as a client, so a scenario drives
the real prompt and the real tools — only the microphone is missing.

    uv run python -m server.eval_bot --port 7860
    uv run pipecat eval run evals/scenarios/*.yaml

or, spawning the bot for you:

    uv run pipecat eval suite evals/suite.yaml
"""

import argparse
import asyncio
import logging
import sys
from datetime import date

from loguru import logger
from pipecat.evals.serializer import EvalSerializer
from pipecat.evals.transport import EvalTransport, EvalTransportParams
from pipecat.utils.prewarm import warm_deferred_imports

from server.bot import run_bot
from server.config import config
from server.session import Session


def main() -> None:
    parser = argparse.ArgumentParser(description="FinVoice under the eval transport")
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=7860)
    parser.add_argument(
        "--as-of",
        type=date.fromisoformat,
        default=config.as_of,
        help="Plan from this date instead of today, so a scenario gets the same "
        "thirty days every run and can assert on a day of the month.",
    )
    args = parser.parse_args()

    logging.basicConfig(level=config.log_level, format="%(levelname)s %(name)s: %(message)s")
    logger.remove()
    logger.add(sys.stderr, level=config.log_level)

    # Same reason as `main.py`'s lifespan, worse odds: the suite spawns four of
    # these at once, and on a cold machine four warm-ups racing one another
    # missed the harness's ten-second bot-ready window on every scenario in the
    # first batch. Here, before listening, nothing is timing us.
    warm_deferred_imports()

    transport = EvalTransport(
        params=EvalTransportParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            serializer=EvalSerializer(),
        ),
        host=args.host,
        port=args.port,
    )
    # Text in, text out: nothing here is ever heard, so nothing is synthesised.
    asyncio.run(run_bot(transport, Session(as_of=args.as_of), speech=False))


if __name__ == "__main__":
    main()
