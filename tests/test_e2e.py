import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from second_brain.config import load_config
from second_brain.core import (BOOTSTRAP_MARKER, CONTEXT_UPDATE_MARKER, COVERAGE_MARKER,
                               _ensure_agent_instructions, initialize, remember, search)
from second_brain.storage import SCHEMA, connect, index, stats, vector_scores


def cli(*args):
    return subprocess.run([sys.executable, "-m", "second_brain", *map(str, args)],
                          check=True, text=True, capture_output=True)


def test_agent_protocol_is_created_and_upgraded_without_losing_custom_rules(tmp_path: Path):
    path = tmp_path / "AGENT_BRAIN.md"
    _ensure_agent_instructions(path)
    instructions = path.read_text(encoding="utf-8")
    assert BOOTSTRAP_MARKER in instructions
    assert CONTEXT_UPDATE_MARKER in instructions
    assert COVERAGE_MARKER in instructions
    assert all(term in instructions for term in ("What changed", "Why it changed", "validation actually performed", "brain_remember", "brain_search"))
    path.write_text("# Custom rule\n\nKeep this.\n", encoding="utf-8")
    _ensure_agent_instructions(path)
    _ensure_agent_instructions(path)
    upgraded = path.read_text(encoding="utf-8")
    assert "Keep this." in upgraded
    assert upgraded.count(BOOTSTRAP_MARKER) == 1
    assert upgraded.count(CONTEXT_UPDATE_MARKER) == 1
    assert upgraded.count(COVERAGE_MARKER) == 1


def test_existing_brain_protocol_gains_coverage_without_losing_custom_rules(tmp_path: Path):
    from second_brain.core import BOOTSTRAP_INSTRUCTIONS, CONTEXT_UPDATE_INSTRUCTIONS

    initialize(tmp_path)
    path = tmp_path / ".brain" / "AGENT_BRAIN.md"
    legacy = "# Custom instructions\n\nKeep deployment manual.\n\n" + BOOTSTRAP_INSTRUCTIONS + "\n" + CONTEXT_UPDATE_INSTRUCTIONS
    path.write_text(legacy)
    idea = tmp_path / ".brain" / "project" / "idea.md"
    idea.write_text("# Project idea\n\nExisting project facts must be preserved.\n")
    guide = tmp_path / ".brain" / "PROJECT_COVERAGE.md"
    assert guide.exists()
    guide.write_text(guide.read_text() + "\nCustom audit rule: review worker queues.\n")
    initialize(tmp_path)
    first_upgrade = path.read_text()
    initialize(tmp_path)
    assert path.read_text() == first_upgrade
    assert first_upgrade.startswith(legacy.rstrip("\n"))
    assert first_upgrade.count(COVERAGE_MARKER) == 1
    assert idea.read_text().endswith("Existing project facts must be preserved.\n")
    assert "review worker queues" in guide.read_text()


def test_init_two_projects_starts_independent_and_docker_mcp_uses_host_paths(tmp_path: Path, monkeypatch):
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    cli("init", "--project", first)
    assert stats(first, load_config(first))["memories"] == 0
    assert (first / ".brain" / "AGENT_BRAIN.md").exists()

    monkeypatch.setenv("BRAIN_DOCKER_WRAPPER", "/opt/second-brain/scripts/brain-docker")
    monkeypatch.setenv("BRAIN_HOST_PROJECT", str(second))
    initialize(second)
    server = json.loads((second / ".mcp.json").read_text())["mcpServers"]["second-brain"]
    assert server == {"command": "/opt/second-brain/scripts/brain-docker",
                      "args": ["mcp", "--project", str(second)]}
    assert stats(second, load_config(second))["memories"] == 0
    assert not list((second / ".brain" / "knowledge").rglob("*.md"))
    assert (first / ".mcp.json").read_text() != (second / ".mcp.json").read_text()


def test_docker_wrapper_maps_host_project_and_keeps_mcp_stdio(tmp_path: Path):
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    docker = fake_bin / "docker"
    docker.write_text("#!/usr/bin/env python3\nimport json, os, sys\n"
                      "if sys.argv[1:3] == ['image', 'inspect']: sys.exit(0)\n"
                      "open(os.environ['FAKE_DOCKER_OUTPUT'], 'w').write(json.dumps(sys.argv[1:]))\n",
                      encoding="utf-8")
    docker.chmod(0o755)
    project = tmp_path / "my project"
    project.mkdir()
    output = tmp_path / "docker-args.json"
    env = os.environ.copy()
    env.update({"PATH": str(fake_bin) + os.pathsep + env["PATH"],
                "FAKE_DOCKER_OUTPUT": str(output), "BRAIN_MODEL_CACHE": str(tmp_path / "models")})
    wrapper = Path(__file__).resolve().parents[1] / "scripts" / "brain-docker"
    subprocess.run([str(wrapper), "mcp", "--project", str(project)],
                   cwd=tmp_path, env=env, check=True, capture_output=True, text=True)
    args = json.loads(output.read_text())
    assert args[0:2] == ["run", "--rm"]
    assert args[-3:] == ["mcp", "--project", "/workspace"]
    assert "--network" in args and "none" in args
    assert f"{project}:/workspace:z" in args
    assert f"BRAIN_HOST_PROJECT={project}" in args
    subprocess.run([str(wrapper), "model", "download", "--project", str(project)],
                   cwd=tmp_path, env=env, check=True, capture_output=True, text=True)
    args = json.loads(output.read_text())
    assert args[-4:] == ["model", "download", "--project", "/workspace"]
    assert "--network" not in args


