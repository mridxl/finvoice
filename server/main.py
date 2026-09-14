"""FastAPI entrypoint. Serves the built SPA, the API, and hosts the bot task.

One process, one port: the built frontend, the API, and the bot task all live here.
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from server import providers
from server.config import config

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("finvoice")

WEB_DIST = Path(__file__).resolve().parent.parent / "web" / "dist"


@asynccontextmanager
async def lifespan(_: FastAPI):
    log.info("providers: %s", providers.describe())
    missing = config.missing_keys()
    if missing:
        log.warning("missing env vars, voice will not start: %s", ", ".join(missing))
        log.warning("copy .env.example to .env and fill these in, then restart")
    yield


app = FastAPI(title="FinVoice", lifespan=lifespan)


@app.get("/api/health")
async def health() -> JSONResponse:
    missing = config.missing_keys()
    return JSONResponse(
        {
            "status": "ok" if not missing else "needs-config",
            "providers": providers.describe(),
            "missing_env": missing,
            "web_built": WEB_DIST.is_dir(),
        }
    )


if WEB_DIST.is_dir():
    # html=True serves index.html for unknown paths, so client-side routing works.
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
