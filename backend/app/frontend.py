from __future__ import annotations

import mimetypes
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_BUILD_DIR = PROJECT_ROOT / "frontend" / "build"
FRONTEND_INDEX_FILE = FRONTEND_BUILD_DIR / "index.html"


def frontend_build_available() -> bool:
    return FRONTEND_INDEX_FILE.is_file()


def resolve_frontend_asset(request_path: str) -> Path | None:
    if not frontend_build_available():
        return None

    relative_path = request_path.lstrip("/")
    if not relative_path:
        return FRONTEND_INDEX_FILE

    build_root = FRONTEND_BUILD_DIR.resolve()
    candidate = (FRONTEND_BUILD_DIR / relative_path).resolve()

    try:
        candidate.relative_to(build_root)
    except ValueError:
        return None

    if candidate.is_file():
        return candidate

    if not Path(relative_path).suffix:
        return FRONTEND_INDEX_FILE

    return None


def guess_content_type(file_path: Path) -> str:
    content_type, _ = mimetypes.guess_type(str(file_path))
    if not content_type:
        return "application/octet-stream"

    if content_type.startswith("text/") or content_type in {
        "application/javascript",
        "application/json",
        "application/xml",
        "application/xhtml+xml",
    }:
        return f"{content_type}; charset=utf-8"

    return content_type
