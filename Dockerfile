# Stage 1 — build the SPA. Its output is copied into the Python image below, so
# the whole system runs as one container on one port.
FROM node:24-slim AS web
WORKDIR /web
# The lockfile comes too, and `npm ci` installs exactly what it pins and fails
# if the two have drifted. `npm install` would silently resolve something newer,
# so the image would stop matching the tree it was built from — the same reason
# uv.lock is committed and `uv sync` is used below.
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

# Stage 2 — runtime.
FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.10.7 /uv /bin/uv

# libsndfile1 backs soundfile, which Pipecat uses for audio I/O.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy PYTHONUNBUFFERED=1

# Dependencies before source, so edits to server/ do not re-resolve the tree.
COPY pyproject.toml uv.lock* ./
RUN uv sync --no-dev

# Resolve the Smart Turn v3 ONNX weights at build time so the first call does not
# block on model loading. Kept above the source copy: it depends only on the
# installed tree, and Docker invalidates every layer after the one that changed.
RUN uv run --no-dev python -c "\
from pipecat.audio.turn.smart_turn.local_smart_turn_v3 import LocalSmartTurnAnalyzerV3; \
LocalSmartTurnAnalyzerV3(); \
print('smart-turn v3 ready')"

COPY server/ ./server/
COPY --from=web /web/dist ./web/dist

ENV PORT=8080
EXPOSE 8080
# --no-dev matters here too: a bare `uv run` re-syncs at container start and
# would pull pytest/ruff into the running image.
CMD ["uv", "run", "--no-dev", "python", "-m", "server.main"]
