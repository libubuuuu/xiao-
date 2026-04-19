from __future__ import annotations

import json
import sqlite3
import threading
from functools import lru_cache
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from .config import get_settings


def _loads(value: str | None, default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default


def _dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    item = dict(row)
    if "owner_only" in item:
        item["owner_only"] = bool(item["owner_only"])
    if "draft_count" in item and item["draft_count"] is not None:
        item["draft_count"] = int(item["draft_count"])
    return item


class ContentRepository:
    def __init__(self, database_path: Path):
        self.database_path = database_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._initialised = False
        self._ensure_schema()

    @contextmanager
    def _connection(self):
        connection = sqlite3.connect(str(self.database_path), timeout=30, check_same_thread=False)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def _ensure_schema(self) -> None:
        with self._lock:
            if self._initialised:
                return
            with self._connection() as connection:
                connection.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS accounts (
                        id TEXT PRIMARY KEY,
                        platform_id TEXT NOT NULL,
                        display_name TEXT NOT NULL,
                        handle TEXT NOT NULL,
                        status TEXT NOT NULL,
                        draft_count INTEGER NOT NULL DEFAULT 0,
                        last_sync TEXT NOT NULL,
                        owner_only INTEGER NOT NULL DEFAULT 1,
                        created_at TEXT NOT NULL
                    );

                    CREATE TABLE IF NOT EXISTS cart_items (
                        item_id TEXT PRIMARY KEY,
                        payload_json TEXT NOT NULL,
                        created_at TEXT NOT NULL
                    );

                    CREATE TABLE IF NOT EXISTS remix_jobs (
                        job_id TEXT PRIMARY KEY,
                        payload_json TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        status TEXT NOT NULL
                    );

                    CREATE TABLE IF NOT EXISTS canvas_jobs (
                        job_id TEXT PRIMARY KEY,
                        payload_json TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        status TEXT NOT NULL
                    );

                    CREATE TABLE IF NOT EXISTS drafts (
                        id TEXT PRIMARY KEY,
                        payload_json TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        status TEXT NOT NULL,
                        account_id TEXT NOT NULL,
                        platform_id TEXT NOT NULL
                    );

                    CREATE TABLE IF NOT EXISTS comment_jobs (
                        job_id TEXT PRIMARY KEY,
                        payload_json TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        status TEXT NOT NULL
                    );

                    CREATE TABLE IF NOT EXISTS activity_log (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        action TEXT NOT NULL,
                        payload_json TEXT NOT NULL,
                        timestamp TEXT NOT NULL
                    );

                    CREATE INDEX IF NOT EXISTS idx_accounts_platform ON accounts(platform_id);
                    CREATE INDEX IF NOT EXISTS idx_cart_created_at ON cart_items(created_at);
                    CREATE INDEX IF NOT EXISTS idx_drafts_created_at ON drafts(created_at);
                    CREATE INDEX IF NOT EXISTS idx_activity_timestamp ON activity_log(timestamp);
                    """
                )
            self._initialised = True

    def seed_accounts(self, accounts: Iterable[Dict[str, Any]], now: str) -> None:
        with self._lock, self._connection() as connection:
            existing = connection.execute("SELECT COUNT(*) AS count FROM accounts").fetchone()["count"]
            if existing:
                return
            for account in accounts:
                connection.execute(
                    """
                    INSERT INTO accounts (
                        id, platform_id, display_name, handle, status, draft_count, last_sync, owner_only, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        account["id"],
                        account["platform_id"],
                        account["display_name"],
                        account["handle"],
                        account.get("status", "connected"),
                        int(account.get("draft_count", 0) or 0),
                        account.get("last_sync", now),
                        1 if account.get("owner_only", True) else 0,
                        account.get("created_at", now),
                    ),
                )

    def list_accounts(self, platform_id: Optional[str] = None) -> List[Dict[str, Any]]:
        query = "SELECT * FROM accounts"
        params: List[Any] = []
        if platform_id:
            query += " WHERE platform_id = ?"
            params.append(platform_id)
        query += " ORDER BY datetime(last_sync) DESC, datetime(created_at) DESC"
        with self._lock, self._connection() as connection:
            rows = connection.execute(query, params).fetchall()
        return [_row_to_dict(row) for row in rows]

    def create_account(
        self,
        account_id: str,
        platform_id: str,
        display_name: str,
        handle: str,
        now: str,
    ) -> Dict[str, Any]:
        with self._lock, self._connection() as connection:
            connection.execute(
                """
                INSERT INTO accounts (
                    id, platform_id, display_name, handle, status, draft_count, last_sync, owner_only, created_at
                ) VALUES (?, ?, ?, ?, 'connected', 0, ?, 1, ?)
                """,
                (account_id, platform_id, display_name, handle, now, now),
            )
        return {
            "id": account_id,
            "platform_id": platform_id,
            "display_name": display_name,
            "handle": handle,
            "status": "connected",
            "draft_count": 0,
            "last_sync": now,
            "owner_only": True,
            "created_at": now,
        }

    def bump_account_draft_count(self, account_id: str, now: str, amount: int = 1) -> None:
        with self._lock, self._connection() as connection:
            connection.execute(
                """
                UPDATE accounts
                SET draft_count = draft_count + ?, last_sync = ?
                WHERE id = ?
                """,
                (amount, now, account_id),
            )

    def add_cart_item(self, item: Dict[str, Any], now: str) -> None:
        with self._lock, self._connection() as connection:
            connection.execute(
                """
                INSERT INTO cart_items (item_id, payload_json, created_at)
                VALUES (?, ?, ?)
                ON CONFLICT(item_id) DO UPDATE SET
                    payload_json = excluded.payload_json,
                    created_at = excluded.created_at
                """,
                (item["id"], _dumps(item), now),
            )

    def list_cart_items(self) -> List[Dict[str, Any]]:
        with self._lock, self._connection() as connection:
            rows = connection.execute(
                "SELECT payload_json FROM cart_items ORDER BY datetime(created_at) ASC"
            ).fetchall()
        return [_loads(row["payload_json"], {}) for row in rows]

    def remove_cart_item(self, item_id: str) -> None:
        with self._lock, self._connection() as connection:
            connection.execute("DELETE FROM cart_items WHERE item_id = ?", (item_id,))

    def save_remix_job(self, job: Dict[str, Any]) -> None:
        with self._lock, self._connection() as connection:
            connection.execute(
                """
                INSERT INTO remix_jobs (job_id, payload_json, created_at, status)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(job_id) DO UPDATE SET
                    payload_json = excluded.payload_json,
                    created_at = excluded.created_at,
                    status = excluded.status
                """,
                (job["job_id"], _dumps(job), job["created_at"], job["status"]),
            )

    def get_remix_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        with self._lock, self._connection() as connection:
            row = connection.execute(
                "SELECT payload_json FROM remix_jobs WHERE job_id = ?",
                (job_id,),
            ).fetchone()
        return _loads(row["payload_json"], None) if row else None

    def list_remix_jobs(self) -> List[Dict[str, Any]]:
        with self._lock, self._connection() as connection:
            rows = connection.execute(
                "SELECT payload_json FROM remix_jobs ORDER BY datetime(created_at) DESC"
            ).fetchall()
        return [_loads(row["payload_json"], {}) for row in rows]

    def save_canvas_job(self, job: Dict[str, Any]) -> None:
        with self._lock, self._connection() as connection:
            connection.execute(
                """
                INSERT INTO canvas_jobs (job_id, payload_json, created_at, status)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(job_id) DO UPDATE SET
                    payload_json = excluded.payload_json,
                    created_at = excluded.created_at,
                    status = excluded.status
                """,
                (job["job_id"], _dumps(job), job["created_at"], job["status"]),
            )

    def get_canvas_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        with self._lock, self._connection() as connection:
            row = connection.execute(
                "SELECT payload_json FROM canvas_jobs WHERE job_id = ?",
                (job_id,),
            ).fetchone()
        return _loads(row["payload_json"], None) if row else None

    def list_canvas_jobs(self) -> List[Dict[str, Any]]:
        with self._lock, self._connection() as connection:
            rows = connection.execute(
                "SELECT payload_json FROM canvas_jobs ORDER BY datetime(created_at) DESC"
            ).fetchall()
        return [_loads(row["payload_json"], {}) for row in rows]

    def save_draft(self, draft: Dict[str, Any]) -> None:
        with self._lock, self._connection() as connection:
            connection.execute(
                """
                INSERT INTO drafts (id, payload_json, created_at, status, account_id, platform_id)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    payload_json = excluded.payload_json,
                    created_at = excluded.created_at,
                    status = excluded.status,
                    account_id = excluded.account_id,
                    platform_id = excluded.platform_id
                """,
                (
                    draft["id"],
                    _dumps(draft),
                    draft["created_at"],
                    draft["status"],
                    draft["account_id"],
                    draft["platform_id"],
                ),
            )

    def list_drafts(self) -> List[Dict[str, Any]]:
        with self._lock, self._connection() as connection:
            rows = connection.execute(
                "SELECT payload_json FROM drafts ORDER BY datetime(created_at) DESC"
            ).fetchall()
        return [_loads(row["payload_json"], {}) for row in rows]

    def save_comment_job(self, job: Dict[str, Any]) -> None:
        with self._lock, self._connection() as connection:
            connection.execute(
                """
                INSERT INTO comment_jobs (job_id, payload_json, created_at, status)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(job_id) DO UPDATE SET
                    payload_json = excluded.payload_json,
                    created_at = excluded.created_at,
                    status = excluded.status
                """,
                (job["job_id"], _dumps(job), job["created_at"], "completed"),
            )

    def list_comment_jobs(self) -> List[Dict[str, Any]]:
        with self._lock, self._connection() as connection:
            rows = connection.execute(
                "SELECT payload_json FROM comment_jobs ORDER BY datetime(created_at) DESC"
            ).fetchall()
        return [_loads(row["payload_json"], {}) for row in rows]

    def log_activity(self, action: str, payload: Dict[str, Any], timestamp: str) -> Dict[str, Any]:
        record = {"action": action, "payload": payload, "timestamp": timestamp}
        with self._lock, self._connection() as connection:
            connection.execute(
                "INSERT INTO activity_log (action, payload_json, timestamp) VALUES (?, ?, ?)",
                (action, _dumps(payload), timestamp),
            )
        return record

    def list_activity(self, limit: int = 25) -> List[Dict[str, Any]]:
        with self._lock, self._connection() as connection:
            rows = connection.execute(
                """
                SELECT action, payload_json, timestamp
                FROM activity_log
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        records = [
            {"action": row["action"], "payload": _loads(row["payload_json"], {}), "timestamp": row["timestamp"]}
            for row in rows
        ]
        return list(reversed(records))

    def overview_counts(self) -> Dict[str, Any]:
        with self._lock, self._connection() as connection:
            counts = {
                "connected_accounts": connection.execute("SELECT COUNT(*) AS count FROM accounts").fetchone()["count"],
                "draft_count": connection.execute("SELECT COUNT(*) AS count FROM drafts").fetchone()["count"],
                "remix_jobs": connection.execute("SELECT COUNT(*) AS count FROM remix_jobs").fetchone()["count"],
                "canvas_jobs": connection.execute("SELECT COUNT(*) AS count FROM canvas_jobs").fetchone()["count"],
                "cart_count": connection.execute("SELECT COUNT(*) AS count FROM cart_items").fetchone()["count"],
                "comment_jobs": connection.execute("SELECT COUNT(*) AS count FROM comment_jobs").fetchone()["count"],
                "activity_count": connection.execute("SELECT COUNT(*) AS count FROM activity_log").fetchone()["count"],
            }
        return counts

    def health(self) -> Dict[str, Any]:
        stats = self.overview_counts()
        stats.update(
            {
                "database_path": str(self.database_path),
                "database_exists": self.database_path.exists(),
                "database_size_bytes": self.database_path.stat().st_size if self.database_path.exists() else 0,
            }
        )
        return stats


@lru_cache(maxsize=1)
def get_repository() -> ContentRepository:
    return ContentRepository(get_settings().database_path)
