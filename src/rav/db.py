"""Database access: plain psycopg 3 and plain SQL, no ORM."""

import os
from pathlib import Path

import psycopg

DEFAULT_URL = "postgresql://rav:rav@localhost:5433/rav"
SCHEMA_FILE = Path(__file__).resolve().parents[2] / "sql" / "schema.sql"


def connect() -> psycopg.Connection:
    return psycopg.connect(os.environ.get("RAV_DATABASE_URL", DEFAULT_URL))


def apply_schema(conn: psycopg.Connection) -> None:
    """Idempotent: every statement is CREATE ... IF NOT EXISTS."""
    conn.execute(SCHEMA_FILE.read_text(encoding="utf-8"))
    conn.commit()
