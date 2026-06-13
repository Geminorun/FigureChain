from datetime import UTC, datetime
from uuid import UUID

from fastapi.testclient import TestClient

from figure_chain.app import create_app
from figure_chain.dependencies import get_ai_service
from figure_chain.errors import ApplicationError, ErrorCode
from figure_chain.schemas import AIChainExplanationResponse, AIRunResponse


class FakeAIService:
    def get_chain_explanation(self, chain_hash: str) -> AIChainExplanationResponse:
        if chain_hash != "known":
            raise ApplicationError(
                code=ErrorCode.AI_RESULT_NOT_FOUND,
                message="AI chain explanation was not found",
                details={"chain_hash": chain_hash},
            )
        return AIChainExplanationResponse(
            id=UUID("00000000-0000-0000-0000-000000000401"),
            ai_run_id=UUID("00000000-0000-0000-0000-000000000301"),
            chain_hash="known",
            source_person_id=UUID("38966b03-8aa7-5143-8021-2d266889b6c5"),
            target_person_id=UUID("46cfdf66-08c4-5876-964b-4a95d098afe9"),
            max_depth=12,
            encounter_ids=["e4f22ec2-22f7-4cda-bcc1-73aa83d0685f"],
            language="zh-Hans",
            summary="这条人物链由一条已审核 encounter 组成。",
            edge_explanations=[
                {
                    "encounter_id": "e4f22ec2-22f7-4cda-bcc1-73aa83d0685f",
                    "explanation": "许几谒见韩琦。",
                    "evidence_basis": "encounter_evidence",
                    "source_ref_ids": [3853784],
                }
            ],
            source_ref_ids=[3853784],
            status="generated",
            created_at=datetime(2026, 6, 13, tzinfo=UTC),
        )

    def get_ai_run(self, run_id: UUID) -> AIRunResponse:
        return AIRunResponse(
            run_id=run_id,
            purpose="chain_explanation",
            provider="fake",
            model_name="fake-history-model",
            prompt_key="chain_explanation",
            prompt_version="2026-06-13.1",
            status="succeeded",
            schema_valid=True,
            error_code=None,
            error_message=None,
            started_at=datetime(2026, 6, 13, tzinfo=UTC),
            finished_at=datetime(2026, 6, 13, tzinfo=UTC),
            created_by="tester",
        )


def test_get_chain_explanation_returns_stored_result() -> None:
    app = create_app(lifespan_enabled=False)
    app.dependency_overrides[get_ai_service] = lambda: FakeAIService()

    with TestClient(app) as client:
        response = client.get("/api/v1/ai/chains/explanations/known")

    assert response.status_code == 200
    body = response.json()
    assert body["chain_hash"] == "known"
    assert body["summary"] == "这条人物链由一条已审核 encounter 组成。"


def test_get_chain_explanation_returns_404_when_missing() -> None:
    app = create_app(lifespan_enabled=False)
    app.dependency_overrides[get_ai_service] = lambda: FakeAIService()

    with TestClient(app) as client:
        response = client.get("/api/v1/ai/chains/explanations/missing")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "ai_result_not_found"


def test_get_ai_run_returns_trace_metadata() -> None:
    app = create_app(lifespan_enabled=False)
    app.dependency_overrides[get_ai_service] = lambda: FakeAIService()

    with TestClient(app) as client:
        response = client.get("/api/v1/ai/runs/00000000-0000-0000-0000-000000000301")

    assert response.status_code == 200
    assert response.json()["prompt_key"] == "chain_explanation"
