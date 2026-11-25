"""Python rules, for checks that are awkward in SQL. Contract: (conn) -> list[Finding]."""

from collections import defaultdict

import psycopg

from rav.rules.models import Finding


def duplicate_lines(conn: psycopg.Connection) -> list[Finding]:
    """Same treaty, period and amounts reported more than once: keep the earliest
    submission and flag every later copy."""
    rows = conn.execute(
        """SELECT l.line_ref, l.treaty_id, l.period_start, l.period_end,
                  l.premium, l.commission, l.claims_paid, s.submitted_on, s.submission_id
           FROM account_lines l JOIN submissions s USING (submission_id)
           WHERE l.treaty_id IS NOT NULL AND l.premium IS NOT NULL"""
    ).fetchall()
    groups: dict[tuple, list[tuple]] = defaultdict(list)
    for ref, *key, submitted_on, submission_id in rows:
        groups[tuple(key)].append((submitted_on, submission_id, ref))
    findings = []
    for members in groups.values():
        members.sort()
        first_ref = members[0][2]
        findings += [
            Finding(ref, f"duplicate of {first_ref} (earlier submission)")
            for _, _, ref in members[1:]
        ]
    return sorted(findings, key=lambda f: f.line_ref)
