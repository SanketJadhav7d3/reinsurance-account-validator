"""Clean synthetic data. Everything flows from one seeded Random, so output is reproducible."""

import random
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from rav.generate.model import Dataset, Line, Submission, Treaty

CEDENTS = ["C1", "C2", "C3", "C4"]
CURRENCIES = ["EUR", "USD", "GBP", "CHF"]
# Premium range per quarter, by line of business (whole currency units).
PREMIUM_RANGE = {
    "property": (200_000, 2_000_000),
    "motor": (100_000, 800_000),
    "marine": (150_000, 1_500_000),
    "liability": (80_000, 600_000),
}
CENT = Decimal("0.01")


def money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def quarter_bounds(year: int, q: int) -> tuple[date, date]:
    start = date(year, 3 * q - 2, 1)
    nxt = date(year + (q == 4), 1 if q == 4 else 3 * q + 1, 1)
    return start, nxt - timedelta(days=1)


def make_treaties(rng: random.Random, n: int) -> list[Treaty]:
    treaties = []
    for i in range(n):
        year = rng.choice([2024, 2025, 2026])
        start = date(year, rng.choice([1, 4, 7, 10]), 1)  # quarter-aligned terms
        end = date(start.year + 1, start.month, 1) - timedelta(days=1)
        treaties.append(
            Treaty(
                treaty_id=f"TR-{year}-{i + 1:04d}",
                cedent_id=CEDENTS[i % len(CEDENTS)],
                line_of_business=rng.choice(list(PREMIUM_RANGE)),
                currency=rng.choice(CURRENCIES),
                term_start=start,
                term_end=end,
                commission_rate=Decimal(rng.randint(2250, 3250)) / Decimal(10000),
            )
        )
    return treaties


def make_line(rng: random.Random, treaty: Treaty, start: date, end: date, ref: str) -> Line:
    lo, hi = PREMIUM_RANGE[treaty.line_of_business]
    premium = Decimal(rng.randint(lo * 100, hi * 100)) / 100
    commission = money(premium * treaty.commission_rate)
    loss_ratio = Decimal(rng.randint(40, 90)) / 100
    claims = money(premium * loss_ratio)
    return Line(
        line_ref=ref,
        treaty_id=treaty.treaty_id,
        period_start=start,
        period_end=end,
        currency=treaty.currency,
        premium=premium,
        commission=commission,
        claims_paid=claims,
        balance=premium - commission - claims,
    )


def generate_dataset(seed: int, n_treaties: int = 40) -> Dataset:
    """Treaties plus one submission per cedent per quarter, all clean (no defects)."""
    rng = random.Random(seed)
    treaties = make_treaties(rng, n_treaties)

    # (cedent, quarter) -> [(treaty, start, end)]
    buckets: dict[tuple[str, str], list[tuple[Treaty, date, date]]] = {}
    for t in treaties:
        for k in range(4):
            month0 = t.term_start.month - 1 + 3 * k
            y, q = t.term_start.year + month0 // 12, (month0 % 12) // 3 + 1
            start, end = quarter_bounds(y, q)
            buckets.setdefault((t.cedent_id, f"{y}Q{q}"), []).append((t, start, end))

    submissions = []
    for (cedent, quarter), items in sorted(buckets.items()):
        items.sort(key=lambda it: it[0].treaty_id)
        period_end = items[0][2]
        sub = Submission(cedent, quarter, period_end + timedelta(days=rng.randint(10, 30)))
        for seq, (t, start, end) in enumerate(items, start=1):
            sub.lines.append(make_line(rng, t, start, end, f"{cedent}-{quarter}-{seq:04d}"))
        submissions.append(sub)
    return Dataset(seed, treaties, submissions)
