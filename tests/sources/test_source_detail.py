from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

import pytest

from figure_data.sources.detail import (
    SourceRefNotFoundError,
    SourceWorkNotFoundError,
    get_source_ref_detail,
    get_source_work_detail,
)


@dataclass
class MappingResult:
    rows: list[dict[str, Any]]

    def mappings(self) -> MappingResult:
        return self

    def one_or_none(self) -> dict[str, Any] | None:
        return self.rows[0] if self.rows else None

    def all(self) -> list[dict[str, Any]]:
        return self.rows


class FakeSession:
    def __init__(self, rows: list[list[dict[str, Any]]]) -> None:
        self.rows = rows
        self.statements: list[str] = []
        self.params: list[dict[str, Any] | None] = []

    def execute(self, statement: Any, params: dict[str, Any] | None = None) -> MappingResult:
        self.statements.append(str(statement))
        self.params.append(params)
        return MappingResult(self.rows.pop(0))


def test_get_source_work_detail_returns_metadata_and_counts() -> None:
    session = FakeSession(
        [
            [
                {
                    "source_work_id": 1,
                    "text_code": 100,
                    "title_zh": "三國志",
                    "title_en": "Records of the Three Kingdoms",
                    "source_name": "CBDB",
                    "source_table": "TEXT_CODES",
                    "source_pk": "100",
                    "ref_count": 3,
                    "encounter_count": 2,
                }
            ]
        ]
    )

    detail = get_source_work_detail(session, 1)  # type: ignore[arg-type]

    assert detail.source_work_id == 1
    assert detail.title_zh == "三國志"
    assert detail.ref_count == 3
    assert detail.encounter_count == 2
    assert "figure_data.source_works" in session.statements[0]
    assert "figure_data.source_refs" in session.statements[0]
    assert "figure_data.encounter_evidence" in session.statements[0]


def test_get_source_work_detail_raises_when_missing() -> None:
    session = FakeSession([[]])

    with pytest.raises(SourceWorkNotFoundError):
        get_source_work_detail(session, 999)  # type: ignore[arg-type]


def test_get_source_ref_detail_returns_work_and_linked_evidence() -> None:
    encounter_id = UUID("00000000-0000-0000-0000-000000000101")
    session = FakeSession(
        [
            [
                {
                    "source_ref_id": 10,
                    "source_work_id": 1,
                    "ref_source_table": "BIOG_MAIN",
                    "ref_source_pk": "25403",
                    "pages": "12a",
                    "notes": "原始引用",
                    "source_name": "CBDB",
                    "source_table": "BIOG_SOURCE_DATA",
                    "source_pk": "10",
                }
            ],
            [
                {
                    "source_work_id": 1,
                    "text_code": 100,
                    "title_zh": "三國志",
                    "title_en": None,
                    "source_name": "CBDB",
                    "source_table": "TEXT_CODES",
                    "source_pk": "100",
                    "ref_count": 3,
                    "encounter_count": 2,
                }
            ],
            [
                {
                    "evidence_id": 55,
                    "encounter_id": encounter_id,
                    "evidence_kind": "candidate",
                    "evidence_summary": "有直接交往證據",
                    "pages": "12a",
                    "created_at": "2026-06-19T00:00:00Z",
                }
            ],
        ]
    )

    detail = get_source_ref_detail(session, 10)  # type: ignore[arg-type]

    assert detail.source_ref_id == 10
    assert detail.source_work is not None
    assert detail.source_work.source_work_id == 1
    assert detail.linked_encounter_evidence[0].evidence_id == 55
    assert detail.linked_encounter_evidence[0].encounter_id == encounter_id
    assert "figure_data.source_refs" in session.statements[0]
    assert "figure_data.source_works" in session.statements[1]
    assert "figure_data.encounter_evidence" in session.statements[2]


def test_get_source_ref_detail_keeps_ref_when_source_work_is_missing() -> None:
    encounter_id = UUID("00000000-0000-0000-0000-000000000101")
    session = FakeSession(
        [
            [
                {
                    "source_ref_id": 3853784,
                    "source_work_id": 7596,
                    "ref_source_table": "BIOG_MAIN",
                    "ref_source_pk": "780",
                    "pages": "11905",
                    "notes": "原始引用",
                    "source_name": "CBDB",
                    "source_table": "BIOG_SOURCE_DATA",
                    "source_pk": "3853784",
                }
            ],
            [],
            [
                {
                    "evidence_id": 55,
                    "encounter_id": encounter_id,
                    "evidence_kind": "reviewed",
                    "evidence_summary": "有直接交往證據",
                    "pages": "11905",
                    "created_at": "2026-06-19T00:00:00Z",
                }
            ],
        ]
    )

    detail = get_source_ref_detail(session, 3853784)  # type: ignore[arg-type]

    assert detail.source_ref_id == 3853784
    assert detail.source_work is None
    assert detail.linked_encounter_evidence[0].encounter_id == encounter_id


def test_get_source_ref_detail_raises_when_missing() -> None:
    session = FakeSession([[]])

    with pytest.raises(SourceRefNotFoundError):
        get_source_ref_detail(session, 999)  # type: ignore[arg-type]
