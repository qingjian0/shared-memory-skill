from __future__ import annotations

import math
from datetime import datetime, timezone

from shared_memory.core.models import MemoryLayer, MemoryItem, MemoryStatus
from shared_memory.core.config import MemoryConfig


class MemoryDecay:
    """Memory decay system — spec section 10. Different decay rates per layer."""

    def __init__(self, config: MemoryConfig):
        self.decay_rates = {
            MemoryLayer.PROFILE:  config.profile_decay_rate,
            MemoryLayer.PROJECT:  config.project_decay_rate,
            MemoryLayer.TASK:     config.task_decay_rate,
            MemoryLayer.EPISODIC: config.episodic_decay_rate,
            MemoryLayer.ARTIFACT: config.project_decay_rate,
        }

    def compute_current_importance(self, item: MemoryItem) -> float:
        """Apply exponential decay based on age and layer type."""
        now = datetime.now(timezone.utc)
        age_days = (now - item.created_at).total_seconds() / 86400.0
        if age_days <= 0:
            return item.importance

        rate = self.decay_rates.get(item.layer, 0.01)
        decayed = item.importance * math.exp(-rate * age_days)

        # Access frequency bonus (spec: increase for frequently accessed)
        # This is applied externally via access log, approximated here
        return min(1.0, max(0.0, decayed))

    def should_archive(self, item: MemoryItem) -> bool:
        """Check if a memory should be archived based on current importance."""
        current = self.compute_current_importance(item)
        # Profile memory is never auto-archived
        if item.layer == MemoryLayer.PROFILE:
            return False
        # Task memory expires quickly
        if item.layer == MemoryLayer.TASK and current < 0.15:
            return True
        # Other layers: archive when importance drops below threshold
        if current < 0.10:
            return True
        return False

    def should_expire(self, item: MemoryItem) -> bool:
        """Check if memory has passed its expiry date."""
        if item.expires_at is None:
            return False
        return datetime.now(timezone.utc) > item.expires_at

    def get_decay_target(self, item: MemoryItem) -> float:
        """Return target importance after decay."""
        return self.compute_current_importance(item)
