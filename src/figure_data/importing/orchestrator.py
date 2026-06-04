from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from figure_data.cbdb.normalize import normalize_int, normalize_text
from figure_data.cbdb.snapshot import load_snapshot_metadata, verify_sqlite_sha256
from figure_data.cbdb.sqlite_reader import SQLiteReader
from figure_data.config import Settings, load_settings
from figure_data.db.models.import_batch import ImportBatch
from figure_data.db.models.office import OfficePosting
from figure_data.db.models.person import Person, PersonAlias, PersonExternalId
from figure_data.db.models.relationship import KinshipCandidate, RelationshipCandidate
from figure_data.db.session import create_session_factory
from figure_data.importing.aliases import transform_alias_row
from figure_data.importing.batch import fail_import_batch, finish_import_batch, start_import_batch
from figure_data.importing.context import ImportContext, imported_record_fields
from figure_data.importing.dictionaries import import_dictionaries
from figure_data.importing.kinship import transform_kinship_row
from figure_data.importing.offices import transform_office_posting_row
from figure_data.importing.persons import local_person_id, transform_person_row
from figure_data.importing.relationships import transform_relationship_row
from figure_data.importing.source_refs import import_source_refs
from figure_data.importing.upsert import execute_upsert_rows

CBDB_IMPORT_TABLE_ORDER = [
    "DYNASTIES",
    "TEXT_CODES",
    "ASSOC_CODES",
    "ASSOC_TYPES",
    "ASSOC_CODE_TYPE_REL",
    "KINSHIP_CODES",
    "BIOG_MAIN",
    "ALTNAME_DATA",
    "ASSOC_DATA",
    "KIN_DATA",
    "POSTED_TO_OFFICE_DATA",
]

REVIEW_PROTECTED_COLUMNS = {
    "review_status",
    "reviewed_at",
    "reviewed_by",
    "review_note",
    "promoted_encounter_id",
}


def import_cbdb(settings: Settings | None = None) -> ImportBatch:
    resolved_settings = settings or load_settings()
    metadata = load_snapshot_metadata(resolved_settings.cbdb_metadata_path)
    verify_sqlite_sha256(resolved_settings.cbdb_sqlite_path, str(metadata["sha256"]))

    session_factory = create_session_factory(resolved_settings)
    session = session_factory()
    batch = start_import_batch(session, resolved_settings, metadata)
    session.commit()

    context = ImportContext(
        source_name=resolved_settings.source_name,
        source_snapshot=resolved_settings.source_snapshot,
    )
    rows_read = 0
    try:
        with SQLiteReader(resolved_settings.cbdb_sqlite_path) as reader:
            person_ids = _load_cbdb_person_ids(reader)
            rows_read += import_dictionaries(session, reader, context, batch.id)
            rows_read += _import_persons(session, reader, context, batch.id)
            rows_read += _import_aliases(session, reader, context, batch.id, person_ids)
            rows_read += _import_relationships(session, reader, context, batch.id, person_ids)
            rows_read += _import_kinships(session, reader, context, batch.id, person_ids)
            rows_read += _import_office_postings(session, reader, context, batch.id, person_ids)
            rows_read += import_source_refs(session, reader, context, batch.id)
        finish_import_batch(session, batch, rows_read=rows_read)
        session.commit()
        return batch
    except Exception as error:
        session.rollback()
        fail_import_batch(session, batch, error)
        session.commit()
        raise
    finally:
        session.close()


def _load_cbdb_person_ids(reader: SQLiteReader) -> set[int]:
    return {
        person_id
        for row in reader.iter_rows("BIOG_MAIN")
        if (person_id := normalize_int(row.get("c_personid"))) is not None
    }


def _import_persons(
    session: Session,
    reader: SQLiteReader,
    context: ImportContext,
    import_batch_id: UUID,
) -> int:
    imported_at = datetime.now(UTC)
    person_rows: list[dict[str, Any]] = []
    external_id_rows: list[dict[str, Any]] = []
    for row in reader.iter_rows("BIOG_MAIN"):
        record = transform_person_row(row, context)
        _add_import_batch_fields(record, import_batch_id, imported_at)
        person_rows.append(record)
        external_id = normalize_int(row.get("c_personid"))
        if external_id is None:
            continue
        external_id_rows.append(
            {
                "person_id": UUID(record["id"]),
                "external_id": str(external_id),
                **imported_record_fields(
                    context=context,
                    source_table="BIOG_MAIN",
                    source_pk=record["source_pk"],
                    source_row_hash=record["source_row_hash"],
                    raw_cbdb=dict(row),
                    import_batch_id=import_batch_id,
                    imported_at=imported_at,
                ),
            }
        )
    execute_upsert_rows(session, Person.__table__, person_rows)
    execute_upsert_rows(session, PersonExternalId.__table__, external_id_rows)
    return len(person_rows)


