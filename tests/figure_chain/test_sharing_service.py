from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import pytest

from figure_chain.errors import ApplicationError, ErrorCode
from figure_chain.schemas import ChainShareCreateRequest
from figure_chain.services import sharing
from figure_chain.services.sharing import SharingService
from figure_data.sharing.markdown import render_chain_markdown
from figure_data.sharing.types import ChainShareSnapshotRecord, NewChainShareSnapshot

SOURCE_PERSON_ID = UUID("38966b03-8aa7-5143-8021-2d266889b6c5")
TARGET_PERSON_ID = UUID("46cfdf66-08c4-5876-964b-4a95d098afe9")
ENCOUNTER_ID = UUID("e4f22ec2-22f7-4cda-bcc1-73aa83d0685f")


class MappingResult:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows

    def mappings(self) -> MappingResult:
        return self

    def all(self) -> list[dict[str, Any]]:
        return self._rows


class FakeShareSession:
    def __init__(self, *, include_encounter: bool = True) -> None:
        self.include_encounter = include_encounter
        self.statements: list[str] = []
        self.params: list[dict[str, Any]] = []

    def execute(self, statement: Any, params: dict[str, Any] | None = None) -> MappingResult:
        sql = str(statement)
        self.statements.append(sql)
        self.params.append(params or {})
        if "from figure_data.encounters" in sql:
            return MappingResult(self._encounter_rows() if self.include_encounter else [])
        if "from figure_data.encounter_evidence" in sql:
            return MappingResult(self._evidence_rows())
        raise AssertionError(f"unexpected query: {sql}")

    def _encounter_rows(self) -> list[dict[str, Any]]:
        return [
            {
                "encounter_id": ENCOUNTER_ID,
                "person_a_id": SOURCE_PERSON_ID,
                "person_b_id": TARGET_PERSON_ID,
                "person_a_name": "許幾",
                "person_a_birth_year": 1000,
                "person_a_death_year": 1064,
                "person_a_cbdb_external_id": "780",
                "person_b_name": "韓琦",
                "person_b_birth_year": 1008,
                "person_b_death_year": 1075,
                "person_b_cbdb_external_id": "630",
                "encounter_kind": "direct_interaction",
                "certainty_level": "high",
                "path_eligible": True,
                "source_work_id": 7596,
                "pages": "卷一",
                "evidence_summary": "許幾謁韓琦於魏",
            }
        ]

    def _evidence_rows(self) -> list[dict[str, Any]]:
        return [
            {
                "encounter_id": ENCOUNTER_ID,
                "evidence_id": 3853784,
                "source_ref_id": 3853784,
                "source_work_id": 7596,
                "title": "宋史",
                "pages": "卷一",
                "notes": "CBDB source ref",
            }
        ]


def request_payload() -> ChainShareCreateRequest:
    return ChainShareCreateRequest(
        source_person_id=SOURCE_PERSON_ID,
        target_person_id=TARGET_PERSON_ID,
        chain_hash="known-chain-hash",
        path_payload={
            "people": [
                {"person_id": str(SOURCE_PERSON_ID), "display_name": "伪造起点"},
                {"person_id": str(TARGET_PERSON_ID), "display_name": "伪造终点"},
            ],
            "edges": [
                {
                    "encounter_id": str(ENCOUNTER_ID),
                    "evidence_summary": "伪造证据",
                    "source_ref_id": 999999,
                    "source_refs": [{"source_ref_id": 999999, "source_work_id": 999999}],
                }
            ],
            "ai_explanation": {
                "ai_run_id": "00000000-0000-0000-0000-000000000999",
                "summary": "伪造 AI 解释",
            },
        },
        filters_applied={"max_depth": 12},
        include_ai_explanation=True,
        include_rag_context=False,
        created_by="lyl",
    )


def test_create_share_rebuilds_snapshot_from_postgres(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, NewChainShareSnapshot] = {}

    def fake_create_share_snapshot(
        session: object,
        snapshot: NewChainShareSnapshot,
    ) -> ChainShareSnapshotRecord:
        captured["snapshot"] = snapshot
        return ChainShareSnapshotRecord(
            id=UUID("00000000-0000-0000-0000-000000000501"),
            share_slug="20260619-test",
            created_at=datetime(2026, 6, 19, tzinfo=UTC),
            **snapshot.__dict__,
        )

    monkeypatch.setattr(sharing, "create_share_snapshot", fake_create_share_snapshot)

    service = SharingService(FakeShareSession())  # type: ignore[arg-type]
    response = service.create_share(request_payload())

    assert response.share_slug == "20260619-test"
    snapshot = captured["snapshot"]
    assert snapshot.encounter_ids == [str(ENCOUNTER_ID)]
    assert snapshot.path_payload["people"] == [
        {
            "person_id": str(SOURCE_PERSON_ID),
            "display_name": "許幾",
            "birth_year": 1000,
            "death_year": 1064,
            "cbdb_external_id": "780",
        },
        {
            "person_id": str(TARGET_PERSON_ID),
            "display_name": "韓琦",
            "birth_year": 1008,
            "death_year": 1075,
            "cbdb_external_id": "630",
        },
    ]
    edge = snapshot.path_payload["edges"][0]  # type: ignore[index]
    assert edge["evidence_summary"] == "許幾謁韓琦於魏"
    assert edge["source_ref_id"] == 3853784
    assert edge["source_work_id"] == 7596
    assert edge["source_refs"] == [
        {
            "source_ref_id": 3853784,
            "source_work_id": 7596,
            "title": "宋史",
            "pages": "卷一",
        }
    ]
    assert "ai_explanation" not in snapshot.path_payload


def test_create_share_rejects_non_path_encounter() -> None:
    service = SharingService(FakeShareSession(include_encounter=False))  # type: ignore[arg-type]

    with pytest.raises(ApplicationError) as exc_info:
        service.create_share(request_payload())

    assert exc_info.value.code == ErrorCode.SHARE_SNAPSHOT_INVALID


def test_created_share_markdown_exports_server_source_ids(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, NewChainShareSnapshot] = {}

    def fake_create_share_snapshot(
        session: object,
        snapshot: NewChainShareSnapshot,
    ) -> ChainShareSnapshotRecord:
        captured["snapshot"] = snapshot
        return ChainShareSnapshotRecord(
            id=UUID("00000000-0000-0000-0000-000000000501"),
            share_slug="20260619-test",
            created_at=datetime(2026, 6, 19, tzinfo=UTC),
            **snapshot.__dict__,
        )

    monkeypatch.setattr(sharing, "create_share_snapshot", fake_create_share_snapshot)

    service = SharingService(FakeShareSession())  # type: ignore[arg-type]
    service.create_share(request_payload())

    record = ChainShareSnapshotRecord(
        id=UUID("00000000-0000-0000-0000-000000000501"),
        share_slug="20260619-test",
        created_at=datetime(2026, 6, 19, tzinfo=UTC),
        **captured["snapshot"].__dict__,
    )
    result = render_chain_markdown(record)

    assert result.source_ids["source_ref_ids"] == ["3853784"]
    assert result.source_ids["source_work_ids"] == ["7596"]
