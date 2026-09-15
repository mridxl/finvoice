"""Cards are pure selectors over `(state, outcome, gaps)`. They render, never compute.

Every card comes from the same state object, so a card cannot drift out of step
with the conversation or with another card. Amounts are sent as paise plus the
text and the spoken form, so the browser never has to do arithmetic to display
one — and never has the chance to disagree with the server about a number.
"""

import hashlib
import json
from dataclasses import asdict
from datetime import date

from server.domain.events import Fact
from server.domain.gaps import COVERAGE, Gap
from server.domain.money import Money, format_rupees, speak_rupees
from server.domain.planner import Action, LedgerRow, PlanOutcome
from server.domain.state import FinancialState

TITLES = {
    "cash_position": "Cash position",
    "income": "Money coming in",
    "obligations": "Loans and cards",
    "essentials": "Essentials",
    "optionals": "Optional spending",
    "calendar": "Next 30 days",
    "bottom_line": "Bottom line",
    "missing_info": "Still to confirm",
    "actions": "Proposed actions",
    "ledger": "Day by day",
}

# `COVERAGE` in `server/domain/gaps.py` says why each category has to be asked
# about. These are the same four said short enough to sit in four columns on a
# laptop, where "Credit card payments" is two words of truncation.
STRIP = {
    "money_in": "Income",
    "essentials": "Essentials",
    "loans": "Loans",
    "cards": "Cards",
}


def build_cards(
    state: FinancialState, outcome: PlanOutcome, gaps: tuple[Gap, ...]
) -> dict[str, dict]:
    """The full card set. Callers diff on `digest` to decide what to push."""
    bodies = {
        "cash_position": {
            "opening": _money(outcome.opening),
            "closing": _money(outcome.closing),
            "lowest": _money(outcome.lowest),
        },
        "income": {"items": [_fact(state, f) for f in state.of_kind("income")]},
        "obligations": {"items": [_fact(state, f) for f in state.of_kind("loan_emi", "credit_card")]},
        "essentials": {"items": [_fact(state, f) for f in state.of_kind("essential")]},
        "optionals": {"items": [_fact(state, f) for f in state.of_kind("optional")]},
        "calendar": {"days": [_day(row) for row in outcome.ledger]},
        "bottom_line": {
            "status": outcome.status,
            "gap_if_all_paid": _money(outcome.baseline_gap),
            "still_short": _money(outcome.shortfall),
            "first_shortfall_on": _iso(outcome.first_shortfall_on),
            "assumptions": list(outcome.assumptions),
        },
        "missing_info": {
            "items": [asdict(g) for g in gaps],
            # The same test `open_questions` hands the model, so the screen and
            # the voice change phase on one signal rather than two. While this
            # is false the assistant is under orders not to say what is left
            # over, and a screen that shows it anyway is the one contradicting
            # the call.
            "enough_information": not gaps,
            "coverage": _coverage(gaps),
        },
        "actions": {
            "cuts": [_action(a) for a in outcome.cuts],
            "arranged": [_action(a) for a in outcome.arranged],
            "unpaid": [_action(a) for a in outcome.unpaid],
        },
        "ledger": {"rows": [_row(row) for row in outcome.ledger]},
    }
    return {
        card_id: {
            "id": card_id,
            "title": TITLES[card_id],
            "revision": state.version,
            "digest": _digest(body),
            "body": body,
        }
        for card_id, body in bodies.items()
    }


def _coverage(gaps: tuple[Gap, ...]) -> list[dict]:
    """How far the intake has got, one entry per category, in asking order.

    A settled category sends no gap at all, so the state is read from what is
    absent — which is why the list is built from `COVERAGE` here rather than
    from the gaps alone. `partly` is the distinction the screen exists for:
    something is recorded, and nobody has yet said it is all of it.
    """
    open_gaps = {g.fact_id: g for g in gaps if g.coverage}
    asking = next((g.fact_id for g in gaps if g.coverage), None)
    return [
        {
            "id": cat.fact_id,
            "label": STRIP[cat.fact_id],
            "state": _state(open_gaps.get(cat.fact_id)),
            "current": cat.fact_id == asking,
        }
        for cat in COVERAGE
    ]


def _state(gap: Gap | None) -> str:
    if gap is None:
        return "done"
    return "empty" if gap.field == "existence" else "partly"


def _money(amount: Money) -> dict:
    return {"paise": amount, "text": format_rupees(amount), "speech": speak_rupees(amount)}


def _fact(state: FinancialState, fact: Fact) -> dict:
    previous = state.history.get(fact.fact_id, ())
    return {
        "fact_id": fact.fact_id,
        "label": fact.label,
        "kind": fact.kind,
        "amount": _money(fact.amount) if fact.amount is not None else None,
        "day": fact.day,
        "spread": fact.spread,
        "certainty": fact.certainty,
        "contested": any(fact.fact_id in c.fact_ids for c in state.open_conflicts),
        # Present only after a correction: the visible proof that the ripple is real.
        "corrected_from": _money(previous[-1].amount) if previous and previous[-1].amount else None,
    }


def _day(row: LedgerRow) -> dict:
    net = sum(e.amount for e in row.entries)
    return {
        "on": _iso(row.on),
        "net": _money(net),
        "closing": _money(row.closing),
        "negative": row.closing < 0,
    }


def _row(row: LedgerRow) -> dict:
    return {
        "on": _iso(row.on),
        "entries": [
            {"label": e.label, "kind": e.kind, "amount": _money(e.amount)} for e in row.entries
        ],
        "closing": _money(row.closing),
    }


def _action(action: Action) -> dict:
    return {
        "fact_id": action.fact_id,
        "label": action.label,
        "kind": action.kind,
        "amount": _money(action.amount),
        "paid": _money(action.paid),
        "outstanding": _money(action.amount - action.paid),
        "on": _iso(action.on),
        "reason": action.reason,
    }


def _iso(when: date | None) -> str | None:
    return when.isoformat() if when else None


def _digest(body: dict) -> str:
    return hashlib.sha1(json.dumps(body, sort_keys=True).encode()).hexdigest()[:8]
