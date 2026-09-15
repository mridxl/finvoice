"""Which missing piece is worth asking about — measured, not guessed.

For every uncertain fact we re-run the planner at both ends of its range and
compare the outcomes. If nothing moves, the question is not worth a turn of
conversation; if the answer flips whether a bill gets paid, it is the next thing
we ask.

That measures uncertainty *within* what has been recorded, which is only half of
knowing whether we have enough. A rent nobody has mentioned has no fact to probe
and no range to swing, so sensitivity analysis reports it identically to a
question already settled — and one recorded rent says nothing about the school
fee standing next to it. Coverage is therefore tracked separately, by what the
user has actually closed off: see `COVERAGE` below. Without it this module
answers "nothing left worth asking" to a conversation that has asked one
question.

The planner decides *what* to ask, and for a whole category, what to anchor the
question on — see `Category`. The model decides how to say it.
"""

from dataclasses import dataclass
from datetime import date
from typing import Literal

from server.domain.events import Bounds, Fact, Kind
from server.domain.money import format_rupees, from_rupees
from server.domain.planner import Action, PlanOutcome, plan
from server.domain.state import FinancialState

# A swing smaller than this is noise in a household budget, not a question.
MATERIAL = from_rupees(1000)

Impact = Literal["high", "medium", "low"]
_ORDER: dict[Impact, int] = {"high": 0, "medium": 1, "low": 2}


@dataclass(frozen=True)
class Category:
    """A side of the month that has to be asked about, and what to anchor on.

    `ask` and `sweep` are the closest this module comes to wording, and they stop
    short of it deliberately: each names the concrete thing a question should be
    about, never a sentence to read out. Nobody can answer "what is your
    essential spending" — everybody can answer where they live and how they get
    to work, and the spending falls out of that. Which to ask is still decided
    here; how to say it is still the model's.
    """

    fact_id: str
    label: str
    kinds: tuple[Kind, ...]
    why: str
    ask: str
    sweep: str


# Categories that make a plan meaningful, and the kinds that satisfy each. A
# thirty-day plan built over a category nobody has mentioned is not a thin plan,
# it is a wrong one: it reported sixty one thousand rupees "left at the end of
# the month" to a user who had simply not been asked what he spends.
#
# Plenty of people have no loan and no card, so those two would nag forever if
# only a recorded debt could clear them. `NothingFurther` is what makes them
# askable — and it is also the only thing that finishes a category that *does*
# have something in it, because one rent is not evidence there is no school fee.
#
# Listed in the order they are worth asking about, which is the order they come
# back in: what comes in, what must go out, then what is owed.
COVERAGE: tuple[Category, ...] = (
    Category(
        "money_in",
        "Money coming in",
        # Cash on hand deliberately does not satisfy this. It is a balance, not an
        # answer to what arrives during the month, and a plan funded by a pocket
        # is a different month from one funded by a salary. Someone genuinely
        # living off savings says so, and that closes it like any other category.
        ("income",),
        (
            "nothing is recorded arriving during the month, so the plan has only "
            "what is already in hand to work with"
        ),
        ask=(
            "what they do for a living, whether the pay is the same every month, "
            "and anything they earn on the side"
        ),
        sweep=(
            "any other money due in — something owed to them, a bonus, or anyone "
            "else at home who puts money in"
        ),
    ),
    Category(
        "essentials",
        "Essential spending",
        ("essential",),
        (
            "nothing is recorded for rent, food, bills or anything else that has to "
            "be paid, so any money left over is an illusion"
        ),
        ask=(
            "where they live and what it costs them, how they get to work, and what "
            "food and bills come to"
        ),
        sweep=(
            "anything else that goes out every month — phone, school fees, medicines, "
            "money sent home, a subscription or a gym"
        ),
    ),
    Category(
        "loans",
        "Loan repayments",
        ("loan_emi",),
        (
            "no loan repayment has been mentioned either way, and an unasked EMI is "
            "the most likely thing to break the month"
        ),
        ask=(
            "any loan or EMI at all, including money borrowed from family, a friend "
            "or an employer"
        ),
        sweep=(
            "any other borrowing, including something informal that no bank would "
            "know about"
        ),
    ),
    Category(
        "cards",
        "Credit card payments",
        ("credit_card",),
        (
            "no credit card has been mentioned either way, and a missed minimum "
            "compounds faster than anything else here"
        ),
        ask="any credit card at all, and what has to go on to it this month",
        sweep="any other card, including one they rarely use",
    ),
)


@dataclass(frozen=True)
class Gap:
    fact_id: str
    label: str
    field: Literal["amount", "day", "existence", "completeness"]
    impact: Impact
    why: str
    low: int | None = None
    high: int | None = None
    swing: int = 0
    # A whole category rather than a recorded fact that is imprecise: either
    # nothing in it at all, or nothing said yet to close it.
    coverage: bool = False
    # The concrete thing to anchor the question on, for coverage gaps. Empty for
    # the rest, which already know what they are about.
    ask: str = ""


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
    ranked = sorted(live, key=lambda g: (_ORDER[g.impact], -g.swing, g.fact_id))
    missing, sweeps = _coverage(probe)
    # Missing categories first, in COVERAGE's own order rather than by impact: a
    # figure pinned down inside half a month is still half a month, and "what
    # comes in" is a stranger question to ask second than it is to ask first.
    #
    # "Is that everything?" goes last, for the mirror reason. It is what remains
    # once nothing else is worth asking, and interrupting with it after every
    # answer is exactly how an intake turns into an interview. Within that tier
    # the order flips: what goes out is swept before what comes in, because a
    # forgotten outgoing makes the plan wrong in the direction that hurts and a
    # forgotten income only makes it cautious.
    return (*missing, *ranked, *sweeps)


def _coverage(state: FinancialState) -> tuple[list[Gap], list[Gap]]:
    """Categories with nothing in them, and categories nobody has closed.

    A category stops being asked about in exactly one way: the user says that is
    all of it. Having recorded a fact is not enough — one rent is not proof there
    is no school fee, and treating it as proof is how a plan comes to report
    money left over that the user does not have.

    "I have no credit cards" and "those are all my loans" are the same answer,
    which is why one event settles both. A fact with no amount yet still counts
    as something in the category: it has been raised, and the missing figure is
    already its own gap.
    """
    have = {fact.kind for fact in state.facts}
    missing: list[Gap] = []
    sweeps: list[Gap] = []
    for cat in sorted(COVERAGE, key=lambda c: "income" in c.kinds):
        if state.declared_complete.intersection(cat.kinds):
            continue
        if have.intersection(cat.kinds):
            sweeps.append(
                Gap(
                    cat.fact_id, cat.label, "completeness", "low",
                    "something is recorded here, but nobody has said it is all of it",
                    coverage=True, ask=cat.sweep,
                )
            )
        else:
            missing.append(
                Gap(cat.fact_id, cat.label, "existence", "high", cat.why,
                    coverage=True, ask=cat.ask)
            )
    return missing, sweeps


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


def _ids(actions: tuple[Action, ...]) -> tuple[str, ...]:
    return tuple(sorted(a.fact_id for a in actions))
