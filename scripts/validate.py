#!/usr/bin/env python3
"""Validate shared memory system installation and health."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path


async def validate() -> int:
    """Run validation checks. Returns 0 if all pass."""
    errors = []
    warnings = []

    # 1. Check Python version
    import platform
    py_ver = tuple(map(int, platform.python_version().split(".")))
    if py_ver < (3, 11):
        errors.append(f"Python 3.11+ required, found {platform.python_version()}")
    else:
        print(f"[OK] Python {platform.python_version()}")

    # 2. Check dependencies
    deps = ["aiosqlite", "pydantic"]
    for dep in deps:
        try:
            __import__(dep)
            print(f"[OK] {dep} installed")
        except ImportError:
            errors.append(f"{dep} not installed. Run: pip install {dep}")

    # 3. Check optional deps
    try:
        __import__("chromadb")
        print(f"[OK] chromadb installed (vector search available)")
    except ImportError:
        warnings.append("chromadb not installed. Vector search disabled. Run: pip install chromadb")

    # 4. Check import
    try:
        from shared_memory import MemoryLayer, MemoryConfig
        print(f"[OK] shared_memory package importable")
    except ImportError as e:
        errors.append(f"Cannot import shared_memory: {e}")
        if errors:
            print(f"\n{len(errors)} error(s):")
            for e in errors:
                print(f"  [ERR] {e}")
            return 1

    # 5. Try DB init
    try:
        from shared_memory.api import SharedMemory
        cfg = MemoryConfig()
        sm = SharedMemory(cfg)
        await sm.initialize()
        stats = await sm.status()
        print(f"[OK] Database initialized. {stats.total} memories stored.")
        await sm.shutdown()
    except Exception as e:
        errors.append(f"Database init failed: {e}")

    # Report
    print()
    if errors:
        print(f"{len(errors)} error(s):")
        for e in errors:
            print(f"  [ERR] {e}")
    if warnings:
        print(f"{len(warnings)} warning(s):")
        for w in warnings:
            print(f"  [WARN] {w}")

    if not errors:
        print("All checks passed!")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(validate()))
