from collections import defaultdict
from datetime import date

import pytest

from rav.generate import ALL_DEFECTS, DEFECT_NAMES, generate_dataset, inject_defects, write_dataset
from rav.ingest import ingest_all
from rav.rules.engine import run_rules
from rav.rules.loader import load_rules

RULES = load_rules()
RULE_FOR = {r.detects: r.id for r in RULES}


def findings_by_rule(conn, run_id):
    out = defaultdict(set)
    for rule_id, ref in conn.execute(
        "SELECT rule_id, line_ref FROM findings WHERE run_id = %s", (run_id,)
    ):
        out[rule_id].add(ref)
    return dict(out)


def test_one_rule_per_defect_type():
    assert sorted(RULE_FOR) == ALL_DEFECTS and len(RULES) == 9


# ---- unit tests: one clean line + one violating line, exactly one finding ----------------

BASE = dict(
    treaty_id="T1", period_start=date(2025, 1, 1), period_end=date(2025, 3, 31), currency="EUR",
    premium=1000, commission=250, claims_paid=400, balance=350, is_reversal=False,
)  # fmt: skip

VIOLATIONS = {
    "R01": dict(balance=999),
    "R02": dict(commission=300, balance=300),
    "R03": dict(period_start=date(2024, 10, 1), period_end=date(2024, 12, 31)),
    "R04": "duplicate",
    "R05": dict(currency="USD"),
    "R06": dict(treaty_id="T-NOPE"),
    "R07": dict(premium=-1000, commission=-250, balance=-1150),
    "R08": dict(claims_paid=None),
    "R09": dict(period_start=date(2025, 4, 1), period_end=date(2025, 6, 30)),
}  # fmt: skip


def insert_line(conn, ref, sid, **kw):
    row = {**BASE, **kw, "line_ref": ref, "submission_id": sid}
    cols = ", ".join(row)
    conn.execute(
        f"INSERT INTO account_lines ({cols}) VALUES ({', '.join(f'%({c})s' for c in row)})", row
    )


@pytest.fixture
def seeded(conn):
    conn.execute(
        "INSERT INTO treaties VALUES ('T1','C1','property','EUR','2025-01-01','2025-12-31',0.25),"
        "('T2','C1','property','EUR','2025-01-01','2025-12-31',0.25)"
    )  # T2 keeps the violating line from looking like a duplicate of the clean one
    sids = [
        conn.execute(
            "INSERT INTO submissions (cedent_id, source_file, submitted_on) "
            "VALUES ('C1', %s, %s) RETURNING submission_id",
            (f"f{i}", d),
        ).fetchone()[0]
        for i, d in enumerate(["2025-04-10", "2025-07-10"])
    ]
    insert_line(conn, "CLEAN", sids[0])
    return conn, sids


@pytest.mark.parametrize("rule_id", sorted(VIOLATIONS))
def test_rule_flags_only_the_violating_line(seeded, rule_id):
    conn, sids = seeded
    spec = VIOLATIONS[rule_id]
    if spec == "duplicate":
        insert_line(conn, "BAD", sids[1])  # same content, later submission
    else:
        insert_line(conn, "BAD", sids[0], **{"treaty_id": "T2", **spec})
    conn.commit()
    run_id, _ = run_rules(conn, RULES)
    # exactly one finding overall, from the expected rule, on the violating line
    assert findings_by_rule(conn, run_id) == {rule_id: {"BAD"}}


def test_clean_fixture_has_no_findings(seeded):
    conn, _ = seeded
    conn.commit()
    _, counts = run_rules(conn, RULES)
    assert sum(counts.values()) == 0
    assert conn.execute("SELECT finished_at FROM rule_runs").fetchone()[0] is not None


# ---- clean-data guard and re-injection regression tests -----------------------------------


def load(conn, tmp_path, defects=None, total=5):
    ds = generate_dataset(42)
    planted = inject_defects(ds, only=defects, total=total) if defects else []
    write_dataset(ds, tmp_path)
    ingest_all(conn, tmp_path)
    return planted


def test_clean_data_produces_zero_findings(conn, tmp_path):
    load(conn, tmp_path)
    _, counts = run_rules(conn, RULES)
    assert counts == {r.id: 0 for r in RULES}


@pytest.mark.parametrize("defect_id", ALL_DEFECTS, ids=lambda d: f"{d}-{DEFECT_NAMES[d]}")
def test_rule_catches_reinjected_defect(conn, tmp_path, defect_id):
    planted = load(conn, tmp_path, [defect_id])
    run_id, _ = run_rules(conn, RULES)
    expected = {RULE_FOR[defect_id]: {d.line_ref for d in planted}}
    assert findings_by_rule(conn, run_id) == expected


# ---- config validation ----------------------------------------------------------------------


def test_bad_rule_file_fails_loudly(tmp_path):
    (tmp_path / "bad.yaml").write_text("id: R99\nname: x\ntype: sql\n", encoding="utf-8")
    with pytest.raises(ValueError, match="bad.yaml"):
        load_rules(tmp_path)


def test_sql_rule_needs_sql_file(tmp_path):
    (tmp_path / "bad.yaml").write_text(
        "id: R99\nname: x\ndetects: D01\nseverity: error\ndescription: d\ntype: sql\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="sql_file"):
        load_rules(tmp_path)
