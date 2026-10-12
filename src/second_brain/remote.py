"""Client side of the Brain service: HTTP client and backends for the CLI and stdio MCP.

Stdlib only, so the CLI keeps working without the server dependencies installed.

* ``RemoteBackend``  — a project linked to a Brain service (source of truth).
* ``LocalBackend``   — the V1 standalone ``.brain/`` (Markdown + SQLite).
* ``LinkedBackend``  — remote first; reads fall back to the local mirror and writes are
  queued in ``.brain/outbox.jsonl`` when the service is unreachable.
"""

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_URL = "http://localhost:8020"


class Unreachable(RuntimeError):
    """The Brain service could not be contacted."""


class BrainHTTPError(RuntimeError):
    def __init__(self, status: int, detail: str):
        super().__init__(f"Brain service error {status}: {detail}")
        self.status = status
        self.detail = detail


class BrainClient:
    def __init__(self, url: str | None = None, *, token: str | None = None, source: str = "cli",
                 timeout: float = 30):
        self.url = (url or os.environ.get("BRAIN_URL") or DEFAULT_URL).rstrip("/")
        self.token = token if token is not None else os.environ.get("BRAIN_API_TOKEN", "")
        self.source = source
        self.timeout = timeout

    def request(self, method: str, path: str, payload=None, params: dict | None = None):
        query = {k: v for k, v in (params or {}).items() if v not in (None, "", [])}
        url = self.url + path + ("?" + urllib.parse.urlencode(query, doseq=True) if query else "")
        data = json.dumps(payload, ensure_ascii=False).encode() if payload is not None else None
        request = urllib.request.Request(url, data=data, method=method)
        request.add_header("Accept", "application/json")
        request.add_header("X-Brain-Source", self.source)
        if data is not None:
            request.add_header("Content-Type", "application/json")
        if self.token:
            request.add_header("Authorization", f"Bearer {self.token}")
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                body = response.read()
                return json.loads(body) if body else None
        except urllib.error.HTTPError as exc:
            try:
                detail = json.loads(exc.read() or b"{}").get("detail", exc.reason)
            except ValueError:
                detail = exc.reason
            raise BrainHTTPError(exc.code, str(detail)) from exc
        except (urllib.error.URLError, ConnectionError, TimeoutError, OSError) as exc:
            raise Unreachable(f"Brain service unreachable at {self.url}: {getattr(exc, 'reason', exc)}") from exc

    def get(self, path, **params):
        return self.request("GET", path, params=params)

    def post(self, path, payload=None, **params):
        return self.request("POST", path, payload, params)

    def put(self, path, payload):
        return self.request("PUT", path, payload)

    def patch(self, path, payload):
        return self.request("PATCH", path, payload)


def _quote(value: str) -> str:
    return urllib.parse.quote(str(value), safe="")


class RemoteBackend:
    def __init__(self, client: BrainClient, project: str | None):
        self.client = client
        self.project = project

    def _p(self, project):
        project = project or self.project
        if not project:
            raise ValueError("No project selected. Run 'brain link <project>' or pass project.")
        return f"/v1/projects/{_quote(project)}"

    def status(self):
        return self.client.get("/healthz")

    def context(self, project, token_budget):
        return self.client.get(self._p(project) + "/context", token_budget=token_budget)

    def relevant_context(self, project, task, token_budget, knowledge):
        return self.client.post(self._p(project) + "/relevant-context",
                                {"task": task, "token_budget": token_budget, "include_knowledge": knowledge})

    def search(self, project, query, scope, kinds, limit, token_budget):
        payload = {"query": query, "scope": scope, "kinds": kinds, "limit": limit, "token_budget": token_budget}
        if scope == "knowledge":
            return self.client.post("/v1/knowledge/search", payload)
        return self.client.post(self._p(project) + "/search", payload)

    def knowledge(self, query, collections, limit, token_budget):
        return self.client.post("/v1/knowledge/search", {"query": query, "collections": collections,
                                                         "limit": limit, "token_budget": token_budget})

    def get(self, project, ref):
        return self.client.get(self._p(project) + "/records/" + _quote(ref))

    def list(self, project, kind, status, limit):
        return self.client.get(self._p(project) + "/records", kind=kind, status=status, limit=limit)

    def record(self, project, payload):
        return self.client.put(self._p(project) + "/records", payload)

    def update_status(self, project, ref, status, note):
        return self.client.patch(self._p(project) + "/records/" + _quote(ref) + "/status",
                                 {"status": status, "note": note})

    def log_event(self, project, payload):
        return self.client.post(self._p(project) + "/events", payload)

    def relate(self, project, src, dst, type):
        return self.client.post(self._p(project) + "/relations", {"src": src, "dst": dst, "type": type})