def test_init_preserves_existing_agent_and_mcp_config(tmp_path: Path):
    (tmp_path / "AGENTS.md").write_text("# Existing rules\n\nKeep tests green.\n", encoding="utf-8")
    (tmp_path / ".mcp.json").write_text(json.dumps({"mcpServers": {
        "other": {"command": "other"},
        "second-brain": {"command": "/old/python", "args": ["mcp", "--project", "/old/project"]}
    }}), encoding="utf-8")
    cli("init", "--project", tmp_path)
    cli("init", "--project", tmp_path)
    instructions = (tmp_path / "AGENTS.md").read_text()
    assert "Keep tests green" in instructions
    assert instructions.count(".brain/AGENT_BRAIN.md") == 1
    servers = json.loads((tmp_path / ".mcp.json").read_text())["mcpServers"]
    assert set(servers) == {"other", "second-brain"}
    assert servers["second-brain"]["command"] == sys.executable
    assert servers["second-brain"]["args"][-1] == str(tmp_path)


def test_legacy_index_migration_and_model_change(tmp_path: Path):
    cli("init", "--project", tmp_path)
    database = tmp_path / ".brain" / "index" / "brain.db"
    database.unlink()
    old = sqlite3.connect(database)
    old.executescript(SCHEMA)
    old.execute("INSERT INTO documents VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                ("decision-old", ".brain/knowledge/decisions/old.md", "hash", "decision", "Old", "[]",
                 0.5, "active", "2026-01-01T00:00:00+00:00", "2026-01-01T00:00:00+00:00", "# Old\n\nOld fact"))
    old.execute("INSERT INTO chunks(document_id,ordinal,text,embedding) VALUES(?,?,?,?)",
                ("decision-old", 0, "Old fact", json.dumps([1.0] + [0.0] * 383)))
    old.commit()
    old.close()
    with connect(tmp_path, load_config(tmp_path)) as db:
        assert db.execute("SELECT COUNT(*) FROM vec_chunks").fetchone()[0] == 1
        assert db.execute("PRAGMA user_version").fetchone()[0] == 2
    config_path = tmp_path / ".brain" / "config.json"
    config = json.loads(config_path.read_text())
    config["embedding"]["model"] = "another/local-model"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    with pytest.raises(ValueError, match="brain rebuild"):
        connect(tmp_path, load_config(tmp_path))
    assert index(tmp_path, load_config(tmp_path), rebuild=True)["deleted_documents"] == 0


def test_vector_scores_work_above_sqlite_vec_knn_limit(tmp_path: Path):
    import sqlite_vec

    initialize(tmp_path)
    query = [1.0] + [0.0] * 383
    vector = sqlite_vec.serialize_float32(query)
    with connect(tmp_path, load_config(tmp_path)) as db:
        db.executemany("INSERT INTO vec_chunks(rowid, embedding) VALUES (?, ?)",
                       ((rowid, vector) for rowid in range(1, 4102)))
        scores = vector_scores(db, query)
    assert len(scores) == 4101
    assert scores[4101] == pytest.approx(1.0)


