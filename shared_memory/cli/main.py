"""CLI tool for shared memory — spec: sm remember / sm recall / sm context / sm status.
One command to rule them all: sm init"""

from __future__ import annotations

import asyncio
import sys
import argparse

from shared_memory.core.models import MemoryLayer, MemoryScope
from shared_memory.core.config import MemoryConfig
from shared_memory.api import SharedMemory, get_shared_memory


async def async_main(args: argparse.Namespace) -> int:
    sm = await get_shared_memory()

    try:
        if args.command == "init":
            from shared_memory.integration.universal_setup import init_all
            report = await init_all()
            print("\n=== Shared Memory Universal Setup ===\n")
            print(f"Directory: {report['shared_memory_dir']}\n")
            print("Tools detected:")
            for name, info in report["tools"].items():
                status = "[OK] Installed" if info["installed"] else "[-] Not found"
                print(f"  {status}: {name}")
            print("\nActions taken:")
            for action in report["actions"]:
                print(f"  + {action}")
            if report["errors"]:
                print("\nErrors:")
                for err in report["errors"]:
                    print(f"  ! {err}")
            print("\n[DONE] Shared memory system initialized.\n")
            return 0

        elif args.command == "remember":
            memory_id = await sm.remember(
                content=args.content,
                layer=MemoryLayer(args.layer),
                scope=MemoryScope(args.scope),
                project=args.project or "",
                title=args.title or "",
                tags=[t.strip() for t in args.tags.split(",")] if args.tags else None,
                importance=float(args.importance),
                source_tool=args.tool or "cli",
            )
            print(f"[OK] Memory stored: {memory_id}")
            return 0

        elif args.command == "recall":
            results = await sm.recall(
                query=args.query,
                top_k=args.top,
                project=args.project or "",
                layers=[MemoryLayer(l) for l in args.layers.split(",")]
                    if args.layers else None,
            )
            print(f"\nFound {len(results)} results:\n")
            for i, r in enumerate(results, 1):
                item = r.item
                print(f"{i}. [{item.layer.value}] [{item.project}] "
                      f"score={r.score:.3f}")
                print(f"   {item.content[:120]}")
                print(f"   id={item.id}\n")
            return 0

        elif args.command == "context":
            ctx = await sm.get_context(
                query=args.query or "",
                project=args.project or "",
                max_tokens=int(args.max_tokens) if args.max_tokens else None,
            )
            print(ctx)
            return 0

        elif args.command == "status":
            stats = await sm.status()
            print(f"\n=== Shared Memory Status ===")
            print(f"  Total memories:    {stats.total}")
            print(f"  By layer:          {stats.by_layer}")
            print(f"  By status:         {stats.by_status}")
            print(f"  Avg importance:    {stats.avg_importance:.3f}")
            print(f"  DB size:           {stats.db_size_bytes / 1024:.1f} KB")
            print(f"  Pending jobs:      {stats.job_queue_size}")
            return 0

        elif args.command == "forget":
            ok = await sm.forget(args.memory_id)
            print(f"[{'OK' if ok else 'FAIL'}] Archived: {args.memory_id}")
            return 0 if ok else 1

        elif args.command == "list":
            items = await sm.list_memories(
                layer=MemoryLayer(args.layer) if args.layer else None,
                limit=int(args.limit),
            )
            print(f"\nMemories (limit={args.limit}):\n")
            for item in items:
                print(f"  [{item.layer.value}] {item.content[:100]}")
                print(f"    id={item.id} imp={item.importance:.2f}")
            return 0

        elif args.command == "decay":
            count = await sm.decay_all()
            print(f"[OK] Decayed and archived {count} memories")
            return 0

        elif args.command == "agents":
            content = await sm.get_agents_content()
            print(content)
            return 0

        else:
            print(f"Unknown command: {args.command}")
            return 1

    finally:
        await sm.shutdown()


def main():
    parser = argparse.ArgumentParser(
        prog="sm",
        description="Shared Memory System CLI — universal memory for all AI tools"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # init (universal setup)
    sub.add_parser("init", help="Auto-detect and configure all AI tools")

    # remember
    p = sub.add_parser("remember", help="Store a new memory")
    p.add_argument("content", help="Memory content text")
    p.add_argument("--layer", default="episodic",
                   choices=["profile","project","task","episodic","artifact"])
    p.add_argument("--scope", default="shared",
                   choices=["private","shared","global"])
    p.add_argument("--project", default="")
    p.add_argument("--title", default="")
    p.add_argument("--tags", default="")
    p.add_argument("--importance", type=float, default=0.5)
    p.add_argument("--tool", default="cli")

    # recall
    p = sub.add_parser("recall", help="Search memories")
    p.add_argument("query")
    p.add_argument("--top", type=int, default=10)
    p.add_argument("--project", default="")
    p.add_argument("--layers", default="")

    # context
    p = sub.add_parser("context", help="Get AI context")
    p.add_argument("--query", default="")
    p.add_argument("--project", default="")
    p.add_argument("--max-tokens", default="")

    # status
    sub.add_parser("status", help="Show memory stats")

    # forget
    p = sub.add_parser("forget", help="Archive a memory")
    p.add_argument("memory_id")

    # list
    p = sub.add_parser("list", help="List memories")
    p.add_argument("--layer", default="")
    p.add_argument("--limit", default="50")

    # decay
    sub.add_parser("decay", help="Run memory decay check")

    # agents
    sub.add_parser("agents", help="Output AGENTS.md content")

    args = parser.parse_args()
    return asyncio.run(async_main(args))


if __name__ == "__main__":
    sys.exit(main())
