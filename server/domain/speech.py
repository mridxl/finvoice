"""How a date is said out loud. Amounts are `money.speak_rupees`.

TTS reads "the 15th" unreliably and "15" as a bare number, so every date the
assistant speaks is spelled out in words. People say "the fifteenth" anyway —
nobody says the year of a bill due this month, and mostly nobody says the month
either. `speak_date` names it in the one case where leaving it out misleads.
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

_MONTHS: tuple[str, ...] = (
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
)


def speak_day(day: int) -> str:
    """A day of the month as it is spoken: `speak_day(21)` is "the twenty-first"."""
    if not 1 <= day <= 31:
        raise ValueError(f"not a day of the month: {day}")
    if day in _ORDINALS:
        return f"the {_ORDINALS[day]}"
    tens, ones = divmod(day, 10)
    return f"the {_TENS[tens]}-{_ORDINALS[ones]}"


def speak_month_day(when: date) -> str:
    """Day and month: `speak_month_day(date(2026, 10, 5))` is "the fifth of October"."""
    return f"{speak_day(when.day)} of {_MONTHS[when.month - 1]}"


def speak_date(when: date | None, since: date | None = None) -> str | None:
    """A date as its day of the month, naming the month only when it has to.

    A thirty-day window starting anywhere but the first straddles two months, and
    inside one the twentieth can fall *before* the fifth. Said as bare days those
    two cannot be ordered, and a listener supplies the calendar order instead —
    which is how a plan came to be explained, out loud, with a sequence that
    could not have produced the shortfall it had just quoted.

    Naming both months everywhere is noise. Naming only the far one carries the
    ordering by itself, the way a person does when they say "the fifth of next
    month": `since` is the day the window opens, and any date outside its month
    gets named. Omit `since` where there is no window to be confused about.
    """
    if when is None:
        return None
    if since is None or (when.year, when.month) == (since.year, since.month):
        return speak_day(when.day)
    return speak_month_day(when)
