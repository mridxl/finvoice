"""The persona from BUILD-PLAN §4.7, as an event log.

One earner plus a spouse with irregular income, servicing more than the month
covers. In 52,200. Out 60,200. Cut every optional rupee and he is still 5,000
short — which is the point: the interesting case is the one that does not solve.

September 2026 has 30 days, so `AS_OF` makes day-of-month and window offset line
up and the ledger stays checkable by hand.
"""

from datetime import date

from server.domain.events import Bounds, Fact, FactRecorded
from server.domain.money import from_rupees

AS_OF = date(2026, 9, 1)


def fact(fact_id: str, kind: str, label: str, rupees=None, **kw) -> FactRecorded:
    amount = None if rupees is None else from_rupees(rupees)
    return FactRecorded(Fact(fact_id=fact_id, kind=kind, label=label, amount=amount, **kw))


GOLDEN = [
    fact("cash", "cash_on_hand", "Cash on hand", 2_200),
    fact("salary", "income", "Salary", 38_000, day=1),
    # "Sometimes late" — the amount is firm, the date is not. That distinction is
    # what makes the spouse income the question worth asking.
    fact("spouse", "income", "Spouse income", 12_000, day=10, day_bounds=Bounds(10, 20)),
    fact("rent", "essential", "Rent", 14_000, day=5),
    fact("scooter", "loan_emi", "Two-wheeler EMI", 4_200, day=8, secured=True),
    fact("school", "essential", "School fee", 15_000, day=10),
    fact("loan", "loan_emi", "Personal loan EMI", 9_500, day=15),
    fact("cc1", "credit_card", "Credit card 1 minimum", 2_100, day=18),
    fact("cc2", "credit_card", "Credit card 2 minimum", 1_400, day=22),
    fact("household", "essential", "Household essentials", 11_000, spread=True),
    fact("optional", "optional", "Optional spending", 3_000, spread=True),
]

# Feasible on monthly totals, broken on dates: 31,000 in against 25,000 out, but
# the money arrives on the 28th and the bill is due on the 5th. A planner that
# works in monthly totals calls this healthy.
TIMING_TRAP = [
    fact("cash", "cash_on_hand", "Cash on hand", 1_000),
    fact("wages", "income", "Wages", 30_000, day=28),
    fact("rent", "essential", "Rent", 25_000, day=5),
]
