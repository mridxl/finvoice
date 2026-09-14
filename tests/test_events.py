"""The log and its fold: corrections, retractions, conflicts.

Corrections append. Every test here checks that the old value survives as
history while the current value moves, because "the user changed their mind"
is a first-class operation, not a patch.
"""

from server.domain.events import (
    Bounds,
    ConflictFlagged,
    ConflictResolved,
    Fact,
    FactCorrected,
    FactRecorded,
    FactRetracted,
)
from server.domain.money import from_rupees
from server.domain.state import fold
from tests.golden import GOLDEN


def test_fold_of_the_golden_log():
    state = fold(GOLDEN)
    assert len(state.facts) == 11
    assert state.version == len(GOLDEN)
    assert state.get("salary").amount == from_rupees(38_000)


def test_certainty_is_derived_from_the_data_not_stored():
    state = fold(GOLDEN)
    assert state.get("salary").certainty == "stated"
    assert state.get("spouse").certainty == "estimated"  # carries day_bounds
    unknown = fold([*GOLDEN, FactRecorded(Fact("gas", "essential", "Gas cylinder"))])
    assert unknown.get("gas").certainty == "unknown"


def test_correction_appends_and_keeps_the_old_value():
    log = [*GOLDEN, FactCorrected("salary", amount=from_rupees(41_000), verbatim="no, forty one", turn=7)]
    state = fold(log)
    assert state.get("salary").amount == from_rupees(41_000)
    assert state.history["salary"][-1].amount == from_rupees(38_000)
    assert state.version == len(log)


def test_correcting_an_amount_supersedes_its_estimate():
    estimated = FactRecorded(
        Fact("gas", "essential", "Gas cylinder", from_rupees(1_000), day=12,
             amount_bounds=Bounds(from_rupees(800), from_rupees(1_200)))
    )
    state = fold([estimated, FactCorrected("gas", amount=from_rupees(1_150))])
    assert state.get("gas").amount_bounds is None
    assert state.get("gas").certainty == "stated"


def test_correcting_a_day_leaves_an_amount_estimate_alone():
    estimated = FactRecorded(
        Fact("spouse", "income", "Spouse income", from_rupees(12_000), day=10,
             amount_bounds=Bounds(from_rupees(10_000), from_rupees(12_000)))
    )
    state = fold([estimated, FactCorrected("spouse", day=14)])
    assert state.get("spouse").day == 14
    assert state.get("spouse").amount_bounds is not None


def test_retraction_removes_the_fact_entirely():
    state = fold([*GOLDEN, FactRetracted("optional", reason="not a real expense")])
    assert state.get("optional") is None
    assert len(state.facts) == 10


def test_an_open_conflict_becomes_one_fact_carrying_the_disputed_range():
    # "nine and a half" then "around eight and a half" — two claims, one EMI.
    second = FactRecorded(Fact("loan_b", "loan_emi", "Personal loan EMI", from_rupees(8_500), day=15))
    state = fold([*GOLDEN, second, ConflictFlagged("c1", ("loan", "loan_b"), "9,500 vs 8,500")])

    planning = {f.fact_id: f for f in state.planning_facts()}
    assert "loan_b" not in planning  # never counted twice
    assert planning["loan"].amount == from_rupees(9_500)  # pessimistic: the larger outflow
    assert planning["loan"].amount_bounds == Bounds(from_rupees(8_500), from_rupees(9_500))
    assert planning["loan"].certainty == "estimated"


def test_resolving_a_conflict_drops_the_losing_claim():
    second = FactRecorded(Fact("loan_b", "loan_emi", "Personal loan EMI", from_rupees(8_500), day=15))
    state = fold([
        *GOLDEN,
        second,
        ConflictFlagged("c1", ("loan", "loan_b"), "9,500 vs 8,500"),
        ConflictResolved("c1", "loan_b"),
    ])
    assert state.get("loan") is None
    assert state.get("loan_b").amount == from_rupees(8_500)
    assert state.open_conflicts == ()
