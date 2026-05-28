from __future__ import annotations

import math
from datetime import datetime, timezone

from shared_memory.core.models import (
    MemoryItem, SearchQuery, SearchResult, MemoryLayer, MemoryScope,
)
from shared_memory.core.config import MemoryConfig
from shared_memory.db.repository import MemoryRepository

# ── Reranking formula (spec section 9) ──
# score = 0.35 * semantic + 0.20 * keyword + 0.15 * importance
#       + 0.10 * recency + 0.10 * scope_match + 0.05 * project_match
#       + 0.05 * access_frequency


class HybridSearcher:
    """Hybrid retrieval with multi-source + reranking."""

    def __init__(self, repo: MemoryRepository, config: MemoryConfig):
        self.repo = repo
        self.config = config

    async def search(self, query: SearchQuery) -> list[SearchResult]:
        """Main hybrid search entry point."""

        # 1. FTS5 full-text search
        fts_results = await self.repo.search_fts(
            self._fts_query(query), limit=query.top_k * 3
        )

        # 2. Tag-based search
        tag_ids: set[str] = set()
        if query.tags:
            tag_ids.update(await self.repo.search_by_tags(query.tags, limit=query.top_k))

        # 3. Entity-based search
        entity_ids: set[str] = set()
        if query.entities:
            entity_ids.update(
                await self.repo.search_by_entities(query.entities, limit=query.top_k)
            )

        # 4. Collect all candidate IDs
        all_ids: set[str] = set()
        fts_scores: dict[str, float] = {}
        for mid, score in fts_results:
            all_ids.add(mid)
            fts_scores[mid] = score
        all_ids.update(tag_ids)
        all_ids.update(entity_ids)

        if not all_ids:
            return []

        # 5. Load full memory items
        items: dict[str, MemoryItem] = {}
        for mid in all_ids:
            item = await self.repo.get_by_id(mid)
            if item and item.status.value == "active":
                items[mid] = item

        # 6. Apply filters
        items = self._apply_filters(items, query)

        # 7. Rerank
        results = self._rerank(items, fts_scores, query)

        # 8. Top-K
        results.sort(key=lambda x: x.score, reverse=True)
        return results[:query.top_k]

    def _fts_query(self, query: SearchQuery) -> str:
        """Build FTS5 query string."""
        parts = [query.query.strip()] if query.query.strip() else []
        if query.tags:
            parts.extend(query.tags)
        if query.entities:
            parts.extend(query.entities)
        return " OR ".join(parts) if parts else "*"

    def _apply_filters(
        self, items: dict[str, MemoryItem], query: SearchQuery
    ) -> dict[str, MemoryItem]:
        filtered: dict[str, MemoryItem] = {}
        for mid, item in items.items():
            if query.layers and item.layer not in query.layers:
                continue
            if query.projects and item.project not in query.projects:
                continue
            if query.scopes and item.scope not in query.scopes:
                continue
            if query.min_importance > 0 and item.importance < query.min_importance:
                continue
            if not query.include_archived and item.status.value != "active":
                continue
            filtered[mid] = item
        return filtered

    def _rerank(
        self,
        items: dict[str, MemoryItem],
        fts_scores: dict[str, float],
        query: SearchQuery,
    ) -> list[SearchResult]:
        """Apply the reranking formula (spec section 9)."""
        now = datetime.now(timezone.utc)
        results: list[SearchResult] = []

        for mid, item in items.items():
            w = self.config

            # Semantic similarity score (from FTS as proxy; vector gives better)
            semantic_score = fts_scores.get(mid, 0.15)

            # Keyword score
            keyword_score = semantic_score * 0.8  # approximated from FTS

            # Importance score (normalized)
            imp_score = item.importance

            # Recency score (exponential decay, max 30 days)
            days_old = max(0, (now - item.updated_at).total_seconds() / 86400.0)
            recency_score = math.exp(-days_old / 30.0)

            # Scope match (higher for shared/global when querying broadly)
            scope_score = 1.0 if item.scope != MemoryScope.PRIVATE else 0.3

            # Project match
            project_score = 1.0 if (query.projects and item.project in query.projects) else 0.5

            # Access frequency score (simplified: use importance as proxy)
            freq_score = min(1.0, item.importance * 0.8)

            # Weighted sum
            score = (
                w.weight_semantic  * semantic_score +
                w.weight_keyword   * keyword_score +
                w.weight_importance * imp_score +
                w.weight_recency   * recency_score +
                w.weight_scope     * scope_score +
                w.weight_project   * project_score +
                w.weight_access_freq * freq_score
            )

            results.append(SearchResult(
                item=item,
                score=round(score, 4),
                match_type="fts" if mid in fts_scores else "entity",
                semantic_score=round(semantic_score, 4),
                keyword_score=round(keyword_score, 4),
                importance_score=round(imp_score, 4),
                recency_score=round(recency_score, 4),
            ))

        return results
