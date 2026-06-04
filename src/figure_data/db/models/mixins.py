from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column


class ImportedRowMixin:
    source_name: Mapped[str] = mapped_column(String(64), nullable=False)
    source_snapshot: Mapped[str] = mapped_column(String(128), nullable=False)
    source_table: Mapped[str] = mapped_column(String(128), nullable=False)
    source_pk: Mapped[str] = mapped_column(Text, nullable=False)
    source_row_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    raw_cbdb: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    import_batch_id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
