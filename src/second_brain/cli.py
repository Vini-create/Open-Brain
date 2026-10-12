import argparse
import json
import os
import sys
from pathlib import Path

from .config import load_config
from .core import initialize, remember, search
from .embedding import download_model
from .mcp import serve
from .storage import index, stats

LIST_ALIASES = {"decisions": "decision", "architecture": "architecture,component", "features": "feature",
                "bugs": "bug", "requirements": "requirement", "risks": "risk", "next-steps": "next_step",
                "constraints": "constraint,rule"}


def parser() -> argparse.ArgumentParser:
    app = argparse.ArgumentParser(prog="brain", description="Persistent project memory and knowledge for coding agents")
    commands = app.add_subparsers(dest="command", required=True)

    def command(name, **kwargs):
        sub = commands.add_parser(name, **kwargs)
        sub.add_argument("--project", type=Path, default=Path.cwd(), help="Project directory (default: cwd)")
        return sub

    init = command("init", help="Initialize .brain in a project")
    init.add_argument("--idea", help="Initial description of the project")
    for name in ("status", "index", "rebuild", "map", "mcp", "unlink"):
        command(name)
    find = command("search", help="Retrieve relevant context")
    find.add_argument("query")
    find.add_argument("--type", dest="types", action="append")
    find.add_argument("--tag", dest="tags", action="append")
    find.add_argument("--limit", type=int)
    find.add_argument("--token-budget", type=int)
    find.add_argument("--scope", choices=["project", "knowledge", "all"], default="project")
    find.add_argument("--json", action="store_true")
    save = command("remember", help="Save durable project knowledge")
    save.add_argument("--type", required=True)
    save.add_argument("--title", required=True)
    save.add_argument("--content", help="Content; reads stdin if omitted")
    save.add_argument("--tag", dest="tags", action="append")
    save.add_argument("--related", action="append")
    save.add_argument("--importance", type=float)
    save.add_argument("--status")
    save.add_argument("--key", help="Stable key (linked projects)")
    model = command("model", help="Manage the local embedding model")
    model.add_argument("action", choices=["download"])

    link = command("link", help="Link this directory to a project in the Brain service")
    link.add_argument("target", help="Project id or slug in the Brain service")
    link.add_argument("--url", help="Brain service URL (default $BRAIN_URL or http://localhost:8020)")
    link.add_argument("--create", action="store_true", help="Create the project if it does not exist")
    link.add_argument("--name", help="Project name when creating")
    link.add_argument("--description", default="")
    link.add_argument("--push-local", action="store_true", help="Upload existing local memories to the service")
    command("sync", help="Send queued offline writes and refresh the local mirror")
    context = command("context", help="Compact project context, or the minimal context for a task")
    context.add_argument("--task")
    context.add_argument("--budget", type=int, default=1200)
    context.add_argument("--no-knowledge", action="store_true")
    context.add_argument("--json", action="store_true")
    listing = command("list", help="List records by kind (decision, feature, bug, ...)")
    listing.add_argument("kind", nargs="?")
    listing.add_argument("--status")
    listing.add_argument("--limit", type=int, default=100)
    listing.add_argument("--json", action="store_true")
    for alias in LIST_ALIASES:
        sub = command(alias, help=f"List {alias}")
        sub.add_argument("--status")
        sub.add_argument("--limit", type=int, default=100)
        sub.add_argument("--json", action="store_true")
    show = command("show", help="Show a record by key, id or title")
    show.add_argument("ref")
    show.add_argument("--json", action="store_true")
    feature = command("feature", help="Show a feature or update its status")
    feature.add_argument("name")
    feature.add_argument("--status", choices=["idea", "planned", "in_progress", "implemented", "blocked", "deprecated"])
    feature.add_argument("--note", default="")
    feature.add_argument("--body", help="Create the feature with this description if missing")
    event = command("event", help="Append an event to the project history")
    event.add_argument("summary")
    event.add_argument("--type", default="note")
    event.add_argument("--data", help="JSON object")
    projects = command("projects", help="List projects in the Brain service")
    projects.add_argument("--url")
    kb = command("kb", help="Knowledge base (reusable technical knowledge)")
    kb.add_argument("action", choices=["ingest", "search", "list"])
    kb.add_argument("value", nargs="?", help="Directory for ingest, query for search")
    kb.add_argument("--collection", default="ai-engineering")
    kb.add_argument("--title")
    kb.add_argument("--limit", type=int, default=5)
    kb.add_argument("--budget", type=int, default=900)
    kb.add_argument("--json", action="store_true")
    cost = command("cost", help="LLM usage and cost report")
    cost.add_argument("--workflow")
    cost.add_argument("--task")
    cost.add_argument("--all", action="store_true", help="All projects")
    cost.add_argument("--group-by", default="component", choices=["component", "model", "task", "workflow_id"])
    cost.add_argument("--json", action="store_true")
    return app


