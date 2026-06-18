import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    APP_NAME: str = os.getenv("APP_NAME", "LexPilot")
    SECRET_KEY: str = os.getenv("SECRET_KEY", "change_me_later")

    DATABASE_URL: str = os.getenv("DATABASE_URL", "")

    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")

    ADMIN_EMAIL: str = os.getenv("ADMIN_EMAIL", "admin@example.com")
    ADMIN_PASSWORD: str = os.getenv("ADMIN_PASSWORD", "admin123")


settings = Settings()