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

**Why the judge is a Flash-Lite model and not the one under test.** The harness
caps the judge's reply at 200 tokens and offers no way to raise it — our factory
hands back a service, not the `EvalJudge`. Gemini 3 Flash counts thinking tokens
against that cap and will not think below `low`, so it truncated its own verdict
mid-JSON (`{"ver`) on a long conversation, which reads as a failed judge call
rather than as a verdict. The Flash-Lite models accept `minimal` and answer well
inside the budget. Measured, not assumed.

That the examiner is then a different model from the one under test is a
happy side effect: judging a model with one from its own family shares blind
spots. The remaining overlap is acceptable because every criterion in
`scenarios/` asks about something observable — did it state a figure, did it
claim to have contacted a lender — rather than about subtle quality.
"""

from typing import Any

from server.config import DEFAULT_LLM_MODELS, config

# Paired deliberately: the level is hard-coded because the model is too, and the
# two were verified together. A scenario overriding `model:` must pick one that
# accepts `minimal` — Gemini 3 Flash does not, and says so with a 400.
JUDGE_MODELS = {"google": "gemini-3.5-flash-lite", "openai": "gpt-5-mini"}
JUDGE_THINKING = "minimal"


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
                thinking=GoogleLLMService.ThinkingConfig(thinking_level=JUDGE_THINKING),
            ),
        )

    if config.llm_provider == "openai":
        from pipecat.services.openai.llm import OpenAILLMService

        return OpenAILLMService(
            api_key=config.openai_api_key,
            settings=OpenAILLMService.Settings(model=model),
        )

    raise ValueError(f"no judge for LLM_PROVIDER: {config.llm_provider!r}")
