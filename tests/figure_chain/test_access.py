from __future__ import annotations

import pytest

from figure_chain.access import OperationContext, OperationRole, require_any_role
from figure_chain.errors import ApplicationError, ErrorCode


def test_reviewer_can_use_reviewer_guard() -> None:
    context = OperationContext(actor_id="alice", role=OperationRole.REVIEWER)

    require_any_role(context, {OperationRole.REVIEWER})


def test_operator_can_use_operator_guard() -> None:
    context = OperationContext(actor_id="ops", role=OperationRole.OPERATOR)

    require_any_role(context, {OperationRole.OPERATOR})


def test_explorer_cannot_use_reviewer_guard() -> None:
    context = OperationContext(actor_id="guest", role=OperationRole.EXPLORER)

    with pytest.raises(ApplicationError) as exc_info:
        require_any_role(context, {OperationRole.REVIEWER})

    assert exc_info.value.code is ErrorCode.ACCESS_DENIED
    assert exc_info.value.details == {
        "required_roles": ["reviewer"],
        "actual_role": "explorer",
    }
