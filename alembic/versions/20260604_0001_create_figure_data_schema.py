"""create figure_data schema

Revision ID: 20260604_0001
Revises:
Create Date: 2026-06-04
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260604_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS figure_data")
    from figure_data.db import models
    from figure_data.db.base import Base

    _model_modules = models.__all__
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind, tables=list(Base.metadata.tables.values()))


def downgrade() -> None:
    from figure_data.db import models
    from figure_data.db.base import Base

    _model_modules = models.__all__
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind, tables=list(reversed(Base.metadata.sorted_tables)))
    op.execute("DROP SCHEMA IF EXISTS figure_data CASCADE")
