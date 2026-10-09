"""Small MCP stdio server. Every line is one JSON-RPC 2.0 message."""

import json
import sys
from pathlib import Path

from .config import load_config
from .core import (AGENT_INSTRUCTIONS, BOOTSTRAP_INSTRUCTIONS, BOOTSTRAP_MARKER,
                   CONTEXT_UPDATE_INSTRUCTIONS, CONTEXT_UPDATE_MARKER, remember, search)
from .storage import stats

TOOLS = [
    {"name": "brain_search", "description": "At session start or before exploring source files, retrieve durable project context.",
     "inputSchema": {"type": "object", "properties": {
         "query": {"type": "string"}, "types": {"type": "array", "items": {"type": "string"}},
         "tags": {"type": "array", "items": {"type": "string"}},
         "limit": {"type": "integer"}, "token_budget": {"type": "integer"}},
         "required": ["query"], "additionalProperties": False}},
    {"name": "brain_remember", "description": "After meaningful changes, save what changed, why, consequences and actual validation as durable Markdown; indexes locally.",
     "inputSchema": {"type": "object", "properties": {
         "type": {"type": "string", "enum": ["architecture", "decision", "rule", "dependency", "bug", "feature", "constraint", "rationale", "next-step"]},
         "title": {"type": "string"}, "content": {"type": "string"},
         "tags": {"type": "array", "items": {"type": "string"}},
         "importance": {"type": "number", "minimum": 0, "maximum": 1},
         "related": {"type": "array", "items": {"type": "string"}}, "status": {"type": "string"}},
         "required": ["type", "title", "content"], "additionalProperties": False}},
    {"name": "brain_status", "description": "Show local Brain status and index counts.",
     "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False}},
]


def _reply(identifier, *, result=None, error=None):
    message = {"jsonrpc": "2.0", "id": identifier}
    if error is not None:
        message["error"] = error
    else:
        message["result"] = result
    sys.stdout.write(json.dumps(message, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def serve(root: Path) -> None:
    root = root.resolve()
    load_config(root)
    instructions_path = root / ".brain" / "AGENT_BRAIN.md"
    instructions = instructions_path.read_text(encoding="utf-8") if instructions_path.exists() else AGENT_INSTRUCTIONS
    if BOOTSTRAP_MARKER not in instructions:
        instructions = instructions.rstrip("\n") + "\n\n" + BOOTSTRAP_INSTRUCTIONS
    if CONTEXT_UPDATE_MARKER not in instructions:
        instructions = instructions.rstrip("\n") + "\n\n" + CONTEXT_UPDATE_INSTRUCTIONS
    for line in sys.stdin:
        try:
            message = json.loads(line)
            if not isinstance(message, dict):
                continue
            identifier = message.get("id")
            method = message.get("method")
            if identifier is None:
                continue
            if method == "initialize":
                requested = message.get("params", {}).get("protocolVersion", "2025-03-26")
                _reply(identifier, result={"protocolVersion": requested, "capabilities": {"tools": {"listChanged": False}},
                                           "serverInfo": {"name": "second-brain-local", "version": "0.1.0"},
                                           "instructions": instructions})
            elif method == "ping":
                _reply(identifier, result={})
            elif method == "tools/list":
                _reply(identifier, result={"tools": TOOLS})
            elif method == "tools/call":
                params = message.get("params") or {}
                name, args = params.get("name"), params.get("arguments") or {}
                if not isinstance(args, dict):
                    raise ValueError("arguments must be an object")
                allowed = {item["name"]: set(item["inputSchema"]["properties"]) for item in TOOLS}
                if name not in allowed:
                    raise ValueError(f"Unknown tool: {name}")
                if set(args) - allowed[name]:
                    raise ValueError("Unknown arguments")
                if name == "brain_search":
                    result = search(root, **args)
                    output = result["context"]
                elif name == "brain_remember":
                    result = remember(root, **args)
                    output = json.dumps(result, ensure_ascii=False)
                else:
                    output = json.dumps(stats(root, load_config(root)), ensure_ascii=False)
                _reply(identifier, result={"content": [{"type": "text", "text": output}], "isError": False})
            else:
                _reply(identifier, error={"code": -32601, "message": f"Method not found: {method}"})
        except Exception as exc:
            if "identifier" in locals() and identifier is not None:
                if isinstance(message, dict) and message.get("method") == "tools/call":
                    _reply(identifier, result={"content": [{"type": "text", "text": str(exc)}], "isError": True})
                else:
                    _reply(identifier, error={"code": -32602, "message": str(exc)})
            else:
                print(f"MCP input error: {exc}", file=sys.stderr)
