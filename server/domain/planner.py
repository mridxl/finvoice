"""The planner: a 30-day day-by-day walk, and the ladder that decides what gives way.

Date-awareness is the whole point. Income on the twenty-fifth does not rescue a
bill due on the tenth, and a model that works in monthly totals gets that wrong
while looking perfectly healthy. So we place every rupee on a day and walk it.

`plan()` is pure: same state and same `as_of` in, same outcome out. No clock is
read here, which is why the tests need neither an LLM nor a network.
"""

from calendar import monthrange
from dataclasses import dataclass, replace
from datetime import date, timedelta
from typing import Literal

from server.domain.events import Fact
from server.domain.money import Money, allocate, from_rupees
from server.domain.state import FinancialState

WINDOW_DAYS = 30

# Below this the month technically clears but leaves nothing for a bad day, and
# calling that "feasible" would be misleading. It is a judgement, so it is named.
CUSHION = from_rupees(1000)

# Conservative defaults in basis points, used only to order obligations against
# one another when something has to give. Never quoted to the user as their
# lender's terms — the outcome carries them as a labelled assumption instead.
DEFAULT_APR_BP: dict[str, int] = {"credit_card": 4200, "loan_emi": 2400}
DEFAULT_LATE_FEE: dict[str, Money] = {"credit_card": from_rupees(500), "loan_emi": from_rupees(500)}

Status = Literal["feasible", "tight", "infeasible"]


@dataclass(frozen=True)
class Entry:
    """One amount landing on one day. Signed: income adds, everything else subtracts."""

    fact_id: str
    label: str
    kind: str
    amount: Money


@dataclass(frozen=True)
class LedgerRow:
    on: date
    entries: tuple[Entry, ...]
    closing: Money


@dataclass(frozen=True)
class Action:
    fact_id: str
    label: str
    kind: str
    amount: Money  # the full contractual amount, magnitude not signed
    on: date | None
    reason: str
    paid: Money = 0  # what the plan still pays toward it; the rest goes unmet


@dataclass(frozen=True)
class PlanOutcome:
    """`infeasible` is a return value, not an error branch, so nothing downstream
    can quietly forget to say that the money does not stretch."""

    status: Status
    ledger: tuple[LedgerRow, ...]
    cuts: tuple[Action, ...]
    arranged: tuple[Action, ...]  # met at a reduced figure the lender confirmed
    unpaid: tuple[Action, ...]
    opening: Money
    closing: Money
    lowest: Money
    shortfall: Money  # what is still missing after the ladder has done its work
    baseline_gap: Money  # what was missing before it, if everything were paid on time
    first_shortfall_on: date | None  # the day it first bites, paying everything on time
    assumptions: tuple[str, ...]

    @property
    def solved(self) -> bool:
        return self.status != "infeasible"


def plan(state: FinancialState, as_of: date) -> PlanOutcome:
    """Walk 30 days from `as_of`, then drop commitments up the ladder until it clears."""
    facts = state.planning_facts()
    opening = sum(f.amount or 0 for f in facts if f.kind == "cash_on_hand")
    spending = [f for f in facts if f.kind != "cash_on_hand"]

    baseline = _simulate(opening, _schedule(spending, as_of), as_of)
    ledger, applied = baseline, {}
    for fact, target in _relief_steps(facts):
        if _lowest(ledger) >= 0:
            break
        trial_applied = {**applied, fact.fact_id: target}
        trial = _simulate(opening, _schedule(_reduced(spending, trial_applied), as_of), as_of)
        # Skip anything that does not move the worst day. Giving up a payment due
        # after the crunch relieves nothing — it would just be a second broken
        # commitment bought for no benefit.
        if _lowest(trial) <= _lowest(ledger):
            continue
        applied, ledger = trial_applied, trial

    lowest = _lowest(ledger)
    cuts, arranged, unpaid = _classify(facts, applied, as_of)
    shortfall = -lowest if lowest < 0 else 0

    return PlanOutcome(
        status=_status(unpaid, cuts, arranged, lowest, shortfall),
        ledger=ledger,
        cuts=cuts,
        arranged=arranged,
        unpaid=unpaid,
        opening=opening,
        closing=ledger[-1].closing,
        lowest=lowest,
        shortfall=shortfall,
        baseline_gap=max(0, -_lowest(baseline)),
        first_shortfall_on=next((r.on for r in baseline if r.closing < 0), None),
        assumptions=_assumptions(facts, [f for f in facts if f.fact_id in applied]),
    )


