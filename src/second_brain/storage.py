import json
import sqlite3
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from .documents import chunks, markdown_paths, parse
from .embedding import embed
from .locking import serialized

SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
 id TEXT PRIMARY KEY, path TEXT NOT NULL UNIQUE, hash TEXT NOT NULL,
 type TEXT NOT NULL, title TEXT NOT NULL, tags TEXT NOT NULL,
 importance REAL NOT NULL, status TEXT, created_at TEXT, updated_at TEXT NOT NULL,
 body TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS chunks (
 id INTEGER PRIMARY KEY, document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
 ordinal INTEGER NOT NULL, text TEXT NOT NULL, embedding TEXT NOT NULL,
 UNIQUE(document_id, ordinal)
);
CREATE INDEX IF NOT EXISTS chunks_document ON chunks(document_id);
CREATE INDEX IF NOT EXISTS documents_type ON documents(type);
CREATE TABLE IF NOT EXISTS index_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
"""

INDEX_FORMAT = "2"  # Smaller passages; upgrades re-embed unchanged Markdown once.


def db_path(root: Path, config: dict) -> Path:
    relative = Path(config["storage"]["database"])
    if relative.is_absolute() or ".." in relative.parts or relative.parts[:2] != (".brain", "index"):
        raise ValueError("storage.database must point inside the project's .brain/index/")
    return root / relative


def connect(root: Path, config: dict) -> sqlite3.Connection:
    try:
        import sqlite_vec
    except ImportError as exc:
        raise RuntimeError("sqlite-vec is missing. Run 'pip install -e .' in the Brain environment.") from exc
    path = db_path(root, config)
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    db.enable_load_extension(True)
    try:
        sqlite_vec.load(db)
    finally:
        db.enable_load_extension(False)
    db.executescript(SCHEMA)
    dimensions = config["embedding"]["dimensions"]
    if not isinstance(dimensions, int) or not 1 <= dimensions <= 4096:
        raise ValueError("Invalid embedding dimension in config.json")
    db.execute(f"CREATE VIRTUAL TABLE IF NOT EXISTS vec_chunks USING vec0(embedding float[{dimensions}] distance_metric=cosine)")
    recorded = dict(db.execute("SELECT key, value FROM index_meta"))
    model_name = config["embedding"]["model"]
    if recorded and (recorded.get("model") != model_name or recorded.get("dimensions") != str(dimensions)):
        db.close()
        raise ValueError("Embedding model or dimension changed. Run 'brain rebuild'.")
    if not recorded:
        db.executemany("INSERT INTO index_meta(key,value) VALUES(?,?)",
                       [("model", model_name), ("dimensions", str(dimensions))])
    if db.execute("PRAGMA user_version").fetchone()[0] < 2:
        # Existing V1 databases stored vectors as JSON in chunks.
        existing_ids = {row[0] for row in db.execute("SELECT rowid FROM vec_chunks")}
        for row in db.execute("SELECT id, embedding FROM chunks"):
            if row["id"] not in existing_ids:
                db.execute("INSERT INTO vec_chunks(rowid, embedding) VALUES (?, ?)",
                           (row["id"], sqlite_vec.serialize_float32(json.loads(row["embedding"]))))
        db.execute("PRAGMA user_version = 2")
    db.commit()
    return db


@serialized
def index(root: Path, config: dict, *, rebuild: bool = False) -> dict:
    if not rebuild:
        return _index(root, config)
    # Build beside the live database. Failed parsing or embedding must not
    # destroy the last usable index.
    path = db_path(root, config)
    temporary = path.with_name(f"rebuild-{uuid4().hex}.db")
    staging = deepcopy(config)
    staging["storage"]["database"] = temporary.relative_to(root).as_posix()
    try:
        result = _index(root, staging)
        temporary.replace(path)
        return result
    finally:
        temporary.unlink(missing_ok=True)


def _index(root: Path, config: dict) -> dict:
    import sqlite_vec

    db = connect(root, config)
    try:
        # Serialize index writers before taking the snapshot, and commit all
        # document/chunk/vector changes together.
        db.execute("BEGIN IMMEDIATE")
        known = {row["path"]: row for row in db.execute("SELECT id, path, hash FROM documents")}
        format_row = db.execute("SELECT value FROM index_meta WHERE key='format'").fetchone()
        upgrade = format_row is None or format_row[0] != INDEX_FORMAT
        seen = set()
        identities = {}
        changed = []
        for path in markdown_paths(root):
            relative = path.relative_to(root).as_posix()
            doc = parse(path, root)
            if doc is None:
                continue
            identity = doc["metadata"]["id"]
            if identity in identities:
                raise ValueError(f"Duplicate memory id '{identity}': {identities[identity]} and {relative}")
            identities[identity] = relative
            seen.add(relative)
            if upgrade or relative not in known or known[relative]["hash"] != doc["hash"]:
                changed.append(doc)
        count_chunks = 0
        # Remove changed and deleted rows first so renames/path swaps cannot
        # delete a newly inserted record or violate the unique path contract.
        stale = [row["id"] for path, row in known.items()
                 if path not in seen and row["id"] not in identities]
        replaced = set(stale)
        for doc in changed:
            replaced.add(doc["metadata"]["id"])
            old = known.get(doc["path"])
            if old:
                replaced.add(old["id"])
        for key in replaced:
            _delete_vectors(db, key)
            db.execute("DELETE FROM documents WHERE id=?", (key,))
        for doc in changed:
            meta = doc["metadata"]
            doc_chunks = chunks(doc["body"])
            texts = [f"{meta['title']}\nTags: {', '.join(meta['tags'])}\n{chunk}" for chunk in doc_chunks]
            vectors = embed(texts, config)
            if len(vectors) != len(doc_chunks):
                raise ValueError("Embedding count differs from chunk count")
            db.execute(
                "INSERT INTO documents(id,path,hash,type,title,tags,importance,status,created_at,updated_at,body) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET "
                "path=excluded.path,hash=excluded.hash,type=excluded.type,title=excluded.title,"
                "tags=excluded.tags,importance=excluded.importance,status=excluded.status,"
                "created_at=excluded.created_at,updated_at=excluded.updated_at,body=excluded.body",
                (meta["id"], doc["path"], doc["hash"], meta["type"], meta["title"],
                 json.dumps(meta["tags"], ensure_ascii=False), meta["importance"], meta.get("status"),
                 meta.get("created_at"), meta.get("updated_at") or datetime.now(timezone.utc).isoformat(), doc["body"]),
            )
            for i, (chunk, vector) in enumerate(zip(doc_chunks, vectors)):
                cursor = db.execute("INSERT INTO chunks(document_id,ordinal,text,embedding) VALUES(?,?,?,?)",
                                    (meta["id"], i, chunk, json.dumps(vector)))
                db.execute("INSERT INTO vec_chunks(rowid, embedding) VALUES (?, ?)",
                           (cursor.lastrowid, sqlite_vec.serialize_float32(vector)))
            count_chunks += len(doc_chunks)
        result = {"changed_documents": len(changed), "embedded_chunks": count_chunks,
                  "deleted_documents": len(stale), "unchanged_documents": len(seen) - len(changed)}
        db.execute("INSERT OR REPLACE INTO index_meta(key,value) VALUES('format',?)", (INDEX_FORMAT,))
        db.commit()
        if changed or stale or not (root / ".brain" / "map.html").exists():
            from .visualization import write_map
            write_map(root)
        return result
    finally:
        db.close()


def _delete_vectors(db: sqlite3.Connection, document_id: str) -> None:
    db.execute("DELETE FROM vec_chunks WHERE rowid IN (SELECT id FROM chunks WHERE document_id=?)", (document_id,))


def stats(root: Path, config: dict) -> dict:
    db = connect(root, config)
    try:
        db.execute("BEGIN")
        documents = db.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        chunk_count = db.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
        vector_count = db.execute("SELECT COUNT(*) FROM vec_chunks").fetchone()[0]
        missing = db.execute("SELECT COUNT(*) FROM chunks c LEFT JOIN vec_chunks v ON v.rowid=c.id WHERE v.rowid IS NULL").fetchone()[0]
        orphaned = db.execute("SELECT COUNT(*) FROM vec_chunks v LEFT JOIN chunks c ON c.id=v.rowid WHERE c.id IS NULL").fetchone()[0]
        timestamps = [row[0] for row in db.execute("SELECT updated_at FROM documents WHERE updated_at IS NOT NULL")]
        def instant(value: str) -> datetime:
            try:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
                return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)
            except ValueError:
                return datetime.min.replace(tzinfo=timezone.utc)
        updated = max(timestamps, key=instant) if timestamps else None
        return {"active": True, "memories": documents, "indexed_chunks": chunk_count,
                "indexed_vectors": vector_count, "index_consistent": missing == 0 and orphaned == 0,
                "missing_vectors": missing, "orphaned_vectors": orphaned,
                "embedding_model": config["embedding"]["model"], "embedding_device": "cpu",
                "vector_backend": "sqlite-vec", "requires_api_key": False, "last_update": updated}
    finally:
        db.close()


def vector_scores(db: sqlite3.Connection, vector: list[float]) -> dict[int, float]:
    import sqlite_vec

    # Hybrid ranking needs a vector score for every chunk. A vec0 KNN query caps
    # k at 4096, so use sqlite-vec's scalar distance over the local table.
    rows = db.execute("SELECT rowid, vec_distance_cosine(embedding, ?) AS distance FROM vec_chunks",
                      (sqlite_vec.serialize_float32(vector),))
    return {row["rowid"]: max(0.0, min(1.0, 1.0 - row["distance"])) for row in rows}
