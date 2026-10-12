"""MCP tool definitions and a transport-independent JSON-RPC handler.

The same tools are exposed over stdio (``brain mcp``) and Streamable HTTP (``POST /mcp``).
A *backend* implements the operations; the server backend talks to Postgres directly,
the remote backend talks HTTP, and the local backend uses the V1 ``.brain/`` files.
This module has no server dependencies so the CLI can import it.
"""

import json
from typing import Any, Protocol

PROTOCOL_VERSION = "2025-06-18"
KINDS = ["idea", "objective", "problem", "actor", "hypothesis", "question", "decision", "alternative",
         "tradeoff", "requirement", "constraint", "architecture", "component", "dependency", "risk", "feature",
         "bug", "state", "next_step", "experiment", "result", "learning", "implementation", "spec", "doc",
         "rule", "rationale"]
_project = {"type": "string", "description": "Project id or slug. Optional when the server or directory is "
                                             "bound to one project."}


def _schema(properties: dict, required: list[str] | None = None) -> dict:
    return {"type": "object", "properties": properties, "required": required or [], "additionalProperties": False}


TOOLS: list[dict] = [
    {"name": "brain_context",
     "description": "Compact project context: objective, current state, accepted decisions, architecture, "
                    "active features, open bugs and recent activity. Call once at session start.",
     "inputSchema": _schema({"project": _project, "token_budget": {"type": "integer", "minimum": 150}})},
    {"name": "brain_relevant_context",
     "description": "Minimal, intent-based context for one task: matching decisions, constraints, features, "
                    "bugs and technical knowledge. Use before planning or editing code for a task.",
     "inputSchema": _schema({"project": _project, "task": {"type": "string"},
                             "token_budget": {"type": "integer", "minimum": 200},
                             "include_knowledge": {"type": "boolean"}}, ["task"])},
    {"name": "brain_search",
     "description": "Hybrid (semantic + keyword) search. scope=project for project memory, knowledge for the "
                    "AI-engineering knowledge base, all for both.",
     "inputSchema": _schema({"project": _project, "query": {"type": "string"},
                             "scope": {"type": "string", "enum": ["project", "knowledge", "all"]},
                             "kinds": {"type": "array", "items": {"type": "string", "enum": KINDS}},
                             "types": {"type": "array", "items": {"type": "string"}},
                             "tags": {"type": "array", "items": {"type": "string"}},
                             "limit": {"type": "integer", "minimum": 1, "maximum": 50},
                             "token_budget": {"type": "integer", "minimum": 40}}, ["query"])},
    {"name": "brain_knowledge",
     "description": "Search reusable technical knowledge (AI engineering material) with intent-based expansion.",
     "inputSchema": _schema({"query": {"type": "string"}, "collections": {"type": "array", "items": {"type": "string"}},
                             "limit": {"type": "integer", "minimum": 1, "maximum": 20},
                             "token_budget": {"type": "integer", "minimum": 80}}, ["query"])},
    {"name": "brain_get",
     "description": "Full record (decision, feature, bug, architecture…) by key, id or exact title, with relations.",
     "inputSchema": _schema({"project": _project, "ref": {"type": "string"}}, ["ref"])},
    {"name": "brain_list",
     "description": "List records by kind and status, e.g. kind=decision, kind=architecture, kind=feature "
                    "status=in_progress, kind=bug status=open, kind=requirement.",
     "inputSchema": _schema({"project": _project, "kind": {"type": "string"}, "status": {"type": "string"},
                             "limit": {"type": "integer", "minimum": 1, "maximum": 200}})},
    {"name": "brain_record",
     "description": "Create or update a durable record (decision, feature, bug, requirement, learning, doc, "
                    "architecture…). Same key updates the record and keeps the previous version. Record what "
                    "changed, why, consequences and actual validation.",
     "inputSchema": _schema({"project": _project, "kind": {"type": "string", "enum": KINDS},
                             "title": {"type": "string"}, "body": {"type": "string"}, "key": {"type": "string"},
                             "status": {"type": "string"}, "importance": {"type": "number", "minimum": 0, "maximum": 1},
                             "tags": {"type": "array", "items": {"type": "string"}},
                             "data": {"type": "object"}}, ["kind", "title", "body"])},
    {"name": "brain_update_status",
     "description": "Update a record's status, e.g. feature in_progress/implemented/blocked, bug fixed, "
                    "decision superseded. Adds a history event.",
     "inputSchema": _schema({"project": _project, "ref": {"type": "string"}, "status": {"type": "string"},
                             "note": {"type": "string"}}, ["ref", "status"])},
    {"name": "brain_log_event",
     "description": "Append an event to project history, e.g. an implementation result with files changed "
                    "and validation run.",
     "inputSchema": _schema({"project": _project, "type": {"type": "string"}, "summary": {"type": "string"},
                             "data": {"type": "object"}, "records": {"type": "array", "items": {"type": "string"}},
                             "workflow_id": {"type": "string"}}, ["type", "summary"])},
    {"name": "brain_relate",
     "description": "Relate two records (depends_on, implements, supersedes, relates_to, blocks, mitigates…).",
     "inputSchema": _schema({"project": _project, "src": {"type": "string"}, "dst": {"type": "string"},
                             "type": {"type": "string"}}, ["src", "dst", "type"])},
    {"name": "brain_status", "description": "Brain status and counts.", "inputSchema": _schema({})},
    {"name": "brain_remember",
     "description": "Compatibility alias of brain_record (Open-Brain V1): type/title/content.",
     "inputSchema": _schema({"project": _project, "type": {"type": "string"}, "title": {"type": "string"},
                             "content": {"type": "string"}, "tags": {"type": "array", "items": {"type": "string"}},
                             "importance": {"type": "number"}, "related": {"type": "array", "items": {"type": "string"}},
                             "status": {"type": "string"}}, ["type", "title", "content"])},
]
TOOL_NAMES = {tool["name"]: set(tool["inputSchema"]["properties"]) for tool in TOOLS}


