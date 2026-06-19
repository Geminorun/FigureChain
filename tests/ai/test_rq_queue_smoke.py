import os
from uuid import uuid4

import pytest

from figure_data.ai.queue import create_ai_job_queue
from figure_data.config import load_settings

pytestmark = pytest.mark.skipif(
    os.environ.get("FIGURE_TEST_REDIS") != "1" or not os.environ.get("REDIS_URL"),
    reason="Redis smoke is opt-in",
)


def test_rq_queue_can_enqueue_minimal_payload() -> None:
    settings = load_settings().model_copy(update={"ai_queue_backend": "rq"})
    queue = create_ai_job_queue(settings)
    job_id = uuid4()

    result = queue.enqueue(
        job_id=job_id,
        queue_name=settings.ai_queue_name,
        timeout_seconds=30,
    )

    assert result.queue_backend == "rq"
    assert result.queue_job_id
