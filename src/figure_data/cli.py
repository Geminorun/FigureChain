import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated
from uuid import UUID

import typer
from neo4j.exceptions import DriverError, Neo4jError, ServiceUnavailable
from redis import Redis
from rq import Queue, Worker

from figure_data.ai.candidate_formatting import (
    format_candidate_suggestion_detail,
    format_candidate_suggestion_summaries,
)
from figure_data.ai.candidate_repository import (
    AICandidateSuggestionNotFoundError,
    CandidateSuggestionListFilters,
    get_candidate_review_suggestion,
    list_candidate_review_suggestions,
)
from figure_data.ai.candidate_service import generate_candidate_review_suggestion
from figure_data.ai.chain_context import InvalidChainContextError
from figure_data.ai.chain_formatting import format_chain_explanation_detail
from figure_data.ai.chain_repository import (
    AIChainExplanationNotFoundError,
    get_chain_explanation_by_hash,
)
from figure_data.ai.chain_service import generate_chain_explanation_for_shortest_path
from figure_data.ai.embedding_provider import EmbeddingProviderConfigurationError
from figure_data.ai.errors import (
    AIOutputPolicyViolation,
    AIOutputValidationError,
    AIProviderConfigurationError,
    AIProviderError,
    AIRunNotFoundError,
)
from figure_data.ai.evaluation_loader import load_acceptance_evidence, load_samples_for_evaluation
from figure_data.ai.evaluation_reporting import write_stage4_evaluation_report
from figure_data.ai.evaluation_scoring import (
    build_gate_summary,
    recommend_stage5_entry,
    score_fixture,
)
from figure_data.ai.evaluation_types import EvaluationReport
from figure_data.ai.formatting import format_ai_run_detail
from figure_data.ai.job_repository import (
    cancel_queued_job,
    get_job,
    list_requeueable_jobs,
    mark_enqueued,
    record_job_event,
    request_running_job_cancel,
)
from figure_data.ai.job_runner import run_ai_jobs
from figure_data.ai.no_path_context import InvalidNoPathContextError
from figure_data.ai.no_path_formatting import format_no_path_exploration_result
from figure_data.ai.no_path_service import generate_no_path_exploration
from figure_data.ai.queue import create_ai_job_queue, rq_job_id
from figure_data.ai.real_provider_evaluation import (
    load_stage5d_evaluation_fixture,
    run_stage5d_evaluation,
)
from figure_data.ai.real_provider_reporting import write_stage5d_evaluation_report
from figure_data.ai.repository import get_ai_run
from figure_data.ai.retrieval_formatting import (
    format_build_rag_index_result,
    format_search_rag_evidence_result,
)
from figure_data.ai.retrieval_service import (
    BuildRagIndexOptions,
    SearchRagEvidenceOptions,
    build_rag_index,
    search_rag_evidence,
)
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


def _echo_cli_line(line: str) -> None:
    try:
        typer.echo(line)
    except UnicodeEncodeError:
        buffer = getattr(sys.stdout, "buffer", None)
        if buffer is None:
            typer.echo(line.encode("ascii", errors="backslashreplace").decode("ascii"))
            return
        buffer.write(f"{line}\n".encode())
        buffer.flush()


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
        _echo_cli_line(line)


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
        _echo_cli_line(line)


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
        _echo_cli_line(line)


@app.command("inspect-ai-run")
def inspect_ai_run_command(
    run_id: Annotated[UUID, typer.Option("--id")],
) -> None:
    """Inspect one recorded AI run."""
    settings = load_settings()
    factory = create_session_factory(settings)
    try:
        with factory() as session:
            record = get_ai_run(session, run_id)
    except AIRunNotFoundError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    for line in format_ai_run_detail(record, ai_api_key=getattr(settings, "ai_api_key", None)):
        _echo_cli_line(line)


