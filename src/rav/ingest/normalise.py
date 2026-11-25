"""Shared normalise step: raw canonical DataFrame -> typed rows.

Rows are never silently dropped. A row that has no line_ref cannot be keyed and is
rejected (logged and counted). An unparseable value becomes NULL (logged and counted) so
that the row still loads and the rules can see it."""

import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any

import pandas as pd

from rav.ingest.config import CedentConfig

log = logging.getLogger("rav.ingest")

AMOUNT_COLS = ["premium", "commission", "claims_paid", "balance"]
CANONICAL = [
    "line_ref", "treaty_id", "period_start", "period_end", "currency",
    *AMOUNT_COLS, "is_reversal", "submitted_on",
]  # fmt: skip
CENT = Decimal("0.01")


@dataclass
class NormalisedFile:
    rows: list[dict[str, Any]] = field(default_factory=list)
    rejected: int = 0  # rows that could not be keyed
    bad_values: int = 0  # values that could not be parsed (loaded as NULL)


def _blank(raw: Any) -> bool:
    return raw is None or (isinstance(raw, float) and pd.isna(raw)) or str(raw).strip() == ""


def parse_decimal(raw: Any, cfg: CedentConfig) -> Decimal | None:
    if _blank(raw):
        return None
    if isinstance(raw, float):  # Excel numeric cells arrive as float
        return Decimal(repr(raw)).quantize(CENT, rounding=ROUND_HALF_UP)
    text = str(raw).strip()
    if cfg.thousands:
        text = text.replace(cfg.thousands, "")
    if cfg.decimal != ".":
        text = text.replace(cfg.decimal, ".")
    return Decimal(text).quantize(CENT, rounding=ROUND_HALF_UP)


def parse_date(raw: Any, cfg: CedentConfig) -> date | None:
    if _blank(raw):
        return None
    if isinstance(raw, datetime):  # Excel date cells
        return raw.date()
    if isinstance(raw, date):
        return raw
    return datetime.strptime(str(raw).strip(), cfg.date_format).date()


def parse_bool(raw: Any, cfg: CedentConfig) -> bool:
    if isinstance(raw, bool):
        return raw
    return str(raw).strip().lower() in cfg.true_values


def _text(raw: Any, upper: bool = False) -> str | None:
    if _blank(raw):
        return None
    text = str(raw).strip()
    return text.upper() if upper else text


def normalise(df: pd.DataFrame, cfg: CedentConfig, source: str) -> NormalisedFile:
    out = NormalisedFile()
    for position, rec in enumerate(df.to_dict("records"), start=1):
        line_ref = _text(rec.get("line_ref"))
        if line_ref is None:
            out.rejected += 1
            log.warning("%s row %d rejected: no line_ref", source, position)
            continue
        row: dict[str, Any] = {
            "line_ref": line_ref,
            "treaty_id": _text(rec.get("treaty_id")),
            "currency": _text(rec.get("currency"), upper=True),
            "source_row": position,
        }
        parsers = {
            **{c: lambda v: parse_decimal(v, cfg) for c in AMOUNT_COLS},
            **{c: lambda v: parse_date(v, cfg) for c in ("period_start", "period_end")},
            "submitted_on": lambda v: parse_date(v, cfg),
        }
        for col, parser in parsers.items():
            try:
                row[col] = parser(rec.get(col))
            except (InvalidOperation, ValueError):
                row[col] = None
                out.bad_values += 1
                log.warning("%s row %d: cannot parse %s=%r", source, position, col, rec.get(col))
        if cfg.flip_claims and row["claims_paid"] is not None:
            row["claims_paid"] = -row["claims_paid"]
        row["is_reversal"] = parse_bool(rec.get("is_reversal"), cfg)
        out.rows.append(row)
    return out
