"""The seam between the model and the domain, exercised without a model.

Every test here calls the same functions the LLM calls, with the same arguments
it would send, and checks what comes back. That is the whole contract: if a tool
would let an invented figure through, or hand back something the model could
misread as licence to do arithmetic, it fails here rather than on a call.
"""

import asyncio
import json
from datetime import date

from pipecat.adapters.schemas.direct_function import DirectFunctionWrapper

from server.domain.money import from_rupees
from server.session import Session
from server.tools import (
    TOOLS,
    compute_plan,
    correct_fact,
    flag_conflict,
    open_questions,
    record_lender_answer,
    record_money_fact,
    resolve_conflict,
    retract_fact,
)

AS_OF = date(2026, 9, 1)


class FakeCall:
    """Stands in for `FunctionCallParams`. The tools touch two fields of it."""

    def __init__(self, session: Session):
        self.app_resources = session
        self.result = None

    async def result_callback(self, result, **_kwargs):
        self.result = result


def call(tool, session: Session, **kwargs):
    """Invoke a tool the way Pipecat would, and return what the model would see."""
    params = FakeCall(session)
    asyncio.run(tool(params, **kwargs))
    return params.result


def intake() -> Session:
    """The BUILD-PLAN persona, recorded through the tools rather than hand-built.

    Labels avoid digits so a payload can be checked for them; the user's own
    words are the one thing in a result that is allowed to contain a numeral.
    """
    session = Session(as_of=AS_OF)
    call(record_money_fact, session, kind="cash_on_hand", label="Cash on hand", amount_rupees=2_200)
    call(record_money_fact, session, kind="income", label="Salary", amount_rupees=38_000, day_of_month=1)
    call(
        record_money_fact, session, kind="income", label="Spouse income",
        amount_rupees=12_000, day_of_month=10, day_earliest=10, day_latest=20,
    )
    call(record_money_fact, session, kind="essential", label="Rent", amount_rupees=14_000, day_of_month=5)
    call(
        record_money_fact, session, kind="loan_emi", label="Two-wheeler EMI",
        amount_rupees=4_200, day_of_month=8, secured=True,
    )
    call(record_money_fact, session, kind="essential", label="School fee", amount_rupees=15_000, day_of_month=10)
    call(record_money_fact, session, kind="loan_emi", label="Personal loan EMI", amount_rupees=9_500, day_of_month=15)
    call(record_money_fact, session, kind="credit_card", label="First card minimum", amount_rupees=2_100, day_of_month=18)
    call(record_money_fact, session, kind="credit_card", label="Second card minimum", amount_rupees=1_400, day_of_month=22)
    call(record_money_fact, session, kind="essential", label="Household essentials", amount_rupees=11_000, spread=True)
    call(record_money_fact, session, kind="optional", label="Optional spending", amount_rupees=3_000, spread=True)
    return session


def test_a_stated_fact_is_recorded_and_read_back_in_words():
    session = Session(as_of=AS_OF)
    result = call(
        record_money_fact, session, kind="essential", label="Rent", amount_rupees=14_000, day_of_month=5
    )
    assert result["fact_id"] == "rent"
    assert result["certainty"] == "stated"
    assert result["read_back"] == "Rent, fourteen thousand rupees on the fifth"
    assert session.state().get("rent").amount == from_rupees(14_000)


def test_an_amount_the_user_does_not_know_is_recorded_as_unknown():
    session = Session(as_of=AS_OF)
    result = call(record_money_fact, session, kind="essential", label="Gas cylinder")
    assert result["certainty"] == "unknown"
    assert session.state().get("gas_cylinder").amount is None


def test_a_range_is_carried_as_an_estimate_rather_than_a_midpoint():
    session = Session(as_of=AS_OF)
    call(
        record_money_fact, session, kind="essential", label="Electricity",
        amount_rupees=2_000, amount_low_rupees=1_800, amount_high_rupees=2_400, day_of_month=12,
    )
    fact = session.state().get("electricity")
    assert fact.certainty == "estimated"
    assert fact.amount_bounds.low == from_rupees(1_800)
    assert fact.amount_bounds.high == from_rupees(2_400)


