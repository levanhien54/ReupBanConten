"""
Database Layer — SQLite with Repository Pattern.

- Schema migrations tự động
- Repository pattern cho CRUD
- Connection pooling
- Type-safe queries
"""
from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Generator, Optional

from src.core.logging import get_logger

logger = get_logger(__name__)

# ──────────────────────────────────────────────
#  Schema
# ──────────────────────────────────────────────

SCHEMA_VERSION = 5

SCHEMA_SQL = """
-- Schema version tracking
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Kênh YouTube
CREATE TABLE IF NOT EXISTS channels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT NOT NULL UNIQUE,
    name TEXT,
    channel_id TEXT,
    subscriber_count INTEGER,
    video_count INTEGER,
    scanned_at TEXT DEFAULT (datetime('now')),
    created_at TEXT DEFAULT (datetime('now'))
);

-- Video gốc
CREATE TABLE IF NOT EXISTS videos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    channel_id INTEGER REFERENCES channels(id) ON DELETE SET NULL,
    video_id TEXT NOT NULL UNIQUE,
    url TEXT NOT NULL,
    title TEXT DEFAULT '',
    description TEXT DEFAULT '',
    duration REAL DEFAULT 0,
    view_count INTEGER DEFAULT 0,
    like_count INTEGER,
    upload_date TEXT,
    tags_json TEXT DEFAULT '[]',
    thumbnail_path TEXT,
    file_path TEXT,
    status TEXT DEFAULT 'pending',
    platform TEXT DEFAULT 'youtube',
    downloaded_at TEXT,
    usage_count INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

-- Transcripts
CREATE TABLE IF NOT EXISTS transcripts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id INTEGER NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
    language TEXT,
    language_probability REAL DEFAULT 0,
    full_text TEXT DEFAULT '',
    segments_json TEXT DEFAULT '[]',
    word_timestamps_json TEXT DEFAULT '[]',
    model_used TEXT,
    duration REAL DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now'))
);

-- Phân tích LLM
CREATE TABLE IF NOT EXISTS analyses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id INTEGER NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
    topics_json TEXT DEFAULT '[]',
    mood TEXT DEFAULT 'neutral',
    category TEXT DEFAULT 'other',
    summary TEXT DEFAULT '',
    highlights_json TEXT DEFAULT '[]',
    overall_energy REAL DEFAULT 0.5,
    viral_potential REAL DEFAULT 0.5,
    llm_provider TEXT,
    llm_model TEXT,
    raw_response TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

-- Clips đã cắt
CREATE TABLE IF NOT EXISTS clips (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id TEXT NOT NULL,
    file_path TEXT NOT NULL,
    start_time REAL NOT NULL,
    end_time REAL NOT NULL,
    duration REAL NOT NULL,
    tags_json TEXT DEFAULT '[]',
    mood TEXT DEFAULT 'neutral',
    energy_level TEXT DEFAULT 'medium',
    content_type TEXT DEFAULT 'unknown',
    highlight_score REAL DEFAULT 0.5,
    transcript_segment TEXT DEFAULT '',
    source_folder TEXT,
    usage_count INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now'))
);

-- Remix projects
CREATE TABLE IF NOT EXISTS remix_projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    strategy TEXT NOT NULL,
    script_json TEXT DEFAULT '{}',
    output_path TEXT,
    output_duration REAL,
    status TEXT DEFAULT 'draft',
    settings_json TEXT DEFAULT '{}',
    created_at TEXT DEFAULT (datetime('now')),
    completed_at TEXT
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_videos_status ON videos(status);
CREATE INDEX IF NOT EXISTS idx_videos_channel ON videos(channel_id);
CREATE INDEX IF NOT EXISTS idx_clips_video ON clips(video_id);
CREATE INDEX IF NOT EXISTS idx_clips_mood ON clips(mood);
CREATE INDEX IF NOT EXISTS idx_clips_energy ON clips(energy_level);
CREATE INDEX IF NOT EXISTS idx_clips_folder ON clips(source_folder);
"""

