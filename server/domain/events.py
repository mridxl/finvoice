"""The event log's vocabulary: facts and the things that happen to them.

Corrections append. Nothing here is ever mutated in place, which is what makes
"the user changed their mind" an ordinary operation rather than a patch, and
leaves an audit trail the cards can show.

The reducer lives in `state.py`, because it produces a `FinancialState` and the
dependency has to point one way.
"""

from dataclasses import dataclass
from typing import Literal

from server.domain.money import Money

Kind = Literal["income", "loan_emi", "credit_card", "essential", "optional", "cash_on_hand"]
Certainty = Literal["stated", "estimated", "unknown"]

OUTFLOW_KINDS: frozenset[str] = frozenset({"loan_emi", "credit_card", "essential", "optional"})


@dataclass(frozen=True)
class Bounds:
    """An inclusive range. Uncertainty is carried as an interval, not a distribution —
    interval arithmetic is explainable out loud in a way Monte Carlo is not."""

    low: int
    high: int

    def __post_init__(self) -> None:
        if self.low > self.high:
            raise ValueError(f"bounds inverted: {self.low} > {self.high}")


@dataclass(frozen=True)
class Fact:
    """One thing the user told us about their money.

    `day` is a day of the month, not a date: people say "the fifth", and which
    fifth it is depends on when the conversation happens. `spread=True` means an
    amount that trickles out across the month rather than landing on a day.
    """

    fact_id: str
    kind: Kind
    label: str
    amount: Money | None = None
    day: int | None = None
    amount_bounds: Bounds | None = None
    day_bounds: Bounds | None = None
    spread: bool = False
    secured: bool = False
    # What the lender has confirmed they will accept this month, when the user
    # has gone and asked them. Never computed, never assumed, and absent unless
    # the user reports an answer — the assistant is forbidden from inventing an
    # arrangement, and this field is the only way one can enter the plan.
    part_payment: Money | None = None
    verbatim: str = ""
    turn: int = 0

    @property
    def certainty(self) -> Certainty:
        """Derived, never stored — a stored certainty can contradict the amount beside it."""
        if self.amount is None:
            return "unknown"
        if self.amount_bounds is not None or self.day_bounds is not None:
            return "estimated"
        return "stated"

    @property
    def signed(self) -> Money:
        """Effect on the balance. Income adds, everything else takes away."""
        if self.amount is None:
            return 0
        return self.amount if self.kind in ("income", "cash_on_hand") else -self.amount


@dataclass(frozen=True)
class FactRecorded:
    fact: Fact


@dataclass(frozen=True)
class FactCorrected:
    """A revision of an existing fact.

    Correcting to a firm amount clears its bounds, because the user has now just
    told us the number. A revision can also go the other way — a stated figure
    becoming a range once they think about it — which is what `amount_bounds`
    carries, alongside the midpoint the planner works from. Without it the only
    way to widen a figure was to record the thing a second time, and the plan
    then carried both.
    """

    fact_id: str
    amount: Money | None = None
    day: int | None = None
    amount_bounds: Bounds | None = None
    verbatim: str = ""
    turn: int = 0


@dataclass(frozen=True)
class FactRetracted:
    fact_id: str
    reason: str = ""


@dataclass(frozen=True)
class ArrangementConfirmed:
    """The user asked their lender and came back with an answer.

    Deliberately not a `FactCorrected`: the user has not revised what they said,
    a third party has told them something new. It leaves the amount owed exactly
    as recorded, because an arrangement to pay less this month does not make the
    debt smaller.
    """

    fact_id: str
    accepts: Money
    verbatim: str = ""
    turn: int = 0


@dataclass(frozen=True)
class NothingFurther:
    """A category is finished: none at all, or none beyond what is already recorded.

    Both readings are the same answer — "that is everything of this kind" — and
    both are answers rather than absences. Without this, "no credit cards" is
    indistinguishable from "nobody has asked about credit cards yet", and "those
    are all my loans" from "one loan is recorded and we stopped there". `gaps`
    could then only choose between nagging about a category forever and never
    raising it again. Recording a fact of the same kind afterwards supersedes it,
    because people remember.
    """

    kind: Kind
    verbatim: str = ""
    turn: int = 0


@dataclass(frozen=True)
class ConflictFlagged:
    """Two statements about the same thing that cannot both be true."""

    conflict_id: str
    fact_ids: tuple[str, ...]
    note: str = ""


@dataclass(frozen=True)
class ConflictResolved:
    conflict_id: str
    chosen_fact_id: str


Event = (
    FactRecorded
    | FactCorrected
    | FactRetracted
    | ArrangementConfirmed
    | NothingFurther
    | ConflictFlagged
    | ConflictResolved
)
