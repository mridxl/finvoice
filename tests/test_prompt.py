"""The one part of the prompt that is computed, so the one part a test can hold.

Wording is judged by `evals/`, not here. What is checkable without a model is
that the span the model is told to repeat arrives as a single phrase it *can*
repeat: given the two dates loose in a sentence it paraphrases them, and the
first thing it drops is the ordinal.
"""

from datetime import date

from server.prompt import system_prompt


def test_the_span_is_one_quotable_phrase():
    prompt = system_prompt(date(2026, 9, 15))
    assert '"the fifteenth of September to the fourteenth of October"' in prompt


def test_the_window_is_thirty_days_inclusive_of_today():
    # The thirtieth day, not the thirtieth day after today.
    assert "the thirtieth of September" in system_prompt(date(2026, 9, 1))


def test_a_different_month_is_refused_rather_than_absorbed():
    assert "only plan the thirty days from today" in system_prompt(date(2026, 9, 15))