MIGRATIONS = {
    2: [
        "ALTER TABLE videos ADD COLUMN file_hash TEXT;",
        "CREATE INDEX idx_videos_hash ON videos(file_hash);"
    ],
    3: [
        "ALTER TABLE videos ADD COLUMN platform TEXT DEFAULT 'youtube';"
    ],
    4: [
        "ALTER TABLE clips ADD COLUMN usage_count INTEGER DEFAULT 0;"
    ],
    5: [
        "ALTER TABLE videos ADD COLUMN usage_count INTEGER DEFAULT 0;"
    ]
}


# ──────────────────────────────────────────────
#  Database Manager
# ──────────────────────────────────────────────

class Database:
    """Thread-safe SQLite database manager."""

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._local = threading.local()

        # Ensure directory exists
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

        # Initialize schema
        self._init_schema()
        logger.info(f"Database initialized: {db_path}")

    def _get_connection(self) -> sqlite3.Connection:
        """Get thread-local connection."""
        if not hasattr(self._local, "connection") or self._local.connection is None:
            conn = sqlite3.connect(self._db_path)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            self._local.connection = conn
        return self._local.connection

    @contextmanager
    def transaction(self) -> Generator[sqlite3.Connection, None, None]:
        """Context manager cho transaction."""
        conn = self._get_connection()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        """Execute single query."""
        conn = self._get_connection()
        return conn.execute(sql, params)

    def execute_many(self, sql: str, params_list: list[tuple]) -> None:
        """Execute batch query."""
        conn = self._get_connection()
        conn.executemany(sql, params_list)
        conn.commit()

    def fetch_one(self, sql: str, params: tuple = ()) -> Optional[dict]:
        """Fetch single row as dict."""
        cursor = self.execute(sql, params)
        row = cursor.fetchone()
        return dict(row) if row else None

    def fetch_all(self, sql: str, params: tuple = ()) -> list[dict]:
        """Fetch all rows as list of dicts."""
        cursor = self.execute(sql, params)
        return [dict(row) for row in cursor.fetchall()]

    def _init_schema(self) -> None:
        """Initialize database schema and apply migrations."""
        conn = self._get_connection()
        conn.executescript(SCHEMA_SQL)

        # Check/set schema version
        res = self.fetch_one("SELECT MAX(version) as v FROM schema_version")
        current_v = res["v"] if res and res["v"] is not None else 0

        if current_v < SCHEMA_VERSION:
            logger.info(f"Upgrading database from version {current_v} to {SCHEMA_VERSION}")
            for v in range(current_v + 1, SCHEMA_VERSION + 1):
                if v in MIGRATIONS:
                    for sql in MIGRATIONS[v]:
                        try:
                            conn.execute(sql)
                        except sqlite3.OperationalError as e:
                            # Tránh lỗi nếu column đã tồn tại (ví dụ rerun schema script)
                            if "duplicate column name" in str(e).lower():
                                continue
                            raise
            
            conn.execute(
                "INSERT OR REPLACE INTO schema_version (version) VALUES (?)",
                (SCHEMA_VERSION,),
            )
            conn.commit()

    def close(self) -> None:
        """Close thread-local connection."""
        if hasattr(self._local, "connection") and self._local.connection:
            self._local.connection.close()
            self._local.connection = None


# ──────────────────────────────────────────────
#  Repositories
# ──────────────────────────────────────────────

