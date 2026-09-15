"""Days as they are spoken. A table, so pin the ends and the joins."""

from datetime import date

import pytest

from server.domain.speech import speak_date, speak_day, speak_month_day


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
    # With no window to be confused about, the month adds nothing.
    assert speak_date(date(2026, 9, 18)) == "the eighteenth"
    assert speak_date(None) is None


def test_a_date_in_the_second_month_of_the_window_is_named():
    # From the fifteenth, "the twentieth" is five days away and "the fifth" is
    # twenty. Said as bare days a listener orders them the other way round, which
    # is how a plan got explained with a sequence that could not produce it.
    opened_midmonth = date(2026, 9, 15)
    assert speak_date(date(2026, 9, 20), opened_midmonth) == "the twentieth"
    assert speak_date(date(2026, 10, 5), opened_midmonth) == "the fifth of October"

    # A window that opens on the first never straddles, so nothing is named and
    # nothing that reads it back has to change.
    assert speak_date(date(2026, 9, 20), date(2026, 9, 1)) == "the twentieth"
    assert speak_date(date(2026, 9, 5), date(2026, 9, 1)) == "the fifth"


def test_a_month_day_names_the_month_whether_or_not_it_is_needed():
    assert speak_month_day(date(2026, 10, 14)) == "the fourteenth of October"
    assert speak_month_day(date(2027, 1, 1)) == "the first of January"
