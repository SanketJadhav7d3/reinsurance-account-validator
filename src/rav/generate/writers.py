"""One writer per cedent format. Output must be byte-identical for the same dataset."""

import csv
import json
import re
import shutil
import zipfile
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from openpyxl import Workbook

from rav.generate.model import Dataset, Line, Submission

FIELDS = [
    "line_ref", "treaty_id", "period_start", "period_end", "currency",
    "premium", "commission", "claims_paid", "balance", "is_reversal", "submitted_on",
]  # fmt: skip
GERMAN_HEADERS = {
    "line_ref": "Referenz", "treaty_id": "Vertrag", "period_start": "Periode_von",
    "period_end": "Periode_bis", "currency": "Währung", "premium": "Prämie",
    "commission": "Provision", "claims_paid": "Schadenzahlungen", "balance": "Saldo",
    "is_reversal": "Storno", "submitted_on": "Eingereicht_am",
}  # fmt: skip
AMOUNTS = ["premium", "commission", "claims_paid", "balance"]


def _iso(d: date | None) -> str:
    return "" if d is None else d.isoformat()


def _de_date(d: date | None) -> str:
    return "" if d is None else d.strftime("%d.%m.%Y")


def _plain(x: Decimal | None) -> str:
    return "" if x is None else f"{x:.2f}"


def _de_num(x: Decimal | None) -> str:
    if x is None:
        return ""
    return f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _bool(v: bool) -> str:
    return "true" if v else "false"


def write_c1(sub: Submission, path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(FIELDS)
        for ln in sub.lines:
            w.writerow(
                [ln.line_ref, ln.treaty_id or "", _iso(ln.period_start), _iso(ln.period_end),
                 ln.currency or "", *(_plain(getattr(ln, a)) for a in AMOUNTS),
                 _bool(ln.is_reversal), _iso(sub.submitted_on)]
            )  # fmt: skip


def write_c2(sub: Submission, path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, delimiter=";", lineterminator="\n")
        w.writerow([GERMAN_HEADERS[k] for k in FIELDS])
        for ln in sub.lines:
            w.writerow(
                [ln.line_ref, ln.treaty_id or "", _de_date(ln.period_start),
                 _de_date(ln.period_end), ln.currency or "",
                 *(_de_num(getattr(ln, a)) for a in AMOUNTS),
                 "ja" if ln.is_reversal else "nein", _de_date(sub.submitted_on)]
            )  # fmt: skip


def _fixed_zip(path: Path) -> None:
    """openpyxl stamps zip entries with the current time; rewrite with a fixed one."""
    tmp = path.with_suffix(".tmp")
    with zipfile.ZipFile(path) as src, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            zi = zipfile.ZipInfo(info.filename, date_time=(2020, 1, 1, 0, 0, 0))
            zi.compress_type = zipfile.ZIP_DEFLATED
            data = src.read(info.filename)
            if info.filename == "docProps/core.xml":  # openpyxl stamps modified = now()
                data = re.sub(
                    rb"(<dcterms:modified[^>]*>)[^<]*", rb"\g<1>2020-01-01T00:00:00Z", data
                )
            dst.writestr(zi, data)
    shutil.move(tmp, path)


def write_c3(sub: Submission, path: Path) -> None:
    """Row 1 title, row 2 merged 'Amounts' group header, row 3 column headers, data from row 4."""
    wb = Workbook()
    wb.properties.creator = "rav"
    wb.properties.created = wb.properties.modified = datetime(2020, 1, 1)
    ws = wb.active
    ws.title = "Account"
    ws.append([f"Technical account {sub.cedent_id} {sub.quarter}"])
    cols = ["Line ref", "Treaty", "From", "To", "Currency", "Premium", "Commission",
            "Claims paid", "Balance", "Reversal", "Submitted on"]  # fmt: skip
    ws.append([None] * 5 + ["Amounts"] + [None] * 5)
    ws.merge_cells(start_row=2, start_column=6, end_row=2, end_column=8)
    ws.append(cols)

    def num(x: Decimal | None) -> float | None:
        return None if x is None else float(x)

    for ln in sub.lines:
        ws.append(
            [ln.line_ref, ln.treaty_id, ln.period_start, ln.period_end, ln.currency,
             num(ln.premium), num(ln.commission), num(ln.claims_paid), num(ln.balance),
             "Yes" if ln.is_reversal else "No", sub.submitted_on]
        )  # fmt: skip
    wb.save(path)
    _fixed_zip(path)


def _line_json(ln: Line) -> dict:
    def amt(x: Decimal | None, sign: int = 1) -> str | None:
        return None if x is None else f"{x * sign:.2f}"

    return {
        "line_ref": ln.line_ref, "treaty_id": ln.treaty_id,
        "period_start": _iso(ln.period_start), "period_end": _iso(ln.period_end),
        "currency": ln.currency, "premium": amt(ln.premium), "commission": amt(ln.commission),
        "claims_paid": amt(ln.claims_paid, -1),  # C4 reports claims as negative
        "balance": amt(ln.balance), "is_reversal": ln.is_reversal,
    }  # fmt: skip


def write_c4(sub: Submission, path: Path) -> None:
    doc = {
        "submission": {"cedent": sub.cedent_id, "quarter": sub.quarter,
                       "submitted_on": _iso(sub.submitted_on)},
        "lines": [_line_json(ln) for ln in sub.lines],
    }  # fmt: skip
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


WRITERS = {"C1": (write_c1, "csv"), "C2": (write_c2, "csv"), "C3": (write_c3, "xlsx"),
           "C4": (write_c4, "json")}  # fmt: skip


def write_dataset(ds: Dataset, out_dir: Path) -> list[Path]:
    """Write treaties.csv and every submission file under out_dir (= data/incoming)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    tpath = out_dir / "treaties.csv"
    with tpath.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["treaty_id", "cedent_id", "line_of_business", "currency",
                    "term_start", "term_end", "commission_rate"])  # fmt: skip
        for t in ds.treaties:
            w.writerow([t.treaty_id, t.cedent_id, t.line_of_business, t.currency,
                        t.term_start.isoformat(), t.term_end.isoformat(),
                        f"{t.commission_rate:.4f}"])  # fmt: skip
    written = [tpath]
    cleaned: set[Path] = set()
    for sub in ds.submissions:
        writer, ext = WRITERS[sub.cedent_id]
        folder = out_dir / sub.cedent_id
        folder.mkdir(exist_ok=True)
        if folder not in cleaned:
            for stale in folder.glob(f"*.{ext}"):
                stale.unlink()  # leftovers from another seed
            cleaned.add(folder)
        path = folder / f"{sub.name}.{ext}"
        writer(sub, path)
        written.append(path)
    return written
