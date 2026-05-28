---
name: shared-memory
description: >-
  Cross-tool shared long-term memory for AI coding agents. Use when the user asks to remember, recall, or search across project knowledge, user preferences, past decisions, debugging history, or cross-tool context. Triggers on phrases like "remember this", "recall what I said about", "what did I decide about", "search my notes", "do you remember", "what's my preference", "across tools", "other AI", "shared context", "persistent memory", "save this for later". Supports 5-layer memory (Profile/Project/Task/Episodic/Artifact), hybrid FTS5+vector search with 7-factor reranking, per-layer token budgets with auto-compression, exponential decay with access-frequency boost, async embedding, multi-tool sync (Codex/Claude/Hermes), MCP server for Claude Desktop, and security auto-redaction. Local-first, SQLite-backed, zero cloud dependency.
license: MIT
metadata:
  author: dev
  version: 1.0.0
compatibility: >-
  Works on all platforms supporting SKILL.md: OpenAI Codex CLI, Claude Code,
  Claude Desktop (via MCP), Hermes Desktop, and other SKILL.md-compatible tools.
---

# Shared Memory — Cross-Tool AI Long-Term Memory

Industrial-grade, local-first shared memory system for multi-AI ecosystems.
One memory bus, four tools, zero context pollution.

## Architecture

```
~/.shared-memory/
├── memory.db      ← SQLite + FTS5 (primary)
├── chroma/        ← vector index
├── fragments/     ← Markdown mirror
└── hooks/         ← tool integration scripts
```

## Trigger

Activate when the user asks to:

- Store important knowledge persistently
- Recall past decisions, preferences, or debugging sessions
- Search across tools for shared context
- Get project-level context for current work
- Check memory statistics or health
- Set up cross-tool memory sharing

**Always search before answering** — never assume the AI already knows the answer.

## Commands

All via the `sm` CLI (auto-available after install):

```bash
# Store a memory
sm remember "User prefers pytest with snake_case naming" --layer profile --project aiapps

# Search memories
sm recall "naming convention" --top 5 --project aiapps

# Get AI context (inject this into your thinking)
sm context --project aiapps

# Show stats
sm status

# Initialize cross-tool setup
sm init
```

## Memory Layers

| Layer | Purpose | Lifecycle | Inject Limit |
|-------|---------|-----------|-------------|
| `profile` | User preferences, defaults | Permanent (~never decays) | ≤ 300 tokens |
| `project` | Architecture, tech stack, conventions | Medium decay | ≤ 1200 tokens |
| `task` | Current bug/refactor context | Fast decay | ≤ 800 tokens |
| `episodic` | Past decisions, pitfalls | On-demand only | ≤ 600 tokens |
| `artifact` | Code snippets, templates | Reference only | On-demand |

## Rules (CRITICAL)

1. **NEVER** load entire memory database into prompt
2. **ALWAYS** use `sm recall` to search before answering
3. **ALWAYS** use `sm context` for current project context injection
4. **ALWAYS** write important learnings with `sm remember`
5. **NEVER** store raw conversations — filter, summarize, deduplicate
6. **NEVER** store sensitive data (API keys, tokens, passwords — auto-redacted)
7. Keep AGENTS.md under 8KB — dynamic memory goes to sm

## Cross-Tool Sync

Memory is automatically shared across:

- **Codex CLI** — via this skill + `sm` tool calls
- **Claude CLI** — via RTK hook in `~/.shared-memory/hooks/`
- **Claude Desktop** — via MCP server (auto-registered by `sm init`)
- **Hermes Desktop** — via MEMORY.md sync + Python SDK

Run `sm init` once to auto-configure all detected tools.
