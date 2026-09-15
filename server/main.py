"""FastAPI entrypoint. Serves the built SPA, the API, and hosts the bot task.

One process, one port: the built frontend, the API, and the bot task all live here.
Starting a call is a POST, not a second process — nothing may ever need a second
terminal to start, and a bot subprocess per call would be exactly that.
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

import aiohttp
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pipecat.utils.prewarm import warm_deferred_imports

from server import daily, providers
from server.bot import run_bot
from server.config import config
from server.session import Session

logging.basicConfig(level=config.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("finvoice")

WEB_DIST = Path(__file__).resolve().parent.parent / "web" / "dist"

# One entry per live call, so shutdown can end them and /api/health can say how
# many are running. The task owns everything else about the call; the Session it
# closes over is reachable only from there, which is what keeps two callers from
# ever seeing each other's money.
_calls: dict[str, asyncio.Task] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("providers: %s", providers.describe())
    # Pipecat defers a pile of heavy imports and warms them inside pipeline
    # setup, on a worker thread, racing a twenty-second budget it shares with
    # joining Daily and opening two Deepgram sockets. The first call in a fresh
    # process lost that race every time — "timeout setting the pipeline up",
    # nought turns, no other trace — while every later call set up in about a
    # millisecond, because by then the modules were in `sys.modules`.
    #
    # Diagnosed by dumping the await chain of every task mid-hang: the setup
    # task parked on `warm_lazy_imports`, itself parked in `to_thread`. Doing it
    # here costs a couple of seconds of startup, where nothing is waiting.
    await asyncio.to_thread(warm_deferred_imports)
    log.info("deferred imports warmed")
    # Said at startup, not on the first call. A provider name nothing can build
    # used to reach the caller as a traceback, after they had joined the room.
    for complaint in config.unknown_providers():
        log.error("%s", complaint)
    missing = config.missing_keys()
    if missing:
        log.warning("missing env vars, voice will not start: %s", ", ".join(missing))
        log.warning("copy .env.example to .env and fill these in, then restart")

    # One HTTP session for the process: Daily's REST helper takes one, and
    # opening a fresh one per call would pay a TLS handshake on every connect.
    async with aiohttp.ClientSession() as http:
        app.state.http = http
        yield
        for task in list(_calls.values()):
            task.cancel()
        await asyncio.gather(*list(_calls.values()), return_exceptions=True)


app = FastAPI(title="FinVoice", lifespan=lifespan)


@app.get("/api/health")
async def health() -> JSONResponse:
    missing = config.missing_keys()
    unknown = config.unknown_providers()
    return JSONResponse(
        {
            "status": "ok" if not (missing or unknown) else "needs-config",
            "providers": providers.describe(),
            "missing_env": missing,
            "misconfigured": unknown,
            "web_built": WEB_DIST.is_dir(),
            "calls_in_progress": len(_calls),
        }
    )


@app.post("/api/connect")
async def connect() -> JSONResponse:
    """Start a call: mint a room, start the bot in it, tell the browser where to go.

    The response is the shape `@pipecat-ai/client-js` expects back from its
    `connect({ endpoint })`, so the browser needs no adapter.
    """
    missing = config.missing_keys()
    unknown = config.unknown_providers()
    if missing or unknown:
        # 503 rather than 500: the code is fine, the deployment is not, and the
        # browser can say which key is absent instead of "something went wrong".
        # An unrecognised provider refuses here for the same reason — the
        # alternative is minting a room and failing once someone is inside it.
        return JSONResponse(
            {
                "detail": "not configured for calls",
                "missing_env": missing,
                "misconfigured": unknown,
            },
            status_code=503,
        )

    call = await daily.mint_call(app.state.http)
    call_id = uuid4().hex
    # The date is read once, here, and carried for the whole call: a conversation
    # that runs over midnight must not silently replan against a different day.
    session = Session(as_of=config.as_of)

    task = asyncio.create_task(_run_call(call_id, call, session), name=f"call-{call_id}")
    _calls[call_id] = task
    task.add_done_callback(lambda _: _calls.pop(call_id, None))

    log.info("call %s starting", call_id)
    # Exactly the two keys the client reads. Pipecat's own dev runner also returns
    # a sessionId, which this client version does not recognise and complains
    # about in the console — the id is ours for correlating logs, not the
    # browser's, so it stays on this side.
    return JSONResponse({"dailyRoom": call.room_url, "dailyToken": call.user_token})


async def _run_call(call_id: str, call: daily.Call, session: Session) -> None:
    """One call, start to finish. Never raises: a failed call must not take the server with it."""
    try:
        await run_bot(daily.make_transport(call), session)
    except asyncio.CancelledError:
        log.info("call %s cancelled", call_id)
        raise
    except Exception:
        log.exception("call %s ended badly", call_id)
    finally:
        log.info("call %s over after %d turns", call_id, session.turn)


if WEB_DIST.is_dir():
    # Mounted last: it claims "/", and html=True answers unknown paths with
    # index.html, which would otherwise swallow the API routes above.
    app.mount("/", StaticFiles(directory=WEB_DIST, html=True), name="web")
else:
    log.warning("no built frontend at %s — run the web build or use Docker", WEB_DIST)

    @app.get("/")
    async def placeholder() -> JSONResponse:
        return JSONResponse({"detail": "frontend not built; see README"}, status_code=503)


def run() -> None:
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=config.port, log_level="info")


if __name__ == "__main__":
    run()