def _print(value, as_json: bool, text: str | None = None) -> None:
    if as_json:
        print(json.dumps(value, ensure_ascii=False, indent=2, default=str))
    else:
        print(text if text is not None else json.dumps(value, ensure_ascii=False, indent=2, default=str))


def _write_config_remote(root: Path, remote: dict | None) -> None:
    path = root / ".brain" / "config.json"
    config = json.loads(path.read_text(encoding="utf-8"))
    if remote is None:
        config.pop("remote", None)
    else:
        config["remote"] = remote
    path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _linked_remote(root: Path):
    from .remote import BrainClient, RemoteBackend, remote_settings

    remote = remote_settings(root)
    if not remote:
        raise ValueError("This project is not linked to a Brain service. Run 'brain link <project>'.")
    from .remote import project_token

    return RemoteBackend(BrainClient(remote.get("url"), token=project_token(root)), remote["project"]), remote


def _sync(root: Path) -> dict:
    from .remote import flush_outbox, write_mirror

    backend, remote = _linked_remote(root)
    flushed = flush_outbox(root, backend)
    export = backend.client.get(f"/v1/projects/{remote['project']}/export")
    mirror = write_mirror(root, export)
    context = backend.context(None, 1500)["context"]
    (root / ".brain" / "BRAIN.md").write_text(
        "<!-- Generated by `brain sync`; edit the Brain, not this file. -->\n\n" + context + "\n", encoding="utf-8")
    result = {"outbox": flushed, "mirror": mirror}
    try:
        result["index"] = index(root, load_config(root))
    except RuntimeError as exc:  # Model not downloaded: the mirror is still readable Markdown.
        result["index"] = {"skipped": str(exc)}
    return result


def _push_local(root: Path, backend) -> int:
    from .documents import markdown_paths, parse

    pushed = 0
    for path in markdown_paths(root):
        doc = parse(path, root)
        if not doc or doc["metadata"].get("mirror"):
            continue
        meta = doc["metadata"]
        kind = {"project": "doc", "next-step": "next_step"}.get(meta["type"], meta["type"])
        body = doc["body"].split("\n", 1)[1].strip() if doc["body"].startswith("# ") else doc["body"]
        backend.record(None, {"kind": kind, "title": meta["title"], "body": body or meta["title"],
                              "tags": meta.get("tags", []), "importance": meta.get("importance", 0.5),
                              "key": f"local:{meta['id']}"})
        pushed += 1
    return pushed


