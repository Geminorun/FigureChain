from pathlib import Path
from typing import Annotated

import typer

from figure_data.config import load_settings
from figure_data.db.session import create_session_factory
from figure_data.importing.orchestrator import import_cbdb
from figure_data.search.person_search import search_people

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


@app.command("search-person")
def search_person_command(
    query: str,
    limit: Annotated[int, typer.Option(min=1, max=50)] = 10,
) -> None:
    """Search imported CBDB people."""
    settings = load_settings()
    factory = create_session_factory(settings)
    with factory() as session:
        results = search_people(session, query, limit)
    for result in results:
        typer.echo(
            f"{result.person_id}\t{result.primary_name_zh_hant}\t"
            f"{result.primary_name_zh_hans}\t{result.birth_year}-{result.death_year}"
        )