def test_two_things_with_the_same_name_get_different_ids():
    session = Session(as_of=AS_OF)
    first = call(record_money_fact, session, kind="credit_card", label="Card minimum", amount_rupees=2_100)
    second = call(record_money_fact, session, kind="credit_card", label="Card minimum", amount_rupees=1_400)
    assert first["fact_id"] != second["fact_id"]
    assert len(session.state().facts) == 2


def test_a_kind_we_do_not_model_is_refused_and_nothing_is_recorded():
    session = Session(as_of=AS_OF)
    result = call(record_money_fact, session, kind="savings", label="Chit fund", amount_rupees=5_000)
    assert "error" in result
    assert session.log == []


def test_a_day_outside_the_month_is_refused():
    session = Session(as_of=AS_OF)
    result = call(record_money_fact, session, kind="essential", label="Rent", amount_rupees=100, day_of_month=45)
    assert "error" in result
    assert session.log == []


def test_a_correction_moves_the_value_and_keeps_what_it_replaced():
    session = Session(as_of=AS_OF)
    call(record_money_fact, session, kind="income", label="Salary", amount_rupees=38_000, day_of_month=1)
    result = call(correct_fact, session, fact_id="salary", amount_rupees=41_000)

    assert result["read_back"] == "Salary, forty one thousand rupees on the first"
    assert session.state().get("salary").amount == from_rupees(41_000)
    assert session.state().history["salary"][-1].amount == from_rupees(38_000)


def test_correcting_something_never_recorded_is_refused():
    session = Session(as_of=AS_OF)
    assert "error" in call(correct_fact, session, fact_id="rent", amount_rupees=100)


def test_a_correction_that_says_nothing_is_refused():
    session = Session(as_of=AS_OF)
    call(record_money_fact, session, kind="essential", label="Rent", amount_rupees=14_000)
    assert "error" in call(correct_fact, session, fact_id="rent")


def test_a_retraction_removes_it_from_the_plan():
    session = intake()
    before = call(compute_plan, session)
    call(retract_fact, session, fact_id="optional_spending", reason="cancelled it")
    assert session.state().get("optional_spending") is None
    assert call(compute_plan, session) != before


def test_a_contradiction_is_flagged_rather_than_settled_by_guessing():
    session = Session(as_of=AS_OF)
    call(record_money_fact, session, kind="loan_emi", label="Personal loan EMI", amount_rupees=9_500, day_of_month=15)
    second = call(record_money_fact, session, kind="loan_emi", label="Personal loan EMI", amount_rupees=8_500, day_of_month=15)
    flagged = call(
        flag_conflict, session, fact_ids=["personal_loan_emi", second["fact_id"]],
        note="nine and a half, then around eight and a half",
    )

    conflict = session.state().open_conflicts[0]
    assert conflict.conflict_id == flagged["conflict_id"]
    # Both claims survive until the user settles it; the planner sees one fact.
    assert len(session.state().facts) == 2
    assert len(session.state().planning_facts()) == 1


def test_resolving_a_conflict_keeps_the_figure_the_user_confirmed():
    session = Session(as_of=AS_OF)
    call(record_money_fact, session, kind="loan_emi", label="Personal loan EMI", amount_rupees=9_500, day_of_month=15)
    second = call(record_money_fact, session, kind="loan_emi", label="Personal loan EMI", amount_rupees=8_500, day_of_month=15)
    call(flag_conflict, session, fact_ids=["personal_loan_emi", second["fact_id"]], note="two figures")
    result = call(
        resolve_conflict, session, conflict_id="conflict_1", chosen_fact_id=second["fact_id"]
    )

    assert "eight thousand five hundred rupees" in result["read_back"]
    assert session.state().open_conflicts == ()


