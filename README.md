# FinVoice

A real-time voice assistant for planning the next 30 days of personal finances — multiple
loans, income landing on different dates, and usually less money than the month demands.

Built on [Pipecat](https://pipecat.ai) and [Daily](https://daily.co).

> **Current state:** the planner, the agent, its tools and its prompt are in place, and the
> pipeline runs as a real voice call over Daily — the browser connects, the assistant joins
> the room, speaks, and the conversation is transcribed live on screen. The same pipeline
> still runs as text through the eval harness. The cards are not built yet, so the screen
> shows the transcript rather than the plan taking shape beside it.

---

## Running it

```bash
cp .env.example .env      # fill in the API keys
docker compose up --build
```

Open <http://localhost:8080>, press **Connect**, and allow the microphone when the browser
asks. The server mints a Daily room per call and puts the assistant in it; nothing about
the room or the keys reaches the browser beyond a join token that is not an owner token.

The first build takes a few minutes — it installs the Python tree, builds the frontend,
and resolves the Smart Turn model weights so the first call doesn't block on them.

---

## Configuration

Copy `.env.example` to `.env`. `.env` is gitignored; no values are committed.

### Required

Which keys you need depends on the providers you select. `GET /api/health` names exactly
what is missing for the combination you chose.

| Variable | Used for | Needed when | Source |
|---|---|---|---|
| `DAILY_API_KEY` | WebRTC transport — creates the call room and mints join tokens. Server-side only; never reaches the browser. | always | [dashboard.daily.co/developers](https://dashboard.daily.co/developers) |
| `OPENAI_API_KEY` | The conversational model, and OpenAI's STT or TTS. | any of the three seams points at `openai` | [platform.openai.com/api-keys](https://platform.openai.com/api-keys) |
| `GOOGLE_API_KEY` | The conversational model, on Gemini. | `LLM_PROVIDER=google` | [aistudio.google.com/apikey](https://aistudio.google.com/apikey) |
| `DEEPGRAM_API_KEY` | Streaming speech-to-text. | `STT_PROVIDER=deepgram` | [console.deepgram.com](https://console.deepgram.com/) |
| `CARTESIA_API_KEY` | Streaming text-to-speech. | `TTS_PROVIDER=cartesia` | [play.cartesia.ai/keys](https://play.cartesia.ai/keys) |

Missing keys don't stop the server — it starts and reports them. No call can be placed
until the ones your configuration needs are set.

**On the Google key:** create it fresh in AI Studio rather than reusing an old one. Google
now rejects unrestricted standard keys and blocks dormant ones; keys created in AI Studio
today are auth keys and are fine. A key in either bad state is tagged in the console.

### Optional

| Variable | Default | Notes |
|---|---|---|
| `LLM_PROVIDER` | `openai` | `openai` or `google` |
| `LLM_MODEL` | per provider | Blank picks the provider's default: `gpt-5-mini`, or `gemini-3.8-flash` |
| `GEMINI_THINKING_LEVEL` | `low` | Gemini only. `minimal`/`low`/`medium`/`high`. `low` is the floor for 3.8-flash and 3.7-flash — both reject `minimal` outright |
| `STT_PROVIDER` | `deepgram` | `deepgram` or `openai` |
| `TTS_PROVIDER` | `cartesia` | `cartesia` or `openai` |
| `TURN_DETECTION` | `smart` | `smart` = Smart Turn v3 semantic end-of-turn; `vad` = fixed silence threshold |
| `VAD_STOP_SECS` | `0.8` | Only read when `TURN_DETECTION=vad` |
| `LOG_LEVEL` | `INFO` | Pipecat's debug output is chatty enough to print key material |
| `AS_OF` | today, in India | Pins the date the 30 days are measured from, so a run is reproducible |
| `PORT` | `8080` | |

**Fewer accounts, more latency.** Setting `STT_PROVIDER=openai` and `TTS_PROVIDER=openai`
runs the whole system on `DAILY_API_KEY` and `OPENAI_API_KEY` alone. It works; it is
slower. OpenAI's TTS adds roughly 200–400ms per reply against Cartesia's sub-100ms
time-to-first-byte, which is a meaningful share of a one-second budget.

**Running on Gemini instead.** Set `LLM_PROVIDER=google` and fill in `GOOGLE_API_KEY`;
leave `LLM_MODEL` blank unless you want something other than `gemini-3.8-flash`. Nothing
else changes — the model is the only seam that moves, and Deepgram and Cartesia keep
handling speech.

Gemini 3 models think before answering. Those tokens cost latency on a call and bill at the
output rate, so `GEMINI_THINKING_LEVEL` is set explicitly rather than left to the model's
own default, for the same reason `VAD_STOP_SECS` is. Keep it as low as your model accepts:
`gemini-3.8-flash` and `gemini-3.7-flash` reject `minimal` with a 400 on the first turn, and
Pipecat 1.10.0 only knows to clamp 3.7, so it will forward a level the model refuses.

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

### Behavioural evals

`tests/` is deterministic and needs no model. How the agent *behaves* is checked
separately, by driving the real pipeline as text over Pipecat's eval transport — same
prompt, same tools, no microphone and no speech synthesised.

```bash
uv run python -m pipecat.evals suite evals/suite.yaml
```

That spawns a bot per scenario, drives it, and tears it down. Use `python -m` rather than
the `pipecat` script: the scenarios' judge lives in this repo at `evals/judge.py`, and only
`-m` puts the working directory on the import path.

To iterate on one scenario against a bot you keep running:

```bash
uv run python -m server.eval_bot --port 7860 --as-of 2026-09-01
uv run python -m pipecat.evals run evals/scenarios/the_month_does_not_work.yaml -v
```

Most scenarios judge *behaviour*, so they carry a natural-language `eval:` criterion
rather than an expected string. `numbers_come_from_the_planner` is the exception: every
fact in it is dated, which makes the plan computed from it determinate, so the figures the
assistant speaks are asserted literally with `text_contains` and never reach the judge at
all. Without it the suite could catch a regression in what the model *records* but not one
in what the planner *computes* — `tests/test_planner.py` checks the arithmetic, and this
checks that the answer reaches the user unchanged.

The judge follows `LLM_PROVIDER` too, so one switch moves the bot and its examiner
together and you can never end up grading a Gemini conversation with a provider you have
no credit for. It deliberately does *not* follow `LLM_MODEL`: a yardstick that moves when
you tune the thing being measured is not a yardstick.

Both the bot under test and the judge call a paid API, so the key for whichever provider
you selected needs credit on it. A suite run is roughly 82k input and 11k output tokens —
about 17 cents on `gemini-3.8-flash`.

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
