"""Cards as projections: everything on screen moves together or the test fails."""

import json

from server.domain.cards import TITLES, build_cards
from server.domain.events import ArrangementConfirmed, Bounds, FactCorrected
from server.domain.gaps import rank_gaps
from server.domain.money import from_rupees
from server.domain.planner import plan
from server.domain.state import fold
from tests.golden import AS_OF, GOLDEN, SWEPT, fact


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


def test_the_ledger_card_is_the_arithmetic_anyone_can_check():
    rows = cards_for(GOLDEN)["ledger"]["body"]["rows"]
    assert len(rows) == 30
    assert rows[0]["on"] == "2026-09-01"
    assert rows[-1]["closing"]["text"] == "4,500"


def test_the_missing_info_card_carries_the_ranked_questions():
    items = cards_for([*GOLDEN, *SWEPT])["missing_info"]["body"]["items"]
    assert [(i["fact_id"], i["impact"]) for i in items] == [("spouse", "high")]


def test_the_card_admits_a_category_nobody_has_closed():
    # The card is the ranking projected, so "still to confirm" cannot quietly
    # disagree with what the assistant is about to ask. Without the sweep both
    # would say the same wrong thing: that a salary and a rent is a finished
    # picture of the month.
    items = cards_for(GOLDEN)["missing_info"]["body"]["items"]
    sweeps = [i for i in items if i["field"] == "completeness"]
    assert {i["fact_id"] for i in sweeps} == {"money_in", "essentials", "loans", "cards"}


def test_the_actions_card_shows_an_arrangement_with_what_remains_owed():
    log = [*GOLDEN, ArrangementConfirmed("loan", from_rupees(4_500), "", 12)]
    body = cards_for(log)["actions"]["body"]
    assert body["unpaid"] == []
    arranged = body["arranged"][0]
    assert arranged["paid"]["text"] == "4,500"
    assert arranged["outstanding"]["text"] == "5,000"


def test_a_started_category_is_not_a_finished_one():
    # The regression this exists for: the screen switched to the plan as soon as
    # every category had something in it, which is the middle of the intake. One
    # loan recorded is "partly" until the user says it is the only one.
    strip = {c["id"]: c["state"] for c in cards_for(GOLDEN)["missing_info"]["body"]["coverage"]}
    assert strip == {"money_in": "partly", "essentials": "partly", "loans": "partly", "cards": "partly"}
    assert not cards_for(GOLDEN)["missing_info"]["body"]["enough_information"]


def test_a_category_nobody_has_mentioned_is_empty_and_is_the_one_being_asked():
    body = cards_for([fact("salary", "income", "Salary", 38_000, day=1)])["missing_info"]["body"]
    strip = {c["id"]: c["state"] for c in body["coverage"]}
    assert strip == {"money_in": "partly", "essentials": "empty", "loans": "empty", "cards": "empty"}
    # Untouched categories are asked about before sweeps, in COVERAGE's own order.
    assert [c["id"] for c in body["coverage"] if c["current"]] == ["essentials"]


def test_there_is_enough_information_only_when_no_question_is_left():
    # Closing all four categories is not the end of it: the spouse income still
    # arrives somewhere between the tenth and the twentieth, and which end it
    # lands on changes the plan. The agent is still asking, so the screen waits.
    swept = cards_for([*GOLDEN, *SWEPT])["missing_info"]["body"]
    assert [c["state"] for c in swept["coverage"]] == ["done"] * 4
    assert not swept["enough_information"]

    settled = cards_for([*GOLDEN, *SWEPT, FactCorrected("spouse", day=12, turn=9)])
    assert settled["missing_info"]["body"]["enough_information"]
    assert settled["missing_info"]["body"]["items"] == []


def test_a_card_shows_the_range_beside_the_figure_the_plan_uses():
    # The amount is the middle of the range, which is ours and not theirs. A card
    # that showed only the middle would be asserting a number the user never said.
    log = [*GOLDEN, FactCorrected("loan", amount=from_rupees(9_000),
                                  amount_bounds=Bounds(from_rupees(8_500), from_rupees(9_500)),
                                  turn=9)]
    item = next(i for i in cards_for(log)["obligations"]["body"]["items"] if i["fact_id"] == "loan")
    assert item["amount"]["text"] == "9,000"
    assert item["amount_range"]["low"]["text"] == "8,500"
    assert item["amount_range"]["high"]["text"] == "9,500"
    assert item["certainty"] == "estimated"


def test_a_plain_figure_carries_no_range():
    item = next(i for i in cards_for(GOLDEN)["essentials"]["body"]["items"] if i["fact_id"] == "rent")
    assert item["amount_range"] is None
