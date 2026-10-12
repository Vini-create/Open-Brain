"""Project memory: typed records, versions, relations, events and declarative projections.

Records have a stable ``key`` per project. Every write is an idempotent upsert; changed
records keep their previous version. Sources that own a namespace (``creare:*``) publish
their full state through :func:`apply_projection`.
"""

import json
import uuid
from dataclasses import dataclass, field
from typing import Any

from second_brain.documents import chunks as text_chunks

from .embeddings import vector_literal
from .text import normalized, slug

KINDS = (
    "idea", "objective", "problem", "actor", "hypothesis", "question", "decision", "alternative",
    "tradeoff", "requirement", "constraint", "architecture", "component", "dependency", "risk",
    "feature", "bug", "state", "next_step", "experiment", "result", "learning", "implementation",
    "spec", "doc", "rule", "rationale", "project",
)
STATUSES: dict[str, tuple[str, ...]] = {
    "feature": ("idea", "planned", "in_progress", "implemented", "blocked", "deprecated"),
    "bug": ("open", "fixed", "wontfix"),
    "decision": ("proposed", "accepted", "superseded", "rejected"),
    "hypothesis": ("unresolved", "supported", "refuted"),
    "risk": ("open", "mitigated", "accepted"),
    "next_step": ("open", "done", "dropped"),
    "experiment": ("planned", "running", "done", "dropped"),
    "alternative": ("candidate", "frontier", "chosen", "rejected", "invalid"),
    "question": ("open", "answered"),
    "requirement": ("active", "met", "dropped"),
    "tradeoff": ("open", "exploring", "resolved", "accepted_tradeoff"),
    "implementation": ("succeeded", "failed", "partial"),
    "spec": ("draft", "approved", "executed", "superseded"),
}
DEFAULT_STATUS = {"feature": "planned", "bug": "open", "decision": "accepted", "hypothesis": "unresolved",
                  "risk": "open", "next_step": "open", "experiment": "planned", "alternative": "candidate",
                  "question": "open", "tradeoff": "open", "implementation": "succeeded", "spec": "draft"}
RELATION_TYPES = ("depends_on", "implements", "supersedes", "relates_to", "chose", "chosen_over",
                  "blocks", "affects", "derived_from", "mitigates", "validates", "part_of", "cites",
                  "resolves", "caused_by", "constrains")
# Legacy Open-Brain V1 type names.
KIND_ALIASES = {"next-step": "next_step", "decisions": "decision", "features": "feature", "bugs": "bug"}


class BrainError(ValueError):
    """A request the Brain rejects; mapped to HTTP 4xx / MCP tool errors."""


class NotFound(BrainError):
    pass


@dataclass
class RecordIn:
    kind: str
    title: str
    body: str = ""
    key: str | None = None
    status: str | None = None
    importance: float | None = None
    tags: list[str] = field(default_factory=list)
    data: dict[str, Any] = field(default_factory=dict)
    origin: str | None = None

    @classmethod
    def parse(cls, raw: dict) -> "RecordIn":
        allowed = {"kind", "title", "body", "key", "status", "importance", "tags", "data", "origin", "content", "type",
                   "related"}
        unknown = set(raw) - allowed
        if unknown:
            raise BrainError(f"Unknown record fields: {', '.join(sorted(unknown))}")
        kind = raw.get("kind") or raw.get("type") or ""
        return cls(kind=kind, title=raw.get("title", ""), body=raw.get("body", raw.get("content", "")) or "",
                   key=raw.get("key"), status=raw.get("status"), importance=raw.get("importance"),
                   tags=list(raw.get("tags") or []), origin=raw.get("origin"),
                   data={**dict(raw.get("data") or {}), **({"related": list(raw["related"])} if raw.get("related") else {})})

    def validated(self) -> "RecordIn":
        kind = KIND_ALIASES.get(self.kind, self.kind)
        if kind not in KINDS:
            raise BrainError(f"Invalid kind '{self.kind}'. Use one of: {', '.join(KINDS)}")
        title = (self.title or "").replace("\x00", "").strip()
        if not 2 <= len(title) <= 300:
            raise BrainError("title must have 2..300 characters")
        body = (self.body or "").replace("\x00", "").strip()
        if len(body) > 60000:
            raise BrainError("body exceeds 60000 characters")
        if self.status is not None and self.status not in STATUSES.get(kind, ("active", "archived")):
            raise BrainError(f"Invalid status '{self.status}' for {kind}. "
                             f"Use: {', '.join(STATUSES.get(kind, ('active',)))}")
        if self.importance is not None and not 0 <= float(self.importance) <= 1:
            raise BrainError("importance must be between 0 and 1")
        if not all(isinstance(tag, str) and 0 < len(tag) <= 64 for tag in self.tags):
            raise BrainError("tags must be non-empty strings of at most 64 characters")
        key = (self.key or f"{kind}:{slug(title)}").strip()
        if not 2 <= len(key) <= 200:
            raise BrainError("key must have 2..200 characters")
        return RecordIn(kind=kind, title=title, body=body, key=key, status=self.status,
                        importance=None if self.importance is None else float(self.importance),
                        tags=list(dict.fromkeys(tag.strip() for tag in self.tags)), data=self.data,
                        origin=self.origin)


