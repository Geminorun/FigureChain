from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from figure_chain.errors import ApplicationError, ErrorCode


class OperationRole(StrEnum):
    EXPLORER = "explorer"
    REVIEWER = "reviewer"
    OPERATOR = "operator"


@dataclass(frozen=True)
class OperationContext:
    actor_id: str
    role: OperationRole


def require_any_role(
    context: OperationContext,
    allowed_roles: set[OperationRole],
) -> None:
    if context.role in allowed_roles:
        return
    required = sorted(role.value for role in allowed_roles)
    raise ApplicationError(
        code=ErrorCode.ACCESS_DENIED,
        message="operation is not allowed for this role",
        details={
            "required_roles": required,
            "actual_role": context.role.value,
        },
    )
