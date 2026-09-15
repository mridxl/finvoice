"""The model's entire numeric API: direct functions that write facts and read plans.

Pipecat derives each schema from the signature and the docstring, so the
docstrings here are prompt text — write them for the model, not for a reader of
the module.

Two rules shape every payload below.

**Nothing computes on the way in.** There is no tool that accepts a total, a
difference or a verdict. The model reports what it heard; the planner decides
what it means.

**Nothing comes back as digits.** Every amount leaves here as words — "nine
thousand five hundred rupees" — so the model has no figure it could round,
restate or quietly adjust, and what it reads aloud is what the planner computed.
Digits go to the cards, which the browser renders and never totals.
"""

from datetime import date

from pipecat.services.llm_service import FunctionCallParams

from server.domain.events import (
    ArrangementConfirmed,
    Bounds,
    ConflictFlagged,
    ConflictResolved,
    Fact,
    FactCorrected,
    FactRecorded,
    FactRetracted,
    Kind,
    NothingFurther,
)
from server.domain.gaps import Gap
from server.domain.money import Money, from_rupees, speak_rupees
from server.domain.planner import Action, PlanOutcome
from server.domain.speech import speak_date, speak_day, speak_month_day
from server.session import Session

KINDS: tuple[Kind, ...] = (
    "income",
    "loan_emi",
    "credit_card",
    "essential",
    "optional",
    "cash_on_hand",
)


async def record_money_fact(
    params: FunctionCallParams,
    kind: str,
    label: str,
    amount_rupees: float | None = None,
    day_of_month: int | None = None,
    amount_low_rupees: float | None = None,
    amount_high_rupees: float | None = None,
    day_earliest: int | None = None,
    day_latest: int | None = None,
    spread: bool = False,
    secured: bool = False,
) -> None:
    """Record one thing the user told you about their money. Call it as soon as you hear it.

    Leave amount_rupees out when they do not know the amount: a missing figure is
    recorded honestly and asked about later. Never put a number here that the user
    did not say.

    Args:
        kind: One of income, loan_emi, credit_card, essential, optional, cash_on_hand.
        label: What it is, in their words. "Rent", "Personal loan EMI", "School fee".
        amount_rupees: The amount in rupees, if they gave one.
        day_of_month: The day of the month it lands on, 1 to 31, if they gave one.
        amount_low_rupees: Lowest it could be, when they gave a range or were unsure.
        amount_high_rupees: Highest it could be, when they gave a range or were unsure.
        day_earliest: Earliest day it could land on, when the date is not firm.
        day_latest: Latest day it could land on, when the date is not firm.
        spread: True when it trickles out across the month rather than landing on
            one day, like groceries or fuel.
        secured: True when a loan is secured against something that can be taken
            away, like a vehicle or a home.
    """
    session = _session(params)
    if kind not in KINDS:
        return await _fail(params, f"kind must be one of: {', '.join(KINDS)}")
    if (bad := _bad_day(day_of_month, day_earliest, day_latest)) is not None:
        return await _fail(params, bad)

    fact_id = session.new_fact_id(label)
    session.record(
        FactRecorded(
            Fact(
                fact_id=fact_id,
                kind=kind,  # type: ignore[arg-type]
                label=label,
                amount=_paise(amount_rupees),
                day=day_of_month,
                amount_bounds=_bounds(_paise(amount_low_rupees), _paise(amount_high_rupees)),
                day_bounds=_bounds(day_earliest, day_latest),
                spread=spread,
                secured=secured,
                turn=session.turn,
            )
        )
    )
    fact = session.state().get(fact_id)
    await _settle(
        params,
        {"fact_id": fact_id, "certainty": fact.certainty, "read_back": _read_back(fact)},
    )


async def correct_fact(
    params: FunctionCallParams,
    fact_id: str,
    amount_rupees: float | None = None,
    day_of_month: int | None = None,
) -> None:
    """Revise a fact the user has changed their mind about, or that you got wrong.

    Use this rather than recording the same thing a second time. The old value is
    kept as history and every card moves to the new one.

    Args:
        fact_id: The id you were given when the fact was recorded.
        amount_rupees: The corrected amount, if the amount changed.
        day_of_month: The corrected day of the month, if the day changed.
    """
    session = _session(params)
    if session.state().get(fact_id) is None:
        return await _fail(params, f"no fact called {fact_id}")
    if amount_rupees is None and day_of_month is None:
        return await _fail(params, "say what changed: the amount, the day, or both")
    if (bad := _bad_day(day_of_month)) is not None:
        return await _fail(params, bad)

    session.record(FactCorrected(fact_id, _paise(amount_rupees), day_of_month, turn=session.turn))
    await _settle(
        params, {"fact_id": fact_id, "read_back": _read_back(session.state().get(fact_id))}
    )


