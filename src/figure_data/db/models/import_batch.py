from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from figure_data.db.base import Base


class ImportBatch(Base):
    __tablename__ = "import_batches"
    __table_args__ = {"schema": "figure_data"}

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid4)
    source_name: Mapped[str] = mapped_column(String(64), nullable=False)
    source_snapshot: Mapped[str] = mapped_column(String(128), nullable=False)
    sqlite_filename: Mapped[str] = mapped_column(Text, nullable=False)
    sqlite_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    rows_read: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rows_inserted: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rows_updated: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rows_skipped: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_summary: Mapped[str | None] = mapped_column(Text)
