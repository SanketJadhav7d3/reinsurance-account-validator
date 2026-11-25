import json

from rav.evaluate import evaluate, pct, render_markdown, score, write_reports
from rav.generate import generate_dataset, inject_defects, write_dataset, write_ground_truth
from rav.ingest import ingest_all
from rav.rules.engine import run_rules
from rav.rules.loader import load_rules

RULES = load_rules()


def by_rule(scores):
    return {s.rule_id: s for s in scores}


def test_score_counts_tp_fp_fn():
    truth = {"L1": "D01", "L2": "D01", "L3": "D05"}
    # R01 hits L1 (TP) and L9 (FP) and misses L2 (FN); R05 flags L1, planted D01 -> FP
    findings = [("R01", "L1"), ("R01", "L9"), ("R05", "L1"), ("R05", "L3")]
    s = by_rule(score(findings, truth, RULES))
    assert (s["R01"].tp, s["R01"].fp, s["R01"].fn) == (1, 1, 1)
    assert s["R01"].missed_lines == ["L2"] and s["R01"].false_positive_lines == ["L9"]
    assert (s["R05"].tp, s["R05"].fp, s["R05"].fn) == (1, 1, 0)
    assert (s["R02"].tp, s["R02"].fp, s["R02"].fn) == (0, 0, 0)
    assert s["R02"].precision is None and s["R02"].recall is None  # undefined, not 100%


def test_pct_is_one_decimal_and_never_rounded_up_to_perfect():
    assert pct(2, 3) == 66.7
    assert pct(199, 200) == 99.5
    assert pct(0, 0) is None


def test_end_to_end_report(conn, tmp_path):
    ds = generate_dataset(42)
    defects = inject_defects(ds)
    write_dataset(ds, tmp_path / "in")
    write_ground_truth(defects, tmp_path / "gt" / "planted_defects.csv")
    (tmp_path / "gt" / "meta.json").write_text('{"seed": 42}', encoding="utf-8")
    ingest_all(conn, tmp_path / "in")
    run_rules(conn, RULES)

    result = evaluate(conn, RULES, tmp_path / "gt" / "planted_defects.csv")
    assert result["seed"] == 42 and result["rules"] == 9
    assert result["planted_defects"] == len(defects)
    assert result["account_lines"] == sum(len(s.lines) for s in ds.submissions)
    assert (result["cedents"], result["formats"]) == (4, 4)
    assert result["overall"]["tp"] == len(defects)
    assert result["overall"]["fp"] == result["overall"]["fn"] == 0

    write_reports(result, tmp_path / "reports")
    assert json.loads((tmp_path / "reports" / "evaluation.json").read_text())["rules"] == 9
    assert "| **Overall** |" in render_markdown(result)