def test_a_fact_id_that_is_not_in_the_conflict_is_refused():
    session = Session(as_of=AS_OF)
    call(record_money_fact, session, kind="loan_emi", label="Personal loan EMI", amount_rupees=9_500)
    call(record_money_fact, session, kind="essential", label="Rent", amount_rupees=14_000)
    call(record_money_fact, session, kind="loan_emi", label="Loan", amount_rupees=8_500)
    call(flag_conflict, session, fact_ids=["personal_loan_emi", "loan"], note="two figures")
    assert "error" in call(resolve_conflict, session, conflict_id="conflict_1", chosen_fact_id="rent")


def test_the_plan_the_model_reads_has_no_digit_in_it_anywhere():
    # The structural half of "the LLM never does arithmetic". There is no figure
    # in the payload to round, restate or quietly adjust — only words, which can
    # be repeated but not operated on.
    payload = json.dumps(call(compute_plan, intake()))
    assert not any(character.isdigit() for character in payload), payload


def test_the_plan_names_what_cannot_be_paid_and_why():
    result = call(compute_plan, intake())
    assert result["status"] == "infeasible"
    assert result["gap_if_everything_is_paid_on_time"] == "eight thousand rupees"
    assert result["first_runs_short_on"] == "the eighteenth"
    assert [a["label"] for a in result["spending_to_cut"]] == ["Optional spending"]
    assert [a["label"] for a in result["cannot_be_paid"]] == ["Personal loan EMI"]
    assert result["cannot_be_paid"][0]["amount"] == "nine thousand five hundred rupees"
    assert result["cannot_be_paid"][0]["due"] == "the fifteenth"


def test_money_left_over_beside_an_unmet_obligation_becomes_a_question_for_the_lender():
    result = call(compute_plan, intake())
    ask = result["ask_the_lender"]
    assert ask["label"] == "Personal loan EMI"
    assert ask["money_left_over"] == "four thousand five hundred rupees"
    # The suggestion is that the user asks. Nothing here offers a figure.
    assert "ask" in ask["suggest"]


def test_nothing_is_suggested_to_a_lender_when_the_month_already_works():
    session = Session(as_of=AS_OF)
    call(record_money_fact, session, kind="income", label="Salary", amount_rupees=50_000, day_of_month=1)
    call(record_money_fact, session, kind="essential", label="Rent", amount_rupees=10_000, day_of_month=5)
    result = call(compute_plan, session)
    assert result["status"] == "feasible"
    assert "ask_the_lender" not in result


def test_a_lender_answer_reduces_what_leaves_the_account_not_what_is_owed():
    session = intake()
    result = call(record_lender_answer, session, fact_id="personal_loan_emi", accepts_rupees=4_500)
    assert result["read_back"] == "four thousand five hundred rupees towards Personal loan EMI"

    plan = call(compute_plan, session)
    assert plan["cannot_be_paid"] == []
    arranged = plan["met_by_arrangement"][0]
    assert arranged["being_paid"] == "four thousand five hundred rupees"
    assert arranged["still_outstanding"] == "five thousand rupees"
    assert session.state().get("personal_loan_emi").amount == from_rupees(9_500)


def test_a_lender_answer_about_something_we_never_recorded_is_refused():
    session = intake()
    assert "error" in call(record_lender_answer, session, fact_id="mortgage", accepts_rupees=1_000)


def test_the_question_to_ask_next_is_the_one_that_changes_the_plan():
    result = call(open_questions, intake())
    assert result["enough_information"] is False
    first = result["questions"][0]
    # Its amount is firm and its date is not, and the date is what moves the month.
    assert (first["label"], first["ask_about"]) == ("Spouse income", "day")
    assert first["impact"] == "high"


