from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi.testclient import TestClient

from figure_chain.app import create_app
from figure_chain.dependencies import get_sharing_service
from figure_chain.errors import ApplicationError, ErrorCode
from figure_chain.schemas import (
    ChainShareCreateRequest,
    ChainShareCreateResponse,
    ChainShareDetailResponse,
    MarkdownExportRequest,
    MarkdownExportResponse,
)

SOURCE_PERSON_ID = "38966b03-8aa7-5143-8021-2d266889b6c5"
TARGET_PERSON_ID = "46cfdf66-08c4-5876-964b-4a95d098afe9"
ENCOUNTER_ID = "e4f22ec2-22f7-4cda-bcc1-73aa83d0685f"


def share_request() -> dict[str, object]:
    return {
        "source_person_id": SOURCE_PERSON_ID,
        "target_person_id": TARGET_PERSON_ID,
        "chain_hash": "known-chain-hash",
        "path_payload": {
            "people": [
                {"person_id": SOURCE_PERSON_ID, "display_name": "許幾"},
                {"person_id": TARGET_PERSON_ID, "display_name": "韓琦"},
            ],
            "edges": [
                {
                    "encounter_id": ENCOUNTER_ID,
                    "evidence_summary": "许几谒韩琦于魏",
                }
            ],
        },
        "filters_applied": {"max_depth": 12},
        "include_ai_explanation": True,
        "include_rag_context": False,
        "created_by": "lyl",
    }


class FakeSharingService:
    def create_share(self, request: ChainShareCreateRequest) -> ChainShareCreateResponse:
        return ChainShareCreateResponse(
            share_slug="20260619-test",
            url_path="/share/20260619-test",
        )

    def get_share(self, share_slug: str) -> ChainShareDetailResponse:
        if share_slug == "missing":
            raise ApplicationError(
                code=ErrorCode.SHARE_SNAPSHOT_NOT_FOUND,
                message="share snapshot not found",
            )
        return ChainShareDetailResponse(
            id=UUID("00000000-0000-0000-0000-000000000501"),
            share_slug=share_slug,
            url_path=f"/share/{share_slug}",
            source_person_id=UUID(SOURCE_PERSON_ID),
            target_person_id=UUID(TARGET_PERSON_ID),
            chain_hash="known-chain-hash",
            encounter_ids=[ENCOUNTER_ID],
            path_payload=share_request()["path_payload"],  # type: ignore[arg-type]
            filters_applied={"max_depth": 12},
            include_ai_explanation=True,
            include_rag_context=False,
            schema_version="share-v1",
            created_by="lyl",
            created_at=datetime(2026, 6, 19, tzinfo=UTC),
        )

    def export_markdown(self, request: MarkdownExportRequest) -> MarkdownExportResponse:
        if request.format != "markdown":
            raise ApplicationError(
                code=ErrorCode.EXPORT_FORMAT_NOT_SUPPORTED,
                message="export format is not supported",
            )
        return MarkdownExportResponse(
            content="# FigureChain 人物链\n",
            filename="figurechain-known-chain-hash.md",
            source_ids={
                "encounter_ids": [ENCOUNTER_ID],
                "source_ref_ids": ["3853784"],
                "source_work_ids": ["7596"],
                "ai_run_ids": [],
                "retrieval_document_ids": [],
            },
        )


def app_client() -> TestClient:
    app = create_app(lifespan_enabled=False)
    app.dependency_overrides[get_sharing_service] = lambda: FakeSharingService()
    return TestClient(app)


def test_create_share_snapshot_returns_slug_and_url_path() -> None:
    with app_client() as client:
        response = client.post("/api/v1/chains/share", json=share_request())

    assert response.status_code == 200
    assert response.json() == {
        "share_slug": "20260619-test",
        "url_path": "/share/20260619-test",
    }


def test_get_share_snapshot_returns_snapshot_detail() -> None:
    with app_client() as client:
        response = client.get("/api/v1/chains/share/20260619-test")

    assert response.status_code == 200
    body = response.json()
    assert body["share_slug"] == "20260619-test"
    assert body["url_path"] == "/share/20260619-test"
    assert body["encounter_ids"] == [ENCOUNTER_ID]
    assert body["path_payload"]["people"][0]["display_name"] == "許幾"


def test_export_markdown_returns_content_and_source_ids() -> None:
    with app_client() as client:
        response = client.post(
            "/api/v1/chains/export/markdown",
            json={"share_slug": "20260619-test", "format": "markdown"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["filename"] == "figurechain-known-chain-hash.md"
    assert body["content"].startswith("# FigureChain")
    assert body["source_ids"]["encounter_ids"] == [ENCOUNTER_ID]


def test_missing_share_returns_application_error() -> None:
    with app_client() as client:
        response = client.get("/api/v1/chains/share/missing")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "share_snapshot_not_found"


def test_unsupported_export_format_returns_application_error() -> None:
    with app_client() as client:
        response = client.post(
            "/api/v1/chains/export/markdown",
            json={"share_slug": "20260619-test", "format": "html"},
        )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "export_format_not_supported"
