from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from figure_data.cbdb.normalize import normalize_int, normalize_text
from figure_data.cbdb.source_identity import build_source_pk, hash_source_row
from figure_data.cbdb.sqlite_reader import SQLiteReader
from figure_data.db.models.office import OfficeCode
from figure_data.db.models.relationship import AssociationCode, KinshipCode
from figure_data.db.models.source import Dynasty, SourceWork
from figure_data.importing.context import ImportContext, ImportPhaseResult, imported_record_fields
from figure_data.importing.upsert import UpsertStats, execute_upsert_rows


def import_dictionaries(
    session: Session,
    reader: SQLiteReader,
    context: ImportContext,
    import_batch_id: UUID,
) -> ImportPhaseResult:
    imported_at = datetime.now(UTC)
    rows_read = 0
    upsert_stats = UpsertStats()
    for import_dictionary in [
        _import_dynasties,
        _import_source_works,
        _import_association_codes,
        _import_kinship_codes,
        _import_office_codes,
    ]:
        result = import_dictionary(session, reader, context, import_batch_id, imported_at)
        rows_read += result.rows_read
        upsert_stats.add(result.upsert_stats)
    return ImportPhaseResult(rows_read=rows_read, upsert_stats=upsert_stats)


def _import_dynasties(
    session: Session,
    reader: SQLiteReader,
    context: ImportContext,
    import_batch_id: UUID,
    imported_at: datetime,
) -> ImportPhaseResult:
    rows = [
        {
            "dynasty_code": normalize_int(row.get("c_dy")),
            "label_zh": normalize_text(row.get("c_dynasty_chn")),
            "label_en": normalize_text(row.get("c_dynasty")),
            **_imported_fields(row, context, "DYNASTIES", ["c_dy"], import_batch_id, imported_at),
        }
        for row in reader.iter_rows("DYNASTIES")
    ]
    return ImportPhaseResult(
        rows_read=len(rows),
        upsert_stats=execute_upsert_rows(session, Dynasty.__table__, rows),
    )


def _import_source_works(
    session: Session,
    reader: SQLiteReader,
    context: ImportContext,
    import_batch_id: UUID,
    imported_at: datetime,
) -> ImportPhaseResult:
    rows = [
        {
            "text_code": normalize_int(row.get("c_textid")),
            "title_zh": normalize_text(row.get("c_title_chn")),
            "title_en": normalize_text(row.get("c_title")),
            **_imported_fields(
                row,
                context,
                "TEXT_CODES",
                ["c_textid"],
                import_batch_id,
                imported_at,
            ),
        }
        for row in reader.iter_rows("TEXT_CODES")
    ]
    return ImportPhaseResult(
        rows_read=len(rows),
        upsert_stats=execute_upsert_rows(session, SourceWork.__table__, rows),
    )


def _import_association_codes(
    session: Session,
    reader: SQLiteReader,
    context: ImportContext,
    import_batch_id: UUID,
    imported_at: datetime,
) -> ImportPhaseResult:
    rows = []
    for row in reader.iter_rows("ASSOC_CODES"):
        example = normalize_text(row.get("c_example"))
        rows.append(
            {
                "association_code": normalize_int(row.get("c_assoc_code")),
                "label_zh": normalize_text(row.get("c_assoc_desc_chn")),
                "label_en": normalize_text(row.get("c_assoc_desc")),
                "role_type": normalize_text(row.get("c_assoc_role_type")),
                "association_type_codes": None,
                "association_type_labels": None,
                "examples": [example] if example is not None else None,
                **_imported_fields(
                    row,
                    context,
                    "ASSOC_CODES",
                    ["c_assoc_code"],
                    import_batch_id,
                    imported_at,
                ),
            }
        )
    return ImportPhaseResult(
        rows_read=len(rows),
        upsert_stats=execute_upsert_rows(session, AssociationCode.__table__, rows),
    )


def _import_kinship_codes(
    session: Session,
    reader: SQLiteReader,
    context: ImportContext,
    import_batch_id: UUID,
    imported_at: datetime,
) -> ImportPhaseResult:
    rows = [
        {
            "kinship_code": normalize_int(row.get("c_kincode")),
            "label_zh": normalize_text(row.get("c_kinrel_chn")),
            "label_en": normalize_text(row.get("c_kinrel")),
            "kinship_path": normalize_text(row.get("c_kin_pair1")),
            "upstep": normalize_int(row.get("c_upstep")),
            "downstep": normalize_int(row.get("c_dwnstep")),
            "marstep": normalize_int(row.get("c_marstep")),
            **_imported_fields(
                row,
                context,
                "KINSHIP_CODES",
                ["c_kincode"],
                import_batch_id,
                imported_at,
            ),
        }
        for row in reader.iter_rows("KINSHIP_CODES")
    ]
    return ImportPhaseResult(
        rows_read=len(rows),
        upsert_stats=execute_upsert_rows(session, KinshipCode.__table__, rows),
    )


def _import_office_codes(
    session: Session,
    reader: SQLiteReader,
    context: ImportContext,
    import_batch_id: UUID,
    imported_at: datetime,
) -> ImportPhaseResult:
    rows = [
        {
            "office_code": normalize_int(row.get("c_office_id")),
            "label_zh": normalize_text(row.get("c_office_chn")),
            "label_en": normalize_text(row.get("c_office_trans"))
            or normalize_text(row.get("c_office_pinyin")),
            "office_category_code": normalize_int(row.get("c_dy")),
            **_imported_fields(
                row,
                context,
                "OFFICE_CODES",
                ["c_office_id"],
                import_batch_id,
                imported_at,
            ),
        }
        for row in reader.iter_rows("OFFICE_CODES")
    ]
    return ImportPhaseResult(
        rows_read=len(rows),
        upsert_stats=execute_upsert_rows(session, OfficeCode.__table__, rows),
    )


def _imported_fields(
    row: dict[str, Any],
    context: ImportContext,
    source_table: str,
    key_columns: list[str],
    import_batch_id: UUID,
    imported_at: datetime,
) -> dict[str, Any]:
    return imported_record_fields(
        context=context,
        source_table=source_table,
        source_pk=build_source_pk(row, key_columns),
        source_row_hash=hash_source_row(row),
        raw_cbdb=dict(row),
        import_batch_id=import_batch_id,
        imported_at=imported_at,
    )
