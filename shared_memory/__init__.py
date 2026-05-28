"""Shared Memory System — 工业级、本地优先、多AI工具共享的长期记忆系统。

Quick start:
    from shared_memory import SharedMemory, get_shared_memory, MemoryLayer

    sm = await get_shared_memory()
    await sm.remember("用户偏好 snake_case", layer=MemoryLayer.PROFILE)
    results = await sm.recall("命名风格", top_k=5)
    ctx = await sm.get_context(project="aiapps")
"""

from shared_memory.api import SharedMemory, get_shared_memory
from shared_memory.core.models import (
    MemoryLayer, MemoryScope, MemoryStatus, EdgeRelation,
    MemoryItem, SearchQuery, SearchResult, MemoryStats,
)
from shared_memory.core.config import MemoryConfig