# ── standalone local Brain (V1) ─────────────────────────────────────────────

class LocalBackend:
    """Operations over the V1 local ``.brain/`` (also used for the offline mirror)."""

    def __init__(self, root: Path):
        self.root = Path(root).resolve()

    def _docs(self):
        from .documents import markdown_paths, parse

        for path in markdown_paths(self.root):
            doc = parse(path, self.root)
            if doc:
                yield doc

    def status(self):
        from .config import load_config
        from .storage import stats

        return stats(self.root, load_config(self.root))

    def context(self, project, token_budget):
        from .core import CHARS_PER_TOKEN

        lines = [f"# Project: {self.root.name}"]
        brain_md = self.root / ".brain" / "BRAIN.md"
        if brain_md.exists():
            text = brain_md.read_text(encoding="utf-8")
        else:
            for name in ("idea.md", "overview.md", "goals.md"):
                path = self.root / ".brain" / "project" / name
                if path.exists():
                    lines.append(path.read_text(encoding="utf-8").strip())
            groups: dict[str, list[str]] = {}
            for doc in self._docs():
                meta = doc["metadata"]
                if meta["type"] in ("decision", "architecture", "feature", "bug", "constraint", "rule", "next-step"):
                    status = f" [{meta.get('status')}]" if meta.get("status") not in (None, "active") else ""
                    groups.setdefault(meta["type"], []).append(f"- {meta['title']}{status}")
            for kind, items in groups.items():
                lines.append(f"\n## {kind}\n" + "\n".join(items[:12]))
            text = "\n".join(lines)
        return {"context": text[:token_budget * CHARS_PER_TOKEN]}

    def relevant_context(self, project, task, token_budget, knowledge):
        context = self.context(project, max(150, token_budget // 4))["context"]
        found = self.search(project, task, "project", None, 8, max(100, token_budget - token_budget // 4))
        return {"context": context + "\n\n## Relevant project memory\n" + found["context"]}

    def search(self, project, query, scope, kinds, limit, token_budget):
        from .core import search

        if scope == "knowledge":
            return RemoteBackend(BrainClient(), None).knowledge(query, None, limit, token_budget)
        local_kinds = [("next-step" if kind == "next_step" else kind) for kind in kinds] if kinds else None
        return search(self.root, query, types=local_kinds, limit=limit, token_budget=token_budget)

    def knowledge(self, query, collections, limit, token_budget):
        return RemoteBackend(BrainClient(), None).knowledge(query, collections, limit, token_budget)

    def get(self, project, ref):
        for doc in self._docs():
            meta = doc["metadata"]
            if ref in (meta["id"], meta.get("key"), meta["title"]) or ref.lower() == meta["title"].lower():
                return {"kind": meta["type"], "key": meta.get("key", meta["id"]), "title": meta["title"],
                        "status": meta.get("status"), "body": doc["body"], "tags": meta.get("tags", []),
                        "source": meta.get("source", "local"), "data": {}, "relations": [
                            {"type": "relates_to", "direction": "out", "kind": "", "title": r, "key": r}
                            for r in meta.get("related", [])]}
        raise ValueError(f"Record not found: {ref}")

    def list(self, project, kind, status, limit):
        kinds = {("next-step" if k == "next_step" else k) for k in kind.split(",")} if kind else None
        rows = []
        for doc in self._docs():
            meta = doc["metadata"]
            if (kinds and meta["type"] not in kinds) or (status and meta.get("status") not in status.split(",")):
                continue
            rows.append({"kind": meta["type"], "key": meta.get("key", meta["id"]), "title": meta["title"],
                         "status": meta.get("status") or "active", "importance": meta.get("importance", 0.5)})
        return sorted(rows, key=lambda r: -r["importance"])[:limit]

    def record(self, project, payload):
        from .core import remember

        kind = payload.get("kind", "")
        return remember(self.root, type="next-step" if kind == "next_step" else kind, title=payload.get("title", ""),
                        content=payload.get("body", ""), tags=payload.get("tags"),
                        importance=payload.get("importance"), status=payload.get("status"),
                        related=payload.get("related"))

    def update_status(self, project, ref, status, note):
        record = self.get(project, ref)
        result = self.record(project, {"kind": record["kind"], "title": record["title"],
                                       "body": record["body"].split("\n", 2)[-1].strip() or record["title"],
                                       "status": status})
        self.log_event(project, {"type": "record.status_changed", "summary": f"{record['title']}: {status} {note}"})
        return result

    def log_event(self, project, payload):
        path = self.root / ".brain" / "history" / "events.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        event = {"timestamp": datetime.now(timezone.utc).isoformat(), **payload}
        with path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(event, ensure_ascii=False) + "\n")
        return {"queued": False, "stored": str(path.relative_to(self.root))}

    def relate(self, project, src, dst, type):
        raise ValueError("Typed relations require a linked Brain service")


# ── linked project with offline fallback ────────────────────────────────────

class LinkedBackend:
    WRITES = {"record", "update_status", "log_event", "relate"}

    def __init__(self, root: Path, remote: RemoteBackend):
        self.root = Path(root)
        self.remote = remote
        self.local = LocalBackend(root)
        self.outbox = self.root / ".brain" / "outbox.jsonl"

    def __getattr__(self, name):
        remote_method = getattr(self.remote, name)

        def call(*args):
            try:
                return remote_method(*args)
            except Unreachable:
                if name in self.WRITES:
                    entry = {"op": name, "args": list(args), "queued_at": datetime.now(timezone.utc).isoformat()}
                    with self.outbox.open("a", encoding="utf-8") as file:
                        file.write(json.dumps(entry, ensure_ascii=False) + "\n")
                    return {"queued": True, "detail": "Brain service offline; run 'brain sync' later"}
                if name in ("knowledge",):
                    raise
                return getattr(self.local, name)(*args)
        return call


CREDENTIALS = "credentials.json"


def project_token(root: Path) -> str | None:
    """Project access token from .brain/credentials.json (kept out of Git by the bundle)."""
    path = Path(root) / ".brain" / CREDENTIALS
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("token") or None
    except ValueError:
        return None


def remote_settings(root: Path) -> dict | None:
    path = Path(root) / ".brain" / "config.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8")).get("remote")


def backend_for(root: Path, *, source: str = "cli"):
    remote = remote_settings(root)
    if remote and remote.get("project"):
        client = BrainClient(remote.get("url"), token=project_token(root), source=source)
        return LinkedBackend(root, RemoteBackend(client, remote["project"]))
    return LocalBackend(root)


def flush_outbox(root: Path, backend: RemoteBackend) -> dict:
    outbox = Path(root) / ".brain" / "outbox.jsonl"
    if not outbox.exists():
        return {"sent": 0, "failed": 0}
    sent, failed, keep = 0, 0, []
    for line in outbox.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        entry = json.loads(line)
        try:
            getattr(backend, entry["op"])(*entry["args"])
            sent += 1
        except Unreachable:
            keep.append(line)
            failed += 1
        except BrainHTTPError as exc:
            # A rejected write will never succeed; keep a record of it instead of retrying forever.
            rejected = Path(root) / ".brain" / "history" / "outbox-rejected.jsonl"
            rejected.parent.mkdir(parents=True, exist_ok=True)
            with rejected.open("a", encoding="utf-8") as file:
                file.write(json.dumps({**entry, "error": str(exc)}, ensure_ascii=False) + "\n")
            failed += 1
    if keep:
        outbox.write_text("\n".join(keep) + "\n", encoding="utf-8")
    else:
        outbox.unlink()
    return {"sent": sent, "failed": failed, "pending": len(keep)}


MIRROR_MANIFEST = "mirror.json"


def write_mirror(root: Path, export: dict) -> dict:
    """Materialize a linked project's records as readable, indexable Markdown under ``.brain/``."""
    from .config import TYPES
    from .documents import render

    brain = Path(root) / ".brain"
    manifest_path = brain / MIRROR_MANIFEST
    previous = set(json.loads(manifest_path.read_text()).get("files", [])) if manifest_path.exists() else set()
    written = []
    for record in export["records"]:
        kind = "next-step" if record["kind"] == "next_step" else record["kind"]
        if kind not in TYPES:
            continue
        name = re.sub(r"[^a-z0-9._-]+", "-", record["key"].lower()).strip("-")[:120] + ".md"
        relative = f"knowledge/{TYPES[kind]}/{name}"
        meta = {"id": "mirror-" + re.sub(r"[^a-z0-9-]+", "-", record["key"].lower())[:100],
                "type": kind, "title": record["title"], "tags": record.get("tags") or [],
                "importance": float(record.get("importance") or 0.5), "status": record.get("status"),
                "key": record["key"], "remote_id": record["id"], "source": record.get("source"),
                "updated_at": record.get("updated_at"), "mirror": True}
        body = f"# {record['title']}\n\n{record.get('body') or record['title']}"
        path = brain / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        content = render(meta, body)
        if not path.exists() or path.read_text(encoding="utf-8") != content:
            path.write_text(content, encoding="utf-8")
        written.append(relative)
    removed = 0
    for relative in previous - set(written):
        path = brain / relative
        if path.exists():
            path.unlink()
            removed += 1
    manifest_path.write_text(json.dumps({"project": str(export["project"]["id"]), "files": sorted(written),
                                         "synced_at": datetime.now(timezone.utc).isoformat()}, indent=1) + "\n")
    return {"written": len(written), "removed": removed}