def test_a_settled_month_has_nothing_left_worth_asking():
    session = Session(as_of=AS_OF)
    call(record_money_fact, session, kind="income", label="Salary", amount_rupees=50_000, day_of_month=1)
    call(record_money_fact, session, kind="essential", label="Rent", amount_rupees=10_000, day_of_month=5)
    result = call(open_questions, session)
    assert result["enough_information"] is True
    assert result["questions"] == []


def schemas():
    """What the model is actually shown, derived the way Pipecat derives it."""
    return {tool.__name__: DirectFunctionWrapper(tool).to_function_schema() for tool in TOOLS}


def test_every_tool_survives_the_direct_function_contract():
    # Constructing the wrapper is the check: it rejects anything that is not
    # async, or whose first parameter is not `params`.
    assert set(schemas()) == {tool.__name__ for tool in TOOLS}


def test_every_tool_and_every_argument_is_described_to_the_model():
    # The docstrings here are prompt text. An argument with no description
    # reaches the model as a bare type and gets filled in by guesswork.
    for name, schema in schemas().items():
        assert schema.description, name
        for argument, spec in schema.properties.items():
            assert spec.get("description"), f"{name}.{argument}"


def test_the_two_reading_tools_take_nothing_in():
    # compute_plan and open_questions hand back a computed result. There is no
    # parameter through which the model could hand one in instead.
    for name in ("compute_plan", "open_questions"):
        assert schemas()[name].properties == {}


def test_no_tool_accepts_a_figure_the_planner_should_have_worked_out():
    # A tripwire on the architectural thesis rather than on today's behaviour:
    # the day someone adds `compute_plan(total_outgoings_rupees=...)`, the model
    # is doing arithmetic again and this is where it shows up.
    computed = {"total", "totals", "balance", "shortfall", "surplus", "gap", "sum", "remaining"}
    for name, schema in schemas().items():
        for argument in schema.properties:
            assert not computed & set(argument.split("_")), f"{name}.{argument}"


def test_the_dated_scenarios_figures_are_still_what_the_planner_says():
    """Guards the literal strings in `evals/scenarios/numbers_come_from_the_planner.yaml`.

    That scenario asserts the assistant speaks these exact words. Discovering a
    drift there costs a minute, an API call and a judge; discovering it here
    costs five seconds and names both files.

    On paper from 2026-09-01, opening two thousand:

        the 1st   +18,000 ->  20,000
        the 5th   -12,000 ->   8,000
        the 8th   - 3,000 ->   5,000
        the 10th  -15,000 -> -10,000   <- first runs short here
        the 12th  - 6,000 -> -16,000   <- the gap if everything is paid on time

    Cutting the subscriptions lifts the worst day to -13,000 and giving up the
    unsecured loan lifts it to -7,000, which is where the ladder runs out: rent
    and the school fee are essentials and are never given up.
    """
    session = Session(as_of=AS_OF)
    for kwargs in (
        {"kind": "cash_on_hand", "label": "Cash on hand", "amount_rupees": 2_000},
        {"kind": "income", "label": "Salary", "amount_rupees": 18_000, "day_of_month": 1},
        {"kind": "essential", "label": "Rent", "amount_rupees": 12_000, "day_of_month": 5},
        {"kind": "optional", "label": "Subscriptions", "amount_rupees": 3_000, "day_of_month": 8},
        {"kind": "essential", "label": "School fee", "amount_rupees": 15_000, "day_of_month": 10},
        {"kind": "loan_emi", "label": "Personal loan EMI", "amount_rupees": 6_000, "day_of_month": 12},
    ):
        call(record_money_fact, session, **kwargs)

    payload = call(compute_plan, session)

    assert payload["first_runs_short_on"] == "the tenth"
    assert payload["still_short_after_all_that"] == "seven thousand rupees"
    assert payload["gap_if_everything_is_paid_on_time"] == "sixteen thousand rupees"
    assert [a["label"] for a in payload["spending_to_cut"]] == ["Subscriptions"]
    assert [a["label"] for a in payload["cannot_be_paid"]] == ["Personal loan EMI"]
