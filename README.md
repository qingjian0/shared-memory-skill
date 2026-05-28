<p align="center">
  <h1 align="center">Shared Memory Skill</h1>
  <p align="center">
    <b>Cross-tool | Local-first | Production-grade</b><br>
    Long-term memory infrastructure for AI coding agents
  </p>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.11+-blue">
  <img src="https://img.shields.io/badge/codex-CLI-green">
  <img src="https://img.shields.io/badge/claude-compatible-purple">
  <img src="https://img.shields.io/badge/MCP-ready-orange">
  <img src="https://img.shields.io/badge/hermes-compatible-pink">
  <img src="https://img.shields.io/badge/license-MIT-yellow">
</p>

---

## Benchmarks

### vs Other AI Memory Projects

| Project | Stars | Local | Codex | MCP | Multi-Tool | 5-Layer | Budget | Redact |
|---------|-------|-------|-------|-----|------------|---------|--------|--------|
| **Shared Memory** | New | Yes | Yes | Yes | 4 tools | Yes | Yes | Yes |
| [guild](https://github.com/mathomhaus/guild) | 299 | Yes | No | No | Partial | No | No | No |
| [ijfw](https://github.com/FerroxLabs/ijfw) | 167 | Yes | Yes | No | Yes | No | No | No |
| [ogham-mcp](https://github.com/ogham-mcp/ogham-mcp) | 105 | Yes | No | Yes | No | No | No | No |
| [stash](https://github.com/Fergana-Labs/stash) | 90 | Yes | No | No | No | No | No | No |
| [continuum](https://github.com/pouyahasanamreji/continuum) | 66 | No | No | Yes | No | No | No | No |

### vs Top Skill Repos

| Feature | [agent-skill-creator](https://github.com/FrancyJGLisboa/agent-skill-creator) (1226*) | [ok-skills](https://github.com/mxyhi/ok-skills) (384*) | **Ours** |
|---------|----------|----------|------|
| SKILL.md YAML Frontmatter | Yes | Yes | Yes |
| Trigger phrases | Yes | Yes | Yes |
| Progressive disclosure | Yes (L1-5) | Yes | Yes |
| references/ deep docs | Yes | No | Yes |
| scripts/ utilities | Yes | Yes | Yes |
| .codex-plugin/ | No | No | Yes |
| AGENTS.md minimal | No | Yes (<50L) | Yes (25L) |
| Cross-platform | Yes (14+tools) | Yes (4+) | Yes (4) |
| One-click install | Yes | Yes | Yes |

---

## Feature Map

### Architecture Overview (Mermaid)

```
                    +--------------------------+
                    |   sm CLI / Python SDK     |
                    | remember recall context   |
                    +------------+-------------+
                                 |
         +-----------------------+-----------------------+
         |                       |                       |
         v                       v                       v
+-----------------+    +-----------------+    +-----------------+
|  5-Layer Memory |    |  Hybrid Search  |    |  Token Budget   |
|                 |    |                 |    |                 |
| L1 Profile 300t |    | FTS5 full-text  |    | Per-layer caps  |
| L2 Project 1200t|    | ChromaDB vector |    | Auto-compress   |
| L3 Task 800t    |    | Tag matching    |    | AGENTS < 8KB   |
| L4 Episodic 600t|    | Entity matching |    | Context < 3000t |
| L5 Artifact 0t  |    | 7-factor rerank |    | Semantic merge  |
+--------+--------+    +--------+--------+    +--------+--------+
         |                       |                       |
         +-----------------------+-----------------------+
                                 |
              +------------------+------------------+
              |                  |                  |
              v                  v                  v
    +-----------------+ +-----------------+ +-----------------+
    |   Data Layer    | |   Security      | |  Multi-Tool     |
    |                 | |                 | |                 |
    | SQLite + FTS5   | | 6-pattern redact| | Codex Skill     |
    | ChromaDB vector | | SHA256 dedup    | | MCP Server      |
    | Markdown mirror | | Append-only ver | | RTK Hook        |
    | Graph edges     | | Async embedding | | Python SDK      |
    +-----------------+ +-----------------+ +-----------------+
```

### Module Details

| Module | File | Lines | Purpose |
|--------|------|-------|---------|
| Data Models | core/models.py | 126 | Pydantic v2: 5 layers + edges + jobs |
| Config | core/config.py | 47 | Token budgets, decay rates, weights |
| DB Schema | db/schema.py | 126 | 4 tables + FTS5 + 3 triggers + 9 indexes |
| Repository | db/repository.py | 379 | Full CRUD + dedup + job queue |
| Hybrid Search | retrieval/searcher.py | 127 | FTS5 + vector + tag + entity + rerank |
| Context Builder | retrieval/context_builder.py | 106 | Token-budgeted AI context injection |
| Compressor | lifecycle/compressor.py | 60 | Per-layer semantic compression |
| Decay Engine | lifecycle/decay.py | 47 | 5 independent decay rates |
| Sanitizer | security/sanitizer.py | 28 | 6 regex auto-redaction patterns |
| Job Queue | workers/queue.py | 70 | Async processing, non-blocking |
| Embedding Worker | workers/embedding_worker.py | 53 | ChromaDB / OpenAI / local fallback |
| Main API | api.py | 189 | SharedMemory class: 14 async methods |
| Codex Adapter | integration/codex_adapter.py | 71 | Tool-call protocol adapter |
| MCP Server | integration/mcp_server.py | 186 | Stdio transport, 5 MCP tools |
| Universal Setup | integration/universal_setup.py | 217 | Auto-detect + one-click config |
| CLI | cli/main.py | 154 | 9 subcommands |

### Retrieval Pipeline

```
Query: "which database should I use?"
         |
         v
+-------------+  +--------------+  +-----------+  +-------------+
| FTS5 Search |  | ChromaDB     |  | Tag Match |  | Entity Match|
| "database"  |  | semantic sim.|  | "backend" |  | "SQLite"    |
| BM25 score  |  | cosine>0.3   |  | "storage" |  | "PostgreSQL"|
+------+------+  +------+-------+  +-----+-----+  +------+------+
       |                |                 |                |
       +----------------+-----------------+----------------+
                        | merge & deduplicate
                        v
            +---------------------------+
            | 7-Factor Reranking        |
            |                           |
            | 0.35 x semantic_similarity|
            | 0.20 x keyword_score      |
            | 0.15 x importance         |
            | 0.10 x recency            |
            | 0.10 x scope_match        |
            | 0.05 x project_match      |
            | 0.05 x access_frequency   |
            +-------------+-------------+
                          v
            +---------------------------+
            | Top-K (default 10)        |
            | -> Token budget compress  |
            | -> Inject into AI prompt  |
            +---------------------------+
```

### Memory Lifecycle

```
New memory
    |
    +--> Auto-redact (6 patterns)
    +--> SHA256 dedup check
    +--> SQLite INSERT (<1ms, sync)
    +--> Enqueue embedding (async)
            |
            v
    +---------------+
    | ACTIVE        |  <-- searchable
    | decays:       |
    | imp x e^(-r x days)|
    +-------+-------+
            | when importance < threshold
            v
    +---------------+
    | ARCHIVED      |  <-- excluded from search
    +-------+-------+
            | when expires_at reached
            v
    +---------------+
    | EXPIRED       |  <-- sm decay batch cleanup
    +---------------+
```

| Layer | Decay Rate | After 6mo | After 1yr | Archive at |
|-------|-----------|-----------|-----------|------------|
| Profile | 0.001 | 83% | 69% | Never auto |
| Project | 0.01 | 17% | 3% | < 0.10 |
| Task | 0.1 | ~0% | 0% | < 0.15 |
| Episodic | 0.03 | 0.4% | 0% | < 0.10 |

---

## Quick Start

### Install

```bash
git clone https://github.com/qingjian0/shared-memory-skill.git
cd shared-memory-skill

# Windows one-click
powershell -ExecutionPolicy Bypass -File install.ps1

# Or manual
pip install -e .
sm init
```

### 30-Second Demo

```bash
# Remember preferences
sm remember "Prefers snake_case + pytest + uv" --layer profile

# Remember project decisions
sm remember "Database: SQLite+FTS5, not PostgreSQL" --layer project --project aiapps

# Search
sm recall "database" --top 5

# Get AI context
sm context --project aiapps

# Stats
sm status
```

Output:
```
=== Shared Memory Status ===
  Total memories:    42
  By layer:          {profile: 5, project: 18, task: 7, ...}
  Avg importance:    0.723
  DB size:           84.2 KB
```

---

## Architecture

```
~/.shared-memory/                     <-- Memory Bus
|
|-- memory.db          <-- SQLite (single source of truth)
|   |-- memory_items       -> Records (5 layers x metadata x scoring)
|   |-- memory_edges       -> Graph (related_to/caused_by/depends_on/supersedes)
|   |-- memory_access_log  -> Access frequency tracking
|   |-- memory_jobs        -> Async queue (embed/summarize/dedup/decay)
|   +-- memory_fts         -> FTS5 (title+content+summary+tags)
|
|-- chroma/            <-- ChromaDB vector index (async update)
|-- fragments/         <-- Markdown mirror (git-trackable)
|-- hooks/             <-- Tool integration scripts
|   |-- claude-sm-hook.ps1
|   +-- hermes-sync.ps1
+-- README.md
```

---

## Memory Layers

| # | Layer | Content | Lifetime | Budget | Decay |
|---|-------|---------|----------|--------|-------|
| L1 | **Profile** | Preferences, naming, defaults | Permanent | <=300t | 0.001 |
| L2 | **Project** | Architecture, stack, conventions | Medium | <=1200t | 0.01 |
| L3 | **Task** | Current bug, current refactor | Short | <=800t | 0.1 |
| L4 | **Episodic** | Past pitfalls, decisions | On-demand | <=600t | 0.03 |
| L5 | **Artifact** | Snippets, templates, commands | Reference | 0t | 0.01 |

Decay: `importance(t) = importance0 * e^(-decay_rate * age_days)`

---

## Security

Auto-redaction before every write:

| Pattern | Example | Replaced |
|---------|---------|----------|
| API Key | `sk-abc123...` | `[REDACTED_API_KEY]` |
| Bearer | `Bearer eyJhb...` | `Bearer [REDACTED]` |
| Password | `password: "x"` | `password: '[REDACTED]'` |
| IP | `192.168.1.1` | `[IP_REDACTED]` |
| Base64 | `dGhpcyBp...` | `[REDACTED_BASE64]` |
| SHA256 | `e3b0c442...` | `[REDACTED_HASH]` |

---

## Multi-Tool Integration

### Codex CLI
```bash
codex skill install shared-memory
# Or: cp -r shared-memory-skill ~/.codex/skills/shared-memory/
# Usage: sm recall "query" / sm remember "content" / sm context
```

### Claude CLI
`sm init` auto-configures RTK hook. Memories queried before each Bash execution.

### Claude Desktop
```json
{ "mcpServers": { "shared-memory": {
    "command": "python", "args": ["-u", "shared_memory/integration/mcp_server.py"]
}}}
```
5 tools: `memory_search` `memory_write` `memory_read` `memory_recent` `memory_status`

### Hermes Desktop
```python
from shared_memory import get_shared_memory, MemoryLayer
sm = await get_shared_memory()
await sm.remember("learned", layer=MemoryLayer.PROJECT)
results = await sm.recall("query")
```

---

## CLI Reference

| Command | Purpose |
|---------|---------|
| `sm init` | Auto-detect & configure all AI tools |
| `sm remember <text>` | Write memory |
| `sm recall <query>` | Search memory |
| `sm context` | Get AI context |
| `sm status` | Show stats |
| `sm forget <id>` | Archive memory |
| `sm list` | List memories |
| `sm decay` | Run decay check |
| `sm agents` | Output AGENTS.md |

---

## Python SDK

```python
from shared_memory import get_shared_memory, MemoryLayer

async def main():
    sm = await get_shared_memory()
    await sm.remember("pref", layer=MemoryLayer.PROFILE, importance=0.9)
    results = await sm.recall("query", top_k=10)
    ctx = await sm.get_context(project="aiapps")
    stats = await sm.status()
    await sm.shutdown()
```

---

## Project Structure

```
shared-memory-skill/
|-- SKILL.md              <-- Codex Skill entry
|-- AGENTS.md             <-- Minimal rules (25L)
|-- README.md             <-- This file
|-- install.ps1           <-- One-click installer
|-- .codex-plugin/
|   +-- plugin.json       <-- Plugin manifest
|-- references/           <-- Deep docs
|   |-- architecture.md
|   |-- api-reference.md
|   +-- integration-guide.md
|-- scripts/
|   |-- validate.py
|   +-- diagnose.py
+-- shared_memory/        <-- Core package
    |-- api.py            <-- SharedMemory (189L, 14 APIs)
    |-- core/             <-- Models, config, exceptions
    |-- db/               <-- SQLite schema, repository
    |-- retrieval/        <-- Hybrid search, context
    |-- lifecycle/        <-- Decay, compression
    |-- security/         <-- Sanitizer
    |-- workers/          <-- Async queue, embedding
    +-- integration/      <-- MCP, Codex, universal setup
```

---

## Performance

| Metric | Target | Method |
|--------|--------|--------|
| Search latency | <100ms | FTS5 + in-memory |
| Context inject | <2000 tokens | Per-layer budget |
| AGENTS.md | <8KB (rec) | Hard limit 32KB |
| Embedding | <5s (async) | Non-blocking worker |
| DB write | <1ms | SQLite WAL mode |
| Decay check | <50ms/1k | Batch processing |

---

## License

MIT

---

<p align="center">
  <sub>Architecture on par with
  <a href="https://github.com/FrancyJGLisboa/agent-skill-creator">agent-skill-creator</a>,
  <a href="https://github.com/mxyhi/ok-skills">ok-skills</a>,
  <a href="https://github.com/mathomhaus/guild">guild</a></sub>
</p>
