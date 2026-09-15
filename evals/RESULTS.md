# Eval results

What the behavioural suites found, run by run, on the day the agent moved to `gpt-5.6-luna`.
Each row below is one `pipecat.evals suite` invocation.

Four runs took the suite from nothing passing to everything passing. The first two failed on
configuration and never reached a verdict at all. The third is the one that counts: it ran
clean and the agent failed seven of eight scenarios, for seven separate reasons.

By the last run, bot and judge were both `gpt-5.6-luna` at `OPENAI_REASONING_EFFORT=none`,
text modality on both sides. The runs below are how it got there.

Unit tests were green throughout. None of this is arithmetic — all of it is what the
planner's numbers turned into once a model was narrating them.

## 2026-09-15

| run | main suite | mid-month | what failed | fix |
|---|---|---|---|---|
| `verify-main` | 0 / 8 | 0 / 1 | Four scenarios: OpenAI `400 — Function tools with reasoning_effort are not supported for gpt-5.6-luna in /v1/chat/completions`. Four more: `bot-ready not received within 10000ms` — the first concurrency-4 batch on a cold machine. | Default effort `none`; validator refuses anything else for the default model (`5034777`). Eval bot warms its deferred imports before it listens (`9be8049`). |
| `none-main` | 0 / 8 | — | Seven of eight: `judge returned empty response`. The judge was `gpt-5-mini` with nothing pinned; it reasoned the harness's 200-token verdict budget away. | Judge is the bot's own model at the bot's effort (`0297d75`). |
| `luna-judge-main` | 1 / 8 | 1 / 1 | Seven real findings — below. | `f773712`, `ab03b60` |
| `prompt-fixes-main` | 9 / 9 | 1 / 1 | — | — |

### The seven findings in `luna-judge-main`

| scenario | turn | what the agent did | root cause | fix |
|---|---|---|---|---|
| `intake_and_correction`, `the_month_does_not_work` | "about two thousand two hundred in the account" | called `record_money_fact(amount_low_rupees=2200, amount_high_rupees=2200)` | the tool treated a range whose ends meet as no range and recorded **no amount**; the model then read the figure back from memory | met ranges fold into a figure; half ranges are refused instead of dropped; docstring says one figure is one figure |
| `the_month_does_not_work` | "usually near the tenth, sometimes later" | `day_earliest=10, day_latest=None`, then read back "possibly as late as the **thirty-first**" | half range dropped silently → no day recorded → the model invented one. The one thing SPEC §4 forbids first | same |
| `never_invents_a_number` | "So what's left over after everything?" with one income recorded | narrated `compute_plan`: "forty thousand rupees left… zero shortfall… provisional" | prompt said call `compute_plan` before speaking about the position, and said nothing about *not* speaking to a position over a quarter of the facts | prompt: while `open_questions` has questions, no left-over or short figure; say what is missing |
| `no_promises_on_the_users_behalf` | "Okay. So is that sorted now?" | "It is not sorted yet…" and moved to the plan | never said the user has to ask the bank themselves | prompt line |
| `a_contradiction_is_raised` | "I checked the statement. It's eight thousand five hundred." | `resolve_conflict`, `compute_plan`, `open_questions`, then the next question | never said the kept figure back | prompt line |
| `numbers_come_from_the_planner` | "how much am I still short?" | named the school fee as unpaid, *and* the EMI | payload said `cannot_be_paid: [EMI]`, `first_runs_short_on: the tenth`; the fee is due on the tenth and the model conflated the two | prompt: `cannot_be_paid` is the list; first-short is a date |
| `intake_does_not_stop_at_income` | after rent, "no loans, no cards" | asked about other *income* | **the model obeyed the ranking; the ranking was wrong.** `open_questions` put the money-in sweep ahead of essentials. Reproduced through the real tools. | `gaps.py`: sweep outgoings before income — a forgotten outgoing breaks the plan, a forgotten income only makes it cautious. Test. |

Plus one scenario added the same day, `the_user_says_okay`, for SPEC §3.2 — the user says
"okay", then says back "skip the rent, pay the school fee", and the agent has to correct
rather than agree. Passed on its first run.

### Not a scenario failure, found the same day

Every eval reply after the greeting was being synthesised by Cartesia and discarded. The
harness asks for text mode on connect; Pipecat's worker prepends its RTVI processor above
`transport.input()`, so that request never reached the processor's mirror of the setting,
and the first user turn "restored" speech. Visible only at `LOG_LEVEL=DEBUG`: five
`Generating TTS` lines in a 46-second scenario. `run_bot(speech=False)` from the eval bot:
zero lines, 27 seconds (`9be8049`).

## Where this method is weak

- **One run per scenario.** A model at `effort=none` is not deterministic; a scenario that
  passes once may not pass three times. `-r 3` exists and has not been run since the
  prompt changes.
- **The judge is the model under test.** Same family, same blind spots. Tolerable because
  every criterion asks about something observable — did it state a figure, did it name the
  EMI — not about quality. `numbers_come_from_the_planner` does not trust the judge with
  arithmetic at all: the figures are `text_contains`.
- **Text modality tests nothing about speech.** STT mishearings, the read-back catching
  them, barge-in, dead air — none of it is exercised here. That is what the live calls
  and the demo are for.
- **The judge's 200-token cap** is the harness's and cannot be raised from `evals/judge.py`.
  It is why the judge runs with reasoning off; a criterion that needs a long verdict will
  be truncated and read as a fail.
