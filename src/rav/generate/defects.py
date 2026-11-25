"""Defect injection: corrupt a clean dataset and record every change as ground truth.

At most one defect per line, so evaluation is unambiguous. Uses its own seeded Random
(derived from the dataset seed) so the clean data is identical with or without defects."""

import csv
import random
from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal
from pathlib import Path

from rav.generate.core import CURRENCIES, money, quarter_bounds
from rav.generate.model import Dataset, Line, Submission

DEFECT_NAMES = {
    "D01": "balance_mismatch",
    "D02": "commission_off_terms",
    "D03": "period_outside_term",
    "D04": "duplicate_line",
    "D05": "currency_mismatch",
    "D06": "unknown_treaty",
    "D07": "negative_premium_no_reversal",
    "D08": "missing_required_field",
    "D09": "future_period",
}
ALL_DEFECTS = sorted(DEFECT_NAMES)


@dataclass(frozen=True)
class Defect:
    line_ref: str
    defect_id: str
    description: str


def _shift_quarter(d: date, n: int) -> tuple[date, date]:
    """Bounds of the calendar quarter n quarters after the one containing d."""
    idx = d.year * 4 + (d.month - 1) // 3 + n
    return quarter_bounds(idx // 4, idx % 4 + 1)


def _rebalance(ln: Line) -> None:
    ln.balance = ln.premium - ln.commission - ln.claims_paid


def inject_defects(
    ds: Dataset,
    only: list[str] | None = None,
    total: int | None = None,
    rate: float = 0.05,
) -> list[Defect]:
    """Mutate ds in place; return the planted defects. Defaults to ~5% of lines, at least
    one of each requested type. `only` restricts the types (used by regression tests)."""
    rng = random.Random(f"{ds.seed}-defects")
    types = sorted(only or ALL_DEFECTS)
    n_lines = sum(len(s.lines) for s in ds.submissions)
    total = total or max(len(types), round(rate * n_lines))
    quota = {t: total // len(types) + (i < total % len(types)) for i, t in enumerate(types)}

    treaties = {t.treaty_id: t for t in ds.treaties}
    subs = sorted(ds.submissions, key=lambda s: (s.cedent_id, s.quarter))
    all_lines = [(s, ln) for s in subs for ln in s.lines]
    used: set[str] = set()
    planted: list[Defect] = []

    def later_sub(sub: Submission) -> Submission | None:
        later = [s for s in subs if s.cedent_id == sub.cedent_id and s.quarter > sub.quarter]
        return later[0] if later else None

    def eligible(defect_id: str) -> list[tuple[Submission, Line]]:
        out = []
        for s, ln in all_lines:
            if ln.line_ref in used:
                continue
            t = treaties[ln.treaty_id]
            if defect_id == "D04" and later_sub(s) is None:
                continue
            if defect_id == "D09" and _shift_quarter(ln.period_start, 1)[1] > t.term_end:
                continue  # keep D09 free of D03: the next quarter must stay inside the term
            out.append((s, ln))
        return out

    def plant(ln: Line, defect_id: str, text: str) -> None:
        used.add(ln.line_ref)
        planted.append(Defect(ln.line_ref, defect_id, text))

    # D04 first: copies are taken from lines that are still clean, and the originals are
    # reserved so no later defect mutates them.
    for defect_id in sorted(quota, key=lambda d: d != "D04"):
        pool = eligible(defect_id)
        for sub, ln in rng.sample(pool, min(quota[defect_id], len(pool))):
            t = treaties[ln.treaty_id]
            if defect_id == "D01":
                delta = Decimal(rng.randint(1000, 500_000)) / 100 * rng.choice([1, -1])
                ln.balance += delta
                plant(ln, defect_id, f"balance shifted by {delta}")
            elif defect_id == "D02":
                bump = Decimal(rng.randint(100, 300)) / 10000  # +1.0 to +3.0 pp
                ln.commission = money(ln.premium * (t.commission_rate + bump))
                _rebalance(ln)
                plant(ln, defect_id, f"commission rate raised by {bump * 100:.1f} pp")
            elif defect_id == "D03":
                ln.period_start, ln.period_end = _shift_quarter(t.term_start, -1)
                plant(ln, defect_id, f"period moved to {ln.period_start}..{ln.period_end}")
            elif defect_id == "D04":
                target = later_sub(sub)
                copy = replace(ln, line_ref=f"{target.name}-{len(target.lines) + 1:04d}")
                target.lines.append(copy)
                used.add(ln.line_ref)  # reserve the original
                plant(copy, defect_id, f"copy of {ln.line_ref} in later submission")
            elif defect_id == "D05":
                other = rng.choice([c for c in CURRENCIES if c != t.currency])
                ln.currency = other
                plant(ln, defect_id, f"currency {other} instead of {t.currency}")
            elif defect_id == "D06":
                ln.treaty_id = f"TR-9999-{rng.randint(1, 9999):04d}"
                plant(ln, defect_id, f"unknown treaty {ln.treaty_id}")
            elif defect_id == "D07":
                ln.premium, ln.commission = -ln.premium, -ln.commission
                _rebalance(ln)  # stay internally consistent: only the sign is wrong
                plant(ln, defect_id, "negative premium, is_reversal=false")
            elif defect_id == "D08":
                field = rng.choice(["claims_paid", "premium"])
                setattr(ln, field, None)
                plant(ln, defect_id, f"{field} blanked")
            elif defect_id == "D09":
                ln.period_start, ln.period_end = _shift_quarter(ln.period_start, 1)
                plant(ln, defect_id, f"period ends {ln.period_end}, submitted {sub.submitted_on}")
    return sorted(planted, key=lambda d: d.line_ref)


def write_ground_truth(defects: list[Defect], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["line_ref", "defect_id", "description"])
        for d in defects:
            w.writerow([d.line_ref, d.defect_id, d.description])
