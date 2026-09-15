"""The judge the scenarios are graded by.

Pipecat's built-in judges are local models served by Ollama, which we do not
run. A `factory:` is how a scenario names any other provider without a key ever
appearing in a committed file — the scenario says nothing about credentials,
this says where they come from.

The judge follows `LLM_PROVIDER`, so one switch moves the bot and its examiner
together; there is no way to end up grading a Gemini conversation with a
provider you have no credit for. It deliberately does *not* follow `LLM_MODEL`.
A yardstick that moves whenever you tune the thing being measured is not a
yardstick, so the judge runs the model named below and a scenario that genuinely
wants another says so with `model:` in its own `judge.eval` block.

**Why the Gemini judge is Flash-Lite and not the model under test.** The
harness caps the judge's reply at 200 tokens and offers no way to raise it — our
factory hands back a service, not the `EvalJudge`. Gemini 3 Flash counts
thinking tokens against that cap and will not think below `low`, so it truncated
its own verdict mid-JSON (`{"ver`) on a long conversation, which reads as a
failed judge call rather than as a verdict. Flash-Lite accepts `minimal` and
answers well inside the budget. Measured, not assumed.

**Why the OpenAI judge is the bot's own model.** The same cap, the same trap:
`gpt-5-mini` with nothing pinned reasoned the whole budget away and returned an
empty verdict on seven scenarios out of eight. The bot already runs
`gpt-5.6-luna` with reasoning off, validated at startup, and a judge that reads
a transcript and writes one line of JSON needs no more thought than that. So it
reuses the bot's default model and the bot's validated effort — one model table
and one setting to be wrong about, not three.

The examiner sharing a family with the examinee shares its blind spots. That is
acceptable because every criterion in `scenarios/` asks about something
observable — did it state a figure, did it claim to have contacted a lender —
rather than about subtle quality.
"""

from typing import Any

from server.config import DEFAULT_LLM_MODELS, config

# Gemini only. Paired deliberately: the level is hard-coded because the model
# is too, and the two were verified together. A scenario overriding `model:`
# must pick one that accepts `minimal` — Gemini 3 Flash does not, and says so
# with a 400. OpenAI has no entry here on purpose: its judge is the bot's
# default, see the module docstring.
JUDGE_MODELS = {"google": "gemini-3.5-flash-lite"}
GEMINI_JUDGE_THINKING = "minimal"


def from_env(block: dict) -> Any:
    """Build the judge for whichever provider the bot is running on.

    Args:
        block: The scenario's `judge.eval` mapping. An optional `model:` pins the
            judge to a specific model instead of this provider's judge default.
    """
    model = block.get("model") or JUDGE_MODELS.get(
        config.llm_provider, DEFAULT_LLM_MODELS.get(config.llm_provider, "")
    )

    if config.llm_provider == "google":
        from pipecat.services.google.llm import GoogleLLMService

        return GoogleLLMService(
            api_key=config.google_api_key,
            settings=GoogleLLMService.Settings(
                model=model,
                # Only the one-line JSON verdict is ever read, so thinking buys
                # nothing here and competes with the verdict for the 200 tokens
                # the harness allows — see the module docstring.
                thinking=GoogleLLMService.ThinkingConfig(thinking_level=GEMINI_JUDGE_THINKING),
            ),
        )

    if config.llm_provider == "openai":
        from pipecat.services.openai.llm import OpenAILLMService

        return OpenAILLMService(
            api_key=config.openai_api_key,
            settings=OpenAILLMService.Settings(
                model=model,
                # Same value, same reason, same catch-all as `providers.py`.
                extra={"reasoning_effort": config.reasoning_effort},
            ),
        )

    raise ValueError(f"no judge for LLM_PROVIDER: {config.llm_provider!r}")
