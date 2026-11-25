import json
from pathlib import Path

import typer

from rav import db
from rav.docs import RULES_DOC, render_rules_md
from rav.evaluate import DEFAULT_TRUTH, write_reports
from rav.evaluate import evaluate as run_evaluation
from rav.generate import generate_dataset, inject_defects, write_dataset, write_ground_truth
from rav.ingest import ingest_all
from rav.rules.engine import run_rules
from rav.rules.loader import load_rules

app = typer.Typer(help="Reinsurance Account Validator. All data is synthetic.")


@app.command()
def generate(
    seed: int = 42,
    no_defects: bool = False,
    out: Path = Path("data/incoming"),
    treaties: int = 40,
    truth: str = "data/ground_truth/planted_defects.csv",
) -> None:
    """Generate synthetic treaties and cedent submissions."""
    ds = generate_dataset(seed, treaties)
    defects = [] if no_defects else inject_defects(ds)
    files = write_dataset(ds, out)
    write_ground_truth(defects, Path(truth))
    meta = Path(truth).parent / "meta.json"
    meta.write_text(json.dumps({"seed": seed}) + "\n", encoding="utf-8")
    typer.echo(f"Wrote {len(files)} files to {out} (seed {seed}); {len(defects)} defects planted.")


@app.command()
def ingest(incoming: Path = Path("data/incoming")) -> None:
    """Load incoming files into PostgreSQL (idempotent per source file)."""
    with db.connect() as conn:
        db.apply_schema(conn)
        r = ingest_all(conn, incoming)
    typer.echo(
        f"Ingested {r.files} files: {r.loaded} lines loaded, "
        f"{r.rejected} rows rejected, {r.bad_values} unparseable values (loaded as NULL)."
    )


@app.command()
def run() -> None:
    """Run all enabled validation rules and store findings."""
    with db.connect() as conn:
        run_id, counts = run_rules(conn, load_rules())
    for rule_id, n in counts.items():
        typer.echo(f"{rule_id}: {n} findings")
    typer.echo(f"Run {run_id} complete: {sum(counts.values())} findings.")


@app.command()
def evaluate(
    truth: Path = DEFAULT_TRUTH,
    out: Path = Path("reports"),
    run_id: int | None = None,
) -> None:
    """Compare findings with planted defects; write reports/evaluation.{md,json}."""
    with db.connect() as conn:
        result = run_evaluation(conn, load_rules(), truth, run_id)
    write_reports(result, out)
    o = result["overall"]
    typer.echo(
        f"TP {o['tp']}  FP {o['fp']}  FN {o['fn']}  "
        f"precision {o['precision']}%  recall {o['recall']}%  -> {out}/evaluation.md"
    )


@app.command()
def docs() -> None:
    """Generate docs/rules.md from rule config."""
    RULES_DOC.parent.mkdir(parents=True, exist_ok=True)
    RULES_DOC.write_text(render_rules_md(load_rules()), encoding="utf-8", newline="\n")
    typer.echo(f"Wrote {RULES_DOC}")


def _todo(name: str) -> int:
    typer.echo(f"`rav {name}` is not implemented yet.")
    return 1
