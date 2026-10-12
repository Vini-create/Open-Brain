"""CLI and stdio MCP against a real Brain service (uvicorn in a thread)."""

import json
import os
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture
def server(service):
    import uvicorn

    from brain_engine.api import create_app

    port = _free_port()
    config = uvicorn.Config(create_app(service=service), host="127.0.0.1", port=port, log_level="warning")
    instance = uvicorn.Server(config)
    thread = threading.Thread(target=instance.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 15
    while not instance.started and time.monotonic() < deadline:
        time.sleep(0.05)
    assert instance.started
    yield f"http://127.0.0.1:{port}", service
    instance.should_exit = True
    thread.join(timeout=10)


def brain(project: Path, *args, url: str, check=True, stdin: str | None = None):
    env = os.environ.copy()
    env["BRAIN_URL"] = url
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src") + os.pathsep + env.get("PYTHONPATH", "")
    run = subprocess.run([sys.executable, "-m", "second_brain", *map(str, args), "--project", str(project)],
                         text=True, capture_output=True, env=env, input=stdin, timeout=180)
    if check and run.returncode:
        raise AssertionError(f"brain {' '.join(map(str, args))} failed:\n{run.stdout}\n{run.stderr}")
    return run


def test_linked_project_cli_workflow_with_offline_recovery(server, tmp_path):
    url, service = server
    project = tmp_path / "app"
    project.mkdir()
    linked = brain(project, "link", "memory-app", "--create", "--name", "Memory app", url=url)
    assert "Linked" in linked.stdout
    config = json.loads((project / ".brain" / "config.json").read_text())
    pid = config["remote"]["project"]

    brain(project, "remember", "--type", "decision", "--title", "Postgres como fonte da verdade",
          "--content", "Brain usa Postgres com pgvector; .brain é espelho.", url=url)
    assert [r["title"] for r in service.records(pid, kind="decision")] == ["Postgres como fonte da verdade"]
    assert "Postgres como fonte da verdade" in brain(project, "decisions", url=url).stdout

    shown = brain(project, "feature", "Retrieval layer", "--body", "Busca híbrida com RRF",
                  "--status", "in_progress", url=url).stdout
    assert "status: in_progress" in shown
    assert service.record(pid, "Retrieval layer")["status"] == "in_progress"

    context = brain(project, "context", "--task", "Implementa a camada de retrieval", url=url).stdout
    assert "Retrieval layer" in context and "Postgres como fonte da verdade" in context

    sync = json.loads(brain(project, "sync", url=url).stdout)
    assert sync["mirror"]["written"] >= 2
    assert "Memory app" in (project / ".brain" / "BRAIN.md").read_text()
    assert list((project / ".brain" / "knowledge" / "features").glob("*.md"))

    # Offline: writes are queued, reads fall back to the local mirror.
    config["remote"]["url"] = f"http://127.0.0.1:{_free_port()}"
    (project / ".brain" / "config.json").write_text(json.dumps(config))
    queued = json.loads(brain(project, "remember", "--type", "bug", "--title", "Timeout no embed",
                              "--content", "Primeira carga do modelo excede 10s.", url=url).stdout)
    assert queued["queued"] is True
    assert (project / ".brain" / "outbox.jsonl").exists()
    offline = brain(project, "decisions", url=url).stdout
    assert "Postgres como fonte da verdade" in offline

    config["remote"]["url"] = url
    (project / ".brain" / "config.json").write_text(json.dumps(config))
    flushed = json.loads(brain(project, "sync", url=url).stdout)
    assert flushed["outbox"]["sent"] == 1
    assert not (project / ".brain" / "outbox.jsonl").exists()
    assert [r["title"] for r in service.records(pid, kind="bug")] == ["Timeout no embed"]


def test_linked_stdio_mcp_exposes_full_toolset(server, tmp_path):
    url, service = server
    project = tmp_path / "svc"
    project.mkdir()
    brain(project, "link", "mcp-app", "--create", url=url)
    messages = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "brain_record", "arguments": {
            "kind": "architecture", "title": "Camadas", "body": "API → serviço → Postgres"}}},
        {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "brain_relevant_context",
                                                                       "arguments": {"task": "mexer na API"}}},
    ]
    run = brain(project, "mcp", url=url, stdin="\n".join(json.dumps(m) for m in messages) + "\n")
    responses = [json.loads(line) for line in run.stdout.splitlines()]
    assert "brain_relate" in {tool["name"] for tool in responses[1]["result"]["tools"]}
    assert responses[2]["result"]["isError"] is False
    assert "Camadas" in responses[3]["result"]["content"][0]["text"]