def _uuid(value: str) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(value))
    except ValueError:
        return None


def _json(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


# ── projects ────────────────────────────────────────────────────────────────

def ensure_project(conn, *, name: str, slug_value: str | None = None, external_ref: str | None = None,
                   description: str = "", root_path: str | None = None, workspace: str = "local") -> dict:
    name = (name or "").strip()
    if not 1 <= len(name) <= 200:
        raise BrainError("project name must have 1..200 characters")
    if external_ref:
        row = conn.execute("SELECT * FROM projects WHERE external_ref=%s", (external_ref,)).fetchone()
        if row:
            if row["name"] != name or (description and row["description"] != description):
                row = conn.execute(
                    "UPDATE projects SET name=%s, description=COALESCE(NULLIF(%s,''), description), "
                    "updated_at=now() WHERE id=%s RETURNING *", (name, description, row["id"])).fetchone()
            return row
    base = slug(slug_value or name, 60)
    if slug_value:
        row = conn.execute("SELECT * FROM projects WHERE workspace=%s AND slug=%s", (workspace, base)).fetchone()
        if row:
            return row
    candidate, suffix = base, 2
    while conn.execute("SELECT 1 FROM projects WHERE workspace=%s AND slug=%s", (workspace, candidate)).fetchone():
        candidate, suffix = f"{base}-{suffix}", suffix + 1
    row = conn.execute(
        "INSERT INTO projects(workspace, slug, name, description, external_ref, root_path) "
        "VALUES (%s,%s,%s,%s,%s,%s) RETURNING *",
        (workspace, candidate, name, description, external_ref, root_path)).fetchone()
    refs = [ref for ref in (external_ref, row["slug"]) if ref]
    conn.execute("UPDATE llm_calls SET project_id=%s WHERE project_id IS NULL AND meta->>'project_ref' = ANY(%s)",
                 (row["id"], refs))
    return row


def get_project(conn, ref: str, workspace: str = "local") -> dict:
    ident = _uuid(ref)
    row = (conn.execute("SELECT * FROM projects WHERE id=%s", (ident,)).fetchone() if ident else None) \
        or conn.execute("SELECT * FROM projects WHERE workspace=%s AND slug=%s", (workspace, ref)).fetchone() \
        or conn.execute("SELECT * FROM projects WHERE external_ref=%s", (ref,)).fetchone()
    if not row:
        raise NotFound(f"Project not found: {ref}")
    return row


def list_projects(conn, workspace: str = "local") -> list[dict]:
    return conn.execute(
        "SELECT p.*, (SELECT count(*) FROM records r WHERE r.project_id=p.id AND NOT r.archived) AS records, "
        "(SELECT max(created_at) FROM events e WHERE e.project_id=p.id) AS last_event_at "
        "FROM projects p WHERE workspace=%s ORDER BY updated_at DESC", (workspace,)).fetchall()


# ── records ─────────────────────────────────────────────────────────────────

def _embed_record(conn, embedder, record_id, project_id, kind: str, title: str, body: str, tags: list[str]):
    conn.execute("DELETE FROM record_chunks WHERE record_id=%s", (record_id,))
    parts = text_chunks(body) if body else [""]
    texts = [f"{kind}: {title}\nTags: {', '.join(tags)}\n{part}".strip() for part in parts]
    vectors = embedder.embed(texts)
    with conn.cursor() as cursor:
        cursor.executemany(
            "INSERT INTO record_chunks(record_id, project_id, ordinal, content, tsv, embedding) "
            "VALUES (%s,%s,%s,%s,to_tsvector('simple', %s),%s::vector)",
            [(record_id, project_id, i, part or title, normalized(text), vector_literal(vector))
             for i, (part, text, vector) in enumerate(zip(parts, texts, vectors))])


def resolve_record(conn, project_id, ref: str, *, include_archived: bool = True) -> dict:
    ident = _uuid(ref)
    row = None
    if ident:
        row = conn.execute("SELECT * FROM records WHERE project_id=%s AND id=%s", (project_id, ident)).fetchone()
    row = row or conn.execute("SELECT * FROM records WHERE project_id=%s AND key=%s", (project_id, ref)).fetchone()
    if not row:
        # Friendly lookup by title for CLI/MCP users: "brain feature auth".
        row = conn.execute(
            "SELECT * FROM records WHERE project_id=%s AND lower(title)=lower(%s) "
            "ORDER BY archived, updated_at DESC LIMIT 1", (project_id, ref)).fetchone()
    if not row or (row["archived"] and not include_archived):
        raise NotFound(f"Record not found: {ref}")
    return row


def upsert_record(conn, embedder, project_id, record: RecordIn, *, source: str,
                  respect_status_owner: bool = False) -> dict:
    record = record.validated()
    existing = conn.execute("SELECT * FROM records WHERE project_id=%s AND key=%s",
                            (project_id, record.key)).fetchone()
    if existing is None:
        status = record.status or DEFAULT_STATUS.get(record.kind, "active")
        # ON CONFLICT: two writers may race on the same key; the loser updates instead of failing.
        row = conn.execute(
            "INSERT INTO records(project_id, kind, key, title, body, status, status_source, importance, tags, "
            "source, origin, data) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb) "
            "ON CONFLICT (project_id, key) DO NOTHING RETURNING *",
            (project_id, record.kind, record.key, record.title, record.body, status, source,
             0.5 if record.importance is None else record.importance, record.tags, source, record.origin,
             _json(record.data))).fetchone()
        if row is not None:
            _embed_record(conn, embedder, row["id"], project_id, row["kind"], row["title"], row["body"], row["tags"])
            return {"id": str(row["id"]), "key": row["key"], "kind": row["kind"], "action": "created", "version": 1}
        existing = conn.execute("SELECT * FROM records WHERE project_id=%s AND key=%s",
                                (project_id, record.key)).fetchone()
    status = existing["status"]
    status_source = existing["status_source"]
    if record.status and record.status != status:
        if not respect_status_owner or existing["status_source"] in (None, source):
            status, status_source = record.status, source
    importance = existing["importance"] if record.importance is None else record.importance
    data = {**existing["data"], **record.data} if respect_status_owner is False else record.data
    changed = (existing["title"] != record.title or existing["body"] != record.body or status != existing["status"]
               or abs(importance - existing["importance"]) > 1e-6 or list(existing["tags"]) != record.tags
               or _json(existing["data"]) != _json(data) or existing["kind"] != record.kind
               or existing["archived"])
    if not changed:
        return {"id": str(existing["id"]), "key": existing["key"], "kind": existing["kind"],
                "action": "unchanged", "version": existing["version"]}
    conn.execute(
        "INSERT INTO record_versions(record_id, version, title, body, status, data, source) "
        "VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s)",
        (existing["id"], existing["version"], existing["title"], existing["body"], existing["status"],
         _json(existing["data"]), existing["source"]))
    row = conn.execute(
        "UPDATE records SET kind=%s, title=%s, body=%s, status=%s, status_source=%s, importance=%s, tags=%s, "
        "source=%s, data=%s::jsonb, version=version+1, archived=false, updated_at=now() "
        "WHERE id=%s RETURNING *",
        (record.kind, record.title, record.body, status, status_source, importance, record.tags, source,
         _json(data), existing["id"])).fetchone()
    if (existing["title"], existing["body"], list(existing["tags"]), existing["kind"]) != \
            (row["title"], row["body"], list(row["tags"]), row["kind"]):
        _embed_record(conn, embedder, row["id"], project_id, row["kind"], row["title"], row["body"], row["tags"])
    return {"id": str(row["id"]), "key": row["key"], "kind": row["kind"], "action": "updated",
            "version": row["version"]}


def set_status(conn, project_id, ref: str, status: str, *, source: str, note: str = "") -> dict:
    row = resolve_record(conn, project_id, ref)
    allowed = STATUSES.get(row["kind"], ("active", "archived"))
    if status not in allowed:
        raise BrainError(f"Invalid status '{status}' for {row['kind']}. Use: {', '.join(allowed)}")
    if status == row["status"] and not note:
        return {"id": str(row["id"]), "key": row["key"], "status": status, "changed": False}
    conn.execute(
        "INSERT INTO record_versions(record_id, version, title, body, status, data, source) "
        "VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s)",
        (row["id"], row["version"], row["title"], row["body"], row["status"], _json(row["data"]), row["source"]))
    conn.execute("UPDATE records SET status=%s, status_source=%s, version=version+1, updated_at=now() WHERE id=%s",
                 (status, source, row["id"]))
    add_event(conn, project_id, type="record.status_changed",
              summary=f"{row['kind']} '{row['title']}': {row['status']} → {status}" + (f" — {note}" if note else ""),
              actor=source, data={"key": row["key"], "from": row["status"], "to": status, "note": note},
              record_ids=[row["id"]])
    return {"id": str(row["id"]), "key": row["key"], "status": status, "changed": True}


def archive(conn, project_id, ref: str, *, source: str, note: str = "") -> dict:
    """Forget a record: it leaves listings and retrieval but keeps its history."""
    row = resolve_record(conn, project_id, ref, include_archived=False)
    conn.execute("UPDATE records SET archived=true, updated_at=now() WHERE id=%s", (row["id"],))
    add_event(conn, project_id, type="record.archived",
              summary=f"{row['kind']} '{row['title']}' arquivado" + (f" — {note}" if note else ""),
              actor=source, data={"key": row["key"], "note": note}, record_ids=[row["id"]])
    return {"id": str(row["id"]), "key": row["key"], "archived": True}


def add_relation(conn, project_id, src_ref: str, dst_ref: str, type: str, *, source: str) -> dict:
    if type not in RELATION_TYPES:
        raise BrainError(f"Invalid relation '{type}'. Use: {', '.join(RELATION_TYPES)}")
    src = resolve_record(conn, project_id, src_ref)
    dst = resolve_record(conn, project_id, dst_ref)
    conn.execute("INSERT INTO relations(project_id, src, dst, type, source) VALUES (%s,%s,%s,%s,%s) "
                 "ON CONFLICT DO NOTHING", (project_id, src["id"], dst["id"], type, source))
    return {"src": src["key"], "dst": dst["key"], "type": type}


def add_event(conn, project_id, *, type: str, summary: str, actor: str, data: dict | None = None,
              record_ids: list | None = None, workflow_id: str | None = None) -> dict:
    if not type or len(type) > 80:
        raise BrainError("event type must have 1..80 characters")
    summary = (summary or "").strip()
    if not summary:
        raise BrainError("event summary is required")
    row = conn.execute(
        "INSERT INTO events(project_id, type, summary, actor, data, record_ids, workflow_id) "
        "VALUES (%s,%s,%s,%s,%s::jsonb,%s,%s) RETURNING id, created_at",
        (project_id, type, summary[:4000], actor, _json(data or {}), list(record_ids or []), workflow_id)).fetchone()
    conn.execute("UPDATE projects SET updated_at=now() WHERE id=%s", (project_id,))
    return {"id": str(row["id"]), "created_at": row["created_at"].isoformat()}


def list_events(conn, project_id, limit: int = 30, type_prefix: str | None = None) -> list[dict]:
    query = "SELECT id, type, summary, actor, data, workflow_id, created_at FROM events WHERE project_id=%s"
    params: list = [project_id]
    if type_prefix:
        query += " AND type LIKE %s"
        params.append(type_prefix + "%")
    query += " ORDER BY created_at DESC LIMIT %s"
    params.append(max(1, min(limit, 200)))
    return conn.execute(query, params).fetchall()


def list_records(conn, project_id, *, kind: str | None = None, status: str | None = None,
                 include_archived: bool = False, limit: int = 200) -> list[dict]:
    query = ("SELECT id, kind, key, title, body, status, importance, tags, source, data, version, archived, "
             "updated_at FROM records WHERE project_id=%s")
    params: list = [project_id]
    if kind:
        kinds = [KIND_ALIASES.get(k, k) for k in kind.split(",")]
        query += " AND kind = ANY(%s)"
        params.append(kinds)
    if status:
        query += " AND status = ANY(%s)"
        params.append(status.split(","))
    if not include_archived:
        query += " AND NOT archived"
    query += " ORDER BY importance DESC, updated_at DESC LIMIT %s"
    params.append(max(1, min(limit, 1000)))
    return conn.execute(query, params).fetchall()


def get_record(conn, project_id, ref: str) -> dict:
    row = resolve_record(conn, project_id, ref)
    relations = conn.execute(
        "SELECT r.type, 'out' AS direction, t.key, t.kind, t.title, t.status FROM relations r "
        "JOIN records t ON t.id=r.dst WHERE r.src=%s UNION ALL "
        "SELECT r.type, 'in' AS direction, t.key, t.kind, t.title, t.status FROM relations r "
        "JOIN records t ON t.id=r.src WHERE r.dst=%s", (row["id"], row["id"])).fetchall()
    versions = conn.execute(
        "SELECT version, status, source, changed_at FROM record_versions WHERE record_id=%s "
        "ORDER BY version DESC LIMIT 10", (row["id"],)).fetchall()
    return {**row, "relations": relations, "versions": versions}


# ── projections ─────────────────────────────────────────────────────────────

def apply_projection(conn, embedder, project_id, *, source: str, namespace: str, records: list[dict],
                     relations: list[dict] | None = None, event: dict | None = None,
                     archive_missing: bool = True) -> dict:
    """Make the namespace's records equal to ``records`` (declarative, idempotent)."""
    if not namespace or ":" in namespace.strip(":"):
        raise BrainError("namespace must be a simple prefix such as 'creare'")
    prefix = namespace.strip(":") + ":"
    parsed = [RecordIn.parse(item) for item in records]
    for item in parsed:
        if not item.key or not item.key.startswith(prefix):
            raise BrainError(f"Projection keys must start with '{prefix}'")
    stats = {"created": 0, "updated": 0, "unchanged": 0, "archived": 0, "relations": 0}
    keys = set()
    for item in parsed:
        result = upsert_record(conn, embedder, project_id, RecordIn(**{**item.__dict__, "origin": namespace}),
                               source=source, respect_status_owner=True)
        stats[result["action"]] += 1
        keys.add(result["key"])
    if archive_missing:
        stale = conn.execute(
            "UPDATE records SET archived=true, updated_at=now() WHERE project_id=%s AND origin=%s "
            "AND NOT archived AND NOT (key = ANY(%s)) RETURNING id", (project_id, namespace, list(keys))).fetchall()
        stats["archived"] = len(stale)
    if relations is not None:
        ids = {row["key"]: row["id"] for row in conn.execute(
            "SELECT id, key FROM records WHERE project_id=%s AND key LIKE %s", (project_id, prefix + "%"))}
        conn.execute("DELETE FROM relations WHERE project_id=%s AND source=%s", (project_id, source))
        for relation in relations:
            src, dst, kind = ids.get(relation.get("src")), ids.get(relation.get("dst")), relation.get("type")
            if src and dst and kind in RELATION_TYPES:
                conn.execute("INSERT INTO relations(project_id, src, dst, type, source) VALUES (%s,%s,%s,%s,%s) "
                             "ON CONFLICT DO NOTHING", (project_id, src, dst, kind, source))
                stats["relations"] += 1
    if event and (stats["created"] or stats["updated"] or stats["archived"] or event.get("always")):
        add_event(conn, project_id, type=event.get("type", f"{namespace}.synced"),
                  summary=event.get("summary") or f"{namespace}: {stats['created']} new, {stats['updated']} updated, "
                                                  f"{stats['archived']} archived",
                  actor=source, data={**(event.get("data") or {}), "stats": stats},
                  workflow_id=event.get("workflow_id"))
    return stats


# ── summaries ───────────────────────────────────────────────────────────────

def project_summary(conn, project_id) -> dict:
    project = conn.execute("SELECT * FROM projects WHERE id=%s", (project_id,)).fetchone()
    counts = conn.execute(
        "SELECT kind, status, count(*) AS n FROM records WHERE project_id=%s AND NOT archived "
        "GROUP BY kind, status ORDER BY kind, status", (project_id,)).fetchall()
    by_kind: dict[str, dict[str, int]] = {}
    for row in counts:
        by_kind.setdefault(row["kind"], {})[row["status"]] = row["n"]
    return {"project": project, "counts": by_kind,
            "records": sum(n for statuses in by_kind.values() for n in statuses.values()),
            "recent_events": list_events(conn, project_id, limit=10)}


def export_project(conn, project_id) -> dict:
    project = conn.execute("SELECT * FROM projects WHERE id=%s", (project_id,)).fetchone()
    records = conn.execute(
        "SELECT id, kind, key, title, body, status, importance, tags, source, data, version, updated_at "
        "FROM records WHERE project_id=%s AND NOT archived ORDER BY kind, key", (project_id,)).fetchall()
    relations = conn.execute(
        "SELECT s.key AS src, d.key AS dst, r.type FROM relations r JOIN records s ON s.id=r.src "
        "JOIN records d ON d.id=r.dst WHERE r.project_id=%s AND NOT s.archived AND NOT d.archived",
        (project_id,)).fetchall()
    return {"project": project, "records": records, "relations": relations}