def main() -> None:
    args = parser().parse_args()
    root = args.project.resolve()
    try:
        if args.command == "init":
            result = initialize(root, args.idea)
            display_root = Path(os.environ.get("BRAIN_HOST_PROJECT", str(root)))
            brain_command = os.environ.get("BRAIN_DOCKER_WRAPPER", "brain")
            print(f"Brain initialized at {display_root / '.brain'}")
            print(f"Open {display_root / '.brain' / 'map.html'} in a browser to inspect this project's memory.")
            print(json.dumps(result, ensure_ascii=False, indent=2))
            if result.get("memories") == 0:
                print("Empty, independent Brain created. Read .brain/AGENT_BRAIN.md; fill "
                      f".brain/project/*.md and run {brain_command} index, or use {brain_command} remember. "
                      f"If the model is not cached, run {brain_command} model download once.")
                print("For an existing codebase, ask the agent to audit project memory coverage "
                      "using .brain/AGENT_BRAIN.md, including major modules and retrieval checks.")
                print(f"To share this Brain with Creare and Jarvis, run {brain_command} link <project> --create.")
            else:
                print(f"Brain ready. Use {brain_command} search to retrieve context and "
                      f"{brain_command} remember to update it.")
        elif args.command == "status":
            from .remote import backend_for, remote_settings

            remote = remote_settings(root)
            result = stats(root, load_config(root))
            if remote:
                try:
                    result = {"local_mirror": result, "linked": remote,
                              "project": backend_for(root).context(None, 300)["context"].splitlines()[0]}
                except Exception as exc:
                    result = {"local_mirror": result, "linked": remote, "service": f"unreachable: {exc}"}
            print(json.dumps(result, ensure_ascii=False, indent=2))
        elif args.command == "map":
            from .visualization import write_map
            write_map(root)
            display_root = Path(os.environ.get("BRAIN_HOST_PROJECT", str(root)))
            print(f"Open {display_root / '.brain' / 'map.html'} in a browser to explore this project's Brain.")
        elif args.command in {"index", "rebuild"}:
            print(json.dumps(index(root, load_config(root), rebuild=args.command == "rebuild"), ensure_ascii=False, indent=2))
        elif args.command == "search":
            from .remote import backend_for, remote_settings

            if remote_settings(root) or args.scope != "project":
                backend = backend_for(root)
                result = backend.search(None, args.query, args.scope, args.types, args.limit or 8,
                                        args.token_budget or 1000)
            else:
                result = search(root, args.query, types=args.types, tags=args.tags, limit=args.limit,
                                token_budget=args.token_budget)
            if args.json:
                _print(result, True)
            else:
                print(result["context"], end="" if result["context"].endswith("\n") else "\n")
        elif args.command == "remember":
            from .remote import backend_for, remote_settings

            content = args.content if args.content is not None else sys.stdin.read()
            if not content:
                raise ValueError("Pass --content or send content through stdin")
            if remote_settings(root):
                payload = {"kind": "next_step" if args.type == "next-step" else args.type, "title": args.title,
                           "body": content, "tags": args.tags or [], "importance": args.importance,
                           "status": args.status, "related": args.related, "key": args.key}
                result = backend_for(root).record(None, {k: v for k, v in payload.items() if v is not None})
            else:
                result = remember(root, type=args.type, title=args.title, content=content, tags=args.tags,
                                  importance=args.importance, related=args.related, status=args.status)
            print(json.dumps(result, ensure_ascii=False, indent=2))
        elif args.command == "mcp":
            serve(root)
        elif args.command == "model":
            config = load_config(root)
            download_model(config["embedding"]["model"])
            print(f"Model available locally: {config['embedding']['model']}")
        elif args.command == "link":
            from .remote import BrainClient, BrainHTTPError, RemoteBackend

            if not (root / ".brain" / "config.json").exists():
                initialize(root)
            client = BrainClient(args.url)
            try:
                project = client.get(f"/v1/projects/{args.target}")["project"]
            except BrainHTTPError as exc:
                if exc.status != 404 or not args.create:
                    raise ValueError(f"Project '{args.target}' not found in {client.url}. "
                                     "Use --create to create it.") from exc
                project = client.post("/v1/projects", {"name": args.name or args.target, "slug": args.target,
                                                       "description": args.description, "root_path": str(root)})
            _write_config_remote(root, {"url": client.url, "project": project["id"], "slug": project["slug"],
                                        "name": project["name"]})
            pushed = _push_local(root, RemoteBackend(client, project["id"])) if args.push_local else 0
            result = _sync(root)
            print(f"Linked {root} to Brain project '{project['name']}' ({project['slug']}) at {client.url}.")
            print(json.dumps({"pushed_local": pushed, **result}, ensure_ascii=False, indent=2, default=str))
        elif args.command == "unlink":
            _write_config_remote(root, None)
            print("Unlinked; the local .brain/ keeps working standalone.")
        elif args.command == "sync":
            print(json.dumps(_sync(root), ensure_ascii=False, indent=2, default=str))
        elif args.command == "context":
            from .remote import backend_for

            backend = backend_for(root)
            result = (backend.relevant_context(None, args.task, args.budget, not args.no_knowledge) if args.task
                      else backend.context(None, args.budget))
            _print(result, args.json, result["context"])
        elif args.command == "list" or args.command in LIST_ALIASES:
            from .mcp_tools import render_records

            from .remote import backend_for

            kind = LIST_ALIASES.get(args.command) or args.kind
            rows = backend_for(root).list(None, kind, args.status, args.limit)
            _print(rows, args.json, render_records(rows))
        elif args.command == "show":
            from .mcp_tools import render_record

            from .remote import backend_for

            record = backend_for(root).get(None, args.ref)
            _print(record, args.json, render_record(record))
        elif args.command == "feature":
            from .mcp_tools import render_record

            from .remote import BrainHTTPError, backend_for

            backend = backend_for(root)
            try:
                record = backend.get(None, args.name)
            except (ValueError, BrainHTTPError):
                if not args.body:
                    raise ValueError(f"Feature '{args.name}' not found. Pass --body to create it.") from None
                backend.record(None, {"kind": "feature", "title": args.name, "body": args.body,
                                      "status": args.status or "planned"})
                record = backend.get(None, args.name)
            if args.status and args.status != record.get("status"):
                backend.update_status(None, record["key"], args.status, args.note)
                record = backend.get(None, record["key"])
            print(render_record(record))
        elif args.command == "event":
            from .remote import backend_for

            data = json.loads(args.data) if args.data else {}
            print(json.dumps(backend_for(root).log_event(None, {"type": args.type, "summary": args.summary,
                                                                "data": data}), ensure_ascii=False, indent=2))
        elif args.command == "projects":
            from .remote import BrainClient

            for project in BrainClient(args.url).get("/v1/projects"):
                print(f"{project['slug']:<32} {project['records']:>5} records  {project['name']}  ({project['id']})")
        elif args.command == "kb":
            from .remote import BrainClient

            if args.action == "list":
                for item in BrainClient().get("/v1/knowledge/collections"):
                    state = (item.get("ingest") or {}).get("state", "")
                    print(f"{item['id']:<24} {item['documents']:>4} docs {item['chunks']:>6} chunks  {state}")
            elif args.action == "search":
                if not args.value:
                    raise ValueError("kb search needs a query")
                result = BrainClient().post("/v1/knowledge/search", {
                    "query": args.value, "collections": [args.collection] if args.collection else None,
                    "limit": args.limit, "token_budget": args.budget})
                _print(result, args.json, result["context"])
            else:
                source = Path(args.value or "").expanduser().resolve()
                if not source.is_dir():
                    raise ValueError(f"Knowledge directory not found: {source}")
                print(json.dumps(BrainClient().post("/v1/knowledge/ingest", {
                    "collection": args.collection, "path": str(source), "title": args.title}), indent=2))
        elif args.command == "cost":
            from .remote import BrainClient, remote_settings

            remote = remote_settings(root)
            project = None if args.all or not remote else remote["project"]
            report = BrainClient(remote.get("url") if remote else None).get(
                "/v1/telemetry/report", workflow_id=args.workflow, project=project, task=args.task,
                group_by=args.group_by)
            _print(report, args.json, report["table"])
    except (ValueError, RuntimeError, OSError) as exc:
        print(f"brain: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
