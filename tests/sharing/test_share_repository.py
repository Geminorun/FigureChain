from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import pytest

from figure_data.sharing.repository import (
    ShareSnapshotNotFoundError,
    create_share_snapshot,
    get_share_snapshot_by_slug,
    record_markdown_export,
)
from figure_data.sharing.types import NewChainShareSnapshot


@dataclass
class ScalarResult:
    value: object

    def scalar_one(self) -> object:
        return self.value


@dataclass
class MappingResult:
    rows: list[dict[str, Any]]

    def mappings(self) -> "MappingResult":
        return self

    def one_or_none(self) -> dict[str, Any] | None:
        return self.rows[0] if self.rows else None


class FakeSession:
    def __init__(self, *, found: bool = True) -> None:
        self.statements: list[str] = []
        self.params: list[dict[str, Any]] = []
        self.snapshot_id = UUID("00000000-0000-0000-0000-000000000501")
        self.export_id = UUID("00000000-0000-0000-0000-000000000502")
        self.created_at = datetime(2026, 6, 19, tzinfo=UTC)
        self.found = found

    def execute(self, statement: Any, params: dict[str, Any] | None = None) -> object:
        sql = str(statement)
        current_params = params or {}
        self.statements.append(sql)
        self.params.append(current_params)
        if "insert into figure_data.chain_share_snapshots" in sql:
            return MappingResult(
                [
                    {
                        "id": self.snapshot_id,
                        "share_slug": current_params["share_slug"],
                        "created_at": self.created_at,
                    }
                ]
            )
        if "insert into figure_data.chain_export_records" in sql:
            return MappingResult(
                [
                    {
                        "id": self.export_id,
                        "created_at": self.created_at,
                    }
                ]
            )
        if not self.found:
            return MappingResult([])
        return MappingResult(
            [
                {
                    "id": self.snapshot_id,
                    "share_slug": "20260619-test",
                    "source_person_id": UUID("38966b03-8aa7-5143-8021-2d266889b6c5"),
                    "target_person_id": UUID("46cfdf66-08c4-5876-964b-4a95d098afe9"),
                    "chain_hash": "known-chain-hash",
                    "encounter_ids": ["e4f22ec2-22f7-4cda-bcc1-73aa83d0685f"],
                    "path_payload": {"length": 1},
                    "filters_applied": {"max_depth": 12},
                    "include_ai_explanation": True,
                    "include_rag_context": False,
                    "schema_version": "share-v1",
                    "created_by": "lyl",
                    "created_at": self.created_at,
                }
            ]
        )


def new_snapshot() -> NewChainShareSnapshot:
    return NewChainShareSnapshot(
        source_person_id=UUID("38966b03-8aa7-5143-8021-2d266889b6c5"),
        target_person_id=UUID("46cfdf66-08c4-5876-964b-4a95d098afe9"),
        chain_hash="known-chain-hash",
        encounter_ids=["e4f22ec2-22f7-4cda-bcc1-73aa83d0685f"],
        path_payload={"length": 1, "people": [{"display_name": "許幾"}]},
        filters_applied={"max_depth": 12},
        include_ai_explanation=True,
        include_rag_context=False,
        schema_version="share-v1",
        created_by="lyl",
    )


def test_create_share_snapshot_generates_slug_and_serializes_payloads() -> None:
    session = FakeSession()

    record = create_share_snapshot(
        session,  # type: ignore[arg-type]
        new_snapshot(),
    )

    assert record.id == session.snapshot_id
    assert record.share_slug.startswith("20260619-")
    assert record.chain_hash == "known-chain-hash"
    assert "insert into figure_data.chain_share_snapshots" in session.statements[0]
    assert session.params[0]["share_slug"] == record.share_slug
    assert "許幾" in session.params[0]["path_payload"]
    assert session.params[0]["filters_applied"] == '{"max_depth": 12}'


def test_get_share_snapshot_by_slug_returns_record() -> None:
    session = FakeSession()

    record = get_share_snapshot_by_slug(
        session,  # type: ignore[arg-type]
        "20260619-test",
    )

    assert record.id == session.snapshot_id
    assert record.share_slug == "20260619-test"
    assert record.path_payload == {"length": 1}
    assert record.filters_applied == {"max_depth": 12}
    assert record.include_ai_explanation is True


def test_get_share_snapshot_by_slug_raises_for_missing_snapshot() -> None:
    session = FakeSession(found=False)

    with pytest.raises(ShareSnapshotNotFoundError):
        get_share_snapshot_by_slug(
            session,  # type: ignore[arg-type]
            "missing",
        )


def test_record_markdown_export_stores_filename_and_source_ids() -> None:
    session = FakeSession()

    record = record_markdown_export(
        session,  # type: ignore[arg-type]
        session.snapshot_id,
        filename="figurechain-known-chain-hash.md",
        source_ids={
            "encounter_ids": ["e4f22ec2-22f7-4cda-bcc1-73aa83d0685f"],
            "source_ref_ids": ["3853784"],
        },
    )

    assert record.id == session.export_id
    assert record.format == "markdown"
    assert record.filename == "figurechain-known-chain-hash.md"
    assert record.source_ids["source_ref_ids"] == ["3853784"]
    assert "insert into figure_data.chain_export_records" in session.statements[0]
    assert session.params[0]["format"] == "markdown"
    assert "3853784" in session.params[0]["source_ids"]
