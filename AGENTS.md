# Shared Memory Agent

This agent has access to a cross-tool shared memory system.

## Memory Rules

1. Before answering questions about past work, search memory first: `sm recall "query"`
2. After important decisions, save to memory: `sm remember "content" --layer project`
3. On startup, load context: `sm context`
4. Know user preferences from Layer 1 (profile), project knowledge from Layer 2

## Commands

```bash
sm remember "content" --layer profile|project|task|episodic|artifact
sm recall "query" --top 10
sm context --project <name>
sm status
sm init        # one-time setup for all tools
```

## Architecture

Storage: `~/.shared-memory/memory.db` (SQLite + FTS5)
Shared with: Claude CLI, Claude Desktop, Hermes Desktop
