from pathlib import Path
from typing import Annotated

import typer

from figure_data.cbdb.sqlite_reader import SQLiteReader
from figure_data.config import load_settings
from figure_data.db.session import create_session_factory, session_scope
from figure_data.encounters.validation import validate_encounters
from figure_data.importing.orchestrator import import_cbdb
from figure_data.review.candidate_detail import get_candidate_detail
from figure_data.review.candidate_listing import CandidateListFilters, list_candidate_summaries
from figure_data.review.candidate_status import mark_candidate_for_review, reject_candidate
from figure_data.review.formatting import (
    format_candidate_detail,
    format_candidate_summaries,
    format_status_change,
)
from figure_data.review.types import CandidateKind, CandidateReviewError
from figure_data.search.person_search import search_people
from figure_data.validation.report import ValidationReport
from figure_data.validation.row_counts import (
    validate_expected_postgres_counts,
    validate_expected_sqlite_counts,
)
from figure_data.validation.sample_queries import validate_sample_person_queries

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
        external_ids = ",".join(result.external_ids)
        typer.echo(
            f"{result.person_id}\t{result.primary_name_zh_hant}\t"
            f"{result.primary_name_zh_hans}\t{result.birth_year}-{result.death_year}\t"
            f"{external_ids}"
        )


@app.command("validate-cbdb")
def validate_cbdb_command() -> None:
    """Validate the configured CBDB import."""
    settings = load_settings()
    checks = []
    with SQLiteReader(settings.cbdb_sqlite_path) as reader:
        checks.extend(validate_expected_sqlite_counts(reader))
    factory = create_session_factory(settings)
    with factory() as session:
        checks.extend(validate_expected_postgres_counts(session))
        checks.extend(validate_sample_person_queries(session))
    report = ValidationReport(checks=checks)
    for check in report.checks:
        status = "PASS" if check.passed else "FAIL"
        typer.echo(f"{status}\t{check.name}\t{check.detail}")
    if not report.passed:
        raise typer.Exit(code=1)


@app.command("validate-encounters")
def validate_encounters_command() -> None:
    """Validate promoted encounter consistency."""
    settings = load_settings()
    factory = create_session_factory(settings)
    with factory() as session:
        checks = validate_encounters(session)
    report = ValidationReport(checks=checks)
    for check in report.checks:
        status = "PASS" if check.passed else "FAIL"
        typer.echo(f"{status}\t{check.name}\t{check.detail}")
    if not report.passed:
        raise typer.Exit(code=1)


@app.command("review-candidates")
def review_candidates_command(
    kind: Annotated[CandidateKind | None, typer.Option("--kind")] = None,
    person: Annotated[str | None, typer.Option("--person")] = None,
    status: Annotated[str | None, typer.Option("--status")] = None,
    strength: Annotated[str | None, typer.Option("--strength")] = None,
    basis: Annotated[str | None, typer.Option("--basis")] = None,
    limit: Annotated[int, typer.Option(min=1, max=200)] = 20,
) -> None:
    """List candidate relationships for manual review."""
    settings = load_settings()
    factory = create_session_factory(settings)
    with factory() as session:
        rows = list_candidate_summaries(
            session,
            CandidateListFilters(
                kind=kind,
                person_query=person,
                review_status=status,
                strength=strength,
                basis=basis,
                limit=limit,
            ),
        )
    for line in format_candidate_summaries(rows):
        typer.echo(line)


@app.command("inspect-candidate")
def inspect_candidate_command(
    kind: Annotated[CandidateKind, typer.Option("--kind")],
    candidate_id: Annotated[int, typer.Option("--id", min=1)],
) -> None:
    """Inspect one candidate relationship and its source evidence."""
    settings = load_settings()
    factory = create_session_factory(settings)
    try:
        with factory() as session:
            detail = get_candidate_detail(session, kind, candidate_id)
    except CandidateReviewError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    for line in format_candidate_detail(detail):
        typer.echo(line)


@app.command("reject-candidate")
def reject_candidate_command(
    kind: Annotated[CandidateKind, typer.Option("--kind")],
    candidate_id: Annotated[int, typer.Option("--id", min=1)],
    reviewed_by: Annotated[str, typer.Option("--reviewed-by")],
    note: Annotated[str, typer.Option("--note")],
) -> None:
    """Reject a candidate relationship without creating an encounter."""
    settings = load_settings()
    factory = create_session_factory(settings)
    try:
        with session_scope(factory) as session:
            change = reject_candidate(
                session,
                kind,
                candidate_id,
                reviewed_by=reviewed_by,
                note=note,
            )
    except CandidateReviewError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(format_status_change(change))


@app.command("mark-candidate-review")
def mark_candidate_review_command(
    kind: Annotated[CandidateKind, typer.Option("--kind")],
    candidate_id: Annotated[int, typer.Option("--id", min=1)],
    reviewed_by: Annotated[str, typer.Option("--reviewed-by")],
    note: Annotated[str, typer.Option("--note")],
) -> None:
    """Mark a candidate relationship as needing later review."""
    settings = load_settings()
    factory = create_session_factory(settings)
    try:
        with session_scope(factory) as session:
            change = mark_candidate_for_review(
                session,
                kind,
                candidate_id,
                reviewed_by=reviewed_by,
                note=note,
            )
    except CandidateReviewError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(format_status_change(change))
