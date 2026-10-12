"""HTTP API: REST (/v1), MCP Streamable HTTP (/mcp) and a small local dashboard (/)."""

import logging
import re
import threading
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import unquote

from fastapi import Body, FastAPI, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from starlette.concurrency import run_in_threadpool

from . import mcp_tools
from .memory import BrainError, NotFound
from .service import BrainService
from .settings import Settings

logger = logging.getLogger("brain.api")
# Routes a project token may never call: cross-project listings, admin and ingestion.
PROJECT_TOKEN_DENIED = ("/v1/telemetry", "/v1/search", "/v1/knowledge/ingest")


class ServiceBackend:
    """MCP backend that calls the service in-process."""

    def __init__(self, service: BrainService, source: str = "mcp"):
        self.service = service
        self.source = source

    def status(self):
        return self.service.status()

    def context(self, project, token_budget):
        return self.service.context(project, token_budget)

    def relevant_context(self, project, task, token_budget, knowledge):
        return self.service.relevant_context(project, task, token_budget, knowledge)

    def search(self, project, query, scope, kinds, limit, token_budget):
        return self.service.search(query, scope=scope, project_ref=project, kinds=kinds, limit=limit,
                                   token_budget=token_budget)

    def knowledge(self, query, collections, limit, token_budget):
        return self.service.search(query, scope="knowledge", collections=collections, limit=limit,
                                   token_budget=token_budget)

    def get(self, project, ref):
        return self.service.record(project, ref)

    def list(self, project, kind, status, limit):
        return self.service.records(project, kind=kind, status=status, limit=limit)

    def record(self, project, payload):
        return self.service.upsert(project, payload, self.source)

    def update_status(self, project, ref, status, note):
        return self.service.set_status(project, ref, status, self.source, note)

    def log_event(self, project, payload):
        return self.service.event(project, payload, self.source)

    def relate(self, project, src, dst, type):
        return self.service.relate(project, src, dst, type, self.source)


def _autoingest(service: BrainService) -> None:
    for collection, root in service.settings.kb_sources.items():
        if not Path(root).is_dir():
            logger.warning("Knowledge source %s not found at %s", collection, root)
            continue
        try:
            stats = service.ingest(collection, root, title=collection.replace("-", " ").title())
            logger.info("Knowledge collection %s ready: %s", collection, stats)
        except Exception:
            logger.exception("Knowledge ingestion failed for %s", collection)


