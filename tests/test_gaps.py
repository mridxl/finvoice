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
)
from server.domain.gaps import rank_gaps
from server.domain.money import from_rupees
from server.domain.planner import plan
from server.domain.state import fold
from tests.golden import AS_OF, GOLDEN, TIMING_TRAP


def test_the_only_question_worth_asking_is_when_the_spouse_is_paid():
    gaps = rank_gaps(fold(GOLDEN), AS_OF)
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
    # The stopping criterion: no remaining unknown moves the outcome.
    assert rank_gaps(fold(TIMING_TRAP), AS_OF) == ()


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
    answered = fold([*GOLDEN, FactCorrected("spouse", day=10, verbatim="the tenth, always")])
    assert rank_gaps(answered, AS_OF) == ()


def test_high_impact_questions_come_first():
    log = [
        *GOLDEN,
        FactRecorded(Fact("gas", "essential", "Gas cylinder", day=12)),
    ]
    impacts = [g.impact for g in rank_gaps(fold(log), AS_OF)]
    assert impacts == sorted(impacts, key=["high", "medium", "low"].index)
