"""Brain service operations shared by the REST API and the MCP endpoint."""

import logging
import threading
from functools import cached_property

from . import access, knowledge, memory, telemetry
from .db import Database
from .embeddings import build_embedder
from .intent import IntentClassifier
from .retrieval import Retriever, core_context, relevant_context
from .settings import Settings

logger = logging.getLogger("brain.service")


def _jsonable(value):
    import datetime
    import decimal
    import uuid

    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, (datetime.datetime, datetime.date)):
        return value.isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, decimal.Decimal):
        return float(value)
    return value


class BrainService:
    def __init__(self, settings: Settings | None = None, *, db: Database | None = None, embedder=None):
        self.settings = settings or Settings.from_env()
        self.db = db or Database(self.settings.database_url, self.settings.schema,
                                 self.settings.embedding_dimensions, self.settings.pool_max_size)
        self._embedder = embedder
        self.ingest_status: dict[str, dict] = {}
        self._ingest_lock = threading.Lock()

    # ── lifecycle ──
    def migrate(self) -> None:
        self.db.migrate(self.embedder.model_name)

    @cached_property
    def embedder(self):
        return self._embedder or build_embedder(self.settings)

    @cached_property
    def retriever(self) -> Retriever:
        return Retriever(self.db, self.embedder, IntentClassifier(self.embedder))

    @cached_property
    def pricing(self) -> dict:
        return telemetry.load_pricing(str(self.settings.pricing_file) if self.settings.pricing_file else None)

    def close(self) -> None:
        self.db.close()

    # ── projects ──
    def _project(self, conn, ref) -> dict:
        if not ref:
            raise memory.BrainError("project is required")
        return memory.get_project(conn, str(ref), self.settings.default_workspace)

    def ensure_project(self, payload: dict) -> dict:
        with self.db.connect() as conn:
            return _jsonable(memory.ensure_project(
                conn, name=payload.get("name", ""), slug_value=payload.get("slug"),
                external_ref=payload.get("external_ref"), description=payload.get("description", ""),
                root_path=payload.get("root_path"), workspace=self.settings.default_workspace))

    def projects(self) -> list[dict]:
        with self.db.connect() as conn:
            return _jsonable(memory.list_projects(conn, self.settings.default_workspace))

    def project(self, ref) -> dict:
        with self.db.connect() as conn:
            project = self._project(conn, ref)
            return _jsonable(memory.project_summary(conn, project["id"]))

    def resolve_project_id(self, ref) -> str:
        with self.db.connect() as conn:
            return str(self._project(conn, ref)["id"])

    # ── context ──
    def context(self, project_ref, token_budget: int = 800) -> dict:
        with self.db.connect() as conn:
            project = self._project(conn, project_ref)
            text, core = core_context(conn, project["id"], token_budget)
            events = memory.list_events(conn, project["id"], limit=5)
        if events:
            text += "\n\n## Recent activity\n" + "\n".join(
                f"- {e['created_at']:%Y-%m-%d} {e['type']}: {e['summary'][:160]}" for e in events)
        return _jsonable({"project": project, "context": text, "core": core})

    def relevant_context(self, project_ref, task: str, token_budget: int = 1500, knowledge_: bool = True,
                         collections=None) -> dict:
        if not (task or "").strip():
            raise memory.BrainError("task is required")
        if not 200 <= token_budget <= 12000:
            raise memory.BrainError("token_budget must be 200..12000")
        project_id = self.resolve_project_id(project_ref)
        return _jsonable(relevant_context(self.retriever, project_id, task.strip(), token_budget=token_budget,
                                          knowledge=knowledge_, collections=collections))

    # ── search ──
    def search(self, query: str, *, scope: str = "project", project_ref=None, kinds=None, collections=None,
               modules=None, limit: int = 8, token_budget: int = 1000, expand: bool = True,
               include_archived: bool = False) -> dict:
        project_id = self.resolve_project_id(project_ref) if scope in ("project", "all") else None
        try:
            return _jsonable(self.retriever.search(
                query, scope=scope, project_id=project_id, kinds=kinds, collections=collections, modules=modules,
                limit=limit, token_budget=token_budget, expand=expand, include_archived=include_archived))
        except ValueError as exc:
            raise memory.BrainError(str(exc)) from exc

    def search_many(self, queries: list[dict], collections=None, limit: int = 2, token_budget: int = 220):
        try:
            return _jsonable(self.retriever.search_many(queries, collections=collections, limit=limit,
                                                        token_budget=token_budget))
        except ValueError as exc:
            raise memory.BrainError(str(exc)) from exc

    # ── records ──
    def records(self, project_ref, kind=None, status=None, include_archived=False, limit=200) -> list[dict]:
        with self.db.connect() as conn:
            project = self._project(conn, project_ref)
            return _jsonable(memory.list_records(conn, project["id"], kind=kind, status=status,
                                                 include_archived=include_archived, limit=limit))

    def record(self, project_ref, ref: str) -> dict:
        with self.db.connect() as conn:
            project = self._project(conn, project_ref)
            return _jsonable(memory.get_record(conn, project["id"], ref))

    def upsert(self, project_ref, payload: dict, source: str) -> dict:
        record = memory.RecordIn.parse(payload)
        with self.db.connect() as conn:
            project = self._project(conn, project_ref)
            result = memory.upsert_record(conn, self.embedder, project["id"], record, source=source)
            if result["action"] != "unchanged":
                memory.add_event(conn, project["id"], type=f"record.{result['action']}",
                                 summary=f"{result['kind']} '{record.title.strip()}' {result['action']}",
                                 actor=source, data={"key": result["key"], "version": result["version"]},
                                 record_ids=[result["id"]])
            return result

    def set_status(self, project_ref, ref: str, status: str, source: str, note: str = "") -> dict:
        with self.db.connect() as conn:
            project = self._project(conn, project_ref)
            return memory.set_status(conn, project["id"], ref, status, source=source, note=note)

    def archive(self, project_ref, ref: str, source: str, note: str = "") -> dict:
        with self.db.connect() as conn:
            project = self._project(conn, project_ref)
            return memory.archive(conn, project["id"], ref, source=source, note=note)

    def relate(self, project_ref, src: str, dst: str, type: str, source: str) -> dict:
        with self.db.connect() as conn:
            project = self._project(conn, project_ref)
            return memory.add_relation(conn, project["id"], src, dst, type, source=source)

    def event(self, project_ref, payload: dict, source: str) -> dict:
        with self.db.connect() as conn:
            project = self._project(conn, project_ref)
            ids = []
            for ref in payload.get("records") or []:
                ids.append(memory.resolve_record(conn, project["id"], ref)["id"])
            return memory.add_event(conn, project["id"], type=payload.get("type", ""),
                                    summary=payload.get("summary", ""), actor=payload.get("actor") or source,
                                    data=payload.get("data"), record_ids=ids, workflow_id=payload.get("workflow_id"))

    def events(self, project_ref, limit: int = 30, type_prefix: str | None = None) -> list[dict]:
        with self.db.connect() as conn:
            project = self._project(conn, project_ref)
            return _jsonable(memory.list_events(conn, project["id"], limit=limit, type_prefix=type_prefix))

    def projection(self, project_ref, payload: dict) -> dict:
        with self.db.connect() as conn:
            project = self._project(conn, project_ref)
            return memory.apply_projection(
                conn, self.embedder, project["id"], source=payload.get("source", ""),
                namespace=payload.get("namespace", ""), records=payload.get("records") or [],
                relations=payload.get("relations"), event=payload.get("event"),
                archive_missing=payload.get("archive_missing", True))

    # ── access tokens ──
    def issue_token(self, project_ref, label: str, *, rotate_prefix: str | None = None) -> dict:
        with self.db.connect() as conn:
            project = self._project(conn, project_ref)
            if rotate_prefix:
                access.revoke_by_label(conn, project["id"], rotate_prefix)
            return _jsonable(access.issue(conn, str(project["id"]), label, self.settings.default_workspace))

    def list_tokens(self, project_ref) -> list[dict]:
        with self.db.connect() as conn:
            return _jsonable(access.list_tokens(conn, project_ref, self.settings.default_workspace))

    def revoke_token(self, project_ref, token_id: str) -> dict:
        with self.db.connect() as conn:
            return access.revoke(conn, project_ref, token_id, self.settings.default_workspace)

    def token_scope(self, secret: str) -> str | None:
        with self.db.connect() as conn:
            return access.scope_of(conn, secret)

    def export(self, project_ref) -> dict:
        with self.db.connect() as conn:
            project = self._project(conn, project_ref)
            return _jsonable(memory.export_project(conn, project["id"]))

    # ── knowledge ──
    def collections(self) -> list[dict]:
        with self.db.connect() as conn:
            rows = knowledge.collections(conn)
        result = _jsonable(rows)
        for item in result:
            item["ingest"] = self.ingest_status.get(item["id"])
        return result

    def ingest(self, collection_id: str, root, title: str | None = None) -> dict:
        with self._ingest_lock:
            self.ingest_status[collection_id] = {"state": "running"}

            def progress(number, total, path, chunks):
                self.ingest_status[collection_id] = {"state": "running", "documents_done": number,
                                                     "documents_total": total, "last": path}
            try:
                stats = knowledge.ingest_collection(self.db, self.embedder, collection_id, root,
                                                    title=title, progress=progress)
                self.ingest_status[collection_id] = {"state": "ready", **stats}
                return stats
            except Exception as exc:
                self.ingest_status[collection_id] = {"state": "failed", "error": str(exc)}
                raise

    # ── telemetry ──
    def telemetry(self, calls: list[dict]) -> list[dict]:
        with self.db.connect() as conn:
            def resolver(ref):
                try:
                    return memory.get_project(conn, str(ref), self.settings.default_workspace)["id"]
                except memory.NotFound:
                    return None
            return telemetry.record_calls(conn, calls, self.pricing, resolver)

    def telemetry_report(self, *, workflow_id=None, project_ref=None, task=None, since=None,
                         group_by="component") -> dict:
        project_id = self.resolve_project_id(project_ref) if project_ref else None
        with self.db.connect() as conn:
            return telemetry.report(conn, workflow_id=workflow_id, project_id=project_id, task=task, since=since,
                                    group_by=group_by)

    def status(self) -> dict:
        with self.db.connect() as conn:
            counts = conn.execute(
                "SELECT (SELECT count(*) FROM projects) AS projects, (SELECT count(*) FROM records) AS records, "
                "(SELECT count(*) FROM kb_documents) AS kb_documents, (SELECT count(*) FROM kb_chunks) AS kb_chunks, "
                "(SELECT count(*) FROM llm_calls) AS llm_calls").fetchone()
        return {"status": "ok", "embedding_model": self.embedder.model_name,
                "embedding_dimensions": self.settings.embedding_dimensions, "schema": self.settings.schema,
                **counts, "ingest": self.ingest_status}
