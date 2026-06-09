from pathlib import Path
from typing import Annotated
from uuid import UUID

import typer
from neo4j.exceptions import DriverError, Neo4jError, ServiceUnavailable

from figure_data.cbdb.sqlite_reader import SQLiteReader
from figure_data.config import load_settings
from figure_data.db.enums import CertaintyLevel, EncounterKind
from figure_data.db.session import create_session_factory, session_scope
from figure_data.encounters.formatting import (
    format_encounter_detail,
    format_encounter_summaries,
    format_promotion_result,
    format_retraction_result,
)
from figure_data.encounters.promotion import promote_candidate_to_encounter
from figure_data.encounters.query import EncounterListFilters, get_encounter_detail, list_encounters
from figure_data.encounters.retraction import retract_encounter
from figure_data.encounters.types import (
    EncounterOperationError,
    EncounterPromotionOptions,
    EncounterRetractionOptions,
)
from figure_data.encounters.validation import validate_encounters
from figure_data.expansion.candidate_planning import (
    ExpansionCandidateFilters,
    plan_encounter_expansion,
)
from figure_data.expansion.formatting import (
    format_chain_samples,
    format_expansion_candidates,
    format_expansion_report_markdown,
)
from figure_data.expansion.reporting import (
    EncounterExpansionReportFilters,
    export_encounter_expansion_report,
)
from figure_data.expansion.sample_chains import ChainSampleFilters, list_chain_samples
from figure_data.graph.formatting import (
    format_chain_result,
    format_projection_stats,
    format_validation_checks,
)
from figure_data.graph.neo4j_client import create_neo4j_driver, get_neo4j_config, graph_session
from figure_data.graph.pathfinding import ChainEndpointInput, find_chain
from figure_data.graph.projection import sync_graph_rebuild
from figure_data.graph.types import GraphOperationError
from figure_data.graph.validation import validate_graph
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


@app.command("sync-graph")
def sync_graph_command(
    rebuild: Annotated[bool, typer.Option("--rebuild")] = False,
) -> None:
    """Rebuild the Neo4j graph projection from PostgreSQL path encounters."""
    if not rebuild:
        typer.echo("--rebuild is required for the first graph projection version", err=True)
        raise typer.Exit(code=1)
    driver = None
    try:
        settings = load_settings()
        factory = create_session_factory(settings)
        driver = create_neo4j_driver(settings)
        config = get_neo4j_config(settings)
        with factory() as pg_session, graph_session(driver, config.database) as neo4j_session:
            stats = sync_graph_rebuild(pg_session, neo4j_session)
    except (GraphOperationError, DriverError, Neo4jError) as exc:
        _exit_graph_error(exc)
    finally:
        if driver is not None:
            driver.close()
    for line in format_projection_stats(stats):
        typer.echo(line)


@app.command("validate-graph")
def validate_graph_command() -> None:
    """Validate the Neo4j graph projection against PostgreSQL."""
    driver = None
    try:
        settings = load_settings()
        factory = create_session_factory(settings)
        driver = create_neo4j_driver(settings)
        config = get_neo4j_config(settings)
        with factory() as pg_session, graph_session(driver, config.database) as neo4j_session:
            checks = validate_graph(pg_session, neo4j_session)
    except (GraphOperationError, DriverError, Neo4jError) as exc:
        _exit_graph_error(exc)
    finally:
        if driver is not None:
            driver.close()
    report = ValidationReport(checks=checks)
    for line in format_validation_checks(report.checks):
        typer.echo(line)
    if not report.passed:
        raise typer.Exit(code=1)


@app.command("find-chain")
def find_chain_command(
    from_query: Annotated[str | None, typer.Option("--from")] = None,
    to_query: Annotated[str | None, typer.Option("--to")] = None,
    from_person_id: Annotated[UUID | None, typer.Option("--from-person-id")] = None,
    to_person_id: Annotated[UUID | None, typer.Option("--to-person-id")] = None,
    from_cbdb_id: Annotated[str | None, typer.Option("--from-cbdb-id")] = None,
    to_cbdb_id: Annotated[str | None, typer.Option("--to-cbdb-id")] = None,
    max_depth: Annotated[int, typer.Option("--max-depth", min=1, max=30)] = 12,
) -> None:
    """Find one shortest chain between two projected people."""
    source = ChainEndpointInput(
        label="from",
        person_id=from_person_id,
        cbdb_id=from_cbdb_id,
        query=from_query,
    )
    target = ChainEndpointInput(
        label="to",
        person_id=to_person_id,
        cbdb_id=to_cbdb_id,
        query=to_query,
    )
    driver = None
    try:
        settings = load_settings()
        factory = create_session_factory(settings)
        driver = create_neo4j_driver(settings)
        config = get_neo4j_config(settings)
        with factory() as pg_session, graph_session(driver, config.database) as neo4j_session:
            result = find_chain(pg_session, neo4j_session, source, target, max_depth)
    except (GraphOperationError, DriverError, Neo4jError) as exc:
        _exit_graph_error(exc)
    finally:
        if driver is not None:
            driver.close()
    for line in format_chain_result(result):
        typer.echo(line)


def _exit_graph_error(exc: GraphOperationError | DriverError | Neo4jError) -> None:
    if isinstance(exc, GraphOperationError):
        typer.echo(str(exc), err=True)
    elif isinstance(exc, ServiceUnavailable):
        typer.echo(
            f"Neo4j is unavailable: {type(exc).__name__}; check NEO4J_URI and service status",
            err=True,
        )
    else:
        typer.echo(
            f"Neo4j operation failed: {type(exc).__name__}; "
            "check Neo4j configuration and database status",
            err=True,
        )
    raise typer.Exit(code=1) from exc


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