class Backend(Protocol):
    def status(self) -> dict: ...
    def context(self, project: str | None, token_budget: int) -> dict: ...
    def relevant_context(self, project: str | None, task: str, token_budget: int, knowledge: bool) -> dict: ...
    def search(self, project: str | None, query: str, scope: str, kinds: list | None, limit: int,
               token_budget: int) -> dict: ...
    def knowledge(self, query: str, collections: list | None, limit: int, token_budget: int) -> dict: ...
    def get(self, project: str | None, ref: str) -> dict: ...
    def list(self, project: str | None, kind: str | None, status: str | None, limit: int) -> list: ...
    def record(self, project: str | None, payload: dict) -> dict: ...
    def update_status(self, project: str | None, ref: str, status: str, note: str) -> dict: ...
    def log_event(self, project: str | None, payload: dict) -> dict: ...
    def relate(self, project: str | None, src: str, dst: str, type: str) -> dict: ...


def render_records(rows: list[dict]) -> str:
    if not rows:
        return "No records."
    lines = []
    for row in rows:
        status = row.get("status") or ""
        lines.append(f"- [{row['kind']}|{status}] {row['title']}  (key: {row['key']})")
    return "\n".join(lines)


def render_record(row: dict) -> str:
    lines = [f"# {row['title']}", f"kind: {row['kind']} · status: {row.get('status')} · key: {row['key']} · "
             f"version: {row.get('version', 1)} · source: {row.get('source', '')}"]
    if row.get("tags"):
        lines.append("tags: " + ", ".join(row["tags"]))
    lines.append("")
    lines.append(row.get("body") or "")
    data = {k: v for k, v in (row.get("data") or {}).items() if k not in ("kb_refs",)}
    if data:
        lines.append("\ndata: " + json.dumps(data, ensure_ascii=False)[:1500])
    if row.get("data", {}).get("kb_refs"):
        lines.append("\nknowledge references:")
        lines.extend(f"- {ref.get('module', '')} {ref.get('section', ref.get('document', ''))}"
                     for ref in row["data"]["kb_refs"][:8])
    if row.get("relations"):
        lines.append("\nrelations:")
        for rel in row["relations"]:
            arrow = "→" if rel["direction"] == "out" else "←"
            lines.append(f"- {rel['type']} {arrow} [{rel['kind']}] {rel['title']} ({rel['key']})")
    return "\n".join(lines)


