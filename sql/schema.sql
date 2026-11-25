-- Reinsurance Account Validator schema. All data is synthetic.
-- Money is NUMERIC(18,2). treaty_id on account_lines is deliberately NOT a foreign key
-- (D06 unknown treaties must land so a rule can catch them); required fields are nullable
-- for the same reason (D08).

CREATE TABLE IF NOT EXISTS treaties (
    treaty_id        TEXT PRIMARY KEY,
    cedent_id        TEXT NOT NULL,
    line_of_business TEXT NOT NULL,
    currency         CHAR(3) NOT NULL,
    term_start       DATE NOT NULL,
    term_end         DATE NOT NULL,
    commission_rate  NUMERIC(6,4) NOT NULL
);

CREATE TABLE IF NOT EXISTS submissions (
    submission_id SERIAL PRIMARY KEY,
    cedent_id     TEXT NOT NULL,
    source_file   TEXT NOT NULL UNIQUE,
    submitted_on  DATE,
    ingested_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS account_lines (
    line_ref      TEXT PRIMARY KEY,
    submission_id INTEGER NOT NULL REFERENCES submissions(submission_id) ON DELETE CASCADE,
    treaty_id     TEXT,
    period_start  DATE,
    period_end    DATE,
    currency      CHAR(3),
    premium       NUMERIC(18,2),
    commission    NUMERIC(18,2),
    claims_paid   NUMERIC(18,2),
    balance       NUMERIC(18,2),
    is_reversal   BOOLEAN NOT NULL DEFAULT FALSE,
    source_row    INTEGER
);

CREATE TABLE IF NOT EXISTS rule_runs (
    run_id        SERIAL PRIMARY KEY,
    started_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at   TIMESTAMPTZ,
    rules_version TEXT
);

CREATE TABLE IF NOT EXISTS findings (
    run_id   INTEGER NOT NULL REFERENCES rule_runs(run_id) ON DELETE CASCADE,
    rule_id  TEXT NOT NULL,
    line_ref TEXT NOT NULL,
    severity TEXT NOT NULL,
    message  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS findings_run_idx ON findings(run_id, rule_id);
