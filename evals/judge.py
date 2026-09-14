"""The judge the scenarios are graded by.

Pipecat's built-in judges are local models served by Ollama, which we do not
run. A `factory:` is how a scenario names any other provider without a key ever
appearing in a committed file — the scenario says which model, this says where
the key comes from.

The judge is deliberately not the model under test's own instance: it reads only
the bot's finished text and answers one yes-or-no question about it.
"""

import os
from typing import Any

DEFAULT_MODEL = "gpt-5-mini"


def openai(config: dict) -> Any:
    """Build the judge named by a scenario's `judge.eval` block."""
    from pipecat.services.openai.llm import OpenAILLMService

    return OpenAILLMService(
        api_key=os.environ.get("OPENAI_API_KEY", ""),
        settings=OpenAILLMService.Settings(model=config.get("model") or DEFAULT_MODEL),
    )