def create_app(settings: Settings | None = None, service: BrainService | None = None) -> FastAPI:
    settings = settings or (service.settings if service else Settings.from_env())
    settings.validate()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        brain = service or BrainService(settings)
        brain.migrate()
        app.state.brain = brain
        if settings.kb_autoingest and settings.kb_sources:
            threading.Thread(target=_autoingest, args=(brain,), name="kb-ingest", daemon=True).start()
        yield
        if service is None:
            brain.close()

    app = FastAPI(title="Brain Engine", version="2.0.0", lifespan=lifespan)

    @app.exception_handler(NotFound)
    async def not_found(_, exc):
        return JSONResponse({"detail": str(exc)}, status_code=404)

    @app.exception_handler(BrainError)
    async def bad_request(_, exc):
        return JSONResponse({"detail": str(exc)}, status_code=400)

    @app.middleware("http")
    async def auth(request: Request, call_next):
        """Admin token: everything. Project token: one project, its MCP and the shared knowledge base."""
        path = request.url.path
        if not path.startswith(("/v1", "/mcp")):
            return await call_next(request)
        header = request.headers.get("authorization", "")
        secret = header[len("Bearer "):].strip() if header.startswith("Bearer ") else ""
        scope = None
        if secret and settings.api_token and secret == settings.api_token:
            scope = None
        elif secret:
            scope = await run_in_threadpool(request.app.state.brain.token_scope, secret)
            if scope is None:
                return JSONResponse({"detail": "Unauthorized"}, status_code=401)
        elif settings.api_token:
            return JSONResponse({"detail": "Unauthorized"}, status_code=401)
        request.state.scope_project = scope
        if scope is not None:
            if path == "/v1/projects" or path.startswith(PROJECT_TOKEN_DENIED) or "/access-tokens" in path:
                return JSONResponse({"detail": "Forbidden for project tokens"}, status_code=403)
            ref = None
            match = re.match(r"^/v1/projects/([^/]+)", path)
            if match:
                ref = unquote(match.group(1))
            if path.startswith("/mcp"):
                ref = request.query_params.get("project") or request.headers.get("x-brain-project")
            if ref:
                try:
                    owner = await run_in_threadpool(request.app.state.brain.resolve_project_id, ref)
                except NotFound:
                    owner = None
                if owner != scope:
                    return JSONResponse({"detail": "Forbidden"}, status_code=403)
        return await call_next(request)

    def brain(request: Request) -> BrainService:
        return request.app.state.brain

    def source_of(value: str | None) -> str:
        source = (value or "api").strip().lower()[:40]
        return source or "api"

    @app.get("/healthz")
    def healthz(request: Request):
        return brain(request).status()

    # ── projects ──
    @app.post("/v1/projects", status_code=201)
    def create_project(request: Request, payload: dict = Body(...)):
        return brain(request).ensure_project(payload)

    @app.get("/v1/projects")
    def projects(request: Request):
        return brain(request).projects()

    @app.get("/v1/projects/{project}")
    def project(request: Request, project: str):
        return brain(request).project(project)

    @app.post("/v1/projects/{project}/access-tokens", status_code=201)
    def issue_access_token(request: Request, project: str, payload: dict = Body(default={})):
        # The secret is returned once; only its digest is stored.
        return brain(request).issue_token(project, payload.get("label", "acesso"),
                                          rotate_prefix=payload.get("rotate_prefix"))

    @app.get("/v1/projects/{project}/access-tokens")
    def list_access_tokens(request: Request, project: str):
        return brain(request).list_tokens(project)

    @app.delete("/v1/projects/{project}/access-tokens/{token_id}")
    def revoke_access_token(request: Request, project: str, token_id: str):
        return brain(request).revoke_token(project, token_id)

    @app.get("/v1/projects/{project}/context")
    def context(request: Request, project: str, token_budget: int = 800):
        return brain(request).context(project, token_budget)

    @app.post("/v1/projects/{project}/relevant-context")
    def relevant(request: Request, project: str, payload: dict = Body(...)):
        return brain(request).relevant_context(project, payload.get("task", ""),
                                               int(payload.get("token_budget") or 1500),
                                               bool(payload.get("include_knowledge", True)),
                                               payload.get("collections"))

    @app.post("/v1/projects/{project}/search")
    def project_search(request: Request, project: str, payload: dict = Body(...)):
        return brain(request).search(payload.get("query", ""), scope=payload.get("scope", "project"),
                                     project_ref=project, kinds=payload.get("kinds"),
                                     collections=payload.get("collections"), limit=int(payload.get("limit") or 8),
                                     token_budget=int(payload.get("token_budget") or 1000),
                                     include_archived=bool(payload.get("include_archived")))

    @app.get("/v1/projects/{project}/records")
    def records(request: Request, project: str, kind: str | None = None, status: str | None = None,
                include_archived: bool = False, limit: int = 200):
        return brain(request).records(project, kind, status, include_archived, limit)

    @app.get("/v1/projects/{project}/records/{ref:path}")
    def record(request: Request, project: str, ref: str):
        return brain(request).record(project, ref)

    @app.put("/v1/projects/{project}/records")
    def upsert(request: Request, project: str, payload: dict = Body(...),
               x_brain_source: str | None = Header(default=None)):
        return brain(request).upsert(project, payload, source_of(x_brain_source))

    @app.delete("/v1/projects/{project}/records/{ref:path}")
    def archive(request: Request, project: str, ref: str, x_brain_source: str | None = Header(default=None)):
        return brain(request).archive(project, ref, source_of(x_brain_source))

    @app.patch("/v1/projects/{project}/records/{ref:path}/status")
    def set_status(request: Request, project: str, ref: str, payload: dict = Body(...),
                   x_brain_source: str | None = Header(default=None)):
        return brain(request).set_status(project, ref, payload.get("status", ""), source_of(x_brain_source),
                                         payload.get("note", ""))

    @app.post("/v1/projects/{project}/relations")
    def relate(request: Request, project: str, payload: dict = Body(...),
               x_brain_source: str | None = Header(default=None)):
        return brain(request).relate(project, payload.get("src", ""), payload.get("dst", ""),
                                     payload.get("type", ""), source_of(x_brain_source))

    @app.post("/v1/projects/{project}/events", status_code=201)
    def add_event(request: Request, project: str, payload: dict = Body(...),
                  x_brain_source: str | None = Header(default=None)):
        return brain(request).event(project, payload, source_of(x_brain_source))

    @app.get("/v1/projects/{project}/events")
    def events(request: Request, project: str, limit: int = 30, type: str | None = None):
        return brain(request).events(project, limit, type)

    @app.post("/v1/projects/{project}/projection")
    def projection(request: Request, project: str, payload: dict = Body(...)):
        return brain(request).projection(project, payload)

    @app.get("/v1/projects/{project}/export")
    def export(request: Request, project: str):
        return brain(request).export(project)

    # ── knowledge ──
    @app.get("/v1/knowledge/collections")
    def collections(request: Request):
        return brain(request).collections()

    @app.post("/v1/knowledge/search")
    def knowledge_search(request: Request, payload: dict = Body(...)):
        return brain(request).search(payload.get("query", ""), scope="knowledge",
                                     collections=payload.get("collections"), modules=payload.get("modules"),
                                     limit=int(payload.get("limit") or 6),
                                     token_budget=int(payload.get("token_budget") or 900),
                                     expand=bool(payload.get("expand", True)))

    @app.post("/v1/knowledge/search-many")
    def knowledge_many(request: Request, payload: dict = Body(...)):
        return brain(request).search_many(payload.get("queries") or [], payload.get("collections"),
                                          int(payload.get("limit") or 2), int(payload.get("token_budget") or 220))

    @app.post("/v1/knowledge/ingest", status_code=202)
    def ingest(request: Request, payload: dict = Body(...)):
        service = brain(request)
        collection = payload.get("collection", "")
        root = payload.get("path") or str(service.settings.kb_sources.get(collection, ""))
        if not root:
            raise BrainError("path is required for an unknown collection")
        threading.Thread(target=service.ingest, args=(collection, root, payload.get("title")),
                         daemon=True).start()
        return {"collection": collection, "path": root, "state": "started"}

    @app.post("/v1/search")
    def search_all(request: Request, payload: dict = Body(...)):
        return brain(request).search(payload.get("query", ""), scope=payload.get("scope", "all"),
                                     project_ref=payload.get("project"), kinds=payload.get("kinds"),
                                     limit=int(payload.get("limit") or 8),
                                     token_budget=int(payload.get("token_budget") or 1200))

    # ── telemetry ──
    @app.post("/v1/telemetry/llm", status_code=201)
    def telemetry(request: Request, payload: dict | list = Body(...)):
        calls = payload if isinstance(payload, list) else payload.get("calls") or [payload]
        return brain(request).telemetry(calls)

    @app.get("/v1/telemetry/report")
    def telemetry_report(request: Request, workflow_id: str | None = None, project: str | None = None,
                         task: str | None = None, since: str | None = None, group_by: str = "component"):
        return brain(request).telemetry_report(workflow_id=workflow_id, project_ref=project, task=task,
                                               since=since, group_by=group_by)

    # ── MCP (Streamable HTTP, JSON responses) ──
    @app.post("/mcp")
    async def mcp(request: Request, project: str | None = None, x_brain_project: str | None = Header(default=None),
                  x_brain_source: str | None = Header(default=None)):
        try:
            message = await request.json()
        except ValueError:
            return JSONResponse({"jsonrpc": "2.0", "id": None,
                                 "error": {"code": -32700, "message": "Parse error"}}, status_code=400)
        backend = ServiceBackend(brain(request), source_of(x_brain_source or "mcp"))
        default_project = project or x_brain_project or getattr(request.state, "scope_project", None)

        def run(item):
            return mcp_tools.handle(item, backend, instructions=mcp_tools.SERVER_INSTRUCTIONS,
                                    server_name="brain-engine", default_project=default_project)

        from starlette.concurrency import run_in_threadpool

        if isinstance(message, list):
            responses = [r for r in [await run_in_threadpool(run, item) for item in message] if r is not None]
            return JSONResponse(responses) if responses else JSONResponse(None, status_code=202)
        response = await run_in_threadpool(run, message)
        return JSONResponse(response) if response is not None else JSONResponse(None, status_code=202)

    @app.get("/mcp")
    def mcp_stream():
        raise HTTPException(405, "This server answers MCP requests with JSON responses; no SSE stream.")

    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        return Path(__file__).with_name("dashboard.html").read_text(encoding="utf-8")

    return app


def main() -> None:
    import uvicorn

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    settings = Settings.from_env()
    uvicorn.run(create_app(settings), host=settings.host, port=settings.port, log_level="info")


if __name__ == "__main__":
    main()
