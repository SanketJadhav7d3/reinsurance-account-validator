import hashlib
import json
from decimal import Decimal
from pathlib import Path

from openpyxl import load_workbook

from rav.generate import generate_dataset, write_dataset


def digest(root: Path) -> dict[str, str]:
    return {
        str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


def test_same_seed_gives_identical_files(tmp_path):
    write_dataset(generate_dataset(42), tmp_path / "a")
    write_dataset(generate_dataset(42), tmp_path / "b")
    assert digest(tmp_path / "a") == digest(tmp_path / "b")


def test_different_seed_gives_different_files(tmp_path):
    write_dataset(generate_dataset(1), tmp_path / "a")
    write_dataset(generate_dataset(2), tmp_path / "b")
    assert digest(tmp_path / "a") != digest(tmp_path / "b")


def test_clean_lines_are_consistent():
    ds = generate_dataset(42)
    treaties = {t.treaty_id: t for t in ds.treaties}
    refs = set()
    for sub in ds.submissions:
        for ln in sub.lines:
            assert ln.line_ref not in refs
            refs.add(ln.line_ref)
            t = treaties[ln.treaty_id]
            assert ln.balance == ln.premium - ln.commission - ln.claims_paid
            assert ln.currency == t.currency
            assert t.term_start <= ln.period_start and ln.period_end <= t.term_end
            assert ln.period_end < sub.submitted_on
            assert abs(ln.commission - ln.premium * t.commission_rate) <= Decimal("0.005")


def test_format_quirks(tmp_path):
    ds = generate_dataset(42)
    write_dataset(ds, tmp_path)
    first = {c: next(s for s in ds.submissions if s.cedent_id == c) for c in ["C2", "C3", "C4"]}
    de = (tmp_path / "C2" / f"{first['C2'].name}.csv").read_text(encoding="utf-8")
    assert de.startswith("Referenz;Vertrag;Periode_von;Periode_bis;Währung;Prämie")
    assert "," in de.splitlines()[1].split(";")[5]  # German decimal comma
    ws = load_workbook(tmp_path / "C3" / f"{first['C3'].name}.xlsx").active
    assert "Technical account" in ws["A1"].value
    assert [str(r) for r in ws.merged_cells.ranges] == ["F2:H2"]
    doc = json.loads((tmp_path / "C4" / f"{first['C4'].name}.json").read_text(encoding="utf-8"))
    assert all(Decimal(ln["claims_paid"]) < 0 for ln in doc["lines"])
