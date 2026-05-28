from __future__ import annotations

import json
import hashlib
import logging
from datetime import datetime, timezone
from typing import Sequence

import aiosqlite

from shared_memory.core.models import (
    MemoryItem, MemoryEdge, MemoryLayer, MemoryScope, MemoryStatus,
    SearchQuery, SearchResult, AccessLog, AsyncJob, JobType, JobStatus,
    EdgeRelation, MemoryStats,
)
from shared_memory.db.connection import get_connection

logger = logging.getLogger(__name__)


def _row_to_item(row: aiosqlite.Row | dict) -> MemoryItem:
    """Convert a DB row to MemoryItem with proper type handling."""
    return MemoryItem(
        id=row["id"],
        layer=MemoryLayer(row["layer"]),
        scope=MemoryScope(row.get("scope", "shared")),
        status=MemoryStatus(row.get("status", "active")),
        project=row.get("project", ""),
        title=row.get("title", ""),
        content=row["content"],
        summary=row.get("summary", ""),
        tags=json.loads(row.get("tags", "[]")),
        entities=json.loads(row.get("entities", "[]")),
        importance=float(row.get("importance", 0.5)),
        confidence=float(row.get("confidence", 0.7)),
        source_tool=row.get("source_tool", ""),
        source_session=row.get("source_session", ""),
        version=int(row.get("version", 1)),
        parent_id=row.get("parent_id"),
        content_hash=row.get("content_hash", ""),
        embedding_json=row.get("embedding_json"),
        created_at=datetime.fromisoformat(row["created_at"])
            if isinstance(row["created_at"], str) else row["created_at"],
        updated_at=datetime.fromisoformat(row["updated_at"])
            if isinstance(row["updated_at"], str) else row["updated_at"],
        last_accessed_at=datetime.fromisoformat(row["last_accessed_at"])
            if isinstance(row["last_accessed_at"], str) else row["last_accessed_at"],
        expires_at=datetime.fromisoformat(row["expires_at"])
            if row.get("expires_at") else None,
    )


def _compute_hash(content: str) -> str:
    return hashlib.sha256(content.encode()).hexdigest()[:16]


