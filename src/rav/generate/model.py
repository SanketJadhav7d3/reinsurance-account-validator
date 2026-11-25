"""Plain data containers for the synthetic dataset. Money is Decimal."""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal


@dataclass
class Treaty:
    treaty_id: str
    cedent_id: str
    line_of_business: str
    currency: str
    term_start: date
    term_end: date
    commission_rate: Decimal


@dataclass
class Line:
    """One account line: one treaty, one period."""

    line_ref: str
    treaty_id: str | None
    period_start: date | None
    period_end: date | None
    currency: str | None
    premium: Decimal | None
    commission: Decimal | None
    claims_paid: Decimal | None
    balance: Decimal | None
    is_reversal: bool = False


@dataclass
class Submission:
    """One file a cedent sent, containing many account lines."""

    cedent_id: str
    quarter: str  # e.g. "2025Q1"
    submitted_on: date
    lines: list[Line] = field(default_factory=list)

    @property
    def name(self) -> str:
        return f"{self.cedent_id}-{self.quarter}"


@dataclass
class Dataset:
    seed: int
    treaties: list[Treaty]
    submissions: list[Submission]
