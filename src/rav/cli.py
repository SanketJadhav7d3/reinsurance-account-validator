from pathlib import Path

import typer

from rav.generate import generate_dataset, write_dataset

app = typer.Typer(help="Reinsurance Account Validator. All data is synthetic.")


@app.command()
def generate(
    seed: int = 42,
    no_defects: bool = False,
    out: Path = Path("data/incoming"),
    treaties: int = 40,
) -> None:
    """Generate synthetic treaties and cedent submissions."""
    if not no_defects:
        typer.echo("Defect injection arrives in milestone 4; writing clean data.")
    files = write_dataset(generate_dataset(seed, treaties), out)
    typer.echo(f"Wrote {len(files)} files to {out} (seed {seed}).")


@app.command()
def ingest() -> None:
    """Load incoming files into PostgreSQL."""
    raise typer.Exit(code=_todo("ingest"))


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
