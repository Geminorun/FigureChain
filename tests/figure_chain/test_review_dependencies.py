from typing import cast

from sqlalchemy.orm import Session

from figure_chain.dependencies import get_review_service
from figure_chain.services.review import ReviewService


def test_get_review_service_uses_existing_pg_session() -> None:
    session = cast(Session, object())

    service = get_review_service(session)

    assert isinstance(service, ReviewService)
