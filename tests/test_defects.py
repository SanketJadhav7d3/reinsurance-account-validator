import csv
import hashlib
from collections import Counter
from decimal import Decimal
from pathlib import Path

import pytest
from typer.testing import CliRunner

from rav.cli import app
from rav.generate import (
    ALL_DEFECTS,
    DEFECT_NAMES,
    generate_dataset,
    inject_defects,
    write_dataset,
)

TOL = Decimal("0.01")


def lines_by_ref(ds):
    return {ln.line_ref: (s, ln) for s in ds.submissions for ln in s.lines}


def test_every_defect_type_is_planted_at_most_once_per_line():
    ds = generate_dataset(42)
    defects = inject_defects(ds)
    assert {d.defect_id for d in defects} == set(ALL_DEFECTS)
    assert len({d.line_ref for d in defects}) == len(defects)
    total = sum(len(s.lines) for s in ds.submissions)
    assert 0.03 < len(defects) / total < 0.10


def test_injection_is_deterministic():
    a, b = generate_dataset(7), generate_dataset(7)
    assert inject_defects(a) == inject_defects(b)


def test_clean_lines_are_untouched_by_injection():
    clean, dirty = generate_dataset(42), generate_dataset(42)
    planted = {d.line_ref for d in inject_defects(dirty)}
    before, after = lines_by_ref(clean), lines_by_ref(dirty)
    for ref, (_, ln) in before.items():
        if ref not in planted:
            assert after[ref][1] == ln  # includes the originals behind D04 copies


@pytest.mark.parametrize("defect_id", ALL_DEFECTS, ids=lambda d: f"{d}-{DEFECT_NAMES[d]}")
def test_planted_line_actually_has_the_defect(defect_id):
    ds = generate_dataset(42)
    defects = inject_defects(ds, only=[defect_id], total=5)
    assert len(defects) == 5
    treaties = {t.treaty_id: t for t in ds.treaties}
    index = lines_by_ref(ds)
    for d in defects:
        sub, ln = index[d.line_ref]
        t = treaties.get(ln.treaty_id)
        if defect_id == "D01":
            assert abs(ln.balance - (ln.premium - ln.commission - ln.claims_paid)) > TOL
        elif defect_id == "D02":
            assert abs(ln.commission / ln.premium - t.commission_rate) > Decimal("0.005")
        elif defect_id == "D03":
            assert not (t.term_start <= ln.period_start and ln.period_end <= t.term_end)
        elif defect_id == "D04":
            twins = [
                o for r, (_, o) in index.items()
                if r != ln.line_ref and (o.treaty_id, o.period_start, o.premium)
                == (ln.treaty_id, ln.period_start, ln.premium)
            ]  # fmt: skip
            assert len(twins) == 1
            assert index[twins[0].line_ref][0].quarter < sub.quarter
        elif defect_id == "D05":
            assert ln.currency != t.currency
        elif defect_id == "D06":
            assert t is None
        elif defect_id == "D07":
            assert ln.premium < 0 and not ln.is_reversal
        elif defect_id == "D08":
            assert ln.premium is None or ln.claims_paid is None
        elif defect_id == "D09":
            assert ln.period_end > sub.submitted_on


def test_cli_writes_ground_truth_and_clean_mode_is_empty(tmp_path):
    runner = CliRunner()
    truth = tmp_path / "truth.csv"
    base = ["generate", "--out", str(tmp_path / "in"), "--truth", str(truth)]
    assert runner.invoke(app, base).exit_code == 0
    with truth.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert set(Counter(r["defect_id"] for r in rows)) == set(ALL_DEFECTS)
    assert runner.invoke(app, [*base, "--no-defects"]).exit_code == 0
    assert truth.read_text(encoding="utf-8").strip() == "line_ref,defect_id,description"


def test_clean_files_identical_with_and_without_defect_step(tmp_path):
    """--no-defects output equals generate_dataset alone (determinism guard for tests)."""
    write_dataset(generate_dataset(42), tmp_path / "a")
    runner = CliRunner()
    runner.invoke(
        app,
        ["generate", "--no-defects", "--out", str(tmp_path / "b"), "--truth", str(tmp_path / "t")],
    )

    def h(root: Path):
        return {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob("*")) if p.is_file()
        }  # fmt: skip

    assert h(tmp_path / "a") == h(tmp_path / "b")
