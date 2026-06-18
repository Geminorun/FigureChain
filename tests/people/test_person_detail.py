from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

import pytest

from figure_data.people.detail import (
    PersonDetailNotFoundError,
    PersonEncounterFilters,
    get_person_detail,
    list_person_encounters,
)

PERSON_ID = UUID("00000000-0000-0000-0000-000000000001")


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


def test_get_person_detail_loads_profile_aliases_external_ids_and_counts() -> None:
    session = FakeSession(
        [
            [
                {
                    "person_id": PERSON_ID,
                    "primary_name_zh_hant": "諸葛亮",
                    "primary_name_zh_hans": "诸葛亮",
                    "primary_name_romanized": "Zhuge Liang",
                    "birth_year": 181,
                    "death_year": 234,
                    "index_year": 207,
                    "floruit_start_year": None,
                    "floruit_end_year": None,
                    "dynasty_code": 6,
                    "dynasty_label_zh": "三國",
                    "dynasty_label_en": "Three Kingdoms",
                    "is_female": False,
                    "notes": "蜀漢丞相",
                }
            ],
            [
                {
                    "alias_zh_hant": "孔明",
                    "alias_zh_hans": "孔明",
                    "alias_romanized": None,
                    "alias_type_label_zh": "字",
                    "alias_type_label_en": "courtesy name",
                }
            ],
            [{"source_name": "CBDB", "external_id": "25403"}],
            [{"active_count": 2, "path_eligible_count": 1, "high_certainty_count": 1}],
        ]
    )

    detail = get_person_detail(session, PERSON_ID)  # type: ignore[arg-type]

    assert detail.person_id == PERSON_ID
    assert detail.primary_name_zh_hant == "諸葛亮"
    assert detail.aliases[0].alias_zh_hant == "孔明"
    assert detail.external_ids[0].external_id == "25403"
    assert detail.encounter_summary.path_eligible_count == 1


def test_get_person_detail_raises_when_missing() -> None:
    session = FakeSession([[]])

    with pytest.raises(PersonDetailNotFoundError):
        get_person_detail(session, PERSON_ID)  # type: ignore[arg-type]


def test_list_person_encounters_builds_filters_and_pagination() -> None:
    session = FakeSession(
        [
            [
                {
                    "encounter_id": UUID("00000000-0000-0000-0000-000000000101"),
                    "other_person_id": UUID("00000000-0000-0000-0000-000000000002"),
                    "other_person_name": "司馬懿",
                    "other_person_birth_year": 179,
                    "other_person_death_year": 251,
                    "encounter_kind": "direct_interaction",
                    "certainty_level": "high",
                    "path_eligible": True,
                    "source_work_id": 1,
                    "source_title": "三國志",
                    "pages": "12a",
                    "evidence_summary": "有直接交往證據",
                    "status": "active",
                    "reviewed_by": "lyl",
                    "reviewed_at": "2026-06-19T00:00:00Z",
                }
            ]
        ]
    )

    items = list_person_encounters(
        session,  # type: ignore[arg-type]
        PERSON_ID,
        PersonEncounterFilters(
            status="active",
            path_eligible=True,
            certainty_level="high",
            encounter_kind="direct_interaction",
            limit=10,
            offset=20,
        ),
    )

    assert len(items) == 1
    assert "e.person_a_id = :person_id or e.person_b_id = :person_id" in session.statements[0]
    assert "e.status = :status" in session.statements[0]
    assert "e.path_eligible = :path_eligible" in session.statements[0]
    assert session.params[0]["limit"] == 10
    assert session.params[0]["offset"] == 20
