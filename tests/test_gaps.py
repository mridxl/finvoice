"""Gap ranking: the planner deciding what is worth a question.

The test that matters most is the negative one — a gap that changes nothing is
not reported, because that is what stops the agent working through a
questionnaire.
"""

from server.domain.events import (
    Bounds,
    ConflictFlagged,
    Fact,
    FactCorrected,
    FactRecorded,
    NothingFurther,
)
from server.domain.gaps import rank_gaps
from server.domain.money import from_rupees
from server.domain.planner import plan
from server.domain.state import fold
from tests.golden import AS_OF, GOLDEN, SWEPT, TIMING_TRAP, fact


def test_the_only_question_worth_asking_is_when_the_spouse_is_paid():
    gaps = rank_gaps(fold([*GOLDEN, *SWEPT]), AS_OF)
    assert len(gaps) == 1
    assert (gaps[0].fact_id, gaps[0].field, gaps[0].impact) == ("spouse", "day", "high")


def test_it_asks_about_the_date_because_the_amount_is_not_in_doubt():
    # Twelve thousand either way. Whether it lands on the tenth or the twentieth
    # is what decides if the card minimum gets paid.
    gap = rank_gaps(fold(GOLDEN), AS_OF)[0]
    assert gap.field == "day"
    assert (gap.low, gap.high) == (10, 20)
    assert "which payments go unmet" in gap.why


def test_a_range_that_changes_nothing_is_not_asked_about():
    vague = FactRecorded(
        Fact("gas", "essential", "Gas cylinder", from_rupees(1_000), day=12,
             amount_bounds=Bounds(from_rupees(900), from_rupees(1_100)))
    )
    gaps = rank_gaps(fold([*GOLDEN, vague]), AS_OF)
    assert "gas" not in {g.fact_id for g in gaps}


def test_nothing_left_to_ask_is_an_empty_ranking():
    # The stopping criterion has two halves. No remaining unknown moves the
    # outcome, *and* every category has been closed off by the user — TIMING_TRAP
    # has no loan and no card, which is only knowable because he was asked and
    # said so, and its one rent is all his spending only because he said that too.
    assert rank_gaps(fold([*TIMING_TRAP, *SWEPT]), AS_OF) == ()


def test_a_category_nobody_has_mentioned_is_asked_about():
    # The demo bug: income and cash recorded, nothing else, and the assistant
    # announced a plan. Sensitivity analysis cannot see an absent category,
    # because an unmentioned rent has no fact to probe and no range to swing.
    log = [
        fact("salary", "income", "Salary", 52_000, day=25),
        fact("cash", "cash_on_hand", "Cash in hand", 9_400),
    ]
    gaps = {g.fact_id: g for g in rank_gaps(fold(log), AS_OF)}
    assert gaps["essentials"].impact == "high"
    assert gaps["essentials"].field == "existence"
    assert {"essentials", "loans", "cards"} <= set(gaps)
    # Money coming in is a different and much weaker question, because something
    # is in it: all that is left there is whether it is everything.
    assert (gaps["money_in"].field, gaps["money_in"].impact) == ("completeness", "low")


def test_saying_you_have_none_settles_a_category_for_good():
    log = [
        fact("salary", "income", "Salary", 52_000, day=25),
        fact("rent", "essential", "Rent", 14_000, day=5),
        NothingFurther("loan_emi"),
    ]
    gaps = {g.fact_id for g in rank_gaps(fold(log), AS_OF)}
    assert "loans" not in gaps
    assert "cards" in gaps  # never asked about, so still open


def test_one_rent_is_not_the_same_as_knowing_what_the_month_costs():
    # The second demo: salary and "thirty three thousand for rent electricity",
    # then a plan announcing forty two thousand left over. No food, no travel, no
    # phone — and nobody had asked whether that rent was the whole story.
    log = [
        fact("salary", "income", "Salary", 75_000, day=1),
        fact("rent", "essential", "Rent and electricity", 33_000, day=5),
        NothingFurther("income"),
        NothingFurther("loan_emi"),
        NothingFurther("credit_card"),
    ]
    gaps = {g.fact_id: g for g in rank_gaps(fold(log), AS_OF)}
    assert gaps["essentials"].field == "completeness"
    assert "all of it" in gaps["essentials"].why
    # And the only thing that ends it is him saying so.
    assert rank_gaps(fold([*log, NothingFurther("essential")]), AS_OF) == ()


