from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from shared_memory.core.models import AsyncJob, JobType, JobStatus
from shared_memory.db.repository import MemoryRepository

logger = logging.getLogger(__name__)


class JobQueue:
    """Async job queue — spec section 11. Processes jobs without blocking main flow."""

    def __init__(self, repo: MemoryRepository, poll_interval: float = 1.0, max_concurrent: int = 4):
        self.repo = repo
        self.poll_interval = poll_interval
        self.max_concurrent = max_concurrent
        self._running = False
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._handlers: dict[JobType, callable] = {}

    def register_handler(self, job_type: JobType, handler):
        """Register an async handler for a job type."""
        self._handlers[job_type] = handler

    async def start(self) -> None:
        """Start polling for jobs."""
        self._running = True
        logger.info("Job queue started (poll=%.1fs, max_concurrent=%d)",
                     self.poll_interval, self.max_concurrent)
        while self._running:
            try:
                job = await self.repo.dequeue_job()
                if job:
                    asyncio.create_task(self._process_job(job))
                else:
                    await asyncio.sleep(self.poll_interval)
            except Exception as e:
                logger.error("Job queue poll error: %s", e)
                await asyncio.sleep(self.poll_interval)

    async def stop(self) -> None:
        self._running = False
        logger.info("Job queue stopped")

    async def _process_job(self, job: AsyncJob) -> None:
        async with self._semaphore:
            handler = self._handlers.get(job.job_type)
            if not handler:
                logger.warning("No handler for job type %s", job.job_type)
                await self.repo.complete_job(job.id)
                return
            try:
                await handler(job)
                await self.repo.complete_job(job.id)
                logger.debug("Job %s completed (%s)", job.id, job.job_type.value)
            except Exception as e:
                logger.warning("Job %s failed: %s", job.id, e)
                await self.repo.fail_job(job.id, str(e))


class JobQueueFactory:
    """Creates a JobQueue with default handlers for embedding, summary, dedup, decay."""

    @staticmethod
    def create(repo: MemoryRepository, embed_handler=None,
               summarize_handler=None, dedup_handler=None,
               decay_handler=None) -> JobQueue:
        queue = JobQueue(repo)

        if embed_handler:
            queue.register_handler(JobType.EMBEDDING, embed_handler)
        if summarize_handler:
            queue.register_handler(JobType.SUMMARIZE, summarize_handler)
        if dedup_handler:
            queue.register_handler(JobType.DEDUPLICATE, dedup_handler)
        if decay_handler:
            queue.register_handler(JobType.DECAY, decay_handler)
        # Default: mark unknown job types as completed
        queue.register_handler(JobType.EXTRACT_ENTITIES, lambda j: None)
        queue.register_handler(JobType.CONSOLIDATE, lambda j: None)

        return queue