def test_v1_acceptance(tmp_path: Path):
    project = tmp_path / "new-project"
    project.mkdir()
    cli("init", "--project", project)
    brain = project / ".brain"
    assert (brain / "project" / "idea.md").exists()
    assert (brain / "project" / "overview.md").exists()
    assert (brain / "project" / "goals.md").exists()
    assert (brain / "AGENT_BRAIN.md").exists()
    assert "brain_search" in (brain / "AGENT_BRAIN.md").read_text()
    assert (project / ".mcp.json").exists()
    ignored = (project / ".gitignore").read_text()
    assert all(path in ignored.splitlines() for path in
               (".brain/index/", ".brain/history/", ".brain/mcp.json", ".mcp.json"))

    (brain / "project" / "idea.md").write_text(
        "# Ideia\n\nAPI SaaS para gerenciamento de projetos para equipes pequenas.\n", encoding="utf-8")
    decision = remember(project, type="decision", title="Autenticação JWT",
                        content="Usar JWT com refresh token em cookie HTTPOnly para autenticação da API SaaS.",
                        tags=["auth"], importance=0.9)
    remember(project, type="architecture", title="Stack", content="API FastAPI com banco PostgreSQL.")
    remember(project, type="rule", title="Separação de camadas",
             content="Router nunca acessa banco de dados diretamente; usa Service e Repository.")
    assert decision["index"]["embedded_chunks"] >= 1
    assert stats(project, load_config(project))["memories"] == 4
    with connect(project, load_config(project)) as db:
        assert db.execute("SELECT COUNT(*) FROM vec_chunks").fetchone()[0] == 4
    assert index(project, load_config(project))["embedded_chunks"] == 0

    found = search(project, "Implemente autenticação para a API de projetos", token_budget=350)
    assert found["estimated_tokens"] <= 350
    context = found["context"]
    for term in ("SaaS", "FastAPI", "PostgreSQL", "JWT", "HTTPOnly", "Router"):
        assert term in context
    assert found["results"][0]["type"] == "decision"
    assert len(search(project, "autenticação", tags=["auth"])["results"]) == 1
    assert (brain / "history" / "searches.jsonl").exists()
    assert remember(project, type="decision", title="Autenticação JWT",
                    content="Usar JWT com refresh token em cookie HTTPOnly para autenticação da API SaaS.")["changed"] is False

    changed = remember(project, type="decision", title="Autenticação JWT",
                       content="Usar JWT com refresh token em cookie HTTPOnly, com rotação após cada uso.")
    assert changed["index"]["changed_documents"] == 1
    assert list((brain / "history" / "versions" / changed["id"]).glob("*.md"))
    assert "auth" in (project / changed["path"]).read_text()

    overview = brain / "project" / "overview.md"
    overview.write_text("# Visão operacional\n\nBackend em FastAPI.\n", encoding="utf-8")
    assert index(project, load_config(project))["changed_documents"] == 1
    assert index(project, load_config(project))["changed_documents"] == 0
    rebuild = cli("rebuild", "--project", project)
    assert json.loads(rebuild.stdout)["changed_documents"] == 5
    with connect(project, load_config(project)) as db:
        assert db.execute("SELECT COUNT(*) FROM vec_chunks").fetchone()[0] == 5
    assert "rotação" in search(project, "Como funciona o refresh token?")["context"]

    messages = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "test", "version": "1"}}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "brain_remember", "arguments": {"type": "feature", "title": "OAuth", "content": "Google OAuth será implementado após autenticação básica."}}},
        {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "brain_search", "arguments": {"query": "OAuth", "limit": 2}}},
        {"jsonrpc": "2.0", "id": 5, "method": "tools/call", "params": {"name": "brain_status", "arguments": {}}},
    ]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src") + os.pathsep + env.get("PYTHONPATH", "")
    run = subprocess.run([sys.executable, "-m", "second_brain", "mcp", "--project", str(project)],
                         input="\n".join(json.dumps(message) for message in messages) + "\n",
                         text=True, capture_output=True, env=env, check=True, timeout=120)
    responses = [json.loads(line) for line in run.stdout.splitlines()]
    assert [response["id"] for response in responses] == [1, 2, 3, 4, 5]
    assert CONTEXT_UPDATE_MARKER in responses[0]["result"]["instructions"]
    assert BOOTSTRAP_MARKER in responses[0]["result"]["instructions"]
    assert "What changed" in responses[0]["result"]["instructions"]
    local_tools = {tool["name"] for tool in responses[1]["result"]["tools"]}
    assert {"brain_search", "brain_remember", "brain_status", "brain_context", "brain_list"} <= local_tools
    assert "brain_relate" not in local_tools  # typed relations need the Brain service
    assert responses[2]["result"]["isError"] is False
    assert "OAuth" in responses[3]["result"]["content"][0]["text"]
    assert "6" in responses[4]["result"]["content"][0]["text"]
    next((brain / "knowledge" / "features").glob("*.md")).unlink()
    assert index(project, load_config(project))["deleted_documents"] == 1
    with connect(project, load_config(project)) as db:
        assert db.execute("SELECT COUNT(*) FROM vec_chunks").fetchone()[0] == 5
        db.execute("UPDATE documents SET updated_at='2020-01-01T00:00:00+00:00'")
        db.execute("UPDATE documents SET updated_at='2026-10-09T14:00:00+00:00' WHERE id='project-idea'")
        db.execute("UPDATE documents SET updated_at='2026-10-09T11:01:00-03:00' WHERE id=?", (changed["id"],))
    assert stats(project, load_config(project))["last_update"] == "2026-10-09T11:01:00-03:00"
