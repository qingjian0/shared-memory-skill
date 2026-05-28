"""MCP (Model Context Protocol) server for Claude Desktop integration.
Stdio transport — spec section 12."""

from __future__ import annotations

import asyncio
import json
import sys
from typing import Any

from shared_memory.core.models import MemoryLayer, MemoryScope
from shared_memory.api import SharedMemory, get_shared_memory

_mcp_sm: SharedMemory | None = None

TOOLS = [
    {
        "name": "memory_search",
        "description": "Search shared memories across all AI tools",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "top_k": {"type": "integer", "default": 10},
                "project": {"type": "string", "default": ""},
                "layers": {
                    "type": "array",
                    "items": {"type": "string",
                              "enum": ["profile","project","task","episodic","artifact"]}
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "memory_write",
        "description": "Write a new memory to the shared memory store",
        "inputSchema": {
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "Memory content"},
                "layer": {"type": "string",
                          "enum": ["profile","project","task","episodic","artifact"],
                          "default": "episodic"},
                "project": {"type": "string", "default": ""},
                "tags": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["content"],
        },
    },
    {
        "name": "memory_read",
        "description": "Read a specific memory by ID",
        "inputSchema": {
            "type": "object",
            "properties": {
                "id": {"type": "string", "description": "Memory ID"},
            },
            "required": ["id"],
        },
    },
    {
        "name": "memory_recent",
        "description": "Get recent memories with context for AI prompt",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "default": ""},
                "project": {"type": "string", "default": ""},
            },
        },
    },
    {
        "name": "memory_status",
        "description": "Get shared memory statistics",
        "inputSchema": {"type": "object", "properties": {}},
    },
]


async def handle_request(req: dict) -> dict:
    global _mcp_sm
    if _mcp_sm is None:
        _mcp_sm = await get_shared_memory()

    method = req.get("method", "")
    req_id = req.get("id")

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "shared-memory-mcp", "version": "1.0.0"},
            },
        }

    elif method == "tools/list":
        return {"jsonrpc": "2.0", "id": req_id, "result": {"tools": TOOLS}}

    elif method == "tools/call":
        params = req.get("params", {})
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})

        try:
            result = await _handle_tool_call(tool_name, arguments)
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"content": [{"type": "text", "text": result}]},
            }
        except Exception as e:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32000, "message": str(e)},
            }

    elif method == "notifications/initialized":
        return {}  # No response needed

    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": f"Unknown: {method}"}}


async def _handle_tool_call(name: str, args: dict) -> str:
    import json as _json

    if name == "memory_search":
        results = await _mcp_sm.recall(
            query=args.get("query", ""),
            top_k=args.get("top_k", 10),
            project=args.get("project", ""),
            layers=[MemoryLayer(l) for l in args.get("layers", [])] if args.get("layers") else None,
        )
        return _json.dumps([
            {"id": r.item.id, "score": r.score, "layer": r.item.layer.value,
             "content": r.item.content[:200], "project": r.item.project}
            for r in results
        ], ensure_ascii=False)

    elif name == "memory_write":
        memory_id = await _mcp_sm.remember(
            content=args["content"],
            layer=MemoryLayer(args.get("layer", "episodic")),
            project=args.get("project", ""),
            tags=args.get("tags"),
            source_tool="claude-desktop",
        )
        return _json.dumps({"id": memory_id, "status": "stored"})

    elif name == "memory_read":
        item = await _mcp_sm.get(args["id"])
        if item:
            return _json.dumps({
                "id": item.id, "layer": item.layer.value, "content": item.content,
                "project": item.project, "importance": item.importance,
            }, ensure_ascii=False)
        return _json.dumps({"error": "not found"})

    elif name == "memory_recent":
        ctx = await _mcp_sm.get_context(
            query=args.get("query", ""),
            project=args.get("project", ""),
        )
        return ctx

    elif name == "memory_status":
        stats = await _mcp_sm.status()
        return _json.dumps({
            "total": stats.total,
            "by_layer": stats.by_layer,
            "pending_jobs": stats.job_queue_size,
        })

    return _json.dumps({"error": f"Unknown tool: {name}"})


async def main():
    """MCP stdio transport loop."""
    reader = asyncio.StreamReader()
    protocol = asyncio.StreamReaderProtocol(reader)
    await asyncio.get_event_loop().connect_read_pipe(
        lambda: protocol, sys.stdin.buffer  # noqa
    )

    writer_transport, writer_protocol = await asyncio.get_event_loop().connect_write_pipe(
        asyncio.streams.FlowControlMixin, sys.stdout.buffer  # noqa
    )
    writer = asyncio.StreamWriter(writer_transport, writer_protocol, reader, asyncio.get_event_loop())  # noqa

    while True:
        try:
            line = await reader.readline()
            if not line:
                break
            data = line.decode("utf-8").strip()
            if not data:
                continue
            req = json.loads(data)
            resp = await handle_request(req)
            if resp:
                writer.write((json.dumps(resp) + "\n").encode("utf-8"))
                await writer.drain()
        except Exception as e:
            err = {"jsonrpc": "2.0", "error": {"code": -32603, "message": str(e)}}
            writer.write((json.dumps(err) + "\n").encode("utf-8"))
            await writer.drain()


if __name__ == "__main__":
    asyncio.run(main())
