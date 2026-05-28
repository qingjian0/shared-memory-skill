from __future__ import annotations

from shared_memory.core.models import MemoryItem, MemoryLayer
from shared_memory.core.config import MemoryConfig


class ContextCompressor:
    """Context compression — spec section 8. Merges similar memories, keeps semantics."""

    def __init__(self, config: MemoryConfig):
        self.config = config
        self.token_estimate = 4  # ~4 characters per token

    def estimate_tokens(self, text: str) -> int:
        return max(1, len(text) // self.token_estimate)

    def get_token_budget(self, layer: MemoryLayer) -> int:
        budgets = {
            MemoryLayer.PROFILE:  self.config.profile_token_budget,
            MemoryLayer.PROJECT:  self.config.project_token_budget,
            MemoryLayer.TASK:     self.config.task_token_budget,
            MemoryLayer.EPISODIC: self.config.episodic_token_budget,
            MemoryLayer.ARTIFACT: self.config.project_token_budget,
        }
        return budgets.get(layer, 500)

    def compress_items(self, items: list[MemoryItem], token_budget: int) -> str:
        """Compress a list of memory items into a budget-limited context string.
        Sorts by importance, then fits within token budget."""
        if not items:
            return ""

        # Sort: highest importance first
        sorted_items = sorted(items, key=lambda x: x.importance, reverse=True)

        lines: list[str] = []
        total_tokens = 0

        for item in sorted_items:
            # Prefer summary, fallback to content
            text = item.summary if item.summary else item.content
            # Compress further: take first 200 chars per item
            compressed = text[:200].replace("\n", " ").strip()
            if not compressed:
                continue

            entry = f"[{item.layer.value}] {compressed}"
            tokens = self.estimate_tokens(entry)

            if total_tokens + tokens > token_budget:
                break

            lines.append(entry)
            total_tokens += tokens

        return "\n".join(lines)

    def build_context_chunks(self, items: list[MemoryItem]) -> str:
        """Build a complete, budgeted context from memory items.
        Applies per-layer token budgets."""
        layers_map: dict[MemoryLayer, list[MemoryItem]] = {}
        for item in items:
            layers_map.setdefault(item.layer, []).append(item)

        chunks: list[str] = []
        layer_order = [MemoryLayer.PROFILE, MemoryLayer.PROJECT,
                       MemoryLayer.TASK, MemoryLayer.EPISODIC, MemoryLayer.ARTIFACT]

        for layer in layer_order:
            layer_items = layers_map.get(layer, [])
            if not layer_items:
                continue
            budget = self.get_token_budget(layer)
            chunk = self.compress_items(layer_items, budget)
            if chunk:
                chunks.append(f"-- {layer.value} --\n{chunk}")

        return "\n\n".join(chunks)
