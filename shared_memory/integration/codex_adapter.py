"""Codex CLI integration adapter — spec section 12.
Generates AGENTS.md-compatible prompts and handles tool-call protocol."""

from __future__ import annotations

import json
from shared_memory.api import SharedMemory, get_shared_memory
from shared_memory.core.models import MemoryLayer, SearchQuery

# Minimal AGENTS.md template for Codex
AGENTS_MD_TEMPLATE = '''# Shared Memory Rules
#
# 这些规则由共享记忆系统自动生成，跨 Codex/Claude/Hermes 共享。
# 禁止手动编辑，运行: sm agents 更新。
#

{content}'''  # noqa: E501


class CodexAdapter:
    """Adapter for Codex CLI integration."""

    def __init__(self, sm: SharedMemory):
        self.sm = sm

    async def query_memories(self, query: str, top_k: int = 10) -> str:
        """Codex calls this before executing tasks. Returns context string."""
        results = await self.sm.recall(query=query, top_k=top_k)
        if not results:
            return "[No relevant memories found]"

        lines = ["[Relevant Shared Memories]"]
        for r in results[:top_k]:
            lines.append(f"- [{r.item.layer.value}] {r.item.content[:150]}")

        return "\n".join(lines)

    async def submit_memory(self, content: str, layer: str = "episodic",
                            project: str = "", importance: float = 0.6) -> dict:
        """Codex calls this to save learnings."""
        memory_id = await self.sm.remember(
            content=content,
            layer=MemoryLayer(layer),
            project=project,
            importance=importance,
            source_tool="codex",
        )
        return {"id": memory_id, "status": "ok"}

    async def get_agents_md(self) -> str:
        """Generate AGENTS.md content."""
        content = await self.sm.get_agents_content()
        return AGENTS_MD_TEMPLATE.format(content=content)

    async def search_tool(self, params: dict) -> str:
        """Handle Codex tool-call: sm.search."""
        q = SearchQuery(
            query=params.get("query", ""),
            top_k=params.get("top_k", 10),
            layers=[MemoryLayer(l) for l in params.get("layers", [])]
                if params.get("layers") else None,
            projects=params.get("projects"),
            tags=params.get("tags"),
        )
        results = await self.sm.recall(
            query=q.query, top_k=q.top_k,
            layers=q.layers, project="",
            tags=q.tags,
        )
        return json.dumps([
            {"id": r.item.id, "content": r.item.content, "layer": r.item.layer.value,
             "score": r.score} for r in results
        ], ensure_ascii=False)

    async def remember_tool(self, params: dict) -> str:
        """Handle Codex tool-call: sm.remember."""
        memory_id = await self.sm.remember(
            content=params["content"],
            layer=MemoryLayer(params.get("layer", "episodic")),
            project=params.get("project", ""),
            importance=params.get("importance", 0.6),
            tags=params.get("tags"),
            source_tool="codex",
        )
        return json.dumps({"id": memory_id})
