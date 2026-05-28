from __future__ import annotations

import asyncio
import json
import logging
from typing import Callable

from shared_memory.core.models import AsyncJob
from shared_memory.db.repository import MemoryRepository

logger = logging.getLogger(__name__)


async def embedding_handler_factory(repo: MemoryRepository):
    """Factory that creates an embedding handler. Uses ChromaDB if available,
    falls back to a hash-based pseudo-embedding."""

    # Try to import ChromaDB
    embed_fn: Callable[[str], list[float]] | None = None
    try:
        from chromadb.api.client import Client
        import chromadb.utils.embedding_functions as ef

        _ef = ef.DefaultEmbeddingFunction()
        if _ef:
            def _chroma_embed(text: str) -> list[float]:
                result = _ef([text])
                return result[0] if result else []
            embed_fn = _chroma_embed
            logger.info("Using ChromaDB DefaultEmbeddingFunction")
    except Exception:
        pass

    if embed_fn is None:
        try:
            import numpy as np
            def _hash_embed(text: str) -> list[float]:
                rng = np.random.RandomState(hash(text) & 0xFFFFFFFF)
                return rng.randn(384).tolist()
            embed_fn = _hash_embed
            logger.warning("Using deterministic hash-based embeddings (384d)")
        except ImportError:
            pass

    # If NO embedding available, store empty
    if embed_fn is None:
        async def _noop_handler(job: AsyncJob) -> None:
            pass
        return _noop_handler

    async def handler(job: AsyncJob) -> None:
        item = await repo.get_by_id(job.memory_id)
        if item is None:
            logger.warning("Memory %s not found for embedding", job.memory_id)
            return
        try:
            embedding = await asyncio.to_thread(embed_fn, item.content)
            await repo.update_embedding(job.memory_id, json.dumps(embedding))
            logger.debug("Embedding done for %s", job.memory_id)
        except Exception as e:
            logger.error("Embedding failed for %s: %s", job.memory_id, e)
            raise

    return handler
