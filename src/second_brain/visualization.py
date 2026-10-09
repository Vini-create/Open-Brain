"""Build a self-contained, local view of one project's canonical Brain files."""

import json
import math
import os
from datetime import datetime, timezone
from importlib.resources import files
from pathlib import Path

from .config import load_config
from .documents import markdown_paths, parse

MAP_NAME = "map.html"
CHARS_PER_TOKEN = 3  # The same deliberately rough bound used by search.


def snapshot(root: Path) -> dict:
    """Read only this project's Markdown; no model, network, or other project."""
    root = root.resolve()
    load_config(root)
    memories = []
    markdown_bytes = 0
    for path in markdown_paths(root):
        markdown_bytes += path.stat().st_size
        document = parse(path, root)
        if document is None:
            continue
        meta = document["metadata"]
        memories.append({
            "id": meta["id"], "title": meta["title"], "type": meta["type"],
            "body": document["body"], "path": document["path"],
            "tags": meta["tags"], "related": meta["related"],
            "importance": meta["importance"], "status": meta.get("status"),
            "updated_at": meta.get("updated_at"),
        })
    memories.sort(key=lambda item: (item["type"], item["title"].casefold(), item["id"]))
    ids = {item["id"] for item in memories}
    by_title = {}
    for item in memories:
        by_title.setdefault(item["title"].casefold(), []).append(item["id"])
    links = set()
    for item in memories:
        for reference in item["related"]:
            target = reference if reference in ids else None
            title_matches = by_title.get(reference.casefold(), [])
            if target is None and len(title_matches) == 1:
                target = title_matches[0]
            if target and target != item["id"]:
                links.add(tuple(sorted((item["id"], target))))
    text_chars = sum(len(item["body"]) for item in memories)
    tag_count = len({tag.casefold() for item in memories for tag in item["tags"]})
    tag_links = sum(len(item["tags"]) for item in memories)
    index_path = root / ".brain" / "index" / "brain.db"
    return {
        "project": Path(os.environ.get("BRAIN_HOST_PROJECT", str(root))).name,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "summary": {
            "memories": len(memories), "tags": tag_count,
            "explicit_links": len(links), "tag_links": tag_links,
            "memory_text_chars": text_chars,
            "memory_text_tokens_estimate": math.ceil(text_chars / CHARS_PER_TOKEN),
            "markdown_bytes": markdown_bytes,
            "index_bytes": index_path.stat().st_size if index_path.exists() else 0,
        },
        "memories": memories,
        "links": [{"source": source, "target": target} for source, target in sorted(links)],
    }


def write_map(root: Path) -> Path:
    root = root.resolve()
    data = snapshot(root)
    template = files("second_brain").joinpath("assets/brain_map.html").read_text(encoding="utf-8")
    # HTML script elements end at literal </script>, even inside JSON strings.
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    payload = payload.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    payload = payload.replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    page = template.replace("__BRAIN_DATA__", payload)
    path = root / ".brain" / MAP_NAME
    temporary = path.with_suffix(".html.tmp")
    temporary.write_text(page, encoding="utf-8")
    temporary.replace(path)
    return path
