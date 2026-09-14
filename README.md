# FinVoice

A real-time voice assistant for planning the next 30 days of personal finances — multiple
loans, income landing on different dates, and usually less money than the month demands.

Built on [Pipecat](https://pipecat.ai) and [Daily](https://daily.co).

> **Current state:** the server, container build and frontend shell are in place. The
> voice conversation is not wired up yet — the app serves a status page and reports its
> provider configuration at `/api/health`.

---

## Running it

```bash
cp .env.example .env      # fill in the API keys
docker compose up --build
```

Open <http://localhost:8080>.

The first build takes a few minutes — it installs the Python tree, builds the frontend,
and resolves the Smart Turn model weights so the first call doesn't block on them.

---

## Configuration

Copy `.env.example` to `.env`. `.env` is gitignored; no values are committed.

### Required

| Variable | Used for | Source |
|---|---|---|
| `DAILY_API_KEY` | WebRTC transport — creates the call room and mints join tokens. Server-side only; never reaches the browser. | [dashboard.daily.co/developers](https://dashboard.daily.co/developers) |
| `OPENAI_API_KEY` | The conversational model. | [platform.openai.com/api-keys](https://platform.openai.com/api-keys) |
| `DEEPGRAM_API_KEY` | Streaming speech-to-text. | [console.deepgram.com](https://console.deepgram.com/) |
| `CARTESIA_API_KEY` | Streaming text-to-speech. | [play.cartesia.ai/keys](https://play.cartesia.ai/keys) |

Missing keys don't stop the server — it starts and `GET /api/health` names exactly what is
absent. No call can be placed until all four are set.

### Optional

| Variable | Default | Notes |
|---|---|---|
| `LLM_PROVIDER` | `openai` | |
| `LLM_MODEL` | `gpt-5-mini` | |
| `STT_PROVIDER` | `deepgram` | `deepgram` or `openai` |
| `TTS_PROVIDER` | `cartesia` | `cartesia` or `openai` |
| `TURN_DETECTION` | `smart` | `smart` = Smart Turn v3 semantic end-of-turn; `vad` = fixed silence threshold |
| `VAD_STOP_SECS` | `0.8` | Only read when `TURN_DETECTION=vad` |
| `PORT` | `8080` | |

**Fewer accounts, more latency.** Setting `STT_PROVIDER=openai` and `TTS_PROVIDER=openai`
runs the whole system on `DAILY_API_KEY` and `OPENAI_API_KEY` alone. It works; it is
slower. OpenAI's TTS adds roughly 200–400ms per reply against Cartesia's sub-100ms
time-to-first-byte, which is a meaningful share of a one-second budget.

---

## Development

`daily-python` ships no Windows wheels, so the backend needs Linux or macOS — on Windows,
use Docker or WSL. Dependency resolution fails outright on a Windows host.

```bash
uv sync --group dev
uv run python -m server.main            # API on :8080
```

```bash
cd web && npm install && npm run dev    # SPA on :5173, proxying /api to :8080
```

```bash
uv run pytest -q
uv run ruff check .
```

Tests are not part of the container image, and the runtime environment is built without
dev dependencies.

---

## Design

**The language model never does arithmetic.**

It extracts facts from the conversation through tool calls; a pure Python planner in
`server/domain/` computes every number. Cards in the UI are projections of that planner's
state, so correcting an amount mid-conversation moves every figure that depends on it.
Consistency is structural rather than prompted, and the planner is testable without an LLM
in the loop.

`SPEC.md` states the requirements. `BUILD-PLAN.md` covers the architecture and the order
of work.

---

## Layout

```
server/          FastAPI app, Pipecat pipeline, provider seam
  domain/        pure planning logic — no I/O, no network, no clock
web/             React + Vite frontend
tests/           deterministic tests for the domain and wiring
evals/           scenario-based behavioural evals
```
