"""Which missing piece is worth asking about — measured, not guessed.

For every uncertain fact we re-run the planner at both ends of its range and
compare the outcomes. If nothing moves, the question is not worth a turn of
conversation; if the answer flips whether a bill gets paid, it is the next thing
we ask. This is the stopping criterion too: when no remaining gap changes the
outcome, we have enough information.

The planner decides *what* to ask. The model only decides how to phrase it.
"""

from dataclasses import dataclass
from datetime import date
from typing import Literal

from server.domain.events import Bounds, Fact
from server.domain.money import format_rupees, from_rupees
from server.domain.planner import PlanOutcome, plan
from server.domain.state import FinancialState

# A swing smaller than this is noise in a household budget, not a question.
MATERIAL = from_rupees(1000)

Impact = Literal["high", "medium", "low"]
_ORDER: dict[Impact, int] = {"high": 0, "medium": 1, "low": 2}


@dataclass(frozen=True)
class Gap:
    fact_id: str
    label: str
    field: Literal["amount", "day"]
    impact: Impact
    why: str
    low: int | None = None
    high: int | None = None
    swing: int = 0


def rank_gaps(state: FinancialState, as_of: date) -> tuple[Gap, ...]:
    """Open questions, most decision-changing first. Gaps that change nothing are absent."""
    probe = state.pinned()
    contested = {fid for c in state.open_conflicts for fid in c.fact_ids}
    found: list[Gap | None] = []

    for fact in probe.facts:
        if fact.amount is None:
            found.append(
                Gap(
                    fact.fact_id,
                    fact.label,
                    "amount",
                    "high",
                    "no amount recorded, so it is missing from the plan entirely",
                )
            )
            continue
        disputed = fact.fact_id in contested
        if fact.amount_bounds is not None:
            found.append(_probe(probe, as_of, fact, "amount", fact.amount_bounds, disputed))
        if fact.day_bounds is not None:
            found.append(_probe(probe, as_of, fact, "day", fact.day_bounds, disputed))

    live = [gap for gap in found if gap is not None]
    return tuple(sorted(live, key=lambda g: (_ORDER[g.impact], -g.swing, g.fact_id)))


def _probe(
    state: FinancialState, as_of: date, fact: Fact, field: str, bounds: Bounds,
    disputed: bool = False,
) -> Gap | None:
    low = plan(_pin(state, fact, field, bounds.low), as_of)
    high = plan(_pin(state, fact, field, bounds.high), as_of)
    verdict = _classify(low, high)
    if verdict is None:
        if not disputed:
            return None
        # A contradiction is not an uncertainty. An estimate that changes nothing
        # is not worth a turn of conversation, but two different figures for the
        # same thing mean our record of what was said is wrong until it is
        # settled — so it is always raised, just never ahead of a question that
        # changes the outcome.
        verdict = ("low", "you gave two different figures for this")
    impact, why = verdict
    return Gap(
        fact.fact_id, fact.label, field, impact, why, bounds.low, bounds.high,
        swing=abs(low.lowest - high.lowest),
    )


def _pin(state: FinancialState, fact: Fact, field: str, value: int) -> FinancialState:
    if field == "amount":
        return state.replacing(fact.fact_id, amount=value, amount_bounds=None)
    return state.replacing(fact.fact_id, day=value, day_bounds=None)


def _classify(low: PlanOutcome, high: PlanOutcome) -> tuple[Impact, str] | None:
    """Rank by what actually changes, in the order a person would care about it."""
    if low.status != high.status:
        return "high", f"it decides the outcome: {low.status} one way, {high.status} the other"
    if _ids(low.unpaid) != _ids(high.unpaid):
        return "high", "it changes which payments go unmet"
    swing = abs(low.lowest - high.lowest)
    if swing >= MATERIAL:
        return "medium", f"it moves the tightest point of the month by {format_rupees(swing)}"
    if _ids(low.cuts) != _ids(high.cuts):
        return "low", "it only changes what gets trimmed"
    return None


def _ids(actions) -> tuple[str, ...]:
    return tuple(sorted(a.fact_id for a in actions))
