"""Cards as projections: everything on screen moves together or the test fails."""

import json

from server.domain.cards import TITLES, build_cards
from server.domain.events import FactCorrected
from server.domain.gaps import rank_gaps
from server.domain.money import from_rupees
from server.domain.planner import plan
from server.domain.state import fold
from tests.golden import AS_OF, GOLDEN


def cards_for(log):
    state = fold(log)
    outcome = plan(state, AS_OF)
    return build_cards(state, outcome, rank_gaps(state, AS_OF))


def test_every_card_is_built():
    assert set(cards_for(GOLDEN)) == set(TITLES)


def test_cards_survive_the_trip_over_the_data_channel():
    # They are pushed as RTVI server messages, so anything unserialisable here
    # fails silently in the browser rather than loudly in a test.
    payload = json.dumps(cards_for(GOLDEN))
    assert "Infinity" not in payload and "NaN" not in payload


def test_amounts_arrive_rendered_so_the_browser_never_does_arithmetic():
    amount = cards_for(GOLDEN)["cash_position"]["body"]["opening"]
    assert amount == {"paise": 220_000, "text": "2,200", "speech": "two thousand two hundred rupees"}


def test_a_correction_moves_every_affected_card():
    before = cards_for(GOLDEN)
    after = cards_for([*GOLDEN, FactCorrected("salary", amount=from_rupees(30_000), turn=9)])

    moved = {k for k in before if before[k]["digest"] != after[k]["digest"]}
    assert {"income", "bottom_line", "calendar", "ledger", "actions"} <= moved
    assert after["bottom_line"]["revision"] > before["bottom_line"]["revision"]


def test_a_corrected_amount_shows_what_it_replaced():
    cards = cards_for([*GOLDEN, FactCorrected("salary", amount=from_rupees(30_000), turn=9)])
    salary = next(i for i in cards["income"]["body"]["items"] if i["fact_id"] == "salary")
    assert salary["amount"]["text"] == "30,000"
    assert salary["corrected_from"]["text"] == "38,000"


def test_untouched_cards_do_not_churn():
    before = cards_for(GOLDEN)
    after = cards_for([*GOLDEN, FactCorrected("salary", amount=from_rupees(30_000), turn=9)])
    assert before["essentials"]["digest"] == after["essentials"]["digest"]


def test_the_bottom_line_says_plainly_that_it_does_not_work():
    body = cards_for(GOLDEN)["bottom_line"]["body"]
    assert body["status"] == "infeasible"
    assert body["gap_if_all_paid"]["text"] == "8,000"
    assert body["first_shortfall_on"] == "2026-09-18"
    assert body["assumptions"]


def test_the_actions_card_separates_a_cut_from_a_missed_payment():
    body = cards_for(GOLDEN)["actions"]["body"]
    assert [a["label"] for a in body["cuts"]] == ["Optional spending"]
    assert [a["label"] for a in body["unpaid"]] == ["Personal loan EMI"]
    assert body["unpaid"][0]["reason"]


def test_the_ledger_card_is_the_arithmetic_a_reviewer_can_check():
    rows = cards_for(GOLDEN)["ledger"]["body"]["rows"]
    assert len(rows) == 30
    assert rows[0]["on"] == "2026-09-01"
    assert rows[-1]["closing"]["text"] == "4,500"


def test_the_missing_info_card_carries_the_ranked_questions():
    items = cards_for(GOLDEN)["missing_info"]["body"]["items"]
    assert [(i["fact_id"], i["impact"]) for i in items] == [("spouse", "high")]