def _import_aliases(
    session: Session,
    reader: SQLiteReader,
    context: ImportContext,
    import_batch_id: UUID,
    person_ids: set[int],
) -> int:
    imported_at = datetime.now(UTC)
    rows: list[dict[str, Any]] = []
    for row in reader.iter_rows("ALTNAME_DATA"):
        cbdb_person_id = normalize_int(row.get("c_personid"))
        if cbdb_person_id not in person_ids:
            continue
        person_id = local_person_id(context, cbdb_person_id)
        if person_id is None:
            continue
        record = transform_alias_row(row, context, person_id)
        _add_import_batch_fields(record, import_batch_id, imported_at)
        rows.append(record)
    execute_upsert_rows(session, PersonAlias.__table__, rows)
    return len(rows)


def _import_relationships(
    session: Session,
    reader: SQLiteReader,
    context: ImportContext,
    import_batch_id: UUID,
    person_ids: set[int],
) -> int:
    imported_at = datetime.now(UTC)
    association_labels = _association_labels(reader)
    rows: list[dict[str, Any]] = []
    for row in reader.iter_rows("ASSOC_DATA"):
        record = transform_relationship_row(row, context)
        record["association_label"] = association_labels.get(record["association_code"])
        _null_missing_person_refs(record, person_ids)
        _add_import_batch_fields(record, import_batch_id, imported_at)
        rows.append(record)
    execute_upsert_rows(
        session,
        RelationshipCandidate.__table__,
        rows,
        protected_columns=REVIEW_PROTECTED_COLUMNS,
    )
    return len(rows)


def _import_kinships(
    session: Session,
    reader: SQLiteReader,
    context: ImportContext,
    import_batch_id: UUID,
    person_ids: set[int],
) -> int:
    imported_at = datetime.now(UTC)
    kinship_codes = _kinship_code_rows(reader)
    rows: list[dict[str, Any]] = []
    for row in reader.iter_rows("KIN_DATA"):
        kinship_code = normalize_int(row.get("c_kin_code"))
        code_row = kinship_codes.get(kinship_code) if kinship_code is not None else None
        source_row = {**row, **code_row} if code_row is not None else row
        record = transform_kinship_row(source_row, context)
        if normalize_int(row.get("c_personid")) not in person_ids:
            record["person_a_id"] = None
        if normalize_int(row.get("c_kin_id")) not in person_ids:
            record["person_b_id"] = None
        _add_import_batch_fields(record, import_batch_id, imported_at)
        rows.append(record)
    execute_upsert_rows(
        session,
        KinshipCandidate.__table__,
        rows,
        protected_columns=REVIEW_PROTECTED_COLUMNS,
    )
    return len(rows)


def _import_office_postings(
    session: Session,
    reader: SQLiteReader,
    context: ImportContext,
    import_batch_id: UUID,
    person_ids: set[int],
) -> int:
    imported_at = datetime.now(UTC)
    office_labels = _office_labels(reader)
    rows: list[dict[str, Any]] = []
    for row in reader.iter_rows("POSTED_TO_OFFICE_DATA"):
        record = transform_office_posting_row(row, context)
        record["office_label"] = office_labels.get(record["office_code"])
        _null_missing_person_refs(record, person_ids)
        _add_import_batch_fields(record, import_batch_id, imported_at)
        rows.append(record)
    execute_upsert_rows(session, OfficePosting.__table__, rows)
    return len(rows)


def _association_labels(reader: SQLiteReader) -> dict[int, str]:
    labels: dict[int, str] = {}
    for row in reader.iter_rows("ASSOC_CODES"):
        code = normalize_int(row.get("c_assoc_code"))
        label = normalize_text(row.get("c_assoc_desc_chn"))
        if code is not None and label is not None:
            labels[code] = label
    return labels


def _kinship_code_rows(reader: SQLiteReader) -> dict[int, dict[str, Any]]:
    rows: dict[int, dict[str, Any]] = {}
    for row in reader.iter_rows("KINSHIP_CODES"):
        code = normalize_int(row.get("c_kincode"))
        if code is not None:
            rows[code] = row
    return rows


def _office_labels(reader: SQLiteReader) -> dict[int, str]:
    labels: dict[int, str] = {}
    for row in reader.iter_rows("OFFICE_CODES"):
        code = normalize_int(row.get("c_office_id"))
        label = normalize_text(row.get("c_office_chn"))
        if code is not None and label is not None:
            labels[code] = label
    return labels


def _null_missing_person_refs(record: dict[str, Any], person_ids: set[int]) -> None:
    if "cbdb_person_a_id" in record and record.get("cbdb_person_a_id") not in person_ids:
        record["person_a_id"] = None
    if "cbdb_person_b_id" in record and record.get("cbdb_person_b_id") not in person_ids:
        record["person_b_id"] = None
    if (
        "person_id" in record
        and normalize_int(record["raw_cbdb"].get("c_personid")) not in person_ids
    ):
        record["person_id"] = None


def _add_import_batch_fields(
    record: dict[str, Any],
    import_batch_id: UUID,
    imported_at: datetime,
) -> None:
    record["import_batch_id"] = import_batch_id
    record["imported_at"] = imported_at
    record["updated_at"] = imported_at
