# What works, what doesn't, what's next

An honest account of the state of this build. `evals/RESULTS.md` has the evidence behind the
eval claims; `journal.md` has the decisions as they were made.

---

## What works

- **The whole call, one command.** `docker compose up --build`, one port, no second
  terminal. Browser connects, the bot joins and talks, the plan builds on screen beside it.
- **The model never does arithmetic.** Every number the user hears came out of
  `server/domain/planner.py` as words. This is not a prompt rule — it is the tool surface.
  There is no path for the model to produce a digit. 152 unit tests cover the planner and
  none of them need an LLM.
- **Corrections ripple.** "Sorry, fourteen not thirteen" moves every figure that depends on
  it, because the cards are a projection of an event log rather than state the model keeps.
- **Contradictions get raised, not silently resolved.** Two figures for the same EMI and it
  puts them side by side and asks which is right.
- **The completeness sweep.** One rent is not what the month costs, so a category closes
  only when the user says it is complete. On the second demo call this caught ₹27,300 of
  outgoings an earlier build would have planned without.
- **Infeasible is a return type, not a branch.** When the month does not work it says so
  first, names the one payment that goes unpaid and why that one, and suggests talking to
  the lender — never a figure, never "they'll probably agree".
- **Thirty days from today, stated out loud up front**, with the month named on any date
  that crosses into the next one. Before that fix the agent narrated "the twentieth" and
  "the fifth" as though the fifth came first.
- **Ten LLM-judged eval scenarios, green.** `evals/RESULTS.md` records the day they went
  from nothing passing to 9/9, and what each of the seven failures actually was.

## What doesn't work

- **Dead air.** One call went silent and never recovered. INFO logs show the user's second
  utterance produced no transcript at all. Not yet reproduced at DEBUG, and there is no idle
  handler — so a bot that goes quiet stays quiet.
- **The plan half of the dashboard is the least-exercised part of the UI.** Reaching it
  requires closing all four categories, which takes a full intake; it has mostly been
  rendered from a fixture.
- **Latency is honest but not fast.** Room mint ~2s, Daily join ~3.4s, Deepgram sockets
  ~2.3s, and the first reply after that.
- **Reasoning is off entirely on OpenAI.** Not a tuning choice — `gpt-5.6-luna` refuses
  function tools on `/v1/chat/completions` at any effort above `none`, and every turn here
  carries tools. The model reads tool results and narrates; it does not think. For this job
  that is fine. It would not be a general-purpose choice.
- **Lakh and crore are boosted for speech recognition but untested by voice.** (for Deepgram) The demo
  persona never says them.
- **One run per eval scenario.** `-r 3` exists and has not been run since the prompt
  changed. A model at `effort=none` is not deterministic.
- **The judge is the same model as the bot.** Same family, same blind spots. Tolerable
  because every criterion asks about something observable rather than about quality, but it
  is a real limit.

## What I'd build next

- A user-idle handler, so silence becomes "sorry, I didn't catch that" instead of nothing.
- Two annotated transcripts in the repo. The conversational behaviours are all built — the
  sweep, the anchored questions, the comprehension check — but nothing here *shows* a
  conversation.
- A flakiness sweep in CI, and a second persona. The timing trap in `tests/golden.py` is
  already a fixture: feasible on monthly totals, broken on dates.
- A scenario for `record_lender_answer`, which currently has a tool and a prompt section
  and no test.

## Where AI helped

- **The domain design.** Integer paise, an append-only event log, a pure planner with
  `as_of` passed in, and gap ranking as the stopping criterion. It came out testable without
  a model in the loop, which is what made everything downstream checkable.
- **Diagnosis by instrumentation instead of by reading.** The 20-second setup timeout: three
  hypotheses argued from surrounding log lines, all three wrong; dumping the await chain of
  every task mid-hang found it in one look. The Cartesia leak: one scenario at DEBUG, five
  `Generating TTS` lines, done.
- **Turning eval failures into named causes and permanent tests.** Seven findings from one
  run — one of which was that the *question ranking itself* was wrong and the model had been
  obeying it correctly.
- **Verification when pushed.** Told it was hallucinating the OpenAI reasoning restriction,
  it came back with the model page, the reasoning guide, and OpenAI's own forum reply.

## Where AI produced incorrect or poor work

- **"The evals don't bill Cartesia."** Stated as confirmed fact. It cost three rotated API
  keys before the leak was found. It had read INFO logs that say nothing about synthesis and
  a usage dashboard that lags.
- **The mute-button fix** was built on a wrong premise — the UI kit was already optimistic —
  and would have masked the real bug for 1.5 seconds and then shown it again. The actual
  cause was daily-js event ordering, found only after reading the code instead of the notes.
- **`OPENAI_REASONING_EFFORT=low` as the default**, chosen from OpenAI's own guidance and
  measured for latency with no tools attached. First eval run after that: nothing passed.
- **The eval judge left on `gpt-5-mini`** with nothing pinned. It reasoned its way past the
  verdict budget and returned empty verdicts on seven of eight scenarios.
- **`speak_date` dropped the month** on a premise its own docstring asserted, and that was
  false on 29 days out of 30.
- **The first dashboard** had tabs that switched under the reader mid-sentence, and a chart
  that painted a balance of exactly zero in the colour for a shortfall.
- Every one of these was caught by a test, an eval, a credit balance, or by hand. None were
  caught by the model re-reading its own work.
