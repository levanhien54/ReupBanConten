"""
PostgreSQL Database Layer — Async implementation using asyncpg.
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime
from typing import Any, Optional, List, Dict
import asyncpg
from src.core.logging import get_logger

logger = get_logger(__name__)

class PostgresDatabase:
    """Manager cho PostgreSQL database (Async)."""

    def __init__(self, config_dict: dict) -> None:
        self._config = config_dict
        self._pool: Optional[asyncpg.Pool] = None

    async def connect(self) -> None:
        """Khởi tạo connection pool."""
        if self._pool is None:
            try:
                self._pool = await asyncpg.create_pool(
                    host=self._config.get("host", "localhost"),
                    port=self._config.get("port", 5432),
                    user=self._config.get("user", "postgres"),
                    password=self._config.get("password", "postgres"),
                    database=self._config.get("dbname", "reup_ban_conten"),
                    min_size=1,
                    max_size=10
                )
                logger.info("Connected to PostgreSQL")
                await self._init_schema()
            except Exception as e:
                logger.error(f"Failed to connect to PostgreSQL: {e}")
                raise

    async def _init_schema(self) -> None:
        """Khởi tạo schema cho PostgreSQL."""
        queries = [
            """
            CREATE TABLE IF NOT EXISTS videos (
                id SERIAL PRIMARY KEY,
                video_id TEXT UNIQUE NOT NULL,
                url TEXT NOT NULL,
                title TEXT,
                file_hash TEXT UNIQUE,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS clips (
                id SERIAL PRIMARY KEY,
                video_id TEXT NOT NULL,
                file_path TEXT NOT NULL,
                start_time REAL NOT NULL,
                end_time REAL NOT NULL,
                duration REAL NOT NULL,
                content_text TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        ]
        async with self._pool.acquire() as conn:
            for q in queries:
                await conn.execute(q)
        logger.info("PostgreSQL schema initialized")

    # Repositories for Postgres
    async def upsert_video(self, video_id: str, **fields: Any):
        cols = ["video_id"] + list(fields.keys())
        vals = [video_id] + list(fields.values())
        placeholders = [f"${i+1}" for i in range(len(cols))]
        
        query = f"""
            INSERT INTO videos ({", ".join(cols)}) 
            VALUES ({", ".join(placeholders)})
            ON CONFLICT (video_id) DO UPDATE SET 
            {", ".join([f"{k} = EXCLUDED.{k}" for k in fields.keys()])}
        """
        await self.execute(query, *vals)

    async def execute(self, query: str, *args: Any) -> str:
        """Execute query không trả về kết quả."""
        async with self._pool.acquire() as conn:
            return await conn.execute(query, *args)

    async def fetch_one(self, query: str, *args: Any) -> Optional[dict]:
        """Fetch single row."""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(query, *args)
            return dict(row) if row else None

    async def fetch_all(self, query: str, *args: Any) -> list[dict]:
        """Fetch all rows."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query, *args)
            return [dict(r) for r in rows]

    async def close(self) -> None:
        """Đóng pool."""
        if self._pool:
            await self._pool.close()
            self._pool = None
