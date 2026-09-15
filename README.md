# FinVoice

A real-time voice assistant for planning the next 30 days of personal finances — multiple
loans, income landing on different dates, and usually less money than the month demands.

Built on [Pipecat](https://pipecat.ai) and [Daily](https://daily.co).

> **Current state:** the call works end to end. The browser connects, the assistant joins
> the room and speaks, and the plan builds on screen beside it — what has been covered, what
> you have said, and once every category is closed, the verdict and what has to give way.
> The same pipeline runs as text through the eval harness, with no microphone.

---

## Running it

```bash
cp .env.example .env      # fill in the keys below
docker compose up --build
```

Open <http://localhost:8080>, press **Connect**, and allow the microphone.

The first build takes a few minutes: it installs the Python tree, builds the frontend, and
bakes in the Smart Turn model so no call waits on a download.

---

## Keys

Three accounts for the default configuration. `GET /api/health` names exactly what is
missing for the combination you chose; the server starts without them and refuses calls
with a 503 rather than failing after you have joined a room.

| Variable | Used for | Needed when | Source |
|---|---|---|---|
| `DAILY_API_KEY` | WebRTC transport. Server-side only; never reaches the browser. | always | [dashboard.daily.co](https://dashboard.daily.co/developers) |
| `DEEPGRAM_API_KEY` | Speech-to-text, and text-to-speech on Aura 2. One key covers both. | `STT_PROVIDER` or `TTS_PROVIDER` is `deepgram` | [console.deepgram.com](https://console.deepgram.com/) |
| `CARTESIA_API_KEY` | Text-to-speech. | `TTS_PROVIDER=cartesia` *(the default)* | [play.cartesia.ai/keys](https://play.cartesia.ai/keys) |
| `OPENAI_API_KEY` | The model, and OpenAI's STT or TTS. | any seam points at `openai` | [platform.openai.com](https://platform.openai.com/api-keys) |
| `GOOGLE_API_KEY` | The model, on Gemini. Create it fresh in AI Studio — Google rejects unrestricted and dormant keys. | `LLM_PROVIDER=google` | [aistudio.google.com](https://aistudio.google.com/apikey) |

**If Cartesia runs out of credit**, set `TTS_PROVIDER=deepgram`. `DEEPGRAM_API_KEY` then
covers both speech seams and the Cartesia account is not needed at all. The symptom is a
call that connects and never speaks.

**To run on two accounts**, set `STT_PROVIDER=openai` and `TTS_PROVIDER=openai`: the whole
system then needs only `DAILY_API_KEY` and `OPENAI_API_KEY`. It costs roughly 200–400ms per
reply against Cartesia's sub-100ms time to first byte.

## Options

| Variable | Default | Notes |
|---|---|---|
| `LLM_PROVIDER` | `openai` | `openai` or `google` |
| `LLM_MODEL` | per provider | Blank picks the provider's default: `gpt-5.6-luna`, or `gemini-3.8-flash` |
| `GEMINI_THINKING_LEVEL` | `low` | Gemini only. `minimal`/`low`/`medium`/`high`. `gemini-3.8-flash` and `3.7-flash` reject `minimal` with a 400 on the first turn |
| `OPENAI_REASONING_EFFORT` | `low` | OpenAI only. `none`/`low`/`medium`/`high`/`xhigh`/`max` for `gpt-5.6-luna`. The model's own default is `medium`, which costs seconds of silence per turn; `none` is faster still but OpenAI reserves it for classification and retrieval rather than tool use |
| `STT_PROVIDER` | `deepgram` | `deepgram` or `openai` |
| `TTS_PROVIDER` | `cartesia` | `cartesia`, `deepgram` (`aura-2-helena-en`), or `openai` |
| `TURN_DETECTION` | `smart` | `smart` = Smart Turn v3 semantic end-of-turn; `vad` = fixed silence threshold |
| `VAD_STOP_SECS` | `0.8` | Only read when `TURN_DETECTION=vad` |
| `LOG_LEVEL` | `INFO` | Pipecat's debug output is chatty enough to print key material |
| `AS_OF` | today, in India | ISO date the 30 days run from, so a run is reproducible. `AS_OF=2026-09-15` plans 15 Sep – 14 Oct |
| `PORT` | `8080` | |

An unrecognised provider name is reported at startup and on `/api/health`, and refuses the
call before a room is minted.

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

Tests are not in the container image, and the runtime environment is built without dev
dependencies.

### Behavioural evals

`tests/` is deterministic and needs no model. How the agent *behaves* is checked separately,
by driving the real pipeline as text over Pipecat's eval transport — same prompt, same
tools, no microphone and nothing synthesised.

```bash
uv run python -m pipecat.evals suite evals/suite.yaml            # window opens on the 1st
uv run python -m pipecat.evals suite evals/suite-midmonth.yaml   # window straddles two months
```

Use `python -m`, not the `pipecat` script: the judge lives in this repo at `evals/judge.py`,
and only `-m` puts the working directory on the import path.

To iterate on one scenario against a bot you keep running:

```bash
uv run python -m server.eval_bot --port 7860 --as-of 2026-09-01
uv run python -m pipecat.evals run evals/scenarios/the_month_does_not_work.yaml -v
```

Both the bot and the judge call a paid API. A suite run is roughly 82k input and 11k output
tokens — about 17 cents on `gemini-3.8-flash`.

---

## Design

**The language model never does arithmetic.**

It extracts facts from the conversation through tool calls; a pure Python planner in
`server/domain/` computes every number. The UI renders that planner's state and never
recomputes anything, so correcting an amount mid-conversation moves every figure that
depends on it. Consistency is structural rather than prompted, and the planner is testable
with no LLM in the loop.

`SPEC.md` states the requirements. `BUILD-PLAN.md` covers the architecture, the provider
seam, and why each of these defaults is what it is.

---

## Layout

```
server/          FastAPI app, Pipecat pipeline, provider seam
  domain/        pure planning logic — no I/O, no network, no clock
web/             React + Vite frontend
tests/           deterministic tests for the domain and wiring
evals/           scenario-based behavioural evals
```
