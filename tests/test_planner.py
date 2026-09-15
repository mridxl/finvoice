"""The planner, checked against arithmetic done by hand.

Expected figures here are worked out on paper from the §4.7 fixture, not copied
from a previous run. A snapshot test would happily lock in a wrong answer.
"""

from datetime import date

from server.domain.events import (
    ArrangementConfirmed,
    Fact,
    FactCorrected,
    FactRecorded,
    FactRetracted,
)
from server.domain.money import from_rupees, speak_rupees
from server.domain.planner import CUSHION, _drop_sequence, cost_of_delay, plan
from server.domain.state import fold
from tests.golden import AS_OF, GOLDEN, TIMING_TRAP, fact


def golden_plan():
    return plan(fold(GOLDEN), AS_OF)


def test_window_is_thirty_days_from_as_of():
    outcome = golden_plan()
    assert len(outcome.ledger) == 30
    assert outcome.ledger[0].on == date(2026, 9, 1)
    assert outcome.ledger[-1].on == date(2026, 9, 30)
    assert (outcome.starts_on, outcome.ends_on) == (date(2026, 9, 1), date(2026, 9, 30))


def demo_log():
    """The facts from the 2026-09-15 demo, in the order they were given."""
    return [
        fact("cash", "cash_on_hand", "Cash in bank", 3_000),
        fact("salary", "income", "Salary", 75_000, day=5),
        fact("delivery", "income", "Food delivery", 4_000, spread=True),
        fact("emi", "loan_emi", "Education loan EMI", 8_000, day=10),
        fact("onetime", "optional", "One-time payment", 7_000, day=13),
        fact("rent", "essential", "Rent", 15_000, day=20),
        fact("living", "essential", "Monthly expenses", 12_500, spread=True),
        fact("phone", "essential", "Phone bill", 300, day=20),
        fact("home", "essential", "Money sent home", 20_000, day=20),
    ]


def test_the_same_facts_are_a_different_month_from_a_different_day():
    # The demo, and the reason the plan was unexplainable rather than wrong.
    # Started on the first, the salary on the fifth arrives before the rent, the
    # phone bill and the money sent home all land together on the twentieth, and
    # the month clears. Started on the fifteenth, the twentieth is five days away
    # and the salary is not until October, so the same facts break.
    #
    # Both answers are correct. Thirty days from today is not this month, and a
    # day of the month cannot say which of the two it belongs to.
    # Spread facts allocate to the paise, so the lowest point lands off a round
    # rupee. It is asserted as spoken, because that is the form he was given it in.
    from_the_first = plan(fold(demo_log()), date(2026, 9, 1))
    assert from_the_first.status == "feasible"
    assert from_the_first.first_shortfall_on is None
    assert speak_rupees(from_the_first.lowest) == "one thousand eight hundred sixty seven rupees"

    from_the_fifteenth = plan(fold(demo_log()), date(2026, 9, 15))
    assert from_the_fifteenth.status == "infeasible"
    assert from_the_fifteenth.first_shortfall_on == date(2026, 9, 20)
    assert speak_rupees(from_the_fifteenth.lowest) == (
        "minus thirty seven thousand nine hundred sixty seven rupees"
    )

    # What does not move is the month's arithmetic: the same money goes in and
    # out either way, and only when decides whether it is ever all there at once.
    assert from_the_first.closing == from_the_fifteenth.closing == from_rupees(19_200)


def test_paying_everything_on_time_runs_out_on_the_eighteenth():
    # Salary and spouse income total 50,000 with 2,200 in hand against 60,200 out.
    # The balance survives rent, the EMI and the school fee, and breaks on the
    # first credit-card minimum.
    outcome = golden_plan()
    assert outcome.baseline_gap == from_rupees(8_000)
    assert outcome.first_shortfall_on == date(2026, 9, 18)


def test_cutting_every_optional_rupee_still_leaves_him_five_thousand_short():
    outcome = plan(fold([*GOLDEN, FactRetracted("optional")]), AS_OF)
    assert outcome.baseline_gap == from_rupees(5_000)


