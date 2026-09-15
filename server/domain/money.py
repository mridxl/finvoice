"""Money is an integer count of paise. No float survives past this module.

Rupees arrive from the model as human decimals and are converted here, once.
Every rounding decision in the codebase happens in this file — if you find
yourself rounding somewhere else, the function you want belongs here instead.
"""

from decimal import ROUND_HALF_UP, Decimal

Money = int  # paise

PAISE = 100

_ONES = (
    "zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine",
    "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen",
    "seventeen", "eighteen", "nineteen",
)
_TENS = ("", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety")
_SCALES = ((10_000_000, "crore"), (100_000, "lakh"), (1_000, "thousand"), (100, "hundred"))


def from_rupees(amount: float | str | Decimal) -> Money:
    """Convert at the boundary. The one function allowed to see a float, and it
    returns paise, so no float ever reaches a balance.

    Via `str()` because `Decimal(float)` preserves the binary error that
    `Decimal(str(float))` discards: `Decimal(0.1)` is 0.1000000000000000055…
    """
    return int((Decimal(str(amount)) * PAISE).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def to_rupees(m: Money) -> Decimal:
    """For display and assertions only. Never feed the result back into a sum."""
    return Decimal(m) / PAISE


def allocate(total: Money, parts: int) -> list[Money]:
    """Split a total into `parts` that sum to exactly the total.

    The remainder is handed out a paisa at a time to the earliest parts rather
    than dropped, so an expense spread over the month still totals what the
    user actually said.
    """
    if parts <= 0:
        raise ValueError("parts must be positive")
    sign = -1 if total < 0 else 1
    base, remainder = divmod(abs(total), parts)
    return [sign * (base + (1 if i < remainder else 0)) for i in range(parts)]


def midpoint(low: Money, high: Money) -> Money:
    """The centre of an interval, for planning on a range nobody has pinned down.

    An interval has a centre and a conflict does not, which is the whole
    difference between this and `FinancialState._collapse`: two figures for one
    thing are a contradiction to be settled, a range is an honest answer to plan
    from. The bounds are kept alongside, so `gaps.py` re-plans at both ends and
    asks only if the spread actually changes the month.

    Half a paisa rounds away from zero, the same direction as `from_rupees`.
    """
    total = low + high
    sign = -1 if total < 0 else 1
    return sign * ((abs(total) + 1) // 2)


def format_rupees(m: Money) -> str:
    """Indian digit grouping, no currency symbol. For cards, not for speech."""
    rupees, paise = divmod(abs(m), PAISE)
    text = _group_indian(rupees)
    if paise:
        text = f"{text}.{paise:02d}"
    return f"-{text}" if m < 0 else text


def speak_rupees(m: Money) -> str:
    """Amounts as words, for anything the assistant says aloud.

    TTS renders the rupee symbol unreliably and long digit strings
    inconsistently, and the user hearing the number correctly is the whole
    point of reading it back.
    """
    rupees = (abs(m) + PAISE // 2) // PAISE  # nearest rupee; paise are never spoken
    unit = "rupee" if rupees == 1 else "rupees"
    return f"{_bare(m)} {unit}"


def speak_range(low: Money, high: Money) -> str:
    """A range as one phrase, with the unit said once at the end.

    Read back to the user in place of the figure the planner is working from,
    because that figure is the middle of this and the user never said it. The
    read-back is there to catch a mishearing, and it cannot do that with a
    number nobody uttered.
    """
    if low > high:
        low, high = high, low
    return f"between {_bare(low)} and {speak_rupees(high)}"


def _bare(m: Money) -> str:
    """Whole rupees in words, without the unit. `speak_rupees` adds it."""
    rupees = (abs(m) + PAISE // 2) // PAISE
    return f"{'minus ' if m < 0 else ''}{_in_words(rupees)}"


def _group_indian(n: int) -> str:
    text = str(n)
    if len(text) <= 3:
        return text
    head, tail = text[:-3], text[-3:]
    groups = []
    while len(head) > 2:
        head, group = head[:-2], head[-2:]
        groups.insert(0, group)
    if head:
        groups.insert(0, head)
    return ",".join([*groups, tail])


def _in_words(n: int) -> str:
    if n < 20:
        return _ONES[n]
    if n < 100:
        tens, ones = divmod(n, 10)
        return _TENS[tens] + (f" {_ONES[ones]}" if ones else "")
    for value, name in _SCALES:
        if n >= value:
            head, rest = divmod(n, value)
            spoken = f"{_in_words(head)} {name}"
            return f"{spoken} {_in_words(rest)}" if rest else spoken
    raise AssertionError("unreachable")
