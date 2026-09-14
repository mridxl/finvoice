"""Days as they are spoken. A table, so pin the ends and the joins."""

from datetime import date

import pytest

from server.domain.speech import speak_date, speak_day


@pytest.mark.parametrize(
    ("day", "spoken"),
    [
        (1, "the first"),
        (2, "the second"),
        (3, "the third"),
        (5, "the fifth"),
        (12, "the twelfth"),
        (20, "the twentieth"),
        (21, "the twenty-first"),
        (22, "the twenty-second"),
        (25, "the twenty-fifth"),
        (30, "the thirtieth"),
        (31, "the thirty-first"),
    ],
)
def test_a_day_of_the_month_is_spoken_as_an_ordinal(day, spoken):
    assert speak_day(day) == spoken


def test_a_day_that_is_not_a_day_is_refused():
    # Better a loud failure here than a bill placed on the thirty-second.
    with pytest.raises(ValueError):
        speak_day(0)
    with pytest.raises(ValueError):
        speak_day(32)


def test_a_date_is_spoken_as_its_day_alone():
    # The whole plan sits inside one thirty-day window, so the month adds nothing.
    assert speak_date(date(2026, 9, 18)) == "the eighteenth"
    assert speak_date(None) is None
