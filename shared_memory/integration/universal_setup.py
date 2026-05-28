"""Universal setup — one command to rule them all.
sm init  -> auto-detect all installed AI tools -> configure each one."""

from __future__ import annotations

import json
import logging
import os
import shutil
from pathlib import Path
from typing import Any

from shared_memory.api import SharedMemory, get_shared_memory
from shared_memory.core.config import MemoryConfig

logger = logging.getLogger(__name__)

HOME = Path.home()
LOCALAPPDATA = Path(os.environ.get("LOCALAPPDATA", str(HOME / "AppData" / "Local")))


# ── Tool detection ────────────────────────────────────

def detect_codex() -> dict:
    """Detect Codex CLI installation."""
    candidates = [
        HOME / ".codex",
        LOCALAPPDATA / "Codex",
    ]
    for c in candidates:
        if c.exists():
            # Check key files
            skills_dir = c / "skills"
            agents_md = c / "AGENTS.md"
            config_toml = c / "config.toml"
            return {
                "installed": True,
                "home": str(c),
                "skills_dir": str(skills_dir),
                "agents_md": str(agents_md),
                "agents_md_exists": agents_md.exists(),
                "config_toml": str(config_toml),
            }
    return {"installed": False}


def detect_claude_cli() -> dict:
    """Detect Claude CLI installation."""
    candidates = [
        HOME / ".claude",
    ]
    for c in candidates:
        if c.exists():
            settings_file = c / "settings.json"
            claude_md = c / "CLAUDE.md"
            hooks = None
            if settings_file.exists():
                try:
                    with open(settings_file) as f:
                        hooks = json.load(f).get("hooks")
                except Exception:
                    pass
            return {
                "installed": True,
                "home": str(c),
                "settings_file": str(settings_file),
                "claude_md": str(claude_md),
                "has_hooks": bool(hooks),
            }
    return {"installed": False}


def detect_claude_desktop() -> dict:
    """Detect Claude Desktop installation."""
    c = LOCALAPPDATA / "Claude"
    config_file = c / "claude_desktop_config.json"
    if c.exists():
        config = {}
        if config_file.exists():
            try:
                with open(config_file) as f:
                    config = json.load(f)
            except Exception:
                pass
        return {
            "installed": True,
            "home": str(c),
            "config_file": str(config_file),
            "has_mcp": "mcpServers" in config,
        }
    return {"installed": False}


def detect_hermes() -> dict:
    """Detect Hermes Desktop installation."""
    c = LOCALAPPDATA / "Hermes"
    if c.exists():
        memory_file = c / "memories" / "MEMORY.md"
        soul_file = c / "SOUL.md"
        return {
            "installed": True,
            "home": str(c),
            "memory_file": str(memory_file),
            "memory_dir": str(memory_file.parent),
            "soul_file": str(soul_file),
        }
    return {"installed": False}


# ── Integration setup ─────────────────────────────────