class VideoRepository:
    """CRUD operations cho videos."""

    def __init__(self, db: Database) -> None:
        self._db = db

    def upsert(self, video_id: str, **fields: Any) -> int:
        """Insert hoặc update video."""
        existing = self._db.fetch_one(
            "SELECT id FROM videos WHERE video_id = ?", (video_id,)
        )

        if existing:
            set_clause = ", ".join(f"{k} = ?" for k in fields.keys())
            self._db.execute(
                f"UPDATE videos SET {set_clause}, updated_at = datetime('now') "
                f"WHERE video_id = ?",
                (*fields.values(), video_id),
            )
            self._db._get_connection().commit()
            return existing["id"]
        else:
            cols = ["video_id"] + list(fields.keys())
            placeholders = ", ".join(["?"] * len(cols))
            col_names = ", ".join(cols)
            cursor = self._db.execute(
                f"INSERT INTO videos ({col_names}) VALUES ({placeholders})",
                (video_id, *fields.values()),
            )
            self._db._get_connection().commit()
            return cursor.lastrowid

    def get_by_video_id(self, video_id: str) -> Optional[dict]:
        return self._db.fetch_one(
            "SELECT * FROM videos WHERE video_id = ?", (video_id,)
        )

    def get_by_status(self, status: str) -> list[dict]:
        return self._db.fetch_all(
            "SELECT * FROM videos WHERE status = ?", (status,)
        )

    def update_status(self, video_id: str, status: str) -> None:
        self._db.execute(
            "UPDATE videos SET status = ?, updated_at = datetime('now') "
            "WHERE video_id = ?",
            (status, video_id),
        )
        self._db._get_connection().commit()

    def get_by_hash(self, file_hash: str) -> Optional[dict]:
        """Tìm video theo mã hash."""
        return self._db.fetch_one(
            "SELECT * FROM videos WHERE file_hash = ?", (file_hash,)
        )

    def increment_usage(self, video_id: str) -> None:
        """Tăng số lần sử dụng của video gốc (toàn cục)."""
        self._db.execute(
            "UPDATE videos SET usage_count = usage_count + 1 WHERE video_id = ?",
            (video_id,)
        )
        self._db._get_connection().commit()

    def get_usage_count(self, video_id: str) -> int:
        res = self._db.fetch_one(
            "SELECT usage_count FROM videos WHERE video_id = ?", (video_id,)
        )
        return res["usage_count"] if res else 0

    def list_all(self, limit: int = 100) -> list[dict]:
        """Lấy tất cả videos."""
        return self._db.fetch_all(
            "SELECT * FROM videos ORDER BY created_at DESC LIMIT ?", (limit,)
        )


class ClipRepository:
    """CRUD operations cho clips."""

    def __init__(self, db: Database) -> None:
        self._db = db

    def insert(self, **fields: Any) -> int:
        cols = list(fields.keys())
        placeholders = ", ".join(["?"] * len(cols))
        col_names = ", ".join(cols)
        cursor = self._db.execute(
            f"INSERT INTO clips ({col_names}) VALUES ({placeholders})",
            tuple(fields.values()),
        )
        self._db._get_connection().commit()
        return cursor.lastrowid

    def get_by_video(self, video_id: str) -> list[dict]:
        return self._db.fetch_all(
            "SELECT * FROM clips WHERE video_id = ?", (video_id,)
        )

    def get_by_folder(self, folder: str) -> list[dict]:
        return self._db.fetch_all(
            "SELECT * FROM clips WHERE source_folder = ?", (folder,)
        )

    def get_by_mood(self, mood: str) -> list[dict]:
        return self._db.fetch_all(
            "SELECT * FROM clips WHERE mood = ?", (mood,)
        )

    def get_by_energy(self, energy: str) -> list[dict]:
        return self._db.fetch_all(
            "SELECT * FROM clips WHERE energy_level = ?", (energy,)
        )

    def list_all(self, limit: int = 500) -> list[dict]:
        return self._db.fetch_all(
            "SELECT * FROM clips ORDER BY created_at DESC LIMIT ?", (limit,)
        )

    def increment_usage(self, clip_id: int) -> None:
        """Tăng số lần sử dụng của clip."""
        self._db.execute(
            "UPDATE clips SET usage_count = usage_count + 1 WHERE id = ?",
            (clip_id,)
        )
        self._db._get_connection().commit()

    def get_usage_count(self, clip_id: int) -> int:
        res = self._db.fetch_one(
            "SELECT usage_count FROM clips WHERE id = ?", (clip_id,)
        )
        return res["usage_count"] if res else 0

# ──────────────────────────────────────────────
#  Singleton
# ──────────────────────────────────────────────

_db_instance: Optional[Any] = None


def get_database(db_path: Optional[str] = None) -> Any:
    """Get global database instance (SQLite or Postgres)."""
    global _db_instance
    if _db_instance is None:
        from src.core.config import get_config
        config = get_config()
        
        if config.database.provider == "postgres":
            from src.core.database_pg import PostgresDatabase
            # Convert DBConfig to dict for adapter
            pg_config = {
                "host": config.database.host,
                "port": config.database.port,
                "user": config.database.user,
                "password": config.database.password,
                "dbname": config.database.dbname
            }
            _db_instance = PostgresDatabase(pg_config)
            # Lưu ý: PostgresDatabase cần được await connect() ở đâu đó khởi đầu
        else:
            if db_path is None:
                db_path = config.database.path
            _db_instance = Database(db_path)
            
    return _db_instance
