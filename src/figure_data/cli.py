import typer

from figure_data.importing.orchestrator import import_cbdb

app = typer.Typer(help="CBDB import and normalization tools for FigureChain.")


@app.callback()
def main() -> None:
    """FigureChain data import command line interface."""


@app.command("import-cbdb")
def import_cbdb_command() -> None:
    """Import the configured CBDB SQLite snapshot into PostgreSQL."""
    batch = import_cbdb()
    typer.echo(f"CBDB import batch {batch.id} {batch.status}: rows_read={batch.rows_read}")