def test_money_in_the_pocket_is_not_money_coming_in():
    # Cash on hand is a starting balance, not an answer to what arrives during
    # the month, and the two fund very different thirty days. Someone who really
    # has nothing coming in says so and the question goes away.
    pocket = [fact("cash", "cash_on_hand", "Cash in hand", 9_400)]
    gaps = {g.fact_id: g for g in rank_gaps(fold(pocket), AS_OF)}
    assert (gaps["money_in"].field, gaps["money_in"].impact) == ("existence", "high")
    assert "what they do for a living" in gaps["money_in"].ask

    living_off_savings = fold([*pocket, NothingFurther("income")])
    assert "money_in" not in {g.fact_id for g in rank_gaps(living_off_savings, AS_OF)}


def test_the_question_carries_what_to_ask_about_rather_than_the_category():
    # "Do you have essential spending" asks someone to audit their own life from
    # a blank page. The anchor is what makes it answerable, and it is chosen here
    # rather than left to the model to improvise.
    cold = fold([fact("cash", "cash_on_hand", "Cash", 900)])
    gaps = {g.fact_id: g for g in rank_gaps(cold, AS_OF)}
    assert "how they get to work" in gaps["essentials"].ask
    assert "borrowed from family" in gaps["loans"].ask
    # An ordinary gap already knows what it is about and needs no anchor.
    assert all(not g.ask for g in rank_gaps(fold([*GOLDEN, *SWEPT]), AS_OF))


def test_remembering_a_loan_supersedes_having_said_there_were_none():
    log = [
        fact("salary", "income", "Salary", 52_000, day=25),
        fact("rent", "essential", "Rent", 14_000, day=5),
        NothingFurther("loan_emi"),
        fact("loan", "loan_emi", "Personal loan EMI", 9_500, day=15),
    ]
    assert fold(log).declared_complete == frozenset()


def test_a_missing_category_outranks_refining_a_figure():
    # Nothing is gained by pinning down the spouse's payday while nobody has said
    # whether there is a credit card at all.
    no_cards = [e for e in GOLDEN if e.fact.kind != "credit_card"]
    ranked = rank_gaps(fold(no_cards), AS_OF)
    assert ranked[0].fact_id == "cards"
    assert ranked[0].coverage is True
    assert any(not g.coverage for g in ranked), "no ordinary gap left to be outranked"


def test_an_amount_never_given_is_always_worth_asking():
    log = [*GOLDEN, FactRecorded(Fact("gas", "essential", "Gas cylinder", day=12))]
    gaps = {g.fact_id: g for g in rank_gaps(fold(log), AS_OF)}
    assert gaps["gas"].impact == "high"
    assert "missing from the plan" in gaps["gas"].why


def disputed_loan():
    second = FactRecorded(
        Fact("loan_b", "loan_emi", "Personal loan EMI", from_rupees(8_500), day=15)
    )
    return [*GOLDEN, second, ConflictFlagged("c1", ("loan", "loan_b"), "9,500 vs 8,500")]


def test_a_disputed_amount_on_an_unpaid_obligation_does_not_move_the_plan():
    # Found by the ranker, not predicted: once the EMI is the payment that goes
    # unmet, 8,500 and 9,500 produce an identical 30-day cash plan. The figure
    # changes what he owes, not what he can pay this month.
    probe = fold(disputed_loan()).pinned()
    outcomes = [
        plan(probe.replacing("loan", amount=from_rupees(n), amount_bounds=None), AS_OF)
        for n in (8_500, 9_500)
    ]
    assert outcomes[0].lowest == outcomes[1].lowest
    assert [a.fact_id for a in outcomes[0].unpaid] == [a.fact_id for a in outcomes[1].unpaid]


def test_a_contradiction_is_raised_even_when_it_changes_nothing():
    # The anti-questionnaire rule suppresses an estimate that moves no outcome.
    # A contradiction is different: leaving it unmentioned means our record of
    # what the user said stays wrong. So it is always asked, just ranked last.
    gaps = {(g.fact_id, g.field): g for g in rank_gaps(fold(disputed_loan()), AS_OF)}
    gap = gaps[("loan", "amount")]
    assert gap.impact == "low"
    assert "two different figures" in gap.why


def test_answering_a_question_removes_it():
    corrected = FactCorrected("spouse", day=10, verbatim="the tenth, always")
    assert rank_gaps(fold([*GOLDEN, *SWEPT, corrected]), AS_OF) == ()


def test_high_impact_questions_come_first():
    log = [
        *GOLDEN,
        FactRecorded(Fact("gas", "essential", "Gas cylinder", day=12)),
    ]
    impacts = [g.impact for g in rank_gaps(fold(log), AS_OF)]
    assert impacts == sorted(impacts, key=["high", "medium", "low"].index)
