"""Brain Engine: storage, isolation, projections, retrieval, ranking, telemetry, API and MCP."""

import pytest

from brain_engine import memory
from brain_engine.intent import IntentClassifier, task_type
from brain_engine.markdown import chunk_markdown, sections
from brain_engine.memory import BrainError, NotFound

# ── pure units ──────────────────────────────────────────────────────────────


def test_markdown_sections_keep_heading_paths_and_code_fences():
    text = "# Doc\n\n## A\n\nPrimeiro parágrafo.\n\n```python\n# not a heading\nx = 1\n```\n\n### A.1\n\nDetalhe."
    found = sections(text)
    assert [s.heading_path for s in found] == [["Doc", "A"], ["Doc", "A", "A.1"]]
    assert "# not a heading" in found[0].text
    chunks = chunk_markdown(text, min_section_chars=0)
    assert all("```" not in c.text or c.text.count("```") == 2 for c in chunks)
    assert chunks[0].anchor == "a" and chunks[1].path_label == "Doc › A › A.1"


def test_chunking_bounds_long_sections_with_overlap():
    body = "## Longa\n\n" + "\n\n".join(f"Frase número {i} sobre memória de agentes. Outra frase {i}." for i in range(80))
    chunks = chunk_markdown(body, max_chars=500, overlap=80)
    assert len(chunks) > 5
    assert all(len(c.text) <= 600 for c in chunks)


@pytest.mark.parametrize("text,expected", [
    ("Implementa autenticação multi-tenant", "implement"),
    ("Começa implementando a camada de retrieval", "implement"),
    ("Corrige o erro no login", "fix"),
    ("Implementa tratamento de erro no parser", "implement"),
    ("Devo usar pgvector ou Qdrant?", "decide"),
    ("Como funciona o ranking?", "ask"),
])
def test_task_type(text, expected):
    assert task_type(text) == expected


def test_intent_maps_agent_memory_query_to_memory_domains():
    intent = IntentClassifier().classify("Quero memória de longo prazo para meus agentes")
    assert intent.domain_ids[0] == "agent_memory"
    assert "agents" in intent.domain_ids or "rag" in intent.domain_ids or len(intent.domain_ids) >= 1


# ── storage and isolation ───────────────────────────────────────────────────


def test_records_are_versioned_idempotent_and_isolated(service):
    a = service.ensure_project({"name": "Alpha", "external_ref": "creare:a"})
    again = service.ensure_project({"name": "Alpha", "external_ref": "creare:a"})
    b = service.ensure_project({"name": "Beta"})
    assert a["id"] == again["id"] and a["slug"] == "alpha"
    first = service.upsert(a["id"], {"kind": "decision", "title": "Usar pgvector", "body": "Postgres já existe."}, "cli")
    same = service.upsert(a["id"], {"kind": "decision", "title": "Usar pgvector", "body": "Postgres já existe."}, "cli")
    changed = service.upsert(a["id"], {"kind": "decision", "title": "Usar pgvector",
                                       "body": "Postgres já existe e suporta HNSW."}, "cli")
    assert (first["action"], same["action"], changed["action"]) == ("created", "unchanged", "updated")
    assert changed["version"] == 2
    record = service.record(a["id"], first["key"])
    assert record["versions"][0]["version"] == 1
    service.upsert(b["id"], {"kind": "decision", "title": "Usar Qdrant", "body": "Banco vetorial dedicado."}, "cli")
    found = service.search("banco vetorial dedicado qdrant", scope="project", project_ref=a["id"])
    assert all(item["citation"]["key"] != "decision:usar-qdrant" for item in found["items"])
    assert [r["title"] for r in service.records(b["id"], kind="decision")] == ["Usar Qdrant"]
    with pytest.raises(NotFound):
        service.record(b["id"], first["key"])


def test_validation_rejects_bad_kinds_status_and_unknown_projects(service):
    project = service.ensure_project({"name": "Gamma"})
    with pytest.raises(BrainError):
        service.upsert(project["id"], {"kind": "wish", "title": "x y", "body": "z"}, "cli")
    with pytest.raises(BrainError):
        service.upsert(project["id"], {"kind": "feature", "title": "Auth", "status": "done-ish"}, "cli")
    service.upsert(project["id"], {"kind": "feature", "title": "Auth", "body": "Login"}, "cli")
    with pytest.raises(BrainError):
        service.set_status(project["id"], "feature:auth", "fixed", "cli")
    with pytest.raises(NotFound):
        service.context("does-not-exist")


