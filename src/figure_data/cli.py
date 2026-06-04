from pathlib import Path
from typing import Annotated

import typer

from figure_data.config import load_settings
from figure_data.importing.orchestrator import import_cbdb

app = typer.Typer(
    help="CBDB import and normalization tools for FigureChain.",
    pretty_exceptions_show_locals=False,
)


@app.callback()
def main() -> None:
    """FigureChain data import command line interface."""


@app.command("import-cbdb")
def import_cbdb_command(
    sqlite: Annotated[
        Path | None,
        typer.Option(
            "--sqlite",
            exists=True,
            file_okay=True,
            dir_okay=False,
            help="Path to the CBDB SQLite snapshot.",
        ),
    ] = None,
) -> None:
    """Import the configured CBDB SQLite snapshot into PostgreSQL."""
    settings = load_settings()
    if sqlite is not None:
        settings = settings.model_copy(update={"cbdb_sqlite_path": sqlite})
    batch = import_cbdb(settings)
    typer.echo(f"import batch {batch.status}")
    typer.echo(f"id={batch.id} rows_read={batch.rows_read}")