async def retract_fact(params: FunctionCallParams, fact_id: str, reason: str = "") -> None:
    """Drop a fact entirely, when it turns out not to be a real expense or income.

    Args:
        fact_id: The id you were given when the fact was recorded.
        reason: Why it is going, in a few words.
    """
    session = _session(params)
    if session.state().get(fact_id) is None:
        return await _fail(params, f"no fact called {fact_id}")
    session.record(FactRetracted(fact_id, reason))
    await _settle(params, {"retracted": fact_id})


async def flag_conflict(params: FunctionCallParams, fact_ids: list[str], note: str) -> None:
    """Record that two things the user said about the same item cannot both be true.

    Do this instead of picking one. Until it is settled the plan uses the worse of
    the two, and the question comes back in open_questions.

    Args:
        fact_ids: The ids of the facts that disagree.
        note: What the disagreement is, in a few words.
    """
    session = _session(params)
    state = session.state()
    missing = [fact_id for fact_id in fact_ids if state.get(fact_id) is None]
    if missing:
        return await _fail(params, f"no fact called {', '.join(missing)}")
    if len(fact_ids) < 2:
        return await _fail(params, "a conflict needs at least two facts")

    conflict_id = f"conflict_{len(state.conflicts) + 1}"
    session.record(ConflictFlagged(conflict_id, tuple(fact_ids), note))
    await _settle(params, {"conflict_id": conflict_id})


async def resolve_conflict(
    params: FunctionCallParams, conflict_id: str, chosen_fact_id: str
) -> None:
    """Settle a flagged conflict once the user has said which figure is right.

    Args:
        conflict_id: The id you were given when the conflict was flagged.
        chosen_fact_id: The id of the fact that turned out to be correct.
    """
    session = _session(params)
    conflict = next((c for c in session.state().conflicts if c.conflict_id == conflict_id), None)
    if conflict is None:
        return await _fail(params, f"no conflict called {conflict_id}")
    if chosen_fact_id not in conflict.fact_ids:
        return await _fail(params, f"{chosen_fact_id} is not part of {conflict_id}")

    session.record(ConflictResolved(conflict_id, chosen_fact_id))
    await _settle(
        params,
        {"kept": chosen_fact_id, "read_back": _read_back(session.state().get(chosen_fact_id))},
    )


async def record_lender_answer(
    params: FunctionCallParams, fact_id: str, accepts_rupees: float
) -> None:
    """Record what a lender said they would accept, after the user has asked them.

    Only ever call this when the user reports an answer they were actually given.
    Never suggest a figure yourself, and never call this on the strength of what a
    lender might say. What is owed does not change; only what leaves the account
    this month does.

    Args:
        fact_id: The id of the loan or card the lender was asked about.
        accepts_rupees: The amount in rupees the lender said they would take.
    """
    session = _session(params)
    fact = session.state().get(fact_id)
    if fact is None:
        return await _fail(params, f"no fact called {fact_id}")
    if accepts_rupees < 0:
        return await _fail(params, "an amount cannot be negative")

    accepts = from_rupees(accepts_rupees)
    session.record(ArrangementConfirmed(fact_id, accepts, turn=session.turn))
    await _settle(
        params,
        {"fact_id": fact_id, "read_back": f"{speak_rupees(accepts)} towards {fact.label}"},
    )


async def record_nothing_further(params: FunctionCallParams, kind: str) -> None:
    """Record that a category is finished — none at all, or none beyond what you have.

    Call this in both situations: when you ask whether they have something and
    they say they have none, and when you ask whether that is all of them and
    they say it is. It is the only way a category stops coming back in
    open_questions, so without it you will keep being told to ask again. If they
    remember one later, just record it and this is superseded.

    Args:
        kind: The category that is finished. One of income, loan_emi,
            credit_card, essential, optional, cash_on_hand.
    """
    if kind not in KINDS:
        return await _fail(params, f"kind must be one of: {', '.join(KINDS)}")
    session = _session(params)
    session.record(NothingFurther(kind=kind, turn=session.turn))  # type: ignore[arg-type]
    await _settle(params, {"recorded": f"nothing further of kind {kind}"})


async def compute_plan(params: FunctionCallParams) -> None:
    """Work out the next thirty days, and get back what there is to say about it.

    Call this before telling the user anything about their position, and again
    after anything changes. Read the amounts back exactly as they come out: they
    are already in words. Do not add, subtract or compare anything yourself.
    """
    _, outcome, _ = _session(params).snapshot()
    await _settle(params, _plan_payload(outcome))


async def open_questions(params: FunctionCallParams) -> None:
    """Get the questions still worth asking, the most decision-changing one first.

    Each one has been measured: asking it would change the plan, or the category
    it belongs to is still open. Some come with an anchor_on, which is the
    concrete thing to ask about. An empty list means there is nothing left worth
    asking, and you should stop gathering information and talk about the plan.
    """
    _, _, gaps = _session(params).snapshot()
    await _settle(
        params,
        {"enough_information": not gaps, "questions": [_question_payload(g) for g in gaps]},
    )


