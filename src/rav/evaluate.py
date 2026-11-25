"""Evaluation: join findings to the planted-defect ground truth.

- true positive:  rule R fired on line L and L was planted with R's `detects` type
- false positive: rule fired on a line that was not planted with its type
- false negative: a planted line whose rule did not flag it
"""

import csv
import json
from dataclasses import dataclass
from pathlib import Path

import psycopg

from rav.ingest.config import load_cedents
from rav.rules.models import RuleConfig

DEFAULT_TRUTH = Path("data/ground_truth/planted_defects.csv")


@dataclass
class RuleScore:
    rule_id: str
    name: str
    detects: str
    tp: int
    fp: int
    fn: int
    false_positive_lines: list[str]
    missed_lines: list[str]

    @property
    def precision(self) -> float | None:
        return pct(self.tp, self.tp + self.fp)

    @property
    def recall(self) -> float | None:
        return pct(self.tp, self.tp + self.fn)


def pct(num: int, den: int) -> float | None:
    """Percentage to one decimal, or None when undefined (nothing to measure)."""
    return None if den == 0 else round(100 * num / den, 1)


def score(
    findings: list[tuple[str, str]], truth: dict[str, str], rules: list[RuleConfig]
) -> list[RuleScore]:
    """findings: (rule_id, line_ref) pairs; truth: line_ref -> planted defect id."""
    scores = []
    for rule in rules:
        flagged = {ref for rid, ref in findings if rid == rule.id}
        planted = {ref for ref, d in truth.items() if d == rule.detects}
        scores.append(
            RuleScore(
                rule_id=rule.id,
                name=rule.name,
                detects=rule.detects,
                tp=len(flagged & planted),
                fp=len(flagged - planted),
                fn=len(planted - flagged),
                false_positive_lines=sorted(flagged - planted),
                missed_lines=sorted(planted - flagged),
            )
        )
    return scores


def read_truth(path: Path) -> dict[str, str]:
    with path.open(encoding="utf-8", newline="") as f:
        return {r["line_ref"]: r["defect_id"] for r in csv.DictReader(f)}


def read_seed(truth_path: Path) -> int | None:
    meta = truth_path.parent / "meta.json"
    if not meta.exists():
        return None
    return json.loads(meta.read_text(encoding="utf-8")).get("seed")


def evaluate(
    conn: psycopg.Connection,
    rules: list[RuleConfig],
    truth_path: Path = DEFAULT_TRUTH,
    run_id: int | None = None,
) -> dict:
    if run_id is None:
        row = conn.execute("SELECT max(run_id) FROM rule_runs").fetchone()
        if row[0] is None:
            raise RuntimeError("no rule run found: run `rav run` first")
        run_id = row[0]
    findings = conn.execute(
        "SELECT rule_id, line_ref FROM findings WHERE run_id = %s", (run_id,)
    ).fetchall()
    truth = read_truth(truth_path)
    scores = score(findings, truth, [r for r in rules if r.enabled])
    tp, fp, fn = (sum(getattr(s, k) for s in scores) for k in ("tp", "fp", "fn"))
    n_lines = conn.execute("SELECT count(*) FROM account_lines").fetchone()[0]
    cedents = [c for (c,) in conn.execute("SELECT DISTINCT cedent_id FROM submissions")]
    configs = load_cedents()
    return {
        "seed": read_seed(truth_path),
        "run_id": run_id,
        "rules": len(scores),
        "account_lines": n_lines,
        "planted_defects": len(truth),
        "cedents": len(cedents),
        "formats": len(
            {(k.format, k.delimiter, k.date_format, k.decimal)
             for c, k in configs.items() if c in cedents}
        ),  # a format = file type + delimiter + date style + decimal style
        "overall": {"tp": tp, "fp": fp, "fn": fn, "precision": pct(tp, tp + fp),
                    "recall": pct(tp, tp + fn)},  # fmt: skip
        "per_rule": [
            {"rule_id": s.rule_id, "name": s.name, "detects": s.detects, "tp": s.tp,
             "fp": s.fp, "fn": s.fn, "precision": s.precision, "recall": s.recall,
             "false_positive_lines": s.false_positive_lines, "missed_lines": s.missed_lines}
            for s in scores
        ],
    }  # fmt: skip


def _fmt(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.1f}%"


def render_markdown(result: dict) -> str:
    o = result["overall"]
    lines = [
        "# Evaluation report",
        "",
        "All data is synthetic. Every number below is computed by `rav evaluate`.",
        "",
        f"- Seed: {result['seed'] if result['seed'] is not None else 'unknown'}",
        f"- Rules: {result['rules']}",
        f"- Account lines: {result['account_lines']}",
        f"- Planted defects: {result['planted_defects']}",
        f"- Cedents: {result['cedents']} ({result['formats']} formats)",
        "",
        "| Rule | Detects | TP | FP | FN | Precision | Recall |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for r in result["per_rule"]:
        lines.append(
            f"| {r['rule_id']} {r['name']} | {r['detects']} | {r['tp']} | {r['fp']} | "
            f"{r['fn']} | {_fmt(r['precision'])} | {_fmt(r['recall'])} |"
        )
    lines.append(
        f"| **Overall** | | {o['tp']} | {o['fp']} | {o['fn']} | "
        f"{_fmt(o['precision'])} | {_fmt(o['recall'])} |"
    )
    misses = [r for r in result["per_rule"] if r["false_positive_lines"] or r["missed_lines"]]
    if misses:
        lines += ["", "## Lines behind FP / FN", ""]
        for r in misses:
            lines.append(
                f"- {r['rule_id']}: false positives {r['false_positive_lines'] or '-'}; "
                f"missed {r['missed_lines'] or '-'}"
            )
    return "\n".join(lines) + "\n"


def write_reports(result: dict, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "evaluation.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    (out_dir / "evaluation.md").write_text(render_markdown(result), encoding="utf-8")
