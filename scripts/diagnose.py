#!/usr/bin/env python3
"""Diagnose shared memory system and connected tools."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path


async def diagnose():
    """Full system diagnosis."""
    HOME = Path.home()
    LOCALAPPDATA = Path(os.environ.get("LOCALAPPDATA", str(HOME / "AppData" / "Local")))

    print("=" * 60)
    print("  Shared Memory System Diagnostics")
    print("=" * 60)
    print()

    # 1. Package status
    print("--- Package ---")
    try:
        from shared_memory import __file__ as pkg_path
        print(f"[OK] Installed at: {pkg_path}")
    except ImportError:
        print("[MISS] shared_memory package not installed")
        return

    # 2. Database
    print("\n--- Database ---")
    from shared_memory.api import SharedMemory, MemoryConfig
    sm = SharedMemory(MemoryConfig())
    await sm.initialize()
    stats = await sm.status()
    print(f"  Total memories: {stats.total}")
    print(f"  By layer: {stats.by_layer}")
    print(f"  DB size: {stats.db_size_bytes / 1024:.1f} KB")
    print(f"  Pending jobs: {stats.job_queue_size}")

    # 3. Connected tools
    from shared_memory.integration.universal_setup import (
        detect_codex, detect_claude_cli, detect_claude_desktop, detect_hermes
    )
    tools = [
        ("Codex CLI", detect_codex()),
        ("Claude CLI", detect_claude_cli()),
        ("Claude Desktop", detect_claude_desktop()),
        ("Hermes Desktop", detect_hermes()),
    ]
    print("\n--- Connected Tools ---")
    for name, info in tools:
        status = "[OK]" if info["installed"] else "[ - ]"
        print(f"  {status} {name}")

    # 4. AGENTS.md / CLAUDE.md status
    print("\n--- Config Files ---")
    configs = [
        ("Codex AGENTS.md", HOME / ".codex" / "AGENTS.md"),
        ("Codex skills/", HOME / ".codex" / "skills" / "shared-memory"),
        ("Claude CLAUDE.md", HOME / ".claude" / "CLAUDE.md"),
        ("Claude Desktop config", LOCALAPPDATA / "Claude" / "claude_desktop_config.json"),
    ]
    for label, path in configs:
        if path.exists():
            print(f"  [OK] {label}: {path}")
        else:
            print(f"  [ - ] {label}: not found")

    # 5. MCP check
    print("\n--- MCP Server ---")
    claude_cfg = LOCALAPPDATA / "Claude" / "claude_desktop_config.json"
    if claude_cfg.exists():
        with open(claude_cfg) as f:
            cfg = json.load(f)
        if "mcpServers" in cfg and "shared-memory" in cfg["mcpServers"]:
            print(f"  [OK] MCP server registered in Claude Desktop config")
        else:
            print(f"  [ - ] MCP server not registered. Run: sm init")
    else:
        print(f"  [ - ] Claude Desktop config not found")

    await sm.shutdown()
    print("\n" + "=" * 60)


if __name__ == "__main__":
    asyncio.run(diagnose())
