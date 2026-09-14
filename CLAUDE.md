# FinVoice

Voice agent for 30-day personal financial planning.
Read `SPEC.md` for the brief, `BUILD-PLAN.md` for the design.

---

## Inviolable rules

### 1. The LLM never does arithmetic

No number reaches the user unless a tool computed it. The model extracts facts and
narrates results — nothing else. If you find yourself writing a prompt that asks the
model to add, subtract, compare, or total anything, stop: that logic belongs in
`server/domain/planner.py`.

This is the architectural thesis of the whole submission. Do not erode it for
convenience.

### 2. Money is `int` paise. Never float

Convert rupees → paise at the boundary, once. Rounding happens in `domain/money.py` and
nowhere else. No `float` in any financial path.


### 3. Never commit secrets

`.env` is gitignored. `.env.example` holds names and comments, never values. Check log
verbosity before any recording — Pipecat is chatty at debug level.

### 4. Do not push

Commit locally when asked. Never `git push`.

---

## Pipecat — use the 1.x API

Pinned: **`pipecat-ai==1.10.0`**, Python 3.12.

Pipecat 1.0 was a large breaking release. Most training data and most blog posts show
the pre-1.0 API. **If a snippet looks familiar, it is probably wrong.** Verify against
the pinned version's own examples: `github.com/pipecat-ai/pipecat/tree/main/examples`.

| Do not use | Use |
|---|---|
| `PipelineTask`, `PipelineRunner` | `PipelineWorker`, `WorkerRunner` |
| `OpenAILLMContext`, `AnthropicLLMContext` | `LLMContext` |
| `llm.create_context_aggregator(ctx)` | `LLMContextAggregatorPair(ctx)` |
| `LLMMessagesFrame` | `LLMContextFrame`, or `LLMRunFrame` to kick off |
| `StartInterruptionFrame` | `InterruptionFrame` |
| `PipelineParams(allow_interruptions=...)` | turn strategies on `LLMUserAggregatorParams` |
| `DailyParams(vad_enabled=, vad_analyzer=)` | `vad_analyzer` on `LLMUserAggregatorParams` |
| `from pipecat.services.openai import ...` | `from pipecat.services.openai.llm import ...` |
| `pipecat.transports.services.daily` | `pipecat.transports.daily.transport` |
| `llm.register_function(...)` | direct functions in `LLMContext(tools=[...])` |
| `camera_in_enabled` | `video_in_enabled` |

**Silent-failure trap:** removed parameters are *ignored, not errored*. Passing
`vad_analyzer` to `DailyParams` will not raise — it will just never run VAD. Never
assume a config took effect because it didn't crash.

**`VADParams.stop_secs` default changed 0.8 → 0.2.** Our users pause mid-sentence while
recalling numbers. Never accept the default.

### Pipeline shape

```python
pipeline = Pipeline([
    transport.input(),
    stt,
    user_aggregator,      # SmartTurn v3 + Silero VAD live here
    llm,
    tts,
    transport.output(),
    assistant_aggregator, # after output, so history == what was actually spoken
])
```

`build_pipeline(transport, session)` takes the transport as a parameter so the same
pipeline runs under `DailyTransport` in production and `EvalTransport` under
`pipecat eval run`. **Never inline a transport into the pipeline builder** — that would
cost us the eval path.

---

## Code standards

- **Keep it short.** The brief says so and the live session depends on it. Every file
  should be explainable in one sentence.
- `domain/` is pure: no I/O, no network, no async, no clock reads. `as_of` is passed in.
  This is what makes it testable and is the reason the tests need no LLM.
- Type hints on every domain function. They are the documentation.
- Prefer a plain function over a class. Prefer a dataclass over a framework.
- No new dependency without a reason you would defend out loud.
- Match the file's existing style. Comment density: low — comment *why*, never *what*.

## Testing

- `tests/` is rule-based and deterministic: no LLM, no network, no sleep.
- `evals/scenarios/*.yaml` is LLM-judged behaviour via `pipecat eval run`.
- Keep those two separate. The separation is itself a graded item (SPEC §8, Track B).
- Every bug found by hand becomes a permanent test.

## Voice output rules

Enforced in `server/prompt.py`:

- No markdown, no bullets, no headers — they get read aloud as noise.
- Two or three sentences per turn. One question at a time.
- Numbers spelled for speech: "eighteen thousand rupees", never `₹18,000`.
  TTS renders the symbol unreliably.
- Read amounts back for confirmation. STT confuses fifteen/fifty and mangles
  lakh/crore; the read-back is a correctness mechanism.
- Cards carry the density. Speech stays short.

## Prohibited agent behaviours (SPEC §4)

The assistant must never invent numbers, promise lender approval, invent settlement or
repayment offers, recommend taking another loan, or claim an action is done when it is
not. Encode these as explicit negative constraints in the prompt, and cover them with
eval scenarios — a prompt rule with no test is a wish.

## Locale

India / INR. Handle "lakh" and "crore" in STT output. Speak amounts in natural Indian
English. Dates as day-of-month ("the fifth", "the twenty-fifth").

## Frontend

React + Vite, `@pipecat-ai/client-react`, Pipecat UI components via
`npx shadcn@latest add @pipecat/...`. Cards are hand-built. Card state arrives through
`onServerMessage` — never recompute a number client-side, only render what the server
sent.

## Running

**The backend cannot run natively on Windows.** `daily-python` publishes wheels only for
`manylinux_2_28_{x86_64,aarch64}` and macOS — there is no `win_amd64` build. `uv sync` on
a Windows host fails at resolution, not at runtime. Use Docker or WSL; never debug this
as if it were a local environment problem.

```bash
docker compose up --build     # the only supported start command; serves :8080
```

Tests and lint run outside the container — the image deliberately contains no tests and
no dev tooling (`.dockerignore` excludes `tests/` and `evals/`; the runtime venv is built
with `--no-dev`). Keep it that way.

```bash
uv sync --group dev
uv run pytest -q
uv run ruff check .
pipecat eval run evals/scenarios/*.yaml   # behavioural evals
```

On a Windows host, run these from a Linux environment (WSL or the equivalent) and point
`UV_PROJECT_ENVIRONMENT` at a native Linux path — a venv is thousands of small files and
resolving it across the Windows mount is slow.

`uv.lock` is resolved on Linux and committed. Do not regenerate it on Windows.

No second terminal may ever be required to start the app. That is a hard submission
requirement.
