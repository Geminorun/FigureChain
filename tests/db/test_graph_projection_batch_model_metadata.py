from __future__ import annotations

from figure_data.db.base import Base
from figure_data.db.models import graph_projection


def test_graph_projection_batches_model_metadata() -> None:
    assert graph_projection
    table = Base.metadata.tables["figure_data.graph_projection_batches"]

    assert table.c.mode.nullable is False
    assert table.c.status.nullable is False
    assert table.c.triggered_by.nullable is False
    assert table.c.validation_summary.type.__class__.__name__ == "JSONB"
    assert "ix_figure_data_graph_projection_batches_status_started_at" in {
        index.name for index in table.indexes
    }