class MemoryRepository:
    """Repository pattern for all memory CRUD operations."""

    def __init__(self, conn: aiosqlite.Connection):
        self.conn = conn

    # ── CREATE ───────────────────────────────────────────

    async def insert(self, item: MemoryItem) -> MemoryItem:
        """Insert a new memory item. Returns the inserted item with generated ID."""
        if not item.id:
            import uuid
            item.id = uuid.uuid4().hex[:20]
        if not item.content_hash and item.content:
            item.content_hash = _compute_hash(item.content)

        now = datetime.now(timezone.utc).isoformat()
        item.created_at = datetime.fromisoformat(now)
        item.updated_at = datetime.fromisoformat(now)

        await self.conn.execute(
            """INSERT INTO memory_items
            (id, layer, scope, status, project, title, content, summary,
             tags, entities, importance, confidence, source_tool, source_session,
             version, parent_id, content_hash, embedding_json,
             created_at, updated_at, last_accessed_at, expires_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                item.id, item.layer.value, item.scope.value, item.status.value,
                item.project, item.title, item.content, item.summary,
                json.dumps(item.tags, ensure_ascii=False),
                json.dumps(item.entities, ensure_ascii=False),
                item.importance, item.confidence,
                item.source_tool, item.source_session,
                item.version, item.parent_id, item.content_hash,
                item.embedding_json,
                item.created_at.isoformat(), item.updated_at.isoformat(),
                item.last_accessed_at.isoformat(),
                item.expires_at.isoformat() if item.expires_at else None,
            ),
        )
        await self.conn.commit()
        logger.debug("Inserted memory %s (%s)", item.id, item.layer.value)
        return item

    async def insert_batch(self, items: list[MemoryItem]) -> list[str]:
        """Bulk insert memories."""
        ids = []
        for item in items:
            inserted = await self.insert(item)
            ids.append(inserted.id)
        return ids

    # ── READ ────────────────────────────────────────────

    async def get_by_id(self, memory_id: str) -> MemoryItem | None:
        cursor = await self.conn.execute(
            "SELECT * FROM memory_items WHERE id=?", (memory_id,)
        )
        row = await cursor.fetchone()
        if not row:
            return None
        # Update access log and timestamp
        await self._log_access(memory_id, "retrieve")
        await self.conn.execute(
            "UPDATE memory_items SET last_accessed_at=? WHERE id=?",
            (datetime.now(timezone.utc).isoformat(), memory_id),
        )
        await self.conn.commit()
        return _row_to_item(row)

    async def list(
        self,
        layer: MemoryLayer | None = None,
        project: str | None = None,
        status: MemoryStatus = MemoryStatus.ACTIVE,
        limit: int = 50,
        offset: int = 0,
    ) -> list[MemoryItem]:
        query = "SELECT * FROM memory_items WHERE status=?"
        params: list = [status.value]
        if layer:
            query += " AND layer=?"
            params.append(layer.value)
        if project:
            query += " AND project=?"
            params.append(project)
        query += " ORDER BY importance DESC, updated_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        cursor = await self.conn.execute(query, tuple(params))
        rows = await cursor.fetchall()
        return [_row_to_item(dict(r)) for r in rows]

    # ── UPDATE ──────────────────────────────────────────

    async def update(self, item: MemoryItem) -> MemoryItem:
        """Update an existing memory (increments version)."""
        if item.content:
            item.content_hash = _compute_hash(item.content)
        item.version += 1
        item.updated_at = datetime.now(timezone.utc)

        await self.conn.execute(
            """UPDATE memory_items SET
                layer=?, scope=?, status=?, project=?, title=?, content=?, summary=?,
                tags=?, entities=?, importance=?, confidence=?,
                source_tool=?, source_session=?,
                version=?, parent_id=?, content_hash=?, embedding_json=?,
                updated_at=?, last_accessed_at=?, expires_at=?
            WHERE id=?""",
            (
                item.layer.value, item.scope.value, item.status.value,
                item.project, item.title, item.content, item.summary,
                json.dumps(item.tags, ensure_ascii=False),
                json.dumps(item.entities, ensure_ascii=False),
                item.importance, item.confidence,
                item.source_tool, item.source_session,
                item.version, item.parent_id, item.content_hash,
                item.embedding_json,
                item.updated_at.isoformat(),
                item.last_accessed_at.isoformat(),
                item.expires_at.isoformat() if item.expires_at else None,
                item.id,
            ),
        )
        await self.conn.commit()
        await self._log_access(item.id, "update")
        return item

    async def update_embedding(self, memory_id: str, embedding_json: str) -> None:
        await self.conn.execute(
            "UPDATE memory_items SET embedding_json=? WHERE id=?",
            (embedding_json, memory_id),
        )
        await self.conn.commit()

    # ── DELETE / ARCHIVE ────────────────────────────────

    async def archive(self, memory_id: str) -> bool:
        cursor = await self.conn.execute(
            "UPDATE memory_items SET status='archived', updated_at=? WHERE id=?",
            (datetime.now(timezone.utc).isoformat(), memory_id),
        )
        await self.conn.commit()
        return cursor.rowcount > 0

    async def delete(self, memory_id: str) -> bool:
        cursor = await self.conn.execute(
            "DELETE FROM memory_items WHERE id=?", (memory_id,)
        )
        await self.conn.commit()
        return cursor.rowcount > 0

    # ── SEARCH ──────────────────────────────────────────

    async def search_fts(self, query_str: str, limit: int = 20) -> list[tuple[str, float]]:
        """FTS5 full-text search. Returns (memory_id, score) tuples."""
        try:
            cursor = await self.conn.execute(
                """SELECT rowid, rank FROM memory_fts
                   WHERE memory_fts MATCH ?
                   ORDER BY rank LIMIT ?""",
                (query_str, limit),
            )
            rows = await cursor.fetchall()
            results: list[tuple[str, float]] = []
            for r in rows:
                # Get the memory_id from the rowid
                rcursor = await self.conn.execute(
                    "SELECT id FROM memory_items WHERE rowid=?", (r["rowid"],)
                )
                idrow = await rcursor.fetchone()
                if idrow:
                    # Normalize FTS5 rank to 0-1
                    rank = float(r["rank"])
                    score = 1.0 / (1.0 + abs(rank)) if rank != 0 else 0.5
                    results.append((idrow["id"], score))
            return results
        except Exception as e:
            logger.warning("FTS search error: %s", e)
            return []

    async def search_by_tags(self, tags: list[str], limit: int = 20) -> list[str]:
        """Find memories matching any of the given tags using LIKE."""
        ids: set[str] = set()
        for tag in tags:
            cursor = await self.conn.execute(
                "SELECT id FROM memory_items WHERE tags LIKE ? AND status='active' LIMIT ?",
                (f'%"{tag}"%', limit),
            )
            rows = await cursor.fetchall()
            ids.update(r["id"] for r in rows)
        return list(ids)[:limit]

    async def search_by_entities(self, entities: list[str], limit: int = 20) -> list[str]:
        """Find memories matching entities."""
        ids: set[str] = set()
        for ent in entities:
            cursor = await self.conn.execute(
                "SELECT id FROM memory_items WHERE entities LIKE ? AND status='active' LIMIT ?",
                (f'%"{ent}"%', limit),
            )
            rows = await cursor.fetchall()
            ids.update(r["id"] for r in rows)
        return list(ids)[:limit]

    # ── EDGES ───────────────────────────────────────────

    async def insert_edge(self, edge: MemoryEdge) -> MemoryEdge:
        if not edge.id:
            import uuid
            edge.id = uuid.uuid4().hex[:16]
        await self.conn.execute(
            """INSERT INTO memory_edges (id, source_id, target_id, relation, weight, created_at)
               VALUES (?,?,?,?,?,?)""",
            (edge.id, edge.source_id, edge.target_id,
             edge.relation.value, edge.weight,
             edge.created_at.isoformat()),
        )
        await self.conn.commit()
        return edge

    async def get_edges(self, memory_id: str) -> list[MemoryEdge]:
        cursor = await self.conn.execute(
            "SELECT * FROM memory_edges WHERE source_id=? OR target_id=?",
            (memory_id, memory_id),
        )
        rows = await cursor.fetchall()
        return [
            MemoryEdge(
                id=r["id"], source_id=r["source_id"], target_id=r["target_id"],
                relation=EdgeRelation(r["relation"]), weight=r["weight"],
                created_at=datetime.fromisoformat(r["created_at"]),
            )
            for r in rows
        ]

    # ── ACCESS LOG ──────────────────────────────────────

    async def _log_access(self, memory_id: str, access_type: str) -> None:
        import uuid
        await self.conn.execute(
            "INSERT INTO memory_access_log (id, memory_id, access_type, accessed_at) VALUES (?,?,?,?)",
            (uuid.uuid4().hex[:16], memory_id, access_type,
             datetime.now(timezone.utc).isoformat()),
        )

    async def get_access_frequency(self, memory_id: str, days: int = 30) -> float:
        cursor = await self.conn.execute(
            """SELECT COUNT(*) as cnt FROM memory_access_log
               WHERE memory_id=? AND access_type='retrieve'
               AND accessed_at > datetime('now', ?)""",
            (memory_id, f'-{days} days'),
        )
        row = await cursor.fetchone()
        return float(row["cnt"]) if row else 0.0

    # ── JOB QUEUE ───────────────────────────────────────

    async def enqueue_job(self, job: AsyncJob) -> AsyncJob:
        if not job.id:
            import uuid
            job.id = uuid.uuid4().hex[:16]
        await self.conn.execute(
            """INSERT INTO memory_jobs
               (id, memory_id, job_type, status, payload, max_retries, created_at)
               VALUES (?,?,?,?,?,?,?)""",
            (job.id, job.memory_id, job.job_type.value, job.status.value,
             job.payload, job.max_retries, job.created_at.isoformat()),
        )
        await self.conn.commit()
        return job

    async def dequeue_job(self) -> AsyncJob | None:
        async with self.conn.execute(
            """SELECT * FROM memory_jobs
               WHERE status='pending'
               ORDER BY created_at ASC LIMIT 1"""
        ) as cursor:
            row = await cursor.fetchone()
        if not row:
            return None
        await self.conn.execute(
            "UPDATE memory_jobs SET status='processing', started_at=? WHERE id=?",
            (datetime.now(timezone.utc).isoformat(), row["id"]),
        )
        await self.conn.commit()
        return AsyncJob(
            id=row["id"], memory_id=row["memory_id"],
            job_type=JobType(row["job_type"]),
            status=JobStatus("processing"),
            payload=row.get("payload", ""),
            retry_count=row.get("retry_count", 0),
            max_retries=row.get("max_retries", 3),
            created_at=datetime.fromisoformat(row["created_at"]),
            started_at=datetime.now(timezone.utc),
        )

    async def complete_job(self, job_id: str) -> None:
        await self.conn.execute(
            "UPDATE memory_jobs SET status='completed', completed_at=? WHERE id=?",
            (datetime.now(timezone.utc).isoformat(), job_id),
        )
        await self.conn.commit()

    async def fail_job(self, job_id: str, error: str) -> None:
        row = await (await self.conn.execute(
            "SELECT retry_count, max_retries FROM memory_jobs WHERE id=?", (job_id,)
        )).fetchone()
        if row and row["retry_count"] < row["max_retries"]:
            await self.conn.execute(
                "UPDATE memory_jobs SET status='pending', error_msg=?, retry_count=retry_count+1 WHERE id=?",
                (error, job_id),
            )
        else:
            await self.conn.execute(
                "UPDATE memory_jobs SET status='failed', error_msg=?, completed_at=? WHERE id=?",
                (error, datetime.now(timezone.utc).isoformat(), job_id),
            )
        await self.conn.commit()

    async def pending_jobs_count(self) -> int:
        cursor = await self.conn.execute(
            "SELECT COUNT(*) as cnt FROM memory_jobs WHERE status='pending'"
        )
        row = await cursor.fetchone()
        return row["cnt"] if row else 0

    # ── STATS ───────────────────────────────────────────

    async def stats(self) -> MemoryStats:
        cursor = await self.conn.execute("SELECT COUNT(*) as cnt FROM memory_items")
        row = await cursor.fetchone()
        total = row["cnt"] if row else 0

        cursor = await self.conn.execute(
            "SELECT layer, COUNT(*) as cnt FROM memory_items GROUP BY layer"
        )
        rows = await cursor.fetchall()
        by_layer = {r["layer"]: r["cnt"] for r in rows}

        cursor = await self.conn.execute(
            "SELECT status, COUNT(*) as cnt FROM memory_items GROUP BY status"
        )
        rows = await cursor.fetchall()
        by_status = {r["status"]: r["cnt"] for r in rows}

        cursor = await self.conn.execute(
            "SELECT AVG(importance) as avg FROM memory_items WHERE status='active'"
        )
        row = await cursor.fetchone()
        avg_imp = float(row["avg"]) if row and row["avg"] else 0.0

        pending = await self.pending_jobs_count()

        import os
        db_size = os.path.getsize(self.conn._connection.db_filename) if self.conn._connection else 0  # noqa

        return MemoryStats(
            total=total, by_layer=by_layer, by_status=by_status,
            avg_importance=avg_imp, db_size_bytes=db_size,
            job_queue_size=pending,
        )

    # ── DEDUP ───────────────────────────────────────────

    async def find_duplicate(self, content_hash: str, project: str = "") -> MemoryItem | None:
        cursor = await self.conn.execute(
            "SELECT * FROM memory_items WHERE content_hash=? AND project=? AND status='active'",
            (content_hash, project),
        )
        row = await cursor.fetchone()
        if not row:
            return None
        return _row_to_item(row)
