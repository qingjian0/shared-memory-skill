# Shared Memory System Architecture

## Overview

The Shared Memory System is a local-first, cross-tool long-term memory infrastructure for AI coding agents. It provides a unified memory bus that Codex CLI, Claude CLI, Claude Desktop, and Hermes Desktop can all read from and write to.

## High-Level Architecture

```
┌─────────────────────────────────────────────────────┐
│                  Memory Bus                          │
│              ~/.shared-memory/                       │
│                                                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────┐   │
│  │ SQLite   │  │ ChromaDB │  │ Markdown Mirror  │   │
│  │ + FTS5   │  │ (vector) │  │ (fragments/)     │   │
│  └────┬─────┘  └────┬─────┘  └────────┬─────────┘   │
│       │              │                │              │
│       └──────────────┼────────────────┘              │
│                      │                               │
│              ┌───────┴────────┐                      │
│              │  Memory API    │                      │
│              │  (sm CLI/SDK)  │                      │
│              └───────┬────────┘                      │
└──────────────────────┼──────────────────────────────┘
                       │
    ┌──────────────────┼──────────────────┐
    │         │        │        │         │
    ▼         ▼        ▼        ▼         ▼
┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐
│Codex │ │Claude│ │Claude│ │Hermes│ │Custom│
│ CLI  │ │ CLI  │ │Desk. │ │Desk. │ │Tool  │
└──────┘ └──────┘ └──────┘ └──────┘ └──────┘
```

## Five-Layer Memory Model

### Layer 1: Profile (User Long-Term Preferences)
- **Content**: naming style, default frameworks, output preferences, environment
- **Lifetime**: Permanent (~never decays)
- **Decay rate**: 0.001
- **Injection limit**: ≤ 300 tokens
- **Access**: Always loaded into context

### Layer 2: Project (Project Memory)
- **Content**: architecture, tech stack, file structure, code conventions, build process
- **Lifetime**: Medium (decays when project inactive)
- **Decay rate**: 0.01
- **Injection limit**: ≤ 1200 tokens
- **Access**: Loaded by project name

### Layer 3: Task (Current Task)
- **Content**: current bug, current refactor, current development goal
- **Lifetime**: Short (fast decay)
- **Decay rate**: 0.1
- **Injection limit**: ≤ 800 tokens
- **Access**: By project + recency

### Layer 4: Episodic (Historical Events)
- **Content**: past pitfalls, historical decisions, debugging sessions, failure records
- **Lifetime**: On-demand (not auto-injected)
- **Decay rate**: 0.03
- **Injection limit**: ≤ 600 tokens
- **Access**: By query only

### Layer 5: Artifact (External Outputs)
- **Content**: code snippets, config templates, docs, commands, output files
- **Lifetime**: Reference only
- **Access**: By query, never auto-injected

## Storage Architecture

### Primary: SQLite + FTS5

The single source of truth. All memory metadata and content lives here.

```sql
-- Core tables
memory_items       -- All memory records
memory_edges       -- Graph relationships
memory_access_log  -- Retrieval frequency tracking
memory_jobs        -- Async task queue

-- Full-text search
memory_fts (FTS5)  -- Indexed on title + content + summary + tags

-- Triggers keep FTS5 in sync on INSERT/UPDATE/DELETE
```

### Secondary: ChromaDB (Vector Index)

Semantic similarity search. Embeddings are computed asynchronously by background workers.

### Mirror: Markdown Files

`fragments/` directory contains human-readable Markdown copies for:
- Git tracking
- Manual browsing
- Backup/export
- Cross-device sync (file-based)

## Retrieval Pipeline

```
Query → FTS5 search → Vector search → Tag match → Entity match
                ↓
          Merge candidates
                ↓
          7-Factor Rerank
                ↓
          Top-K results
```

### Reranking Formula

```
score = 0.35 * semantic_similarity
      + 0.20 * keyword_score
      + 0.15 * importance
      + 0.10 * recency
      + 0.10 * scope_match
      + 0.05 * project_match
      + 0.05 * access_frequency
```

## Async Job Queue

```
Write request → SQLite INSERT → Enqueue embedding job → Return immediately
                                     ↓
                           Background worker picks up
                                     ↓
                           Compute embedding (ChromaDB/OpenAI/local)
                                     ↓
                           Update embedding_json in SQLite
```

Jobs are processed by `workers/queue.py` with configurable concurrency.

## Security

### Auto-Redaction Patterns

Before storage, content is scanned for:
- API keys (`sk-...`)
- Bearer tokens
- Password/key/secret/token assignments
- IP addresses
- Long hex strings (potential hashes)

### Version Control

All memory mutations are append-only:
- `version` counter incremented on update
- `parent_id` links to previous version
- `content_hash` enables deduplication

Never silently overwrites old memory.

## Performance Targets

| Metric | Target |
|--------|--------|
| Retrieval latency | < 100ms |
| Context injection | < 2000 tokens |
| AGENTS.md size | < 8KB (recommended) |
| AGENTS.md hard limit | 32KB |
| Embedding queue latency | < 5s (async) |