def test_the_ladder_order_is_pinned():
    # The decision itself, not a consequence of it. Optional spending, then the
    # unsecured loan, then card minimums cheapest-to-delay first, then the
    # secured EMI. Changing this line should require changing this test.
    order = [f.fact_id for f in _drop_sequence(fold(GOLDEN).planning_facts())]
    assert order == ["optional", "loan", "cc2", "cc1", "scooter"]


def test_the_ladder_cuts_optional_spending_then_names_the_personal_loan():
    outcome = golden_plan()
    assert [a.fact_id for a in outcome.cuts] == ["optional"]
    assert [a.fact_id for a in outcome.unpaid] == ["loan"]
    assert outcome.unpaid[0].amount == from_rupees(9_500)
    assert outcome.unpaid[0].on == date(2026, 9, 15)


def test_an_unmet_obligation_is_infeasible_however_much_is_left_over():
    outcome = golden_plan()
    assert outcome.status == "infeasible"
    # 3,000 cut and a 9,500 EMI unpaid against an 8,000 gap leaves 4,500 spare.
    # The month clears on paper and the obligation is still not met, so the
    # leftover must never soften the verdict.
    assert outcome.closing == from_rupees(4_500)
    assert outcome.shortfall == 0


def test_essentials_and_the_secured_emi_are_never_sacrificed():
    outcome = golden_plan()
    touched = {a.fact_id for a in outcome.cuts + outcome.unpaid}
    assert touched.isdisjoint({"rent", "school", "household", "scooter"})


def test_card_minimums_outrank_the_unsecured_loan():
    outcome = golden_plan()
    assert {"cc1", "cc2"}.isdisjoint({a.fact_id for a in outcome.unpaid})
    # Same amount, different instrument: missing the card costs more, so the card
    # is protected and the loan is what gives way.
    card = Fact("a", "credit_card", "card", from_rupees(2_100))
    loan = Fact("b", "loan_emi", "loan", from_rupees(2_100))
    assert cost_of_delay(card) > cost_of_delay(loan)


def test_the_ledger_adds_up_to_the_closing_balance():
    outcome = golden_plan()
    moved = sum(e.amount for row in outcome.ledger for e in row.entries)
    assert outcome.opening + moved == outcome.closing
    assert outcome.lowest == min(row.closing for row in outcome.ledger)


def test_a_spread_expense_lands_on_every_day_and_totals_exactly():
    outcome = golden_plan()
    household = [e for row in outcome.ledger for e in row.entries if e.fact_id == "household"]
    assert len(household) == 30
    assert sum(e.amount for e in household) == -from_rupees(11_000)


def test_the_plan_labels_what_it_assumed():
    outcome = golden_plan()
    assert any("Spouse income" in note for note in outcome.assumptions)


def test_totals_can_look_healthy_while_the_dates_do_not_work():
    state = fold(TIMING_TRAP)
    income = sum(f.amount for f in state.of_kind("income", "cash_on_hand"))
    outgoings = sum(f.amount for f in state.of_kind("essential"))
    assert income > outgoings  # a monthly-total model stops here and says fine

    outcome = plan(state, AS_OF)
    assert outcome.status == "infeasible"
    assert outcome.first_shortfall_on == date(2026, 9, 5)
    assert outcome.shortfall == from_rupees(24_000)


def test_the_same_money_arriving_earlier_solves_it():
    outcome = plan(fold([*TIMING_TRAP, FactCorrected("wages", day=1)]), AS_OF)
    assert outcome.status == "feasible"
    assert outcome.shortfall == 0


def test_a_comfortable_month_is_feasible():
    log = [
        fact("cash", "cash_on_hand", "Cash on hand", 50_000),
        fact("salary", "income", "Salary", 50_000, day=1),
        fact("rent", "essential", "Rent", 10_000, day=5),
    ]
    assert plan(fold(log), AS_OF).status == "feasible"


def test_clearing_the_month_on_fumes_is_tight_not_feasible():
    log = [
        fact("salary", "income", "Salary", 10_000, day=1),
        fact("rent", "essential", "Rent", 9_500, day=5),
    ]
    outcome = plan(fold(log), AS_OF)
    assert outcome.lowest < CUSHION
    assert outcome.status == "tight"


