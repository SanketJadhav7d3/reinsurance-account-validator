import importlib
import subprocess
from collections.abc import Callable

import psycopg

from rav.rules.loader import ROOT
from rav.rules.models import Finding, RuleConfig


def rules_version() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True
        )
        return out.stdout.strip() or "unknown"
    except OSError:
        return "unknown"


def run_sql_rule(conn: psycopg.Connection, rule: RuleConfig) -> list[Finding]:
    """A SQL rule is a SELECT returning line_ref and message for every violating line."""
    sql = (ROOT / rule.sql_file).read_text(encoding="utf-8")
    cur = conn.execute(sql, rule.params)
    columns = [c.name for c in cur.description]
    if columns[:2] != ["line_ref", "message"]:
        raise ValueError(f"{rule.id}: SQL must return line_ref, message (got {columns})")
    return [Finding(ref, msg) for ref, msg in cur.fetchall()]


def run_python_rule(conn: psycopg.Connection, rule: RuleConfig) -> list[Finding]:
    module, _, name = rule.function.rpartition(".")
    fn: Callable[[psycopg.Connection], list[Finding]] = getattr(
        importlib.import_module(module), name
    )
    return fn(conn)


def run_rules(conn: psycopg.Connection, rules: list[RuleConfig]) -> tuple[int, dict[str, int]]:
    """Run all enabled rules, record a rule_runs row and write findings.
    Returns (run_id, findings per rule id)."""
    run_id = conn.execute(
        "INSERT INTO rule_runs (rules_version) VALUES (%s) RETURNING run_id", (rules_version(),)
    ).fetchone()[0]
    counts: dict[str, int] = {}
    for rule in (r for r in rules if r.enabled):
        runner = run_sql_rule if rule.type == "sql" else run_python_rule
        findings = runner(conn, rule)
        counts[rule.id] = len(findings)
        conn.cursor().executemany(
            "INSERT INTO findings (run_id, rule_id, line_ref, severity, message) "
            "VALUES (%s, %s, %s, %s, %s)",
            [(run_id, rule.id, f.line_ref, rule.severity, f.message) for f in findings],
        )
    conn.execute("UPDATE rule_runs SET finished_at = now() WHERE run_id = %s", (run_id,))
    conn.commit()
    return run_id, counts
