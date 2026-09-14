"""`FinancialState` — the fold of the event log, and the only thing the planner reads.

Every card is a projection of this one object, so two cards disagreeing with
each other is not a bug we have to avoid: it is unrepresentable.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace

from server.domain.events import (
    ArrangementConfirmed,
    Bounds,
    ConflictFlagged,
    ConflictResolved,
    Event,
    Fact,
    FactCorrected,
    FactRecorded,
    FactRetracted,
    Kind,
)
from server.domain.money import Money


@dataclass(frozen=True)
class Revision:
    """A superseded value, kept so a card can say "18,000 (corrected from 15,000)"."""

    amount: Money | None
    day: int | None
    verbatim: str
    turn: int


@dataclass(frozen=True)
class Conflict:
    conflict_id: str
    fact_ids: tuple[str, ...]
    note: str = ""
    resolved_with: str | None = None

    @property
    def open(self) -> bool:
        return self.resolved_with is None


@dataclass(frozen=True)
class FinancialState:
    facts: tuple[Fact, ...] = ()
    conflicts: tuple[Conflict, ...] = ()
    history: Mapping[str, tuple[Revision, ...]] = None  # type: ignore[assignment]
    version: int = 0

    def __post_init__(self) -> None:
        if self.history is None:
            object.__setattr__(self, "history", {})

    def of_kind(self, *kinds: Kind) -> tuple[Fact, ...]:
        return tuple(f for f in self.facts if f.kind in kinds)

    def get(self, fact_id: str) -> Fact | None:
        return next((f for f in self.facts if f.fact_id == fact_id), None)

    @property
    def open_conflicts(self) -> tuple[Conflict, ...]:
        return tuple(c for c in self.conflicts if c.open)

    def planning_facts(self) -> tuple[Fact, ...]:
        """What the planner may use. Facts locked in an open conflict are collapsed
        into a single fact carrying the disputed range, so nothing is double-counted."""
        contested = {fid: c for c in self.open_conflicts for fid in c.fact_ids}
        out: list[Fact] = []
        done: set[str] = set()
        for fact in self.facts:
            conflict = contested.get(fact.fact_id)
            if conflict is None:
                out.append(fact)
            elif conflict.conflict_id not in done:
                done.add(conflict.conflict_id)
                out.append(self._collapse(conflict))
        return tuple(out)

    def pinned(self) -> "FinancialState":
        """Conflicts flattened into ordinary facts. The basis for what-if probes."""
        return replace(self, facts=self.planning_facts(), conflicts=())

    def replacing(self, fact_id: str, **changes) -> "FinancialState":
        facts = tuple(replace(f, **changes) if f.fact_id == fact_id else f for f in self.facts)
        return replace(self, facts=facts)

    def _collapse(self, conflict: Conflict) -> Fact:
        """One fact standing for a contradiction.

        The point estimate is the pessimistic end — the larger outflow, the
        smaller or later income — because a conflict, unlike an estimate, has no
        centre to plan from. The range it carries is what makes `gaps` rank the
        clarifying question, so this never becomes a silent choice.
        """
        members = [f for f in (self.get(fid) for fid in conflict.fact_ids) if f is not None]
        amounts = [f.amount for f in members if f.amount is not None]
        days = [f.day for f in members if f.day is not None]
        head = members[0]
        inflow = head.kind in ("income", "cash_on_hand")
        return replace(
            head,
            amount=(min(amounts) if inflow else max(amounts)) if amounts else None,
            amount_bounds=Bounds(min(amounts), max(amounts)) if len(set(amounts)) > 1 else None,
            day=(max(days) if inflow else min(days)) if days else head.day,
            day_bounds=Bounds(min(days), max(days)) if len(set(days)) > 1 else head.day_bounds,
        )


def fold(events: Sequence[Event]) -> FinancialState:
    """Replay the log. This is the only way a `FinancialState` is ever built."""
    facts: dict[str, Fact] = {}
    history: dict[str, tuple[Revision, ...]] = {}
    conflicts: dict[str, Conflict] = {}

    for event in events:
        match event:
            case FactRecorded(fact=fact):
                facts[fact.fact_id] = fact

            case FactCorrected(fact_id=fact_id):
                previous = facts.get(fact_id)
                if previous is None:
                    continue
                history[fact_id] = (
                    *history.get(fact_id, ()),
                    Revision(previous.amount, previous.day, previous.verbatim, previous.turn),
                )
                facts[fact_id] = replace(
                    previous,
                    amount=previous.amount if event.amount is None else event.amount,
                    day=previous.day if event.day is None else event.day,
                    # A correction is the user stating the number, so it supersedes
                    # whatever range we were carrying for the field they corrected.
                    amount_bounds=None if event.amount is not None else previous.amount_bounds,
                    day_bounds=None if event.day is not None else previous.day_bounds,
                    verbatim=event.verbatim or previous.verbatim,
                    turn=event.turn or previous.turn,
                )

            case FactRetracted(fact_id=fact_id):
                facts.pop(fact_id, None)

            case ArrangementConfirmed(fact_id=fact_id):
                previous = facts.get(fact_id)
                if previous is not None:
                    facts[fact_id] = replace(previous, part_payment=event.accepts)

            case ConflictFlagged(conflict_id=conflict_id):
                conflicts[conflict_id] = Conflict(conflict_id, event.fact_ids, event.note)

            case ConflictResolved(conflict_id=conflict_id, chosen_fact_id=chosen):
                existing = conflicts.get(conflict_id)
                if existing is None:
                    continue
                conflicts[conflict_id] = replace(existing, resolved_with=chosen)
                for fact_id in existing.fact_ids:
                    if fact_id != chosen:
                        facts.pop(fact_id, None)

    return FinancialState(
        facts=tuple(facts.values()),
        conflicts=tuple(conflicts.values()),
        history=history,
        version=len(events),
    )
