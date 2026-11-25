# Reinsurance Account Validator

All accounting data in this repository is synthetic.

A small, local, rule-based validation engine for reinsurance client accounting data. Fictional
cedents send quarterly technical accounts in four different formats (clean CSV, German CSV,
Excel with merged headers, nested JSON). The project maps them into one PostgreSQL schema,
runs configurable validation rules written in SQL or Python, and measures how many deliberately
planted defects the rules catch. It exists to show rule-based checks, extraction from different
sources with SQL and Python, data cleaning, tests and documentation in one finished codebase.

## Quickstart

Requires Docker, and [uv](https://docs.astral.sh/uv/).

```bash
docker compose up -d postgres        # PostgreSQL 16 on localhost:5433
uv sync
uv run rav generate --seed 42        # synthetic treaties + 4 cedent formats + planted defects
uv run rav ingest                    # load into PostgreSQL (idempotent per source file)
uv run rav run                       # run the validation rules
uv run rav evaluate                  # compare findings with the planted defects
uv run rav docs                      # regenerate docs/rules.md
uv run pytest                        # tests need the PostgreSQL container
```

`rav generate --no-defects` produces clean data. Set `RAV_DATABASE_URL` to use a different
database (the tests truncate its tables, so only point it at a throwaway database).

## Results

Copied from `reports/evaluation.md`, produced by `rav evaluate`.

- Seed: 42
- Rules: 9
- Account lines: 161
- Planted defects: 9
- Cedents: 4 (4 formats)

| Rule | Detects | TP | FP | FN | Precision | Recall |
|---|---|---:|---:|---:|---:|---:|
| R01 Balance does not match its components | D01 | 1 | 0 | 0 | 100.0% | 100.0% |
| R02 Commission rate differs from the treaty rate | D02 | 1 | 0 | 0 | 100.0% | 100.0% |
| R03 Period lies outside the treaty term | D03 | 1 | 0 | 0 | 100.0% | 100.0% |
| R04 Duplicate account line | D04 | 1 | 0 | 0 | 100.0% | 100.0% |
| R05 Currency differs from the treaty currency | D05 | 1 | 0 | 0 | 100.0% | 100.0% |
| R06 Treaty is not in the master data | D06 | 1 | 0 | 0 | 100.0% | 100.0% |
| R07 Negative premium not marked as reversal | D07 | 1 | 0 | 0 | 100.0% | 100.0% |
| R08 Required field is missing | D08 | 1 | 0 | 0 | 100.0% | 100.0% |
| R09 Period ends after the submission date | D09 | 1 | 0 | 0 | 100.0% | 100.0% |
| **Overall** | | 9 | 0 | 0 | 100.0% | 100.0% |

## Limitations

- Recall only measures the defects we planted. Real cedent data will contain defect types that
  are not modelled here.
- The balance formula is simplified: `balance = premium - commission - claims_paid`.
- Treaties have no layers, reinstatements or profit commission.
- Each rule was built against a known defect type, so high scores here say the rules and the
  defect injector agree, not that the rules would be this accurate on real data.
- The number of defects per type is small at the default dataset size, so per-rule percentages
  are coarse.

## Documentation

- [Rule catalogue](docs/rules.md) (generated from `config/rules/`)
- [Architecture and design decisions](docs/architecture.md)
