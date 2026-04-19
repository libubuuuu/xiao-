from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
import os

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATABASE_PATH = PROJECT_ROOT / "backend" / "data" / "social_content.sqlite3"
DEFAULT_FRONTEND_BUILD_DIR = PROJECT_ROOT / "frontend" / "build"
DEFAULT_CORS_ORIGINS = (
    "http://localhost:3000",
    "http://127.0.0.1:3000",
)


def _int(value: str | None, default: int) -> int:
    try:
        return int(value) if value is not None else default
    except ValueError:
        return default


def _csv(value: str | None, default: tuple[str, ...]) -> tuple[str, ...]:
    if not value:
        return default
    items = [item.strip() for item in value.split(",")]
    cleaned = tuple(item for item in items if item)
    return cleaned or default


@dataclass(frozen=True)
class Settings:
    app_name: str
    environment: str
    host: str
    port: int
    owner_access_token: str
    database_path: Path
    frontend_build_dir: Path
    cors_origins: tuple[str, ...]
    log_level: str
    service_version: str
    max_upload_size_mb: int


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings(
        app_name=os.getenv("APP_NAME", "Social Content Platform"),
        environment=os.getenv("APP_ENV", "development"),
        host=os.getenv("HOST", "0.0.0.0"),
        port=_int(os.getenv("PORT"), 8000),
        owner_access_token=os.getenv("OWNER_ACCESS_TOKEN", "owner-demo-token"),
        database_path=Path(os.getenv("APP_DB_PATH", DEFAULT_DATABASE_PATH)),
        frontend_build_dir=Path(os.getenv("FRONTEND_BUILD_DIR", DEFAULT_FRONTEND_BUILD_DIR)),
        cors_origins=_csv(os.getenv("CORS_ORIGINS"), DEFAULT_CORS_ORIGINS),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        service_version=os.getenv("APP_VERSION", "0.2.0"),
        max_upload_size_mb=_int(os.getenv("MAX_UPLOAD_SIZE_MB"), 50),
    )