def test_projection_upserts_archives_and_respects_foreign_status(service):
    project = service.ensure_project({"name": "Creare room", "external_ref": "creare:room"})
    records = [
        {"key": "creare:idea", "kind": "idea", "title": "Memória para agentes", "body": "Agentes esquecem."},
        {"key": "creare:feature:retrieval", "kind": "feature", "title": "Camada de retrieval", "body": "Busca híbrida",
         "status": "planned"},
        {"key": "creare:constraint:local", "kind": "constraint", "title": "runs_local = true", "body": "Rodar local"},
    ]
    stats = service.projection(project["id"], {"source": "creare", "namespace": "creare", "records": records,
                                               "relations": [{"src": "creare:feature:retrieval",
                                                              "dst": "creare:constraint:local", "type": "constrains"}],
                                               "event": {"type": "creare.synced"}})
    assert stats["created"] == 3 and stats["relations"] == 1
    # Jarvis implements the feature; Creare's next projection must not reset the status.
    service.set_status(project["id"], "creare:feature:retrieval", "implemented", "jarvis", "tests green")
    stats = service.projection(project["id"], {"source": "creare", "namespace": "creare",
                                               "records": records[:2]})
    assert stats["archived"] == 1 and stats["unchanged"] == 2
    feature = service.record(project["id"], "creare:feature:retrieval")
    assert feature["status"] == "implemented"
    assert [r["key"] for r in service.records(project["id"], kind="constraint")] == []
    events = service.events(project["id"])
    assert any(e["type"] == "record.status_changed" for e in events)
    with pytest.raises(BrainError):
        service.projection(project["id"], {"source": "creare", "namespace": "creare",
                                           "records": [{"key": "jarvis:x", "kind": "idea", "title": "No"}]})


# ── knowledge and retrieval ─────────────────────────────────────────────────


def test_knowledge_ingest_is_incremental_and_links_modules(service, kb_dir):
    stats = service.ingest("ai-engineering", kb_dir)
    assert stats["changed"] == 4 and stats["total_chunks"] >= 5
    assert service.ingest("ai-engineering", kb_dir)["changed"] == 0
    (kb_dir / "15_DEPLOY_SCALE_LATENCY_COST.md").write_text("# 15\n\n## 15.1 Custo\n\nNovo conteúdo sobre custo de GPU e quantização.\n")
    assert service.ingest("ai-engineering", kb_dir)["changed"] == 1
    with service.db.connect() as conn:
        doc = conn.execute("SELECT module, category FROM kb_documents WHERE module='09'").fetchone()
        links = conn.execute("SELECT count(*) AS n FROM kb_links").fetchone()["n"]
    assert doc["category"] == "RAG e agentes" and links >= 1
    (kb_dir / "16_NUL.md").write_text("# 16\n\n## Seção\n\nTexto exportado com byte\x00 nulo no meio.\n")
    assert service.ingest("ai-engineering", kb_dir)["changed"] == 1
    (kb_dir / "16_NUL.md").unlink()
    (kb_dir / "15_DEPLOY_SCALE_LATENCY_COST.md").unlink()
    assert service.ingest("ai-engineering", kb_dir)["removed"] == 2


def test_knowledge_search_uses_intent_expansion_budget_and_citations(service, kb_dir):
    service.ingest("ai-engineering", kb_dir)
    result = service.search("Quero memória de longo prazo para meus agentes", scope="knowledge",
                            limit=4, token_budget=300)
    assert result["intent"]["domains"][0]["id"] == "agent_memory"
    assert result["expansions"], "memory intent must expand into related concepts"
    assert result["items"][0]["citation"]["module"] == "14"
    assert result["estimated_tokens"] <= 300
    assert all(item["citation"]["source"] == "knowledge" for item in result["items"])
    many = service.search_many([{"id": "hybrid", "query": "busca híbrida BM25 RRF"},
                                {"id": "hnsw", "query": "índice HNSW pgvector"}])
    assert many[0]["items"][0]["citation"]["module"] == "09"
    assert many[1]["items"][0]["citation"]["module"] == "14"


