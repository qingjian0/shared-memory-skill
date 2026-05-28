from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from shared_memory.core.models import (
    MemoryLayer, MemoryScope, MemoryStatus, MemoryItem,
    SearchQuery, SearchResult, AsyncJob, JobType, JobStatus,
    MemoryEdge, EdgeRelation, MemoryStats,
)
from shared_memory.core.config import MemoryConfig
from shared_memory.db.connection import get_connection, close_connection
from shared_memory.db.schema import initialize_schema
from shared_memory.db.repository import MemoryRepository
from shared_memory.security.sanitizer import sanitize
from shared_memory.retrieval.searcher import HybridSearcher
from shared_memory.retrieval.context_builder import ContextBuilder
from shared_memory.lifecycle.decay import MemoryDecay
from shared_memory.workers.queue import JobQueue, JobQueueFactory
from shared_memory.workers.embedding_worker import embedding_handler_factory

logger = logging.getLogger(__name__)


class SharedMemory:
    """Main API for the shared memory system. Thread-safe, async-first."""

    def __init__(self, config: MemoryConfig | None = None):
        self.config = config or MemoryConfig()
        self._conn = None
        self._repo: MemoryRepository | None = None
        self._searcher: HybridSearcher | None = None
        self._context_builder: ContextBuilder | None = None
        self._decay: MemoryDecay | None = None
        self._job_queue: JobQueue | None = None
        self._task: asyncio.Task | None = None

    async def initialize(self) -> None:
        """Initialize the shared memory system: DB, schema, workers."""
        self._conn = await get_connection(self.config)
        await initialize_schema(self._conn)
        self._repo = MemoryRepository(self._conn)
        self._searcher = HybridSearcher(self._repo, self.config)
        self._context_builder = ContextBuilder(self._repo, self.config)
        self._decay = MemoryDecay(self.config)

        # Setup async worker
        embed_handler = await embedding_handler_factory(self._repo)
        self._job_queue = JobQueueFactory.create(
            self._repo,
            embed_handler=embed_handler,
        )
        self._task = asyncio.create_task(self._job_queue.start())
        logger.info("SharedMemory system initialized")

    async def shutdown(self) -> None:
        """Graceful shutdown."""
        if self._job_queue:
            await self._job_queue.stop()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        await close_connection()

    # ── Core API ───────────────────────────────────────

    async def remember(
        self,
        content: str,
        *,
        layer: MemoryLayer = MemoryLayer.EPISODIC,
        scope: MemoryScope = MemoryScope.SHARED,
        project: str = "",
        title: str = "",
        tags: list[str] | None = None,
        entities: list[str] | None = None,
        importance: float = 0.5,
        confidence: float = 0.7,
        source_tool: str = "",
        source_session: str = "",
    ) -> str:
        """Write a new memory. Auto-sanitizes and enqueues embedding."""

        # Security: sanitize content
        clean_content = sanitize(content)
        if not clean_content.strip():
            return ""

        item = MemoryItem(
            layer=layer,
            scope=scope,
            project=project,
            title=title or clean_content[:80],
            content=clean_content,
            tags=tags or [],
            entities=entities or [],
            importance=importance,
            confidence=confidence,
            source_tool=source_tool,
            source_session=source_session,
        )

        # Insert
        inserted = await self._repo.insert(item)

        # Enqueue async embedding job
        await self._repo.enqueue_job(AsyncJob(
            memory_id=inserted.id,
            job_type=JobType.EMBEDDING,
        ))

        logger.info("Remembered: %s (%s)", inserted.id, layer.value)
        return inserted.id

    async def recall(
        self,
        query: str = "",
        *,
        top_k: int = 10,
        layers: list[MemoryLayer] | None = None,
        project: str = "",
        tags: list[str] | None = None,
        entities: list[str] | None = None,
        min_importance: float = 0.0,
    ) -> list[SearchResult]:
        """Search memories using hybrid retrieval."""
        sq = SearchQuery(
            query=query,
            layers=layers,
            projects=[project] if project else None,
            tags=tags,
            entities=entities,
            top_k=top_k,
            min_importance=min_importance,
        )
        return await self._searcher.search(sq)

    async def forget(self, memory_id: str) -> bool:
        """Archive a memory (soft delete)."""
        return await self._repo.archive(memory_id)

    async def get(self, memory_id: str) -> MemoryItem | None:
        return await self._repo.get_by_id(memory_id)

    async def get_context(
        self, query: str = "", project: str = "", max_tokens: int | None = None
    ) -> str:
        """Get token-budgeted context for AI prompt injection."""
        return await self._context_builder.build_context(
            query=query, project=project, max_tokens=max_tokens,
        )

    async def get_agents_content(self) -> str:
        """Get compact content suitable for AGENTS.md."""
        return await self._context_builder.build_agents_content()

    async def status(self) -> MemoryStats:
        return await self._repo.stats()

    async def list_memories(
        self,
        layer: MemoryLayer | None = None,
        project: str | None = None,
        limit: int = 50,
    ) -> list[MemoryItem]:
        return await self._repo.list(layer=layer, project=project, limit=limit)

    async def decay_all(self) -> int:
        """Run decay check on active memories. Returns count of archived items."""
        count = 0
        items = await self._repo.list(limit=1000)
        for item in items:
            if self._decay.should_archive(item):
                await self._repo.archive(item.id)
                count += 1
        return count

    async def deduplicate(self, item: MemoryItem) -> MemoryItem | None:
        """Check if similar memory exists and return it."""
        return await self._repo.find_duplicate(item.content_hash, item.project)

    async def link(
        self,
        source_id: str,
        target_id: str,
        relation: EdgeRelation = EdgeRelation.RELATED_TO,
    ) -> MemoryEdge:
        edge = MemoryEdge(
            source_id=source_id,
            target_id=target_id,
            relation=relation,
        )
        return await self._repo.insert_edge(edge)

    async def get_links(self, memory_id: str) -> list[MemoryEdge]:
        return await self._repo.get_edges(memory_id)


# Global singleton
_global_sm: SharedMemory | None = None
_global_lock = asyncio.Lock()


async def get_shared_memory(config: MemoryConfig | None = None) -> SharedMemory:
    """Get or create the global shared memory singleton."""
    global _global_sm
    if _global_sm is not None:
        return _global_sm
    async with _global_lock:
        if _global_sm is not None:
            return _global_sm
        _global_sm = SharedMemory(config)
        await _global_sm.initialize()
        return _global_sm
