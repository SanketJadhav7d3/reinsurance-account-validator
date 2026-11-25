import pytest

from rav import db


@pytest.fixture
def conn():
    """Fresh, empty tables on the Compose / CI Postgres. Skips if no database is reachable."""
    try:
        c = db.connect()
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"PostgreSQL not available: {exc}")
    db.apply_schema(c)
    c.execute("TRUNCATE findings, rule_runs, account_lines, submissions, treaties CASCADE")
    c.commit()
    yield c
    c.close()
