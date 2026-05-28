# API Reference

## CLI Commands

### sm remember
Store a new memory.

```bash
sm remember <content> [options]

Options:
  --layer       Memory layer (profile|project|task|episodic|artifact)
  --scope       Visibility (private|shared|global)
  --project     Project name
  --title       Custom title
  --tags        Comma-separated tags
  --importance  Importance score (0.0-1.0, default 0.5)
  --tool        Source tool identifier

Examples:
  sm remember "User prefers pytest" --layer profile
  sm remember "Decided to use ChromaDB" --layer project --project aiapps --tags "decision,db"
```

### sm recall
Search memories.

```bash
sm recall <query> [options]

Options:
  --top       Number of results (default 10)
  --project   Filter by project
  --layers    Comma-separated layer filter

Examples:
  sm recall "naming convention" --top 5
  sm recall "bug" --layers episodic,task
```

### sm context
Get memory context for AI injection.

```bash
sm context [options]

Options:
  --query       Relevant query for episodic search
  --project     Project name
  --max-tokens  Override token budget

Examples:
  sm context --project aiapps
  sm context --query "database migration" --max-tokens 2000
```

### sm status
Show memory statistics.

```bash
sm status

Output:
  Total memories, By layer, By status, Avg importance, DB size, Pending jobs
```

### sm forget
Archive a memory (soft delete).

```bash
sm forget <memory_id>
```

### sm list
List memories.

```bash
sm list [--layer <layer>] [--limit <n>]
```

### sm decay
Run memory decay check (archives low-importance old memories).

```bash
sm decay
```

### sm agents
Output minimal AGENTS.md content from profile/project memories.

```bash
sm agents
```

### sm init
Auto-detect and configure all installed AI tools.

```bash
sm init

Detects: Codex CLI, Claude CLI, Claude Desktop, Hermes Desktop
Configures: SKILL.md, AGENTS.md, MCP server, hooks, MEMORY.md sync
```

## Python SDK

### Quick Start

```python
from shared_memory import get_shared_memory, MemoryLayer

async def main():
    sm = await get_shared_memory()

    # Write memory
    await sm.remember(
        "User prefers snake_case naming",
        layer=MemoryLayer.PROFILE,
        project="aiapps",
    )

    # Search memory
    results = await sm.recall("naming", top_k=5)
    for r in results:
        print(f"{r.item.id}: {r.item.content}")

    # Get context for AI prompt
    ctx = await sm.get_context(project="aiapps")

    # Get stats
    stats = await sm.status()
    print(f"Total: {stats.total}, Avg importance: {stats.avg_importance}")

    await sm.shutdown()
```

### SharedMemory API

| Method | Description |
|--------|-------------|
| `remember(content, *, layer, scope, project, ...)` | Store new memory |
| `recall(query, *, top_k, layers, project, ...)` | Hybrid search |
| `forget(memory_id)` | Archive memory |
| `get(memory_id)` | Get by ID |
| `get_context(query, project, max_tokens)` | AI context string |
| `get_agents_content()` | AGENTS.md content |
| `status()` | Memory statistics |
| `list_memories(layer, project, limit)` | List memories |
| `decay_all()` | Run decay on all memories |
| `deduplicate(item)` | Find duplicates |
| `link(source_id, target_id, relation)` | Create graph edge |
| `get_links(memory_id)` | Get graph edges |

### MCP Server

The MCP server exposes 5 tools for Claude Desktop:

| Tool | Description |
|------|-------------|
| `memory_search` | Search shared memories |
| `memory_write` | Write a new memory |
| `memory_read` | Read memory by ID |
| `memory_recent` | Get recent context |
| `memory_status` | Get statistics |

Claude Desktop config (`claude_desktop_config.json`):
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
