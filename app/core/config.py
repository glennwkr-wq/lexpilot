import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    APP_NAME: str = os.getenv("APP_NAME", "LexPilot")
    SECRET_KEY: str = os.getenv("SECRET_KEY", "change_me_later")

    DATABASE_URL: str = os.getenv("DATABASE_URL", "")

    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
    RERANK_MODEL: str = os.getenv("RERANK_MODEL", "gpt-4o-mini")

    ADMIN_EMAIL: str = os.getenv("ADMIN_EMAIL", "admin@example.com")
    ADMIN_PASSWORD: str = os.getenv("ADMIN_PASSWORD", "admin123")
    INIT_DB_TOKEN: str = os.getenv("INIT_DB_TOKEN", "lexpilot_init_2026")


settings = Settings()