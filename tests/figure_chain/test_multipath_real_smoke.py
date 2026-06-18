import os

import pytest
from fastapi.testclient import TestClient

from figure_chain.app import create_app


pytestmark = pytest.mark.skipif(
    os.environ.get("FIGURECHAIN_RUN_REAL_SMOKE") != "1",
    reason="real PostgreSQL/Neo4j smoke is opt-in",
)


def test_multipath_real_smoke_returns_stable_shape() -> None:
    app = create_app()
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/chains/multipath",
            json={
                "source": {"query": "许几"},
                "target": {"query": "韩琦"},
                "max_depth": 4,
                "max_paths": 5,
                "extra_depth": 1,
                "filters": {
                    "min_certainty_level": "high",
                    "encounter_kinds": [],
                    "exclude_person_ids": [],
                    "exclude_encounter_ids": [],
                    "source_work_ids": [],
                    "intermediate_dynasty_codes": [],
                    "intermediate_year_min": None,
                    "intermediate_year_max": None,
                },
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] in {"found", "no_path"}
    assert body["returned_paths"] == len(body["paths"])
    assert body["max_paths"] == 5
