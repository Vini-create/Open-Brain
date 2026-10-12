"""Knowledge-base ingestion: reusable technical knowledge, separate from project memory."""

import hashlib
import json
import logging
import os
import re
import time
from pathlib import Path

from .embeddings import vector_literal
from .markdown import chunk_markdown, document_title, module_references
from .taxonomy import DOMAINS
from .text import normalized

logger = logging.getLogger("brain.kb")
# Bump when chunk metadata rules change; unchanged documents are re-tagged without re-embedding.
KB_FORMAT = "2"
TOC_HEADING = re.compile(r"sum[aá]rio|[ií]ndice|table of contents|\bcontents\b|toc\b", re.IGNORECASE)
LINK_LINE = re.compile(r"^\s*(?:[-*+]|\d+\.)?\s*\[[^\]]+\]\([^)]*\)\s*$")
MODULE_CODE = re.compile(r"^(\d{2})_")
RANGE = re.compile(r"(\d{2})\s*[–-]\s*(\d{2})")


def _module(path: Path) -> str | None:
    match = MODULE_CODE.match(path.name)
    return match.group(1) if match else None


def categories_from_index(root: Path) -> dict[str, str]:
    """Read module → phase from a master-index table (``| Fase | Módulos | Objetivo |``)."""
    result: dict[str, str] = {}
    for index in sorted(root.rglob("README*INDEX*.md")) + sorted(root.rglob("README.md"))[:1]:
        for line in index.read_text(encoding="utf-8", errors="ignore").splitlines():
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            if len(cells) < 2 or not re.search(r"\d{2}", cells[1]) or set(cells[0]) <= {"-", ":"}:
                continue
            phase = re.sub(r"[*`]", "", cells[0]).strip()
            codes = set(re.findall(r"\b(\d{2})\b", cells[1]))
            for start, end in RANGE.findall(cells[1]):
                codes.update(f"{n:02d}" for n in range(int(start), int(end) + 1))
            for code in codes:
                result.setdefault(code, phase)
        if result:
            break
    return result


def is_table_of_contents(heading_path: str, content: str) -> bool:
    """Navigation sections match every query lexically but answer none."""
    lines = [line for line in content.splitlines() if line.strip()]
    links = sum(bool(LINK_LINE.match(line)) for line in lines)
    return bool(TOC_HEADING.search(heading_path.rsplit("›", 1)[-1])) or (len(lines) >= 4 and links / len(lines) > 0.6)


def topics_for(text: str, heading_path: str = "", content: str = "") -> list[str]:
    from .intent import _keyword_hits

    norm = normalized(text)
    topics = [domain.id for domain in DOMAINS if len(_keyword_hits(norm, domain)) >= 2][:6]
    if is_table_of_contents(heading_path, content or text):
        topics.append("_toc")
    return topics


def _retag(conn, document_id) -> None:
    rows = conn.execute("SELECT id, heading_path, content FROM kb_chunks WHERE document_id=%s",
                        (document_id,)).fetchall()
    for row in rows:
        conn.execute("UPDATE kb_chunks SET topics=%s WHERE id=%s",
                     (topics_for(row["heading_path"] + "\n" + row["content"], row["heading_path"], row["content"]),
                      row["id"]))
    conn.execute("UPDATE kb_documents SET meta = meta || %s::jsonb WHERE id=%s",
                 (json.dumps({"format": KB_FORMAT}), document_id))