def _question_payload(gap: Gap) -> dict:
    payload = {
        "fact_id": gap.fact_id,
        "label": gap.label,
        "ask_about": gap.field,
        "impact": gap.impact,
        "why_it_matters": gap.why,
    }
    if gap.ask:
        payload["anchor_on"] = gap.ask
    return payload


TOOLS = [
    record_money_fact,
    correct_fact,
    retract_fact,
    flag_conflict,
    resolve_conflict,
    record_lender_answer,
    record_nothing_further,
    compute_plan,
    open_questions,
]


def _plan_payload(outcome: PlanOutcome) -> dict:
    """The plan as the model may repeat it: words, never figures."""
    since = outcome.starts_on
    payload = {
        "status": outcome.status,
        # Thirty days from today, which is not the same as this month. Said aloud
        # so the user orders the dates the way the plan does: on the fifteenth,
        # "the twentieth" is five days away and "the fifth" is twenty.
        "planning_window": (
            f"{speak_month_day(since)} to {speak_month_day(outcome.ends_on)}"
        ),
        "money_in_hand_now": speak_rupees(outcome.opening),
        "left_at_the_end_of_the_month": speak_rupees(outcome.closing),
        "gap_if_everything_is_paid_on_time": speak_rupees(outcome.baseline_gap),
        "first_runs_short_on": speak_date(outcome.first_shortfall_on, since),
        "spending_to_cut": [_action_payload(a, since) for a in outcome.cuts],
        "met_by_arrangement": [_action_payload(a, since) for a in outcome.arranged],
        "cannot_be_paid": [_action_payload(a, since) for a in outcome.unpaid],
        "assumptions": list(outcome.assumptions),
    }
    if outcome.shortfall:
        payload["still_short_after_all_that"] = speak_rupees(outcome.shortfall)
    if (ask := _ask_the_lender(outcome)) is not None:
        payload["ask_the_lender"] = ask
    return payload


def _ask_the_lender(outcome: PlanOutcome) -> dict | None:
    """Money left over and an obligation unmet: the one thing left to suggest.

    Whether that is the situation is arithmetic, so it is decided here rather
    than left to the model to notice. What it must not become is an offer — we do
    not know what any lender will take, so the suggestion is only that the user
    asks, and the answer comes back through `record_lender_answer`.
    """
    if not outcome.unpaid or outcome.closing <= 0:
        return None
    largest = max(outcome.unpaid, key=lambda a: a.amount)
    return {
        "fact_id": largest.fact_id,
        "label": largest.label,
        "money_left_over": speak_rupees(outcome.closing),
        "suggest": (
            "say how much is left over and suggest they ask this lender what, if "
            "anything, would be accepted this month. Do not name a figure, and do "
            "not say what the lender will agree to."
        ),
    }


def _action_payload(action: Action, since: date) -> dict:
    payload = {
        "fact_id": action.fact_id,
        "label": action.label,
        "amount": speak_rupees(action.amount),
        "due": speak_date(action.on, since),
        "reason": action.reason,
    }
    if action.paid:
        payload["being_paid"] = speak_rupees(action.paid)
        payload["still_outstanding"] = speak_rupees(action.amount - action.paid)
    return payload


def _read_back(fact: Fact | None) -> str:
    """What to say back, so a misheard figure is caught now and not in the plan."""
    if fact is None:
        return ""
    if fact.amount is None:
        return f"{fact.label}, amount not known yet"
    said = f"{fact.label}, {speak_rupees(fact.amount)}"
    if fact.spread:
        return f"{said} across the month"
    if fact.day is not None:
        return f"{said} on {speak_day(fact.day)}"
    return said


def _session(params: FunctionCallParams) -> Session:
    return params.app_resources


def _paise(rupees: float | None) -> Money | None:
    return None if rupees is None else from_rupees(rupees)


def _bounds(low: int | None, high: int | None) -> Bounds | None:
    if low is None or high is None or low == high:
        return None
    return Bounds(min(low, high), max(low, high))


def _bad_day(*days: int | None) -> str | None:
    if any(day is not None and not 1 <= day <= 31 for day in days):
        return "a day of the month is between 1 and 31"
    return None


async def _settle(params: FunctionCallParams, payload: dict) -> None:
    """Push whatever moved on screen, then hand the model its result."""
    await _session(params).push_cards()
    await params.result_callback(payload)


async def _fail(params: FunctionCallParams, why: str) -> None:
    """A refusal the model can act on. Nothing was recorded, so there is nothing to undo."""
    await params.result_callback({"error": why})