def cost_of_delay(fact: Fact, days_late: int = 30) -> Money:
    """What one month of lateness costs. Only ever used to rank obligations."""
    apr_bp = DEFAULT_APR_BP.get(fact.kind, 0)
    fee = DEFAULT_LATE_FEE.get(fact.kind, 0)
    return fee + ((fact.amount or 0) * apr_bp * days_late) // (10_000 * 365)


def _drop_sequence(facts: tuple[Fact, ...]) -> list[Fact]:
    """The priority ladder, read backwards: the order in which things give way.

    Optional spending goes first. Then unsecured obligations, cheapest-to-delay
    first. Then card minimums: missing one starts revolving interest compounding
    on the *whole outstanding balance* at 36-48% a year, which is the most
    expensive money available to an Indian household — far more than the penal
    interest on one missed instalment. Then secured EMIs, which put the asset at
    risk, and the two-wheeler is how he gets to work, so losing it costs income.

    Essentials are not in this list at all. Nothing is cut out of someone's food
    or roof to service a lender.

    Deliberately all-or-nothing, not pro-rata. UK debt-advice practice splits
    what is available across non-priority creditors by share of debt, but that is
    for negotiating arrears under an agreed plan. Here the contractual amounts
    are still due, so 60% of an EMI is still a missed EMI — and proposing partial
    settlements is exactly what this assistant is forbidden to invent.
    """
    tiers: dict[str, int] = {}
    for fact in facts:
        if fact.kind == "optional":
            tiers[fact.fact_id] = 0
        elif fact.kind == "loan_emi" and not fact.secured:
            tiers[fact.fact_id] = 1
        elif fact.kind == "credit_card":
            tiers[fact.fact_id] = 2
        elif fact.kind == "loan_emi" and fact.secured:
            tiers[fact.fact_id] = 3

    candidates = [f for f in facts if f.fact_id in tiers and f.amount]
    # Optionals: largest first, so the fewest cuts buy the most room. Obligations:
    # least costly to delay first. fact_id only breaks ties deterministically.
    return sorted(
        candidates,
        key=lambda f: (
            tiers[f.fact_id],
            -(f.amount or 0) if f.kind == "optional" else cost_of_delay(f),
            f.fact_id,
        ),
    )


def _relief_steps(facts: tuple[Fact, ...]) -> list[tuple[Fact, Money]]:
    """Every way a commitment can give way, in ladder order, as (fact, amount left paid).

    An obligation gives way once — to nothing — unless the user has come back
    with an amount the lender confirmed they would accept. Then it gives way
    twice: down to that figure first, and only to nothing if the month still
    does not clear. The figure is the lender's, relayed by the user; we neither
    choose it nor suggest one.
    """
    steps: list[tuple[Fact, Money]] = []
    for fact in _drop_sequence(facts):
        agreed = fact.part_payment
        if agreed is not None and 0 < agreed < (fact.amount or 0):
            steps.append((fact, agreed))
        steps.append((fact, 0))
    return steps


def _reduced(facts: list[Fact], applied: dict[str, Money]) -> list[Fact]:
    return [replace(f, amount=applied[f.fact_id]) if f.fact_id in applied else f for f in facts]


def _classify(
    facts: tuple[Fact, ...], applied: dict[str, Money], as_of: date
) -> tuple[tuple[Action, ...], tuple[Action, ...], tuple[Action, ...]]:
    """Split what gave way into spending cut, obligations met as arranged, and
    obligations simply not met. `applied` is in the order the ladder reached them."""
    by_id = {f.fact_id: f for f in facts}
    cuts, arranged, unpaid = [], [], []
    for fact_id, still_paid in applied.items():
        fact = by_id[fact_id]
        if fact.kind == "optional":
            cuts.append(_action(fact, as_of, "optional spending, cut first"))
        elif still_paid > 0:
            arranged.append(
                _action(fact, as_of, "reduced to the figure you said your lender would accept",
                        still_paid)
            )
        else:
            unpaid.append(_action(fact, as_of, _why_unpaid(fact)))
    return tuple(cuts), tuple(arranged), tuple(unpaid)