def ingest_collection(db, embedder, collection_id: str, root: Path, *, title: str | None = None,
                      description: str = "", progress=None) -> dict:
    root = Path(root).expanduser().resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"Knowledge source not found: {root}")
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,60}", collection_id):
        raise ValueError("collection id must be lowercase letters, digits, '-' or '_'")
    if not os.access(root, os.R_OK | os.X_OK):
        raise PermissionError(f"Knowledge source is not readable: {root} (container mount / SELinux?)")
    started = time.monotonic()
    files = sorted(p for p in root.rglob("*.md")
                   if not any(part.startswith(".") for part in p.relative_to(root).parts))
    if not files:
        # An empty or unreadable mount must never be mistaken for "every document was deleted".
        raise FileNotFoundError(f"No Markdown files under {root}; refusing to empty collection '{collection_id}'")
    categories = categories_from_index(root)
    with db.connect() as conn:
        conn.execute(
            "INSERT INTO kb_collections(id, title, description, root, meta) VALUES (%s,%s,%s,%s,%s::jsonb) "
            "ON CONFLICT (id) DO UPDATE SET title=excluded.title, root=excluded.root, "
            "description=COALESCE(NULLIF(excluded.description,''), kb_collections.description), updated_at=now()",
            (collection_id, title or collection_id, description, str(root), json.dumps({"categories": categories})))
        known = {row["path"]: row for row in conn.execute(
            "SELECT id, path, hash, meta->>'format' AS format FROM kb_documents WHERE collection_id=%s",
            (collection_id,))}
    stats = {"documents": len(files), "changed": 0, "unchanged": 0, "removed": 0, "chunks": 0}
    seen = set()
    for number, path in enumerate(files, 1):
        relative = path.relative_to(root).as_posix()
        seen.add(relative)
        # Postgres text cannot hold NUL bytes; some exported Markdown contains them.
        raw = path.read_text(encoding="utf-8", errors="replace").replace("\x00", "")
        digest = hashlib.sha256(raw.encode()).hexdigest()
        if relative in known and known[relative]["hash"] == digest:
            if known[relative]["format"] != KB_FORMAT:
                with db.connect() as conn:
                    _retag(conn, known[relative]["id"])
            stats["unchanged"] += 1
            continue
        module = _module(path)
        doc_title = document_title(raw, path.stem.replace("_", " "))
        chunks = chunk_markdown(raw)
        label = f"{module} " if module else ""
        texts = [f"{label}{doc_title} › {chunk.path_label}\n{chunk.text}" for chunk in chunks]
        vectors = embedder.embed(texts) if texts else []
        with db.connect() as conn:
            row = conn.execute(
                "INSERT INTO kb_documents(collection_id, path, title, module, category, hash, meta) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb) ON CONFLICT (collection_id, path) DO UPDATE SET "
                "title=excluded.title, module=excluded.module, category=excluded.category, hash=excluded.hash, "
                "meta=excluded.meta, updated_at=now() RETURNING id",
                (collection_id, relative, doc_title, module, categories.get(module or ""), digest,
                 json.dumps({"references": module_references(raw), "chars": len(raw), "format": KB_FORMAT}))).fetchone()
            conn.execute("DELETE FROM kb_chunks WHERE document_id=%s", (row["id"],))
            with conn.cursor() as cursor:
                cursor.executemany(
                    "INSERT INTO kb_chunks(document_id, collection_id, ordinal, heading_path, anchor, content, "
                    "topics, tsv, embedding) VALUES (%s,%s,%s,%s,%s,%s,%s,to_tsvector('simple', %s),%s::vector)",
                    [(row["id"], collection_id, chunk.ordinal, chunk.path_label, chunk.anchor, chunk.text,
                      topics_for(text, chunk.path_label, chunk.text), normalized(text), vector_literal(vector))
                     for chunk, text, vector in zip(chunks, texts, vectors)])
        stats["changed"] += 1
        stats["chunks"] += len(chunks)
        if progress:
            progress(number, len(files), relative, len(chunks))
    with db.connect() as conn:
        removed = [path for path in known if path not in seen]
        if removed:
            conn.execute("DELETE FROM kb_documents WHERE collection_id=%s AND path = ANY(%s)",
                         (collection_id, removed))
        stats["removed"] = len(removed)
        if stats["changed"] or removed:
            _rebuild_links(conn, collection_id)
        stats["total_chunks"] = conn.execute(
            "SELECT count(*) AS n FROM kb_chunks WHERE collection_id=%s", (collection_id,)).fetchone()["n"]
    stats["seconds"] = round(time.monotonic() - started, 1)
    logger.info("kb ingest collection=%s %s", collection_id, stats)
    return stats


def _rebuild_links(conn, collection_id: str) -> None:
    documents = conn.execute("SELECT id, module, meta FROM kb_documents WHERE collection_id=%s",
                             (collection_id,)).fetchall()
    by_module = {row["module"]: row["id"] for row in documents if row["module"]}
    conn.execute("DELETE FROM kb_links WHERE src_document IN (SELECT id FROM kb_documents WHERE collection_id=%s)",
                 (collection_id,))
    rows = []
    for doc in documents:
        for module, count in (doc["meta"].get("references") or {}).items():
            target = by_module.get(module)
            if target and target != doc["id"]:
                rows.append((doc["id"], target, count))
    if rows:
        with conn.cursor() as cursor:
            cursor.executemany("INSERT INTO kb_links(src_document, dst_document, count) VALUES (%s,%s,%s) "
                               "ON CONFLICT DO NOTHING", rows)


def collections(conn) -> list[dict]:
    return conn.execute(
        "SELECT c.id, c.title, c.description, c.root, c.updated_at, "
        "(SELECT count(*) FROM kb_documents d WHERE d.collection_id=c.id) AS documents, "
        "(SELECT count(*) FROM kb_chunks k WHERE k.collection_id=c.id) AS chunks "
        "FROM kb_collections c ORDER BY c.id").fetchall()
