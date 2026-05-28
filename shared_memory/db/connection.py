from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path

import aiosqlite

from shared_memory.core.config import MemoryConfig

logger = logging.getLogger(__name__)

_db_connection: aiosqlite.Connection | None = None
_lock = asyncio.Lock()


async def get_connection(config: MemoryConfig | None = None) -> aiosqlite.Connection:
    """Get or create the singleton database connection."""
    global _db_connection
    if _db_connection is not None:
        return _db_connection

    async with _lock:
        if _db_connection is not None:
            return _db_connection

        cfg = config or MemoryConfig()
        db_dir = Path(cfg.db_dir)
        db_dir.mkdir(parents=True, exist_ok=True)

        db_path = cfg.db_path or str(db_dir / "memory.db")
        _db_connection = await aiosqlite.connect(db_path)
        _db_connection.row_factory = aiosqlite.Row
        await _db_connection.execute("PRAGMA journal_mode=WAL")
        await _db_connection.execute("PRAGMA foreign_keys=ON")
        await _db_connection.execute("PRAGMA busy_timeout=5000")
        logger.info("Connected to %s", db_path)
        return _db_connection


async def close_connection() -> None:
    global _db_connection
    if _db_connection:
        await _db_connection.close()
        _db_connection = None
        logger.info("Database connection closed")