def _schedule(facts: list[Fact], as_of: date) -> dict[date, list[Entry]]:
    days: dict[date, list[Entry]] = {}
    for fact in facts:
        if not fact.amount:
            continue  # unknown or reduced to nothing; gaps.py asks about unknowns
        for when, amount in _placements(fact, as_of):
            days.setdefault(when, []).append(Entry(fact.fact_id, fact.label, fact.kind, amount))
    return days


def _placements(fact: Fact, as_of: date) -> list[tuple[date, Money]]:
    total = fact.signed
    if fact.spread:
        return [
            (as_of + timedelta(days=i), part) for i, part in enumerate(allocate(total, WINDOW_DAYS))
        ]
    if fact.day is not None:
        return [(_date_for_day(fact.day, as_of), total)]
    # No date given at all: assume the worst placement it could have — money out
    # on the first day, money in on the last. Recorded as an assumption, and
    # gaps.py will rank the question if the guess actually matters.
    return [(as_of + timedelta(days=WINDOW_DAYS - 1) if total > 0 else as_of, total)]


def _date_for_day(day: int, as_of: date) -> date:
    """First date in the window on that day of the month, clamped in short months."""
    for offset in range(WINDOW_DAYS):
        when = as_of + timedelta(days=offset)
        if when.day == min(day, monthrange(when.year, when.month)[1]):
            return when
    return as_of + timedelta(days=WINDOW_DAYS - 1)


def _simulate(
    opening: Money, schedule: dict[date, list[Entry]], as_of: date
) -> tuple[LedgerRow, ...]:
    rows, balance = [], opening
    for offset in range(WINDOW_DAYS):
        when = as_of + timedelta(days=offset)
        entries = tuple(schedule.get(when, ()))
        balance += sum(e.amount for e in entries)
        rows.append(LedgerRow(when, entries, balance))
    return tuple(rows)


def _lowest(ledger: tuple[LedgerRow, ...]) -> Money:
    return min(row.closing for row in ledger)


def _why_unpaid(fact: Fact) -> str:
    if fact.kind == "credit_card":
        return "card minimum, given up only after unsecured loans because missing it compounds"
    if fact.secured:
        return "secured EMI, given up last because the asset itself is at risk"
    return "unsecured loan: nothing is repossessed, and the penalty compounds least"


def _action(fact: Fact, as_of: date, reason: str, paid: Money = 0) -> Action:
    when = None if fact.spread or fact.day is None else _date_for_day(fact.day, as_of)
    return Action(fact.fact_id, fact.label, fact.kind, fact.amount or 0, when, reason, paid)


def _status(
    unpaid: tuple[Action, ...],
    cuts: tuple[Action, ...],
    arranged: tuple[Action, ...],
    lowest: Money,
    shortfall: Money,
) -> Status:
    if unpaid or shortfall > 0:
        return "infeasible"
    # An arrangement the lender confirmed means this month's obligation is met,
    # so it is not infeasible — but it took an arrangement to get there, and the
    # balance behind it is still owed. That is never "feasible".
    if cuts or arranged or lowest < CUSHION:
        return "tight"
    return "feasible"


def _assumptions(facts: tuple[Fact, ...], gave_way: list[Fact]) -> tuple[str, ...]:
    notes = []
    for fact in facts:
        undated = fact.amount is not None and fact.day is None and not fact.spread
        # Cash on hand is the opening balance, not a payment waiting for a date:
        # `plan` never schedules it, so saying it was placed anywhere is false —
        # and it is a sentence the assistant reads out. An unconfirmed *amount*
        # of cash is still worth flagging, which is why only this note is skipped.
        if undated and fact.kind != "cash_on_hand":
            notes.append(f"{fact.label}: no date given, so it is placed at the worst point.")
        if fact.amount_bounds is not None:
            notes.append(f"{fact.label}: planned on a figure that is not yet confirmed.")
        if fact.day_bounds is not None:
            notes.append(f"{fact.label}: planned on a date that is not yet confirmed.")
    if any(f.kind in DEFAULT_APR_BP for f in gave_way):
        notes.append("Late-payment costs use conservative defaults, not your lender's actual terms.")
    return tuple(notes)