@app.command("build-rag-index")
def build_rag_index_command(
    source_ref_id: Annotated[int | None, typer.Option("--source-ref-id", min=1)] = None,
    include_encounter_evidence: Annotated[
        bool,
        typer.Option("--include-encounter-evidence/--source-refs-only"),
    ] = True,
    limit: Annotated[int, typer.Option("--limit", min=1, max=500)] = 50,
) -> None:
    """Build a small RAG evidence index from source refs and encounter evidence."""
    settings = load_settings()
    factory = create_session_factory(settings)
    try:
        with session_scope(factory) as session:
            result = build_rag_index(
                session=session,
                settings=settings,
                options=BuildRagIndexOptions(
                    source_ref_id=source_ref_id,
                    limit=limit,
                    include_encounter_evidence=include_encounter_evidence,
                ),
            )
    except (EmbeddingProviderConfigurationError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    for line in format_build_rag_index_result(result):
        _echo_cli_line(line)


@app.command("search-rag-evidence")
def search_rag_evidence_command(
    query: Annotated[str, typer.Option("--query")],
    source_ref_id: Annotated[int | None, typer.Option("--source-ref-id", min=1)] = None,
    limit: Annotated[int, typer.Option("--limit", min=1, max=50)] = 5,
) -> None:
    """Search the local RAG evidence index."""
    settings = load_settings()
    factory = create_session_factory(settings)
    try:
        with factory() as session:
            result = search_rag_evidence(
                session=session,
                settings=settings,
                options=SearchRagEvidenceOptions(
                    query=query,
                    source_ref_id=source_ref_id,
                    limit=limit,
                ),
            )
    except (EmbeddingProviderConfigurationError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    for line in format_search_rag_evidence_result(result):
        _echo_cli_line(line)


@app.command("evaluate-ai-samples")
def evaluate_ai_samples_command(
    fixture: Annotated[
        Path,
        typer.Option("--fixture", exists=True, file_okay=True, dir_okay=False),
    ] = Path("docs/superpowers/evaluation/stage4-ai-samples.json"),
    evidence: Annotated[
        Path | None,
        typer.Option("--evidence", exists=True, file_okay=True, dir_okay=False),
    ] = None,
    output: Annotated[
        Path,
        typer.Option("--output", file_okay=True, dir_okay=False),
    ] = Path("docs/superpowers/reports/2026-06-14-ai-stage4-acceptance.md"),
    resolve_ai_runs: Annotated[
        bool,
        typer.Option("--resolve-ai-runs/--fixture-only"),
    ] = False,
) -> None:
    """Evaluate fixed AI samples and write a Stage 4 acceptance report."""
    try:
        if resolve_ai_runs:
            settings = load_settings()
            factory = create_session_factory(settings)
            with factory() as session:
                fixture_model = load_samples_for_evaluation(
                    fixture,
                    session=session,
                    resolve_ai_runs=True,
                )
        else:
            fixture_model = load_samples_for_evaluation(
                fixture,
                resolve_ai_runs=False,
            )
        evidence_model = load_acceptance_evidence(evidence)
        item_results = score_fixture(fixture_model)
        gate_summary = build_gate_summary(item_results, evidence_model)
        recommendation = recommend_stage5_entry(gate_summary)
        report = EvaluationReport(
            generated_at=datetime.now(UTC).isoformat(),
            fixture_version=fixture_model.fixture_version,
            item_results=item_results,
            acceptance_evidence=evidence_model,
            gate_summary=gate_summary,
            recommendation=recommendation,
        )
        report_path = write_stage4_evaluation_report(report, output)
    except ValueError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    _echo_cli_line(f"evaluation_report\t{report_path}")
    _echo_cli_line(f"samples\t{len(fixture_model.samples)}")
    _echo_cli_line(f"recommendation\t{recommendation}")


@app.command("evaluate-real-provider")
def evaluate_real_provider_command(
    fixture: Annotated[
        Path,
        typer.Option("--fixture", exists=True, file_okay=True, dir_okay=False),
    ] = Path("docs/superpowers/fixtures/stage5d-real-provider-eval-small.json"),
    output: Annotated[
        Path,
        typer.Option("--output", file_okay=True, dir_okay=False),
    ] = Path("docs/superpowers/reports/2026-06-19-stage5d-real-provider-acceptance.md"),
    allow_real_provider: Annotated[bool, typer.Option("--allow-real-provider")] = False,
) -> None:
    """Run the Stage 5D real-provider acceptance evaluation."""
    try:
        settings = load_settings()
        fixture_model = load_stage5d_evaluation_fixture(fixture)
        factory = create_session_factory(settings)
        with factory() as session:
            result = run_stage5d_evaluation(
                fixture=fixture_model,
                settings=settings,
                session=session,
                allow_real_provider=allow_real_provider,
            )
        report_path = write_stage5d_evaluation_report(result, output)
    except (ValueError, AIProviderConfigurationError, AIProviderError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    _echo_cli_line(f"samples\t{result.sample_count}")
    _echo_cli_line(f"passed\t{result.passed_count}")
    _echo_cli_line(f"failed\t{result.failed_count}")
    _echo_cli_line(f"errors\t{result.error_count}")
    _echo_cli_line(f"provider\t{result.provider}")
    _echo_cli_line(f"model\t{result.model_name}")
    _echo_cli_line(f"real_provider_used\t{result.real_provider_used}")
    _echo_cli_line(f"evaluation_report\t{report_path}")


@app.command("suggest-candidate-review")
def suggest_candidate_review_command(
    kind: Annotated[CandidateKind, typer.Option("--kind")],
    candidate_id: Annotated[int, typer.Option("--id", min=1)],
    created_by: Annotated[str, typer.Option("--created-by")],
) -> None:
    """Generate an AI review suggestion for one candidate relationship."""
    settings = load_settings()
    factory = create_session_factory(settings)
    session = factory()
    try:
        result = generate_candidate_review_suggestion(
            session=session,
            settings=settings,
            kind=kind,
            candidate_id=candidate_id,
            created_by=created_by,
        )
        session.commit()
    except (
        AIProviderConfigurationError,
        AIProviderError,
        AIOutputValidationError,
        AIOutputPolicyViolation,
    ) as exc:
        session.commit()
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    except (
        CandidateReviewError,
        ValueError,
    ) as exc:
        session.rollback()
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
    for line in format_candidate_suggestion_detail(result.suggestion):
        _echo_cli_line(line)


@app.command("run-ai-jobs")
def run_ai_jobs_command(
    limit: Annotated[int, typer.Option("--limit", min=1, max=100)] = 10,
    job_type: Annotated[str | None, typer.Option("--job-type")] = None,
) -> None:
    """Run queued AI generation jobs."""
    if job_type not in (None, "candidate_review_suggestion"):
        typer.echo(f"unsupported AI job type: {job_type}", err=True)
        raise typer.Exit(code=1)
    settings = load_settings()
    factory = create_session_factory(settings)
    with session_scope(factory) as session:
        summary = run_ai_jobs(
            session=session,
            settings=settings,
            limit=limit,
            job_type=job_type,
        )
    _echo_cli_line(
        "ai_jobs\t"
        f"claimed={summary.claimed_count}\t"
        f"succeeded={summary.succeeded_count}\t"
        f"failed={summary.failed_count}"
    )
    for failure in summary.failures:
        _echo_cli_line(
            f"failed_job\t{failure.job_id}\t{failure.error_code}\t{failure.error_message}"
        )


@app.command("requeue-ai-jobs")
def requeue_ai_jobs_command(
    limit: Annotated[int, typer.Option("--limit", min=1, max=100)] = 50,
) -> None:
    """List queued AI jobs that can be enqueued by the RQ backend."""
    settings = load_settings()
    if settings.ai_queue_backend != "rq":
        _echo_cli_line("ai_jobs_requeue\tbackend=database\trequeued=0")
        return
    queue = create_ai_job_queue(settings)
    factory = create_session_factory(settings)
    with session_scope(factory) as session:
        jobs = list_requeueable_jobs(session, limit=limit)
        for job in jobs:
            enqueued = queue.enqueue(
                job.id,
                queue_name=settings.ai_queue_name,
                timeout_seconds=settings.ai_job_timeout_seconds,
            )
            if enqueued.queue_job_id is not None:
                mark_enqueued(
                    session,
                    job.id,
                    queue_backend=enqueued.queue_backend,
                    queue_name=enqueued.queue_name,
                    queue_job_id=enqueued.queue_job_id,
                )
                record_job_event(
                    session,
                    job_id=job.id,
                    event_type="requeued",
                    actor="cli",
                    metadata={
                        "queue_name": enqueued.queue_name,
                        "dedupe_job_id": rq_job_id(job.id),
                    },
                )
    _echo_cli_line(f"ai_jobs_requeue\tbackend=rq\trequeued={len(jobs)}")


@app.command("cancel-ai-job")
def cancel_ai_job_command(
    job_id: Annotated[UUID, typer.Option("--job-id")],
    cancelled_by: Annotated[str, typer.Option("--cancelled-by")],
) -> None:
    """Request cancellation for an AI generation job."""
    settings = load_settings()
    factory = create_session_factory(settings)
    with session_scope(factory) as session:
        job = get_job(session, job_id)
        if job is None:
            typer.echo(f"AI job not found: {job_id}", err=True)
            raise typer.Exit(code=1)
        if job.status == "queued":
            record = cancel_queued_job(session, job_id, cancelled_by=cancelled_by)
        elif job.status == "running":
            record = request_running_job_cancel(session, job_id, cancelled_by=cancelled_by)
        else:
            record = job
        record_job_event(
            session,
            job_id=job_id,
            event_type="cancel_requested",
            actor=cancelled_by,
            metadata={"previous_status": job.status, "new_status": record.status},
        )
    _echo_cli_line(f"ai_job_cancel\t{job_id}\tstatus={record.status}")


@app.command("run-ai-worker")
def run_ai_worker_command(
    queue_name: Annotated[str | None, typer.Option("--queue")] = None,
) -> None:
    """Run an RQ worker for AI generation jobs."""
    settings = load_settings()
    if settings.ai_queue_backend != "rq":
        typer.echo("FIGURE_AI_QUEUE_BACKEND must be 'rq' to run RQ worker", err=True)
        raise typer.Exit(code=1)
    if settings.redis_url is None:
        typer.echo("REDIS_URL is required to run RQ worker", err=True)
        raise typer.Exit(code=1)

    resolved_queue_name = queue_name or settings.ai_queue_name
    redis_connection = Redis.from_url(settings.redis_url)
    queue = Queue(name=resolved_queue_name, connection=redis_connection)
    worker = Worker([queue], connection=redis_connection)
    worker.work()


@app.command("generate-chain-explanation")
def generate_chain_explanation_command(
    from_query: Annotated[str | None, typer.Option("--from")] = None,
    to_query: Annotated[str | None, typer.Option("--to")] = None,
    from_person_id: Annotated[UUID | None, typer.Option("--from-person-id")] = None,
    to_person_id: Annotated[UUID | None, typer.Option("--to-person-id")] = None,
    from_cbdb_id: Annotated[str | None, typer.Option("--from-cbdb-id")] = None,
    to_cbdb_id: Annotated[str | None, typer.Option("--to-cbdb-id")] = None,
    max_depth: Annotated[int, typer.Option("--max-depth", min=1, max=30)] = 12,
    language: Annotated[str, typer.Option("--language")] = "zh-Hans",
    created_by: Annotated[str, typer.Option("--created-by")] = "local",
) -> None:
    """Generate and store an AI explanation for one reviewed shortest chain."""
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
    session = None
    try:
        settings = load_settings()
        factory = create_session_factory(settings)
        driver = create_neo4j_driver(settings)
        config = get_neo4j_config(settings)
        session = factory()
        with graph_session(driver, config.database) as neo4j_session:
            result = generate_chain_explanation_for_shortest_path(
                session=session,
                neo4j_session=neo4j_session,
                settings=settings,
                source=source,
                target=target,
                max_depth=max_depth,
                created_by=created_by,
                language=language,
            )
        session.commit()
    except (
        AIProviderConfigurationError,
        AIProviderError,
        AIOutputValidationError,
        AIOutputPolicyViolation,
        InvalidChainContextError,
    ) as exc:
        if session is not None:
            session.commit()
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    except (GraphOperationError, DriverError, Neo4jError, ValueError) as exc:
        if session is not None:
            session.rollback()
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    except Exception:
        if session is not None:
            session.rollback()
        raise
    finally:
        if session is not None:
            session.close()
        if driver is not None:
            driver.close()
    for line in format_chain_explanation_detail(result.explanation):
        _echo_cli_line(line)


@app.command("suggest-no-path-exploration")
def suggest_no_path_exploration_command(
    from_query: Annotated[str | None, typer.Option("--from")] = None,
    to_query: Annotated[str | None, typer.Option("--to")] = None,
    from_person_id: Annotated[UUID | None, typer.Option("--from-person-id")] = None,
    to_person_id: Annotated[UUID | None, typer.Option("--to-person-id")] = None,
    from_cbdb_id: Annotated[str | None, typer.Option("--from-cbdb-id")] = None,
    to_cbdb_id: Annotated[str | None, typer.Option("--to-cbdb-id")] = None,
    max_depth: Annotated[int, typer.Option("--max-depth", min=1, max=30)] = 12,
    candidate_limit: Annotated[int, typer.Option("--candidate-limit", min=0, max=50)] = 10,
    rag_limit: Annotated[int, typer.Option("--rag-limit", min=0, max=10)] = 5,
    language: Annotated[str, typer.Option("--language")] = "zh-Hans",
    created_by: Annotated[str, typer.Option("--created-by")] = "local",
) -> None:
    """Generate an AI suggestion for a shortest-path query that currently has no path."""
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
    session = None
    try:
        settings = load_settings()
        factory = create_session_factory(settings)
        driver = create_neo4j_driver(settings)
        config = get_neo4j_config(settings)
        session = factory()
        with graph_session(driver, config.database) as neo4j_session:
            result = generate_no_path_exploration(
                session=session,
                neo4j_session=neo4j_session,
                settings=settings,
                source=source,
                target=target,
                max_depth=max_depth,
                created_by=created_by,
                language=language,
                candidate_limit=candidate_limit,
                rag_limit=rag_limit,
            )
        session.commit()
    except (
        AIProviderConfigurationError,
        AIProviderError,
        AIOutputValidationError,
        AIOutputPolicyViolation,
        InvalidNoPathContextError,
        EmbeddingProviderConfigurationError,
    ) as exc:
        if session is not None:
            session.commit()
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    except (GraphOperationError, DriverError, Neo4jError, ValueError) as exc:
        if session is not None:
            session.rollback()
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    except Exception:
        if session is not None:
            session.rollback()
        raise
    finally:
        if session is not None:
            session.close()
        if driver is not None:
            driver.close()
    for line in format_no_path_exploration_result(result):
        _echo_cli_line(line)


@app.command("inspect-chain-explanation")
def inspect_chain_explanation_command(
    chain_hash: Annotated[str, typer.Option("--hash")],
) -> None:
    """Inspect one stored AI chain explanation."""
    settings = load_settings()
    factory = create_session_factory(settings)
    try:
        with factory() as session:
            record = get_chain_explanation_by_hash(session, chain_hash)
    except AIChainExplanationNotFoundError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    for line in format_chain_explanation_detail(record):
        _echo_cli_line(line)


@app.command("list-ai-candidate-suggestions")
def list_ai_candidate_suggestions_command(
    status: Annotated[str | None, typer.Option("--status")] = "generated",
    kind: Annotated[CandidateKind | None, typer.Option("--kind")] = None,
    candidate_id: Annotated[int | None, typer.Option("--candidate-id", min=1)] = None,
    limit: Annotated[int, typer.Option(min=1, max=200)] = 20,
) -> None:
    """List stored AI candidate review suggestions."""
    settings = load_settings()
    factory = create_session_factory(settings)
    with factory() as session:
        rows = list_candidate_review_suggestions(
            session,
            CandidateSuggestionListFilters(
                status=status,
                candidate_kind=kind,
                candidate_id=candidate_id,
                limit=limit,
            ),
        )
    for line in format_candidate_suggestion_summaries(rows):
        _echo_cli_line(line)


@app.command("inspect-ai-candidate-suggestion")
def inspect_ai_candidate_suggestion_command(
    suggestion_id: Annotated[UUID, typer.Option("--id")],
) -> None:
    """Inspect one stored AI candidate review suggestion."""
    settings = load_settings()
    factory = create_session_factory(settings)
    try:
        with factory() as session:
            record = get_candidate_review_suggestion(session, suggestion_id)
    except AICandidateSuggestionNotFoundError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    for line in format_candidate_suggestion_detail(record):
        _echo_cli_line(line)


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