@app.command("plan-encounter-expansion")
def plan_encounter_expansion_command(
    status: Annotated[str | None, typer.Option("--status")] = "unreviewed",
    limit: Annotated[int, typer.Option(min=1, max=500)] = 50,
) -> None:
    """List high-priority relationship candidates for encounter data expansion."""
    settings = load_settings()
    factory = create_session_factory(settings)
    with factory() as session:
        rows = plan_encounter_expansion(
            session,
            ExpansionCandidateFilters(review_status=status, limit=limit),
        )
    for line in format_expansion_candidates(rows):
        typer.echo(line)


@app.command("list-chain-samples")
def list_chain_samples_command(
    max_depth: Annotated[int, typer.Option("--max-depth", min=1, max=3)] = 3,
    limit: Annotated[int, typer.Option(min=1, max=100)] = 20,
) -> None:
    """List one-hop to three-hop reviewed path samples from PostgreSQL."""
    settings = load_settings()
    factory = create_session_factory(settings)
    with factory() as session:
        rows = list_chain_samples(
            session,
            ChainSampleFilters(max_depth=max_depth, limit=limit),
        )
    for line in format_chain_samples(rows):
        typer.echo(line)


@app.command("export-encounter-expansion-report")
def export_encounter_expansion_report_command(
    since: Annotated[str | None, typer.Option("--since")] = None,
    limit: Annotated[int, typer.Option(min=1, max=1000)] = 200,
) -> None:
    """Export a Markdown draft for reviewed path encounters."""
    settings = load_settings()
    factory = create_session_factory(settings)
    with factory() as session:
        report = export_encounter_expansion_report(
            session,
            EncounterExpansionReportFilters(reviewed_since=since, limit=limit),
        )
    for line in format_expansion_report_markdown(report):
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


@app.command("promote-encounter")
def promote_encounter_command(
    kind: Annotated[CandidateKind, typer.Option("--kind")],
    candidate_id: Annotated[int, typer.Option("--id", min=1)],
    reviewed_by: Annotated[str, typer.Option("--reviewed-by")],
    evidence_summary: Annotated[str, typer.Option("--evidence-summary")],
    note: Annotated[str | None, typer.Option("--note")] = None,
    encounter_kind: Annotated[EncounterKind | None, typer.Option("--encounter-kind")] = None,
    certainty: Annotated[CertaintyLevel | None, typer.Option("--certainty")] = None,
    path_eligible: Annotated[
        bool | None,
        typer.Option("--path-eligible/--no-path-eligible"),
    ] = None,
    allow_non_default: Annotated[bool, typer.Option("--allow-non-default")] = False,
) -> None:
    """Promote a reviewed candidate relationship into an encounter."""
    settings = load_settings()
    factory = create_session_factory(settings)
    try:
        with session_scope(factory) as session:
            result = promote_candidate_to_encounter(
                session,
                EncounterPromotionOptions(
                    candidate_kind=kind,
                    candidate_id=candidate_id,
                    reviewed_by=reviewed_by,
                    evidence_summary=evidence_summary,
                    review_note=note,
                    encounter_kind=encounter_kind,
                    certainty_level=certainty,
                    path_eligible=path_eligible,
                    allow_non_default=allow_non_default,
                ),
            )
    except (CandidateReviewError, EncounterOperationError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(format_promotion_result(result))


@app.command("list-encounters")
def list_encounters_command(
    person: Annotated[str | None, typer.Option("--person")] = None,
    status: Annotated[str | None, typer.Option("--status")] = None,
    path_eligible: Annotated[
        bool | None,
        typer.Option("--path-eligible/--no-path-eligible"),
    ] = None,
    limit: Annotated[int, typer.Option(min=1, max=200)] = 20,
) -> None:
    """List reviewed encounters."""
    settings = load_settings()
    factory = create_session_factory(settings)
    with factory() as session:
        rows = list_encounters(
            session,
            EncounterListFilters(
                person_query=person,
                status=status,
                path_eligible=path_eligible,
                limit=limit,
            ),
        )
    for line in format_encounter_summaries(rows):
        typer.echo(line)


@app.command("inspect-encounter")
def inspect_encounter_command(
    encounter_id: Annotated[UUID, typer.Option("--id")],
) -> None:
    """Inspect one reviewed encounter and its evidence."""
    settings = load_settings()
    factory = create_session_factory(settings)
    try:
        with factory() as session:
            detail = get_encounter_detail(session, encounter_id)
    except EncounterOperationError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    for line in format_encounter_detail(detail):
        typer.echo(line)


@app.command("retract-encounter")
def retract_encounter_command(
    encounter_id: Annotated[UUID, typer.Option("--id")],
    reviewed_by: Annotated[str, typer.Option("--reviewed-by")],
    note: Annotated[str, typer.Option("--note")],
    force: Annotated[bool, typer.Option("--force")] = False,
) -> None:
    """Retract an encounter and remove it from path eligibility."""
    settings = load_settings()
    factory = create_session_factory(settings)
    try:
        with session_scope(factory) as session:
            result = retract_encounter(
                session,
                EncounterRetractionOptions(
                    encounter_id=encounter_id,
                    reviewed_by=reviewed_by,
                    note=note,
                    force=force,
                ),
            )
    except EncounterOperationError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(format_retraction_result(result))
