import hashlib
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

import yaml

from .config import TYPES


def now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def slug(value: str) -> str:
    ascii_text = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", ascii_text).strip("-")[:65] or "memory"


def document_id(kind: str, title: str) -> str:
    return f"{kind}-{slug(title)}-{hashlib.sha256(title.casefold().encode()).hexdigest()[:8]}"


def render(meta: dict, body: str) -> str:
    return "---\n" + yaml.safe_dump(meta, allow_unicode=True, sort_keys=False) + "---\n\n" + body.strip() + "\n"


def parse(path: Path, root: Path) -> dict | None:
    raw = path.read_text(encoding="utf-8")
    relative = path.relative_to(root).as_posix()
    if raw.startswith("---\n"):
        parts = raw.split("---\n", 2)
        if len(parts) < 3:
            raise ValueError(f"Incomplete front matter: {relative}")
        meta = yaml.safe_load(parts[1]) or {}
        if not isinstance(meta, dict):
            raise ValueError(f"Invalid front matter: {relative}")
        body = parts[2].strip()
    else:
        meta = {}
        body = raw.strip()
    if not body or not any(line.strip() and not line.lstrip().startswith("#") for line in body.splitlines()):
        return None
    project_kind = path.stem if path.parent.name == "project" else None
    if project_kind:
        meta.setdefault("id", f"project-{project_kind}")
        meta.setdefault("type", "project")
        meta.setdefault("title", {"idea": "Project idea", "overview": "Project overview", "goals": "Goals"}.get(project_kind, project_kind.replace("-", " ").title()))
        meta.setdefault("importance", 0.9)
    required = ("id", "type", "title")
    if any(not isinstance(meta.get(key), str) or not meta[key].strip() for key in required):
        raise ValueError(f"Required fields id, type, and title are missing: {relative}")
    if meta["type"] not in {*TYPES, "project"}:
        raise ValueError(f"Invalid type in {relative}: {meta['type']}")
    importance = float(meta.get("importance", 0.5))
    if not 0 <= importance <= 1:
        raise ValueError(f"importance must be between 0 and 1: {relative}")
    meta["importance"] = importance
    for field in ("tags", "related"):
        value = meta.get(field) or []
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            raise ValueError(f"{field} must be a list of strings: {relative}")
        meta[field] = value
    for field in ("created_at", "updated_at"):
        if field in meta:
            meta[field] = str(meta[field])
    return {"metadata": meta, "body": body, "path": relative, "hash": hashlib.sha256(raw.encode()).hexdigest()}


def markdown_paths(root: Path):
    for folder in (root / ".brain" / "project", root / ".brain" / "knowledge"):
        if folder.exists():
            yield from sorted(folder.rglob("*.md"))


def chunks(body: str, max_chars: int = 1300, overlap: int = 160) -> list[str]:
    if len(body) <= max_chars:
        return [body]
    result = []
    position = 0
    while position < len(body):
        end = min(position + max_chars, len(body))
        if end < len(body):
            boundary = body.rfind("\n\n", position + max_chars // 2, end)
            if boundary > position:
                end = boundary
        result.append(body[position:end].strip())
        if end == len(body):
            break
        position = max(position + 1, end - overlap)
    return [item for item in result if item]