def test_relevant_context_combines_core_memory_and_knowledge(service, kb_dir):
    service.ingest("ai-engineering", kb_dir)
    project = service.ensure_project({"name": "Agent memory"})
    pid = project["id"]
    service.upsert(pid, {"kind": "objective", "title": "Memória persistente para coding agents",
                         "body": "Agentes devem lembrar decisões entre sessões."}, "creare")
    service.upsert(pid, {"kind": "decision", "title": "Usar pgvector com busca híbrida",
                         "body": "Postgres local, HNSW e FTS com RRF."}, "creare")
    service.upsert(pid, {"kind": "feature", "title": "Camada de retrieval", "body": "Busca híbrida e budget",
                         "status": "planned"}, "creare")
    service.upsert(pid, {"kind": "learning", "title": "Receita de bolo", "body": "Farinha e ovos."}, "cli")
    ctx = service.relevant_context(pid, "Começa implementando a camada de retrieval híbrida", 1200)
    assert ctx["intent"]["task"] == "implement"
    assert "Usar pgvector com busca híbrida" in ctx["context"]
    assert "Camada de retrieval" in ctx["context"]
    assert ctx["knowledge_items"], "technical knowledge must be attached"
    assert ctx["estimated_tokens"] <= 1300
    assert ctx["project_items"][0]["citation"]["key"] != "learning:receita-de-bolo"


def test_telemetry_estimates_reports_and_prefers_reported_cost(service):
    project = service.ensure_project({"name": "Costs"})
    stored = service.telemetry([
        {"workflow_id": "w1", "project_id": project["id"], "component": "creare.compiler", "model": "gpt-4.1-mini",
         "input_tokens": 1_000_000, "output_tokens": 100_000},
        {"workflow_id": "w1", "project": project["slug"], "component": "executor.claude", "model": "claude-sonnet-4",
         "input_tokens": 10, "output_tokens": 10, "cost_usd": 0.5},
        {"workflow_id": "w1", "component": "jarvis.spec", "model": "mystery-model", "input_tokens": 5},
    ])
    assert stored[0]["cost_source"] == "estimated" and stored[0]["cost_usd"] == pytest.approx(0.56)
    assert stored[1]["cost_source"] == "reported"
    assert stored[2]["cost_source"] == "unpriced"
    report = service.telemetry_report(workflow_id="w1")
    assert report["total"]["cost_usd"] == pytest.approx(1.06)
    assert "executor.claude" in report["table"] and "*" in report["table"]
    assert service.telemetry_report(project_ref=project["id"])["total"]["calls"] == 2
    with pytest.raises(BrainError):
        service.telemetry([{"component": "x", "input_tokens": -1}])


# ── HTTP API and MCP ────────────────────────────────────────────────────────


@pytest.fixture
def client(service):
    from fastapi.testclient import TestClient

    from brain_engine.api import create_app

    with TestClient(create_app(service=service)) as http:
        yield http


def test_rest_api_round_trip(client):
    project = client.post("/v1/projects", json={"name": "API project"}).json()
    pid = project["id"]
    put = client.put(f"/v1/projects/{pid}/records", headers={"X-Brain-Source": "jarvis"},
                     json={"kind": "bug", "title": "Login falha com SSO", "body": "Callback 500."})
    assert put.status_code == 200 and put.json()["action"] == "created"
    assert client.patch(f"/v1/projects/{pid}/records/bug:login-falha-com-sso/status",
                        json={"status": "fixed", "note": "patch"}).json()["changed"]
    assert client.get(f"/v1/projects/{pid}/records?kind=bug&status=fixed").json()[0]["status"] == "fixed"
    assert client.put(f"/v1/projects/{pid}/records", json={"kind": "nope", "title": "x y"}).status_code == 400
    assert client.get("/v1/projects/missing/context").status_code == 404
    events = client.get(f"/v1/projects/{pid}/events").json()
    assert {e["actor"] for e in events} >= {"jarvis"}


