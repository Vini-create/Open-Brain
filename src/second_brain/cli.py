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


def parser() -> argparse.ArgumentParser:
    app = argparse.ArgumentParser(prog="brain", description="Local project memory for coding agents")
    commands = app.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init", help="Initialize .brain in a project")
    init.add_argument("--project", type=Path, default=Path.cwd())
    init.add_argument("--idea", help="Initial description of the project")
    for name in ("status", "index", "rebuild", "mcp"):
        command = commands.add_parser(name)
        command.add_argument("--project", type=Path, default=Path.cwd())
    find = commands.add_parser("search", help="Retrieve relevant context")
    find.add_argument("query")
    find.add_argument("--project", type=Path, default=Path.cwd())
    find.add_argument("--type", dest="types", action="append")
    find.add_argument("--tag", dest="tags", action="append")
    find.add_argument("--limit", type=int)
    find.add_argument("--token-budget", type=int)
    save = commands.add_parser("remember", help="Save durable project knowledge")
    save.add_argument("--project", type=Path, default=Path.cwd())
    save.add_argument("--type", required=True)
    save.add_argument("--title", required=True)
    save.add_argument("--content", help="Content; reads stdin if omitted")
    save.add_argument("--tag", dest="tags", action="append")
    save.add_argument("--related", action="append")
    save.add_argument("--importance", type=float)
    save.add_argument("--status")
    model = commands.add_parser("model", help="Manage the local embedding model")
    model.add_argument("action", choices=["download"])
    model.add_argument("--project", type=Path, default=Path.cwd())
    return app


def main() -> None:
    args = parser().parse_args()
    root = args.project.resolve()
    try:
        if args.command == "init":
            result = initialize(root, args.idea)
            display_root = Path(os.environ.get("BRAIN_HOST_PROJECT", str(root)))
            brain_command = os.environ.get("BRAIN_DOCKER_WRAPPER", "brain")
            print(f"Brain initialized at {display_root / '.brain'}")
            print(json.dumps(result, ensure_ascii=False, indent=2))
            if result.get("memories") == 0:
                print("Empty, independent Brain created. Read .brain/AGENT_BRAIN.md; fill "
                      f".brain/project/*.md and run {brain_command} index, or use {brain_command} remember. "
                      f"If the model is not cached, run {brain_command} model download once.")
            else:
                print(f"Brain ready. Use {brain_command} search to retrieve context and "
                      f"{brain_command} remember to update it.")
        elif args.command == "status":
            print(json.dumps(stats(root, load_config(root)), ensure_ascii=False, indent=2))
        elif args.command in {"index", "rebuild"}:
            print(json.dumps(index(root, load_config(root), rebuild=args.command == "rebuild"), ensure_ascii=False, indent=2))
        elif args.command == "search":
            print(search(root, args.query, types=args.types, tags=args.tags, limit=args.limit,
                         token_budget=args.token_budget)["context"], end="")
        elif args.command == "remember":
            content = args.content if args.content is not None else sys.stdin.read()
            if not content:
                raise ValueError("Pass --content or send content through stdin")
            print(json.dumps(remember(root, type=args.type, title=args.title, content=content,
                                      tags=args.tags, importance=args.importance, related=args.related,
                                      status=args.status), ensure_ascii=False, indent=2))
        elif args.command == "mcp":
            serve(root)
        elif args.command == "model":
            config = load_config(root)
            download_model(config["embedding"]["model"])
            print(f"Model available locally: {config['embedding']['model']}")
    except (ValueError, RuntimeError, OSError) as exc:
        print(f"brain: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