async def setup_codex(info: dict, sm_memory_dir: str) -> list[str]:
    """Configure Codex CLI to use shared memory."""
    actions = []

    codex_home = Path(info["home"])

    # 1. Create Codex Skill
    skills_dir = Path(info["skills_dir"])
    skills_dir.mkdir(parents=True, exist_ok=True)
    sm_skill_dir = skills_dir / "shared-memory"
    sm_skill_dir.mkdir(parents=True, exist_ok=True)

    skill_md = f'''# Shared Memory Skill

This skill gives Codex access to a cross-tool shared memory system.
Memory is stored in `{sm_memory_dir}` and shared with Claude, Hermes, and other AI tools.

## Tools Available

When the user asks you to:
- Remember important information
- Recall past decisions or preferences
- Search across project knowledge

Use these shell commands:

### Remember something
```bash
sm remember "the content to store" --layer profile --project <project>
```

### Recall/search knowledge
```bash
sm recall "query" --top 10
```

### Get AI context (inject into your thinking)
```bash
sm context --project <current_project>
```

### Check memory statistics
```bash
sm status
```

## Memory Layers

- `profile` — user preferences, naming style, default frameworks (permanent, slow decay)
- `project` — project architecture, tech stack, code conventions
- `task` — current bug/refactor context, short life
- `episodic` — past decisions, pitfalls, debugging history (on-demand only)
- `artifact` — code snippets, templates, commands (reference only)

## Rules

- NEVER load the entire memory database into prompt
- ALWAYS use sm recall to search first
- ALWAYS use sm context for current project context
- Write important learnings with sm remember
- Keep AGENTS.md small — dynamic memory goes to sm
'''

    skill_file = sm_skill_dir / "SKILL.md"
    with open(skill_file, "w", encoding="utf-8") as f:
        f.write(skill_md)
    actions.append(f"Codex Skill created: {skill_file}")

    # 2. Update AGENTS.md with minimal reference
    agents_md = codex_home / "AGENTS.md"
    agents_content = ""
    if agents_md.exists():
        agents_content = agents_md.read_text(encoding="utf-8")

    # Backup
    if agents_md.exists():
        shutil.copy(agents_md, agents_md.with_suffix(".md.bak"))

    sm_block = f'''\n
# Shared Memory
This agent has access to a shared memory system at `{sm_memory_dir}`.
Use the shared-memory skill to remember/recall/context.
Cross-tool memory shared with: Claude CLI, Claude Desktop, Hermes.

## Quick commands
- `sm recall "query"` — search memories
- `sm remember "content" --layer profile` — write persistent memory
- `sm context` — get current project context
'''

    if "# Shared Memory" not in agents_content:
        agents_content += sm_block

    with open(agents_md, "w", encoding="utf-8") as f:
        f.write(agents_content)
    actions.append(f"Codex AGENTS.md updated: {agents_md}")

    return actions


async def setup_claude_cli(info: dict, sm_memory_dir: str) -> list[str]:
    """Configure Claude CLI to use shared memory via hook."""
    actions = []

    claude_home = Path(info["home"])

    # 1. Create hook script
    hooks_dir = Path(sm_memory_dir) / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    hook_file = hooks_dir / "claude-sm-hook.ps1"

    hook_content = r'''
# Shared Memory hook for Claude CLI
# Called by RTK before each Bash tool execution
param($input)

$project = (Get-Location).Path
$query = if ($input) { $input } else { "" }

try {
    $context = sm context --query "$query" --project "$project" 2>&1
    if ($context -and $context -notmatch "No relevant") {
        Write-Output "[SharedMemory] $context"
    }
} catch {
    # Silently continue if sm not available
}
'''

    with open(hook_file, "w", encoding="utf-8") as f:
        f.write(hook_content.strip())
    actions.append(f"Claude CLI hook created: {hook_file}")

    # 2. Update CLAUDE.md
    claude_md = claude_home / "CLAUDE.md"
    claude_content = claude_md.read_text(encoding="utf-8") if claude_md.exists() else ""

    sm_block = f'''\n
## Shared Memory
Cross-tool memory shared via `{sm_memory_dir}`.
Query memories: `sm recall "query"`
Write memories: `sm remember "content" --layer project`
Get context: `sm context`
'''

    if "Shared Memory" not in claude_content and claude_md.exists():
        claude_content += sm_block
        if claude_md.exists():
            shutil.copy(claude_md, claude_md.with_suffix(".md.bak"))
        with open(claude_md, "w", encoding="utf-8") as f:
            f.write(claude_content)
        actions.append(f"Claude CLI CLAUDE.md updated: {claude_md}")

    return actions


