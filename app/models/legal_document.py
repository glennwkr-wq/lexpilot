from sqlalchemy import String, Text, Date, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base import Base


class LegalDocument(Base):
    __tablename__ = "legal_documents"

    id: Mapped[int] = mapped_column(primary_key=True)

    title: Mapped[str] = mapped_column(Text, nullable=False)
    document_type: Mapped[str] = mapped_column(String(100), nullable=False)

    source: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    document_date: Mapped[Date | None] = mapped_column(Date, nullable=True)

    content: Mapped[str] = mapped_column(Text, nullable=False)

    created_at = mapped_column(DateTime, server_default=func.now())