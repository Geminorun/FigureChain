from uuid import UUID

from sqlalchemy.orm import Session

from figure_chain.errors import ApplicationError, ErrorCode
from figure_chain.schemas import AIChainExplanationResponse, AIRunResponse
from figure_data.ai.chain_repository import (
    AIChainExplanationNotFoundError,
    get_chain_explanation_by_hash,
)
from figure_data.ai.errors import AIRunNotFoundError
from figure_data.ai.repository import get_ai_run


class AIService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_chain_explanation(self, chain_hash: str) -> AIChainExplanationResponse:
        try:
            record = get_chain_explanation_by_hash(self._session, chain_hash)
        except AIChainExplanationNotFoundError as exc:
            raise ApplicationError(
                code=ErrorCode.AI_RESULT_NOT_FOUND,
                message="AI chain explanation was not found",
                details={"chain_hash": chain_hash},
            ) from exc
        return AIChainExplanationResponse(**record.__dict__)

    def get_ai_run(self, run_id: UUID) -> AIRunResponse:
        try:
            record = get_ai_run(self._session, run_id)
        except AIRunNotFoundError as exc:
            raise ApplicationError(
                code=ErrorCode.AI_RESULT_NOT_FOUND,
                message="AI run was not found",
                details={"run_id": str(run_id)},
            ) from exc
        return AIRunResponse(
            run_id=record.run_id,
            purpose=record.purpose,
            provider=record.provider,
            model_name=record.model_name,
            prompt_key=record.prompt_key,
            prompt_version=record.prompt_version,
            status=record.status,
            schema_valid=record.schema_valid,
            error_code=record.error_code,
            error_message=record.error_message,
            started_at=record.started_at,
            finished_at=record.finished_at,
            created_by=record.created_by,
        )
