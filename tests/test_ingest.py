from decimal import Decimal

import pytest

from rav.generate import generate_dataset, write_dataset
from rav.ingest import ingest_all, parse_file
from rav.ingest.config import load_cedents

CEDENTS = load_cedents()


@pytest.fixture(scope="module")
def clean(tmp_path_factory):
    root = tmp_path_factory.mktemp("incoming")
    ds = generate_dataset(42)
    write_dataset(ds, root)
    return ds, root


@pytest.mark.parametrize("cedent", ["C1", "C2", "C3", "C4"])
def test_adapter_roundtrips_every_line(clean, cedent):
    """Parsing each cedent's file gives back exactly what the generator wrote."""
    ds, root = clean
    for sub in (s for s in ds.submissions if s.cedent_id == cedent):
        cfg = CEDENTS[cedent]
        path = next((root / cedent).glob(f"{sub.name}.*"))
        parsed = parse_file(path, cfg)
        assert parsed.rejected == 0 and parsed.bad_values == 0
        assert len(parsed.rows) == len(sub.lines)
        for row, ln in zip(parsed.rows, sub.lines, strict=True):
            assert row["line_ref"] == ln.line_ref
            assert (row["premium"], row["commission"], row["claims_paid"], row["balance"]) == (
                ln.premium, ln.commission, ln.claims_paid, ln.balance,
            )  # fmt: skip
            assert row["period_start"] == ln.period_start
            assert row["period_end"] == ln.period_end
            assert row["submitted_on"] == sub.submitted_on
            assert row["currency"] == ln.currency


def test_german_decimals_and_dates(clean):
    _, root = clean
    path = next((root / "C2").glob("*.csv"))
    text = path.read_text(encoding="utf-8")
    assert "." in text.splitlines()[1].split(";")[2]  # 31.03.2025 style date
    row = parse_file(path, CEDENTS["C2"]).rows[0]
    assert isinstance(row["premium"], Decimal) and row["premium"] > 1000


def test_c4_negative_claims_are_flipped(clean):
    _, root = clean
    path = next((root / "C4").glob("*.json"))
    assert '"claims_paid": "-' in path.read_text(encoding="utf-8")
    assert all(r["claims_paid"] > 0 for r in parse_file(path, CEDENTS["C4"]).rows)


def test_c3_skips_title_and_merged_header(clean):
    _, root = clean
    rows = parse_file(next((root / "C3").glob("*.xlsx")), CEDENTS["C3"]).rows
    assert rows[0]["line_ref"].startswith("C3-")


def test_unparseable_value_loads_as_null_and_missing_ref_is_rejected(tmp_path):
    f = tmp_path / "c1.csv"
    f.write_text(
        "line_ref,treaty_id,period_start,period_end,currency,premium,commission,"
        "claims_paid,balance,is_reversal,submitted_on\n"
        "C1-2025Q1-0001,TR-1,2025-01-01,2025-03-31,eur,abc,1.00,2.00,3.00,false,2025-04-10\n"
        ",TR-1,2025-01-01,2025-03-31,EUR,1,1,1,1,false,2025-04-10\n",
        encoding="utf-8",
    )
    parsed = parse_file(f, CEDENTS["C1"])
    assert parsed.rejected == 1 and parsed.bad_values == 1
    assert parsed.rows[0]["premium"] is None and parsed.rows[0]["currency"] == "EUR"


def test_ingest_is_idempotent(conn, clean):
    ds, root = clean
    expected = sum(len(s.lines) for s in ds.submissions)

    def counts():
        return [
            conn.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
            for t in ("treaties", "submissions", "account_lines")
        ]

    first = ingest_all(conn, root)
    assert first.loaded == expected
    after_first = counts()
    ingest_all(conn, root)
    assert counts() == after_first == [len(ds.treaties), len(ds.submissions), expected]
