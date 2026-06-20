from __future__ import annotations

from figure_data.db.base import Base
from figure_data.db.models import admin


def test_admin_operations_model_metadata() -> None:
    assert admin
    table = Base.metadata.tables["figure_data.admin_operations"]

    assert table.c.operation_type.nullable is False
    assert table.c.actor.nullable is False
    assert table.c.status.nullable is False
    assert table.c.request_payload.type.__class__.__name__ == "JSONB"
    assert table.c.result_summary.type.__class__.__name__ == "JSONB"
    assert "ix_figure_data_admin_operations_status_created_at" in {
        index.name for index in table.indexes
    }
    assert "ix_figure_data_admin_operations_type_created_at" in {
        index.name for index in table.indexes
    }
    assert "ix_figure_data_admin_operations_related_resource" in {
        index.name for index in table.indexes
    }
