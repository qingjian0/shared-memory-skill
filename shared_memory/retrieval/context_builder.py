from __future__ import annotations

from shared_memory.core.models import MemoryLayer, SearchQuery
from shared_memory.core.config import MemoryConfig
from shared_memory.db.repository import MemoryRepository
from shared_memory.retrieval.searcher import HybridSearcher
from shared_memory.lifecycle.compressor import ContextCompressor


class ContextBuilder:
    """Builds token-budgeted context for AI injection — spec section 2/7/8."""

    def __init__(self, repo: MemoryRepository, config: MemoryConfig):
        self.repo = repo
        self.config = config
        self.searcher = HybridSearcher(repo, config)
        self.compressor = ContextCompressor(config)

    async def build_context(
        self,
        query: str = "",
        project: str = "",
        max_tokens: int | None = None,
    ) -> str:
        """Build a complete context string for injection into AI prompt.
        Respects per-layer token budgets and overall limit."""

        if max_tokens is None:
            max_tokens = self.config.max_context_tokens

        # Always include profile memory
        profile_items = await self.repo.list(
            layer=MemoryLayer.PROFILE, limit=5
        )

        # Project memory
        project_items = await self.repo.list(
            layer=MemoryLayer.PROJECT, limit=10
        )
        if project:
            project_items = sorted(
                project_items,
                key=lambda x: 1.0 if x.project == project else 0.3,
                reverse=True,
            )

        # Task memory (current project)
        task_items = await self.repo.list(
            layer=MemoryLayer.TASK, limit=5
        )
        if project:
            task_items = [i for i in task_items if i.project == project]

        # If query provided, search episodic
        episodic_items: list = []
        if query:
            search_results = await self.searcher.search(
                SearchQuery(
                    query=query,
                    layers=[MemoryLayer.EPISODIC],
                    projects=[project] if project else None,
                    top_k=5,
                )
            )
            episodic_items = [r.item for r in search_results]
        else:
            episodic_items = await self.repo.list(
                layer=MemoryLayer.EPISODIC, limit=5
            )

        # Combine all items
        all_items = profile_items + project_items + task_items + episodic_items

        # Compress
        context = self.compressor.compress_items(all_items, max_tokens)

        # Estimate tokens for the context
        est_tokens = self.compressor.estimate_tokens(context)

        # Build header
        header = f"[Shared Memory Context | ~{est_tokens} tokens]"

        return f"{header}\n{context}" if context else ""

    async def build_agents_content(self) -> str:
        """Build minimal content for AGENTS.md / CLAUDE.md.
        Strictly limited to rules/constraints — spec section 12."""

        profile_items = await self.repo.list(
            layer=MemoryLayer.PROFILE, limit=10
        )

        rules: list[str] = [
            "# Shared Memory Rules (auto-generated)",
            "",
            "These rules are shared across all AI tools (Codex, Claude, Hermes).",
            "",
        ]

        for item in profile_items:
            if item.summary:
                rules.append(f"- {item.summary}")
            elif item.content and len(item.content) < 200:
                rules.append(f"- {item.content}")

        # Project conventions
        project_items = await self.repo.list(
            layer=MemoryLayer.PROJECT, limit=15
        )
        if project_items:
            rules.append("")
            rules.append("## Project Conventions")
            seen_projects: set[str] = set()
            for item in project_items:
                if item.summary and item.project not in seen_projects:
                    seen_projects.add(item.project)
                    rules.append(f"- [{item.project}] {item.summary[:120]}")

        content = "\n".join(rules)

        # Hard size check
        content_bytes = len(content.encode("utf-8"))
        max_bytes = self.config.agents_hard_limit_kb * 1024
        if content_bytes > max_bytes:
            # Truncate to hard limit
            content = content[:max_bytes].rsplit("\n", 1)[0]
            content += "\n[truncated — exceeds hard limit]"

        return content
