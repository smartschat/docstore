"""Application configuration using pydantic-settings."""

from pathlib import Path
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application
    app_name: str = "DocStore"
    debug: bool = False

    # Authentication
    auth_password: str = "changeme"
    secret_key: str = "change-this-secret-key-in-production"
    session_expire_hours: int = 24 * 7  # 1 week

    # Paths
    data_dir: Path = Path("../data")
    inbox_dir: Path = Path("../data/inbox")
    archive_dir: Path = Path("../data/archive")
    database_path: Path = Path("../data/docstore.db")

    # OpenAI
    openai_api_key: str = ""
    openai_embedding_model: str = "text-embedding-ada-002"
    openai_chat_model: str = "gpt-5-nano"

    # OCR
    ocr_language: str = "deu+eng"  # German + English
    ocr_deskew: bool = True
    ocr_rotate_pages: bool = True

    # Processing
    max_file_size_mb: int = 50
    supported_mime_types: list[str] = [
        "application/pdf",
        "image/jpeg",
        "image/png",
        "image/tiff",
    ]

    @property
    def database_url(self) -> str:
        return f"sqlite+aiosqlite:///{self.database_path}"

    def ensure_directories(self) -> None:
        """Create required directories if they don't exist."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.inbox_dir.mkdir(parents=True, exist_ok=True)
        self.archive_dir.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
