"""Ingestion: adapters -> normalise -> idempotent load into PostgreSQL."""

import csv
from dataclasses import dataclass
from pathlib import Path

import psycopg

from rav.ingest.adapters import ADAPTERS
from rav.ingest.config import DEFAULT_CONFIG, CedentConfig, load_cedents
from rav.ingest.normalise import NormalisedFile, normalise

__all__ = ["IngestResult", "ingest_all", "load_treaties", "parse_file"]

COLS = ["line_ref", "treaty_id", "period_start", "period_end", "currency", "premium",
        "commission", "claims_paid", "balance", "is_reversal", "source_row"]  # fmt: skip


@dataclass
class IngestResult:
    files: int = 0
    loaded: int = 0
    rejected: int = 0
    bad_values: int = 0


def parse_file(path: Path, cfg: CedentConfig) -> NormalisedFile:
    df = ADAPTERS[cfg.format](path, cfg)
    return normalise(df, cfg, path.name)


def load_treaties(conn: psycopg.Connection, incoming: Path) -> int:
    with (incoming / "treaties.csv").open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    with conn.cursor() as cur:
        for r in rows:
            cur.execute(
                """INSERT INTO treaties (treaty_id, cedent_id, line_of_business, currency,
                       term_start, term_end, commission_rate)
                   VALUES (%(treaty_id)s, %(cedent_id)s, %(line_of_business)s, %(currency)s,
                       %(term_start)s, %(term_end)s, %(commission_rate)s)
                   ON CONFLICT (treaty_id) DO UPDATE SET
                       cedent_id = EXCLUDED.cedent_id,
                       line_of_business = EXCLUDED.line_of_business,
                       currency = EXCLUDED.currency, term_start = EXCLUDED.term_start,
                       term_end = EXCLUDED.term_end, commission_rate = EXCLUDED.commission_rate""",
                r,
            )
    conn.commit()
    return len(rows)


def load_submission(
    conn: psycopg.Connection, cedent_id: str, source_file: str, parsed: NormalisedFile
) -> None:
    """Idempotent per source_file: a re-run replaces that file's submission (cascade)."""
    submitted = next((r["submitted_on"] for r in parsed.rows if r["submitted_on"]), None)
    with conn.cursor() as cur:
        cur.execute("DELETE FROM submissions WHERE source_file = %s", (source_file,))
        cur.execute(
            """INSERT INTO submissions (cedent_id, source_file, submitted_on)
               VALUES (%s, %s, %s) RETURNING submission_id""",
            (cedent_id, source_file, submitted),
        )
        sid = cur.fetchone()[0]
        cur.executemany(
            f"INSERT INTO account_lines (submission_id, {', '.join(COLS)}) "
            f"VALUES (%(submission_id)s, {', '.join(f'%({c})s' for c in COLS)})",
            [{**r, "submission_id": sid} for r in parsed.rows],
        )
    conn.commit()


def ingest_all(
    conn: psycopg.Connection, incoming: Path, config_path: Path = DEFAULT_CONFIG
) -> IngestResult:
    cedents = load_cedents(config_path)
    result = IngestResult()
    load_treaties(conn, incoming)
    for cedent_id, cfg in sorted(cedents.items()):
        folder = incoming / cedent_id
        for path in sorted(folder.glob(f"*.{cfg.format}")):
            parsed = parse_file(path, cfg)
            load_submission(conn, cedent_id, f"{cedent_id}/{path.name}", parsed)
            result.files += 1
            result.loaded += len(parsed.rows)
            result.rejected += parsed.rejected
            result.bad_values += parsed.bad_values
    return result