def test_an_amount_we_do_not_know_is_left_out_rather_than_guessed():
    log = [*GOLDEN, FactRecorded(Fact("gas", "essential", "Gas cylinder", day=12))]
    assert plan(fold(log), AS_OF).closing == golden_plan().closing


def test_an_expense_with_no_date_is_placed_at_the_worst_point():
    log = [
        fact("salary", "income", "Salary", 10_000, day=20),
        fact("mystery", "essential", "Repair bill", 6_000),
    ]
    outcome = plan(fold(log), AS_OF)
    assert outcome.first_shortfall_on == date(2026, 9, 1)
    assert any("no date given" in note for note in outcome.assumptions)


def test_the_planner_never_invents_a_part_payment():
    # Nothing in the log mentions an arrangement, so the EMI stays all-or-nothing
    # and goes unmet in full. A reduced figure can only ever come from the user
    # reporting what their lender said.
    outcome = golden_plan()
    assert outcome.arranged == ()
    assert outcome.unpaid[0].paid == 0


def test_an_arrangement_the_user_brought_back_is_honoured():
    # He asked; they said they would take 4,500 this month. That is exactly the
    # 5,000 of relief the month needed after cutting optional spending, so the
    # balance lands on nothing left and nothing missed.
    log = [*GOLDEN, ArrangementConfirmed("loan", from_rupees(4_500), "they'll take 4,500", 12)]
    outcome = plan(fold(log), AS_OF)

    assert [a.fact_id for a in outcome.arranged] == ["loan"]
    assert outcome.arranged[0].paid == from_rupees(4_500)
    assert outcome.arranged[0].amount == from_rupees(9_500)  # still what he owes
    assert outcome.unpaid == ()
    assert outcome.closing == 0
    # It took cuts and an arrangement to get here, and 5,000 of the EMI is still
    # outstanding. That is never "feasible".
    assert outcome.status == "tight"


def test_the_arranged_amount_is_what_actually_leaves_the_account():
    log = [*GOLDEN, ArrangementConfirmed("loan", from_rupees(4_500), "", 12)]
    outcome = plan(fold(log), AS_OF)
    on_the_fifteenth = next(r for r in outcome.ledger if r.on == date(2026, 9, 15))
    loan = next(e for e in on_the_fifteenth.entries if e.fact_id == "loan")
    assert loan.amount == -from_rupees(4_500)


def test_an_arrangement_too_small_to_rescue_the_month_falls_through_to_unpaid():
    # They would only come down to 9,000. That frees 500 against a 5,000 gap, so
    # the ladder carries on and the EMI ends up unmet anyway.
    log = [*GOLDEN, ArrangementConfirmed("loan", from_rupees(9_000), "", 12)]
    outcome = plan(fold(log), AS_OF)
    assert outcome.arranged == ()
    assert [a.fact_id for a in outcome.unpaid] == ["loan"]


def test_an_arrangement_is_left_unused_when_the_month_already_clears():
    # The planner must never shrink a payment just because it is allowed to.
    log = [
        fact("cash", "cash_on_hand", "Cash on hand", 50_000),
        fact("salary", "income", "Salary", 50_000, day=1),
        fact("loan", "loan_emi", "Personal loan EMI", 9_500, day=15),
        ArrangementConfirmed("loan", from_rupees(4_500), "", 3),
    ]
    outcome = plan(fold(log), AS_OF)
    assert outcome.arranged == ()
    assert outcome.status == "feasible"


def test_only_a_payment_with_no_date_is_called_out_as_placed_at_the_worst_point():
    # Cash on hand has no date because it is the opening balance, not because
    # anyone forgot to say one — it is never placed on a day at all. An undated
    # bill genuinely is placed at its worst point, and still says so.
    log = [*GOLDEN, fact("insurance", "essential", "Insurance premium", 3_000)]
    placed = [n for n in plan(fold(log), AS_OF).assumptions if "worst point" in n]
    assert placed == ["Insurance premium: no date given, so it is placed at the worst point."]
