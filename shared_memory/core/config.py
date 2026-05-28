from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


class MemoryConfig(BaseModel):
    """Global configuration for shared memory system."""

    # Storage paths
    db_dir: str = str(Path.home() / ".shared_memory")
    db_path: str = ""   # defaults to db_dir/memory.db

    # Embedding
    embedding_provider: Literal["chromadb", "openai", "local"] = "chromadb"
    embedding_model: str = "all-MiniLM-L6-v2"
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_embedding_model: str = "text-embedding-3-small"

    # Async worker
    worker_poll_interval_sec: float = 1.0
    worker_max_concurrent: int = 4

    # Token budgets (spec section 7)
    profile_token_budget: int = 300
    project_token_budget: int = 1200
    task_token_budget: int = 800
    episodic_token_budget: int = 600
    max_context_tokens: int = 3000

    # Retrieval
    default_top_k: int = 10
    min_semantic_score: float = 0.3
    embedding_dim: int = 384

    # Reranking weights (spec section 9)
    weight_semantic: float = 0.35
    weight_keyword: float = 0.20
    weight_importance: float = 0.15
    weight_recency: float = 0.10
    weight_scope: float = 0.10
    weight_project: float = 0.05
    weight_access_freq: float = 0.05

    # Decay (spec section 10)
    profile_decay_rate: float = 0.001
    project_decay_rate: float = 0.01
    task_decay_rate: float = 0.1
    episodic_decay_rate: float = 0.03

    # AGENTS.md limits (spec section 12)
    agents_max_size_kb: int = 8
    agents_hard_limit_kb: int = 32

    # Chunk size for context compression (approx chars, ~4 chars/token)
    chunk_size: int = 400
    model_config = {"extra": "ignore"}