def call_tool(backend: Backend, name: str, args: dict, default_project: str | None = None) -> str:
    if name not in TOOL_NAMES:
        raise ValueError(f"Unknown tool: {name}")
    unknown = set(args) - TOOL_NAMES[name]
    if unknown:
        raise ValueError(f"Unknown arguments: {', '.join(sorted(unknown))}")
    project = args.get("project") or default_project
    if name == "brain_status":
        return json.dumps(backend.status(), ensure_ascii=False, default=str)
    if name == "brain_context":
        return backend.context(project, int(args.get("token_budget") or 800))["context"]
    if name == "brain_relevant_context":
        return backend.relevant_context(project, args["task"], int(args.get("token_budget") or 1500),
                                        bool(args.get("include_knowledge", True)))["context"]
    if name == "brain_search":
        kinds = args.get("kinds") or args.get("types")
        return backend.search(project, args["query"], args.get("scope") or "project", kinds,
                              int(args.get("limit") or 8), int(args.get("token_budget") or 1000))["context"]
    if name == "brain_knowledge":
        return backend.knowledge(args["query"], args.get("collections"), int(args.get("limit") or 5),
                                 int(args.get("token_budget") or 900))["context"]
    if name == "brain_get":
        return render_record(backend.get(project, args["ref"]))
    if name == "brain_list":
        return render_records(backend.list(project, args.get("kind"), args.get("status"),
                                           int(args.get("limit") or 50)))
    if name in ("brain_record", "brain_remember"):
        payload = {key: value for key, value in args.items() if key != "project"}
        if name == "brain_remember":
            payload = {"kind": payload.pop("type"), "title": payload.pop("title"), "body": payload.pop("content"),
                       **payload}
        return json.dumps(backend.record(project, payload), ensure_ascii=False, default=str)
    if name == "brain_update_status":
        return json.dumps(backend.update_status(project, args["ref"], args["status"], args.get("note") or ""),
                          ensure_ascii=False, default=str)
    if name == "brain_log_event":
        payload = {key: value for key, value in args.items() if key != "project"}
        return json.dumps(backend.log_event(project, payload), ensure_ascii=False, default=str)
    if name == "brain_relate":
        return json.dumps(backend.relate(project, args["src"], args["dst"], args["type"]), ensure_ascii=False)
    raise ValueError(f"Unhandled tool: {name}")


def handle(message: Any, backend: Backend, *, instructions: str, server_name: str = "brain",
           default_project: str | None = None, tools: list[dict] | None = None) -> dict | None:
    """Handle one JSON-RPC message; return the response, or None for notifications."""
    if not isinstance(message, dict):
        return {"jsonrpc": "2.0", "id": None, "error": {"code": -32600, "message": "Invalid request"}}
    identifier, method = message.get("id"), message.get("method")
    if identifier is None:
        return None

    def reply(result=None, error=None):
        response = {"jsonrpc": "2.0", "id": identifier}
        response["error" if error is not None else "result"] = error if error is not None else result
        return response

    try:
        if method == "initialize":
            requested = (message.get("params") or {}).get("protocolVersion") or PROTOCOL_VERSION
            return reply({"protocolVersion": requested, "capabilities": {"tools": {"listChanged": False}},
                          "serverInfo": {"name": server_name, "version": "2.0.0"}, "instructions": instructions})
        if method == "ping":
            return reply({})
        if method == "tools/list":
            return reply({"tools": tools or TOOLS})
        if method == "tools/call":
            params = message.get("params") or {}
            args = params.get("arguments") or {}
            if not isinstance(args, dict):
                raise ValueError("arguments must be an object")
            try:
                text = call_tool(backend, params.get("name"), args, default_project)
                return reply({"content": [{"type": "text", "text": text}], "isError": False})
            except Exception as exc:  # Tool errors are results, so the agent can recover.
                return reply({"content": [{"type": "text", "text": f"{type(exc).__name__}: {exc}"}],
                              "isError": True})
        return reply(error={"code": -32601, "message": f"Method not found: {method}"})
    except Exception as exc:
        return reply(error={"code": -32602, "message": str(exc)})


SERVER_INSTRUCTIONS = """This Brain holds durable project memory (decisions, architecture, features, bugs,
constraints, history) and reusable AI-engineering knowledge. At session start call brain_context.
Before planning or editing for a task call brain_relevant_context with the task. Retrieved memory is
context, not proof: verify source files before editing. After meaningful work record what changed, why,
consequences and the validation actually run (brain_record / brain_update_status / brain_log_event).
Never store secrets."""
