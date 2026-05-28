# Integration Guide

How to connect each AI tool to the shared memory bus.

## Codex CLI

### Method 1: Skill Installation (Recommended)

```bash
codex skill install shared-memory
```

### Method 2: Direct CLI

Add to AGENTS.md:
```markdown
# Shared Memory
Use sm CLI: sm recall / sm remember / sm context
```

### Method 3: Tool Call Adapter

```python
from shared_memory.integration.codex_adapter import CodexAdapter
from shared_memory import get_shared_memory

sm = await get_shared_memory()
adapter = CodexAdapter(sm)
context = await adapter.query_memories("current task")
```

---

## Claude CLI

### Via RTK Hook

The hook at `~/.shared-memory/hooks/claude-sm-hook.ps1` (created by `sm init`)
queries memory before each Bash tool execution.

### Via CLAUDE.md

```markdown
## Shared Memory
Cross-tool memory via ~/.shared-memory/
- sm recall "query"      search memories
- sm remember "content"  write memory
- sm context             get project context
```

---

## Claude Desktop

### Via MCP Server

`sm init` auto-configures `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "shared-memory": {
      "command": "python",
      "args": ["-u", "shared_memory/integration/mcp_server.py"]
    }
  }
}
```

Tools exposed: `memory_search`, `memory_write`, `memory_read`, `memory_recent`, `memory_status`

---

## Hermes Desktop

### Via Python SDK

```python
from shared_memory import get_shared_memory, MemoryLayer

sm = await get_shared_memory()
await sm.remember("learned", layer=MemoryLayer.PROJECT)
results = await sm.recall("query")
```

### Via MEMORY.md Sync

`sm init` creates `~/.shared-memory/hooks/hermes-sync.ps1`

---

## Verification

```bash
sm init          # setup all tools
sm status        # check stats
sm recall "test" # verify search works
```
