"""One call, one `Session`: the event log and everything derived from it.

`domain/` reads no clock, so `as_of` has to be passed in. It is decided once, in
`config`, and every planner call in the process gets it from this object — which
is also why pinning the date gives a scenario the same plan every run.

The session owns the only mutable state in the server. Tools append to its log;
cards are recomputed from the log and pushed when they actually change.
"""

import re
from collections.abc import Awaitable, Callable
from datetime import date

from server.domain.cards import build_cards
from server.domain.events import Event
from server.domain.gaps import Gap, rank_gaps
from server.domain.planner import PlanOutcome, plan
from server.domain.state import FinancialState, fold

Publisher = Callable[[dict], Awaitable[None]]


class Session:
    """The log for one conversation, plus the projections over it."""

    def __init__(self, as_of: date, publish: Publisher | None = None):
        self.as_of = as_of
        self.log: list[Event] = []
        # Which conversational turn we are on, so a fact can say when it was said.
        # Bumped by the pipeline, not by the tools — several facts can arrive in
        # one breath and they all belong to the same turn.
        self.turn = 0
        self.publish = publish
        self._sent: dict[str, str] = {}

    def record(self, *events: Event) -> None:
        self.log.extend(events)

    def state(self) -> FinancialState:
        return fold(self.log)

    def snapshot(self) -> tuple[FinancialState, PlanOutcome, tuple[Gap, ...]]:
        """State, plan and open questions from one fold, so they cannot disagree."""
        state = self.state()
        return state, plan(state, self.as_of), rank_gaps(state, self.as_of)

    def cards(self) -> dict[str, dict]:
        return build_cards(*self.snapshot())

    def new_fact_id(self, label: str) -> str:
        """A readable id derived from the label, so the model can refer back to it.

        The model never invents an id — it gets one back from the tool that
        recorded the fact. Ids stay stable and legible, which matters when the
        next thing that happens is a correction naming one out loud.
        """
        base = re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_") or "fact"
        taken = {f.fact_id for f in self.state().facts}
        if base not in taken:
            return base
        suffix = 2
        while f"{base}_{suffix}" in taken:
            suffix += 1
        return f"{base}_{suffix}"

    async def push_cards(self) -> list[str]:
        """Send every card whose content moved. Returns the ids actually sent.

        Diffing on the digest keeps an untouched card off the wire, so the UI can
        treat an arriving card as "this one changed" and highlight it.
        """
        if self.publish is None:
            return []
        changed = [c for c in self.cards().values() if self._sent.get(c["id"]) != c["digest"]]
        for card in changed:
            self._sent[card["id"]] = card["digest"]
            await self.publish({"type": "card", "card": card})
        return [c["id"] for c in changed]
