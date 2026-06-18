from app.db.base import Base
from app.db.session import engine

from app.models.user import User
from app.models.case import LegalCase
from app.models.document import Document, GeneratedDocument
from app.models.knowledge import KnowledgeItem, KnowledgeChunk
from app.models.chat import ChatMessage
from app.models.timeline import TimelineEvent


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    print("LexPilot database tables created successfully.")


if __name__ == "__main__":
    init_db()