def test_mcp_streamable_http_lists_and_calls_tools(client):
    project = client.post("/v1/projects", json={"name": "MCP project"}).json()
    init = client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "initialize",
                                     "params": {"protocolVersion": "2025-06-18"}}).json()
    assert init["result"]["serverInfo"]["name"] == "brain-engine"
    tools = {t["name"] for t in client.post("/mcp", json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
             .json()["result"]["tools"]}
    assert {"brain_context", "brain_relevant_context", "brain_record", "brain_update_status"} <= tools
    call = client.post(f"/mcp?project={project['id']}", json={
        "jsonrpc": "2.0", "id": 3, "method": "tools/call",
        "params": {"name": "brain_record", "arguments": {"kind": "decision", "title": "Usar MCP HTTP",
                                                         "body": "Transporte JSON simples."}}}).json()
    assert call["result"]["isError"] is False
    listed = client.post("/mcp", headers={"X-Brain-Project": project["id"]}, json={
        "jsonrpc": "2.0", "id": 4, "method": "tools/call",
        "params": {"name": "brain_list", "arguments": {"kind": "decision"}}}).json()
    assert "Usar MCP HTTP" in listed["result"]["content"][0]["text"]
    failed = client.post("/mcp", json={"jsonrpc": "2.0", "id": 5, "method": "tools/call",
                                       "params": {"name": "brain_context", "arguments": {}}}).json()
    assert failed["result"]["isError"] is True
    assert client.post("/mcp", json={"jsonrpc": "2.0", "method": "notifications/initialized"}).status_code == 202


def test_api_token_is_enforced_when_configured(service):
    from dataclasses import replace

    from fastapi.testclient import TestClient

    from brain_engine.api import create_app

    service.settings = replace(service.settings, api_token="secret")
    with TestClient(create_app(service=service)) as http:
        assert http.get("/v1/projects").status_code == 401
        assert http.get("/v1/projects", headers={"Authorization": "Bearer secret"}).status_code == 200
        assert http.get("/healthz").status_code == 200


def test_memory_kinds_cover_the_requested_ontology():
    required = {"idea", "objective", "problem", "hypothesis", "decision", "alternative", "tradeoff", "requirement",
                "architecture", "component", "dependency", "risk", "constraint", "feature", "bug", "state",
                "next_step", "experiment", "result", "learning"}
    assert required <= set(memory.KINDS)


def test_table_of_contents_sections_are_demoted(service, kb_dir):
    from brain_engine.knowledge import is_table_of_contents

    toc = "\n".join(f"- [{i}. Seção sobre memória e agentes](#{i}-secao)" for i in range(8))
    assert is_table_of_contents("Doc › Sumário clicável", "texto")
    assert is_table_of_contents("Doc › Mapa", toc)
    assert not is_table_of_contents("Doc › 14.1 Memória", "Memória episódica guarda eventos.")
    (kb_dir / "10_AGENTS.md").write_text("# 10\n\n## Sumário\n\n" + toc + "\n\n## 10.1 Agentes com memória\n\n"
                                         "Agentes usam memória de longo prazo e ferramentas para lembrar decisões.\n")
    service.ingest("ai-engineering", kb_dir)
    result = service.search("memória de agentes", scope="knowledge", limit=6, token_budget=600)
    sections = [item["section"] for item in result["items"]]
    assert not sections[0].endswith("Sumário")


def test_empty_or_unreadable_source_never_wipes_a_collection(service, kb_dir, tmp_path):
    service.ingest("ai-engineering", kb_dir)
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(FileNotFoundError):
        service.ingest("ai-engineering", empty)
    with service.db.connect() as conn:
        assert conn.execute("SELECT count(*) AS n FROM kb_documents").fetchone()["n"] == 4


def test_telemetry_before_project_creation_is_backfilled(service):
    service.telemetry([{"workflow_id": "creare:x", "project": "creare:early", "component": "creare.compiler",
                        "model": "gpt-4.1-mini", "input_tokens": 100}])
    project = service.ensure_project({"name": "Early", "external_ref": "creare:early"})
    assert service.telemetry_report(project_ref=project["id"])["total"]["calls"] == 1


def test_project_tokens_are_scoped_to_their_own_project(service):
    from dataclasses import replace

    from fastapi.testclient import TestClient

    from brain_engine.api import create_app

    service.settings = replace(service.settings, api_token="admin-secret")
    with TestClient(create_app(service=service)) as http:
        admin = {"Authorization": "Bearer admin-secret"}
        a = http.post("/v1/projects", json={"name": "Alpha Projeto"}, headers=admin).json()
        b = http.post("/v1/projects", json={"name": "Beta Projeto"}, headers=admin).json()
        http.put(f"/v1/projects/{b['id']}/records", headers=admin,
                 json={"kind": "decision", "title": "Segredo do beta", "body": "Não deve vazar."})
        issued = http.post(f"/v1/projects/{a['id']}/access-tokens", headers=admin,
                           json={"label": "creare-export-1"}).json()
        token = {"Authorization": f"Bearer {issued['token']}"}
        assert issued["token"].startswith("brn_")
        assert "token" not in http.get(f"/v1/projects/{a['id']}/access-tokens", headers=admin).json()[0]

        assert http.get("/healthz").status_code == 200
        assert http.get(f"/v1/projects/{a['id']}/context", headers=token).status_code == 200
        assert http.get(f"/v1/projects/{b['id']}/context", headers=token).status_code == 403
        assert http.get("/v1/projects", headers=token).status_code == 403
        assert http.get(f"/v1/projects/{a['id']}/access-tokens", headers=token).status_code == 403
        assert http.post("/v1/telemetry/llm", json={"calls": []}, headers=token).status_code == 403
        assert http.get("/v1/knowledge/collections", headers=token).status_code == 200
        assert http.get("/v1/projects/nao-existe/context", headers=token).status_code == 403
        assert http.get("/v1/projects/nao-existe/context").status_code == 401

        # MCP defaults to the token's project; asking for another project is refused.
        listing = http.post("/mcp", headers=token, json={"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                                                         "params": {"name": "brain_list", "arguments": {}}}).json()
        assert "Segredo do beta" not in listing["result"]["content"][0]["text"]
        assert http.post(f"/mcp?project={b['id']}", headers=token, json={"jsonrpc": "2.0", "id": 2,
                                                                         "method": "tools/list"}).status_code == 403

        # Rotation: the previous export token stops working, the new one works.
        rotated = http.post(f"/v1/projects/{a['id']}/access-tokens", headers=admin,
                            json={"label": "creare-export-2", "rotate_prefix": "creare-export"}).json()
        assert http.get(f"/v1/projects/{a['id']}/context", headers=token).status_code == 401
        new = {"Authorization": f"Bearer {rotated['token']}"}
        assert http.get(f"/v1/projects/{a['id']}/context", headers=new).status_code == 200
        revoked_id = http.get(f"/v1/projects/{a['id']}/access-tokens", headers=admin).json()[0]["id"]
        assert http.delete(f"/v1/projects/{a['id']}/access-tokens/{revoked_id}", headers=admin).json()["revoked"]


def test_archive_forgets_a_record_but_keeps_history(service):
    project = service.ensure_project({"name": "Delta"})
    stored = service.upsert(project["id"], {"kind": "learning", "title": "Prefere pnpm", "body": "Usa pnpm em Node."}, "jarvis")
    service.archive(project["id"], stored["key"], "jarvis")
    assert service.records(project["id"], kind="learning") == []
    found = service.search("pnpm node", scope="project", project_ref=project["id"])
    assert all(item["citation"]["key"] != stored["key"] for item in found["items"])
    with pytest.raises(NotFound):
        service.archive(project["id"], stored["key"], "jarvis")


def test_production_requires_token_and_real_embeddings():
    from brain_engine.settings import Settings

    Settings(environment="local").validate()
    with pytest.raises(RuntimeError, match="BRAIN_API_TOKEN"):
        Settings(environment="production", embedder="e5", database_url="postgresql://u:p@db/brain").validate()
    with pytest.raises(RuntimeError, match="hash"):
        Settings(environment="production", api_token="x" * 32, embedder="hash", database_url="postgresql://u:p@db/brain").validate()
    Settings(environment="production", api_token="x" * 32, embedder="e5", database_url="postgresql://u:p@db/brain").validate()
