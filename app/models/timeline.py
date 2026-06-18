from sqlalchemy import String, Text, DateTime, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base import Base


class TimelineEvent(Base):
    __tablename__ = "timeline_events"

    id: Mapped[int] = mapped_column(primary_key=True)

    case_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("cases.id"),
        nullable=False,
        index=True,
    )

    event_date: Mapped[str | None] = mapped_column(String(50), nullable=True)

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    source: Mapped[str | None] = mapped_column(String(255), nullable=True)
    importance: Mapped[str | None] = mapped_column(String(50), nullable=True)

    created_at = mapped_column(DateTime(timezone=True), server_default=func.now())