"""How a date is said out loud. Amounts are `money.speak_rupees`.

TTS reads "the 15th" unreliably and "15" as a bare number, so every date the
assistant speaks is spelled as a day of the month in words. People say "the
fifteenth" anyway — nobody says the year of a bill due this month.
"""

from datetime import date

_ORDINALS: dict[int, str] = {
    1: "first", 2: "second", 3: "third", 4: "fourth", 5: "fifth",
    6: "sixth", 7: "seventh", 8: "eighth", 9: "ninth", 10: "tenth",
    11: "eleventh", 12: "twelfth", 13: "thirteenth", 14: "fourteenth",
    15: "fifteenth", 16: "sixteenth", 17: "seventeenth", 18: "eighteenth",
    19: "nineteenth", 20: "twentieth", 30: "thirtieth",
}
_TENS: dict[int, str] = {2: "twenty", 3: "thirty"}


def speak_day(day: int) -> str:
    """A day of the month as it is spoken: `speak_day(21)` is "the twenty-first"."""
    if not 1 <= day <= 31:
        raise ValueError(f"not a day of the month: {day}")
    if day in _ORDINALS:
        return f"the {_ORDINALS[day]}"
    tens, ones = divmod(day, 10)
    return f"the {_TENS[tens]}-{_ORDINALS[ones]}"


def speak_date(when: date | None) -> str | None:
    """A date as its day of the month. The month is never spoken: everything in
    the plan falls inside one thirty-day window, so naming it adds only noise."""
    return None if when is None else speak_day(when.day)
