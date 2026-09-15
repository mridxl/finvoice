# SPEC — Riverline AI Engineer assignment

Source: https://riverline.notion.site/engineering-assignment
This file is the authoritative restatement of the brief.
---

## 1. The problem

Build a **real-time voice assistant that helps a person plan their finances for the
next 30 days.**

The person may have:

- Multiple loans and credit-card payments
- Income arriving on different dates
- Essential household expenses
- Optional expenses
- Missing or uncertain information
- Conflicting numbers
- More payments than they can afford

The assistant must understand the situation, ask the right questions, perform the
calculations, and produce a realistic plan. **English only.**

---

## 2. Mandatory stack

- **Pipecat**
- **Daily**

The conversation must be **real-time**. It cannot work as a series of recorded voice
messages.

---

## 3. What must be built

### 3.1 Web application

The user can:

- Start and end a voice conversation
- Speak naturally with the assistant
- See useful information generated during the conversation
- Review the final financial plan

### 3.2 Real-time voice agent

The agent must:

- Ask questions based on the conversation
- Avoid following a fixed questionnaire
- Remember information already provided
- Ask for clarification when information conflicts
- Allow the user to correct previous information
- Avoid presenting guesses as facts
- Explain the final plan simply
- Confirm that the user understands the plan

### 3.3 Generative cards

Cards appear or update **during** the conversation. Candidate cards named in the brief:

- Income
- Available money
- Essential expenses
- Loan and credit-card payments
- Missing information
- Upcoming payment dates
- Monthly shortfall or surplus
- Proposed actions
- Final plan

We decide which are useful and when they appear.

> **Hard requirement:** cards must remain consistent with the conversation. If the user
> corrects an amount, **every affected card and calculation must update.**

### 3.4 Financial plan

The plan may:

- Show the shortfall or surplus
- Prioritise upcoming payments
- Suggest changes to optional expenses
- Account for **when** income and payments occur
- Build a practical 30-day plan
- **Clearly explain when the situation cannot be solved** using the available money

> **Hard requirement:** the calculations must be **visible and testable**.

---

## 4. Prohibitions — the assistant must not

1. Invent numbers
2. Promise loan or lender approval
3. Invent settlement or repayment offers
4. Recommend taking another loan
5. Claim that an action has been completed when it has not

---

## 5. Decision journal — mandatory

**Written entirely by the candidate. Handwritten or typed.**

AI must not be used to write, rewrite, improve, summarise, or paraphrase it.

> **AI-generated journal content disqualifies the submission.
> A missing journal also disqualifies the submission.**

Grammar and presentation are not evaluated.

For each important decision, record:

- Approximate date and time
- What happened
- What you noticed
- Options you considered
- What you decided and why
- What you tested
- What changed your mind
- AI suggestions you rejected or corrected
- Limitations you accepted

Entries are written **while working**, not only after completion.

---

## 6. Submission

Via the Riverline engineering assignment submission form.

- Source-code repository
- README with Docker setup, environment variables, local web address
- Short product demo video
- Decision journal
- Test and evaluation results
- A short list of: what works / what does not work / what you would build next /
  where AI helped / where AI produced incorrect or poor work

### Startup contract

Deployment is not required. The complete application must start with **one command**:

```bash
docker compose up --build
```

After it completes, the web app must be reachable at the local address given in the
README. **Starting the agent backend or web application must not require extra commands
in separate terminals.**

Also required:

- `.env.example` containing **every** required environment variable
- README explaining: what each variable is for, which are required, how the reviewer
  provides API keys, the exact start command, the exact local address
- **No committed API keys or secrets**

---

## 7. Evaluation criteria

- Does the product work end to end?
- Does the agent ask useful questions?
- Are the calculations correct?
- Is the financial plan realistic?
- Does the system handle corrections and missing information?
- Do the voice experience and cards remain consistent?
- Did you understand the code you submitted?
- Did you make sensible trade-offs?
- Did you test the important parts?
- Is the implementation simple enough to understand and extend?

> "We care more about one strong, complete journey than many unfinished features."

General guidance from the brief: **keep code short and concise**; there are no right
answers, approach matters more than correctness; make suitable assumptions where things
are undefined.

---

## 8. Optional depth — choose ONE, not both

### Track A: Conversational intelligence

Better follow-up questions; handling corrections naturally; handling interruptions;
avoiding repeated questions; knowing when enough information has been collected;
explaining difficult outcomes clearly; checking the user actually understands the plan;
adapting instead of scripting. **Show real conversations.**

### Track B: Evaluation and regression testing

Different user scenarios; measuring conversation quality; checking financial
calculations; testing missing and conflicting information; separating rule-based checks
from LLM-based evaluation; turning failures into permanent tests; comparing agent
versions; explaining where the evaluation method may be wrong. **Show at least one
failure found, the change made, and evidence the change improved the system.**

---

## 9. The framing that sets the bar

> "We are not testing whether you can produce code. We are testing whether you
> understand what you built, can defend your decisions under live questioning, can
> modify your system under novel constraints on the spot, and made genuine engineering
> trade-offs that reflect judgment, not generation."

The submission is followed by a **live technical session with no AI assistance**.
If the codebase cannot be navigated fluently, the methodology explained, and the system
adapted live, submission quality is irrelevant.

Reference: a Riverline product demo video is linked in the brief. Treat it as a
reference for expectations only — real-time voice, useful cards, a clear financial
outcome. **Do not copy its interface, questions, or conversation flow.**

---

## 10. Locked decisions

Settled for this build.

| # | Decision | Choice |
|---|---|---|
| 1 | Numeric authority | LLM never does arithmetic; a pure planner owns every number |
| 2 | Server scaffolding | Hand-rolled FastAPI, not the Pipecat dev runner |
| 3 | Eval transport | Kept available — `build_pipeline(transport)` takes transport as a parameter |
| 4 | Card channel | RTVI server messages over Daily's data channel |
| 5 | Frontend | Pipecat UI (shadcn) + `@pipecat-ai/client-react` |
| 6 | Turn detection | Smart Turn v3 (semantic), not fixed-threshold VAD |
| 7 | Locale | India / INR, with lakh-crore handling |
| 8 | Ports | Single port, single container, `docker compose up --build` |

## 11. Late decisions

Open when the build started, weighed on evidence rather than up front, and settled.

| # | Question | Outcome |
|---|---|---|
| A | STT / TTS / LLM providers | **Deepgram STT, Cartesia TTS, OpenAI LLM**, each swappable by env var — latency and cost per default in BUILD-PLAN §7.1 |
| B | Optional track A or B | **Track B**, 2026-09-15 — see `evals/RESULTS.md` and BUILD-PLAN §6 |
