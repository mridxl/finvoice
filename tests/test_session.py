"""The session: ids the model can name, and cards that go out only when they move."""

import asyncio
from datetime import date

from server.domain.events import Fact, FactRecorded
from server.domain.money import from_rupees
from server.session import Session

AS_OF = date(2026, 9, 1)


def fact(fact_id: str, kind: str, label: str, rupees: int, **kw) -> FactRecorded:
    return FactRecorded(Fact(fact_id, kind, label, from_rupees(rupees), **kw))


def collector():
    sent: list[dict] = []

    async def publish(message: dict) -> None:
        sent.append(message)

    return sent, publish


def test_the_date_enters_here_and_nowhere_else():
    # `domain/` reads no clock, so a session with a pinned date replays identically.
    session = Session(as_of=AS_OF)
    session.record(fact("salary", "income", "Salary", 30_000, day=1))
    assert session.snapshot()[1].ledger[0].on == AS_OF


def test_an_id_is_readable_and_derived_from_what_the_user_called_it():
    session = Session(as_of=AS_OF)
    assert session.new_fact_id("Personal loan EMI") == "personal_loan_emi"
    assert session.new_fact_id("  Rent!  ") == "rent"


def test_a_second_thing_with_the_same_name_does_not_take_the_first_one_s_id():
    session = Session(as_of=AS_OF)
    session.record(fact("card_minimum", "credit_card", "Card minimum", 2_100))
    assert session.new_fact_id("Card minimum") == "card_minimum_2"


def test_only_the_cards_that_moved_go_over_the_wire():
    sent, publish = collector()
    session = Session(as_of=AS_OF, publish=publish)
    session.record(fact("salary", "income", "Salary", 30_000, day=1))
    first = asyncio.run(session.push_cards())
    assert "income" in first and len(sent) == len(first)

    session.record(fact("rent", "essential", "Rent", 10_000, day=5))
    moved = asyncio.run(session.push_cards())
    assert "essentials" in moved
    assert "income" not in moved  # nothing about the salary changed


def test_a_card_that_has_not_changed_is_not_sent_twice():
    _, publish = collector()
    session = Session(as_of=AS_OF, publish=publish)
    session.record(fact("salary", "income", "Salary", 30_000, day=1))
    asyncio.run(session.push_cards())
    assert asyncio.run(session.push_cards()) == []


def test_a_session_with_nowhere_to_publish_still_works():
    # The eval transport and the tests both run without a browser attached.
    session = Session(as_of=AS_OF)
    session.record(fact("salary", "income", "Salary", 30_000, day=1))
    assert asyncio.run(session.push_cards()) == []