async def setup_claude_desktop(info: dict, sm_memory_dir: str) -> list[str]:
    """Configure Claude Desktop to use MCP server."""
    actions = []

    config_file = Path(info["config_file"])
    config = {}
    if config_file.exists():
        try:
            with open(config_file) as f:
                config = json.load(f)
        except Exception:
            config = {}

    # Determine Python path
    python_path = shutil.which("python") or shutil.which("python3") or "python"

    # MCP server path
    mcp_script = Path(__file__).parent / "mcp_server.py"

    config["mcpServers"] = config.get("mcpServers", {})
    config["mcpServers"]["shared-memory"] = {
        "command": python_path,
        "args": ["-u", str(mcp_script)],
    }

    # Backup
    if config_file.exists():
        shutil.copy(config_file, config_file.with_suffix(".json.bak"))

    with open(config_file, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
    actions.append(f"Claude Desktop MCP configured: {config_file}")

    return actions


async def setup_hermes(info: dict, sm_memory_dir: str) -> list[str]:
    """Configure Hermes to sync with shared memory."""
    actions = []

    memory_dir = Path(info["memory_dir"])
    memory_dir.mkdir(parents=True, exist_ok=True)
    memory_file = Path(info["memory_file"])

    # Create sync script
    hooks_dir = Path(sm_memory_dir) / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    sync_script = hooks_dir / "hermes-sync.ps1"

    sync_content = f'''
# Hermes to Shared Memory sync
# Reads Hermes MEMORY.md and pushes to shared memory
# Run periodically or hook into Hermes session end

$hermesMemory = "{memory_file}"
$sm_dir = "{sm_memory_dir}"

if (Test-Path $hermesMemory) {{
    $content = Get-Content $hermesMemory -Raw
    # Push to shared memory
    sm remember $content --layer project --tool hermes
    Write-Output "[OK] Hermes memories synced"
}} else {{
    Write-Output "[SKIP] Hermes MEMORY.md not found"
}}
'''

    with open(sync_script, "w", encoding="utf-8") as f:
        f.write(sync_content.strip())
    actions.append(f"Hermes sync script created: {sync_script}")

    # Update Hermes MEMORY.md with header referencing shared memory
    if memory_file.exists():
        content = memory_file.read_text(encoding="utf-8")
        if "shared-memory" not in content:
            new_content = f"<!-- Shared memory: {sm_memory_dir} -->\n{content}"
            memory_file.write_text(new_content, encoding="utf-8")
        actions.append(f"Hermes MEMORY.md linked to shared memory: {memory_file}")
    else:
        memory_file.write_text(
            f"<!-- Shared memory: {sm_memory_dir} -->\n# Hermes Memory\n", encoding="utf-8"
        )
        actions.append(f"Hermes MEMORY.md initialized: {memory_file}")

    return actions


# ── Main init command ─────────────────────────────────

async def init_all() -> dict:
    """Detect all tools and configure them. Returns a report."""

    sm = await get_shared_memory()
    sm_dir = sm.config.db_dir

    # Ensure DB is initialized
    memory_file = Path(sm_dir) / "memory.db"
    Path(sm_dir).mkdir(parents=True, exist_ok=True)

    report = {
        "tools": {},
        "actions": [],
        "errors": [],
        "shared_memory_dir": str(sm_dir),
    }

    # Detect and setup each tool
    setups = [
        ("codex", detect_codex, setup_codex),
        ("claude-cli", detect_claude_cli, setup_claude_cli),
        ("claude-desktop", detect_claude_desktop, setup_claude_desktop),
        ("hermes", detect_hermes, setup_hermes),
    ]

    for name, detector, setuper in setups:
        info = detector()
        report["tools"][name] = info

        if info["installed"]:
            try:
                actions = await setuper(info, sm_dir)
                report["actions"].extend(actions)
                logger.info("%s: configured (%d actions)", name, len(actions))
            except Exception as e:
                err = f"{name}: failed — {e}"
                report["errors"].append(err)
                logger.error(err)
        else:
            logger.info("%s: not installed, skipped", name)

    # Write README
    readme = Path(sm_dir) / "README.md"
    readme.write_text(f'''# Shared Memory System

Memory bus for: Codex, Claude CLI, Claude Desktop, Hermes

## Quick Start

```bash
sm remember "important knowledge" --layer project
sm recall "query"
sm context
sm status
```

## Structure

- `memory.db` — SQLite database (primary)
- `fragments/` — Markdown mirror (human-readable)
- `hooks/` — Integration hook scripts
- `README.md` — This file

## Tool Integration Status

{chr(10).join(f"- {t}: {'Configured' if i['installed'] else 'Not found'}" for t, i in report['tools'].items())}
''', encoding="utf-8")

    await sm.shutdown()
    return report
