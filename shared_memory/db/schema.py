from __future__ import annotations

import logging

import aiosqlite

logger = logging.getLogger(__name__)

SCHEMA_SQL = """
-- Core memory table (spec section 4: memory_items)
CREATE TABLE IF NOT EXISTS memory_items (
    id              TEXT PRIMARY KEY,
    layer           TEXT NOT NULL CHECK(layer IN ('profile','project','task','episodic','artifact')),
    scope           TEXT NOT NULL DEFAULT 'shared' CHECK(scope IN ('private','shared','global')),
    status          TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','archived','consolidated','expired')),
    project         TEXT NOT NULL DEFAULT '',
    title           TEXT NOT NULL DEFAULT '',
    content         TEXT NOT NULL,
    summary         TEXT NOT NULL DEFAULT '',
    tags            TEXT NOT NULL DEFAULT '[]',
    entities        TEXT NOT NULL DEFAULT '[]',
    importance      REAL NOT NULL DEFAULT 0.5,
    confidence      REAL NOT NULL DEFAULT 0.7,
    source_tool     TEXT NOT NULL DEFAULT '',
    source_session  TEXT NOT NULL DEFAULT '',
    version         INTEGER NOT NULL DEFAULT 1,
    parent_id       TEXT,
    content_hash    TEXT NOT NULL DEFAULT '',
    embedding_json  TEXT,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL,
    last_accessed_at TEXT NOT NULL,
    expires_at      TEXT
);

-- FTS5 full-text search index
CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(
    title,
    content,
    summary,
    tags,
    content='memory_items',
    content_rowid='rowid'
);

-- Triggers to keep FTS in sync
CREATE TRIGGER IF NOT EXISTS memory_items_ai AFTER INSERT ON memory_items BEGIN
    INSERT INTO memory_fts(rowid, title, content, summary, tags)
    VALUES (new.rowid, new.title, new.content, new.summary, new.tags);
END;

CREATE TRIGGER IF NOT EXISTS memory_items_ad AFTER DELETE ON memory_items BEGIN
    INSERT INTO memory_fts(memory_fts, rowid, title, content, summary, tags)
    VALUES ('delete', old.rowid, old.title, old.content, old.summary, old.tags);
END;

CREATE TRIGGER IF NOT EXISTS memory_items_au AFTER UPDATE ON memory_items BEGIN
    INSERT INTO memory_fts(memory_fts, rowid, title, content, summary, tags)
    VALUES ('delete', old.rowid, old.title, old.content, old.summary, old.tags);
    INSERT INTO memory_fts(rowid, title, content, summary, tags)
    VALUES (new.rowid, new.title, new.content, new.summary, new.tags);
END;

-- Graph edges (spec section 4: memory_edges)
CREATE TABLE IF NOT EXISTS memory_edges (
    id          TEXT PRIMARY KEY,
    source_id   TEXT NOT NULL REFERENCES memory_items(id) ON DELETE CASCADE,
    target_id   TEXT NOT NULL REFERENCES memory_items(id) ON DELETE CASCADE,
    relation    TEXT NOT NULL CHECK(relation IN ('related_to','caused_by','depends_on','supersedes')),
    weight      REAL NOT NULL DEFAULT 1.0,
    created_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_edges_source ON memory_edges(source_id);
CREATE INDEX IF NOT EXISTS idx_edges_target ON memory_edges(target_id);

-- Access log (spec section 4: memory_access_log)
CREATE TABLE IF NOT EXISTS memory_access_log (
    id          TEXT PRIMARY KEY,
    memory_id   TEXT NOT NULL REFERENCES memory_items(id) ON DELETE CASCADE,
    access_type TEXT NOT NULL CHECK(access_type IN ('retrieve','inject','update')),
    source_tool TEXT NOT NULL DEFAULT '',
    accessed_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_access_log_memory ON memory_access_log(memory_id);
CREATE INDEX IF NOT EXISTS idx_access_log_time ON memory_access_log(accessed_at);

-- Async job queue (spec section 4: memory_jobs)
CREATE TABLE IF NOT EXISTS memory_jobs (
    id          TEXT PRIMARY KEY,
    memory_id   TEXT NOT NULL REFERENCES memory_items(id) ON DELETE CASCADE,
    job_type    TEXT NOT NULL CHECK(job_type IN ('embedding','summarize','deduplicate','extract_entities','decay','consolidate')),
    status      TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','processing','completed','failed')),
    payload     TEXT NOT NULL DEFAULT '',
    error_msg   TEXT NOT NULL DEFAULT '',
    retry_count INTEGER NOT NULL DEFAULT 0,
    max_retries INTEGER NOT NULL DEFAULT 3,
    created_at  TEXT NOT NULL,
    started_at  TEXT,
    completed_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON memory_jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_type ON memory_jobs(job_type);

-- Indices for common queries
CREATE INDEX IF NOT EXISTS idx_items_layer ON memory_items(layer);
CREATE INDEX IF NOT EXISTS idx_items_project ON memory_items(project);
CREATE INDEX IF NOT EXISTS idx_items_status ON memory_items(status);
CREATE INDEX IF NOT EXISTS idx_items_importance ON memory_items(importance);
CREATE INDEX IF NOT EXISTS idx_items_updated ON memory_items(updated_at);
"""


async def initialize_schema(conn: aiosqlite.Connection) -> None:
    """Create all tables and indices."""
    await conn.executescript(SCHEMA_SQL)
    await conn.commit()
    logger.info("Schema initialized successfully")


async def get_db_stats(conn: aiosqlite.Connection) -> dict:
    """Return database statistics."""
    cursor = await conn.execute("SELECT COUNT(*) as cnt FROM memory_items")
    row = await cursor.fetchone()
    total = row["cnt"] if row else 0

    cursor = await conn.execute(
        "SELECT layer, COUNT(*) as cnt FROM memory_items GROUP BY layer"
    )
    rows = await cursor.fetchall()
    by_layer = {r["layer"]: r["cnt"] for r in rows}

    cursor = await conn.execute(
        "SELECT COUNT(*) as cnt FROM memory_jobs WHERE status='pending'"
    )
    row = await cursor.fetchone()
    pending_jobs = row["cnt"] if row else 0

    import os
    db_size = os.path.getsize(conn._connection.db_filename) if conn._connection else 0  # noqa

    return {
        "total": total,
        "by_layer": by_layer,
        "pending_jobs": pending_jobs,
        "db_size_bytes": db_size,
    }
