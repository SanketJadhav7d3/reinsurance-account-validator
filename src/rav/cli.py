from pathlib import Path

import typer

from rav import db
from rav.generate import generate_dataset, inject_defects, write_dataset, write_ground_truth
from rav.ingest import ingest_all

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
    """Run validation rules."""
    raise typer.Exit(code=_todo("run"))


@app.command()
def evaluate() -> None:
    """Compare findings with planted defects."""
    raise typer.Exit(code=_todo("evaluate"))


@app.command()
def docs() -> None:
    """Generate docs/rules.md from rule config."""
    raise typer.Exit(code=_todo("docs"))


def _todo(name: str) -> int:
    typer.echo(f"`rav {name}` is not implemented yet.")
    return 1
