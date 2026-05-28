from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class MemoryLayer(str, Enum):
    """Five-layer memory hierarchy per spec section 2."""
    PROFILE  = "profile"
    PROJECT  = "project"
    TASK     = "task"
    EPISODIC = "episodic"
    ARTIFACT = "artifact"


class MemoryStatus(str, Enum):
    ACTIVE       = "active"
    ARCHIVED     = "archived"
    CONSOLIDATED = "consolidated"
    EXPIRED      = "expired"


class MemoryScope(str, Enum):
    PRIVATE = "private"
    SHARED  = "shared"
    GLOBAL  = "global"


class EdgeRelation(str, Enum):
    RELATED_TO  = "related_to"
    CAUSED_BY   = "caused_by"
    DEPENDS_ON  = "depends_on"
    SUPERSEDES  = "supersedes"


class JobType(str, Enum):
    EMBEDDING   = "embedding"
    SUMMARIZE   = "summarize"
    DEDUPLICATE = "deduplicate"
    EXTRACT_ENTITIES = "extract_entities"
    DECAY       = "decay"
    CONSOLIDATE = "consolidate"


class JobStatus(str, Enum):
    PENDING    = "pending"
    PROCESSING = "processing"
    COMPLETED  = "completed"
    FAILED     = "failed"


class MemoryItem(BaseModel):
    """Core memory record — spec section 4."""
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:20])
    layer: MemoryLayer
    scope: MemoryScope = MemoryScope.SHARED
    status: MemoryStatus = MemoryStatus.ACTIVE

    # Content
    project: str = ""
    title: str = ""
    content: str
    summary: str = ""
    tags: list[str] = Field(default_factory=list)
    entities: list[str] = Field(default_factory=list)

    # Scoring
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    confidence: float = Field(default=0.7, ge=0.0, le=1.0)

    # Source tracking
    source_tool: str = ""
    source_session: str = ""

    # Version control (append-only preferred)
    version: int = 1
    parent_id: str | None = None
    content_hash: str = ""

    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_accessed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime | None = None

    # Embedding (populated asynchronously by worker)
    embedding_json: str | None = None

    model_config = {"extra": "allow", "frozen": False}


class MemoryEdge(BaseModel):
    """Graph relationship — spec section 4, memory_edges table."""
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:16])
    source_id: str
    target_id: str
    relation: EdgeRelation
    weight: float = 1.0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SearchQuery(BaseModel):
    """Hybrid search query."""
    query: str = ""
    layers: list[MemoryLayer] | None = None
    projects: list[str] | None = None
    tags: list[str] | None = None
    entities: list[str] | None = None
    scopes: list[MemoryScope] | None = None
    top_k: int = Field(default=10, ge=1, le=100)
    min_importance: float = 0.0
    include_archived: bool = False
    offset: int = 0


class SearchResult(BaseModel):
    item: MemoryItem
    score: float
    match_type: str = ""
    semantic_score: float = 0.0
    keyword_score: float = 0.0
    importance_score: float = 0.0
    recency_score: float = 0.0


class MemoryStats(BaseModel):
    total: int = 0
    by_layer: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    by_project: dict[str, int] = Field(default_factory=dict)
    avg_importance: float = 0.0
    db_size_bytes: int = 0
    job_queue_size: int = 0


class AccessLog(BaseModel):
    """Tracks memory access frequency — spec section 4."""
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:16])
    memory_id: str
    access_type: str  # retrieve, inject, update
    source_tool: str = ""
    accessed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AsyncJob(BaseModel):
    """Async job queue entry — spec section 11."""
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:16])
    memory_id: str
    job_type: JobType
    status: JobStatus = JobStatus.PENDING
    payload: str = ""       # JSON payload for the job
    error_message: str = ""
    retry_count: int = 0
    max_retries: int = 3
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: datetime | None = None
    completed_at: datetime | None = None
