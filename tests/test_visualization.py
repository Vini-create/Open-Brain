import json
import re
import subprocess
import sys
from pathlib import Path

from second_brain.config import load_config
from second_brain.core import MAP_INSTRUCTIONS, MAP_MARKER, initialize, remember, search
from second_brain.mcp import instructions_for
from second_brain.storage import index, stats
from second_brain.visualization import snapshot


def map_data(project: Path) -> dict:
    html = (project / ".brain" / "map.html").read_text(encoding="utf-8")
    match = re.search(r'<script id="brain-data" type="application/json">(.*?)</script>', html, re.S)
    assert match is not None
    return json.loads(match.group(1))


def cli(*args: object) -> str:
    result = subprocess.run([sys.executable, "-m", "second_brain", *map(str, args)],
                            check=True, text=True, capture_output=True)
    return result.stdout


def mcp_search(project: Path, query: str) -> str:
    messages = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
            "protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "test", "version": "1"}}},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {
            "name": "brain_search", "arguments": {"query": query}}},
    ]
    result = subprocess.run([sys.executable, "-m", "second_brain", "mcp", "--project", str(project)],
                            input="\n".join(json.dumps(item) for item in messages) + "\n",
                            check=True, text=True, capture_output=True, timeout=120)
    return json.loads(result.stdout.splitlines()[1])["result"]["content"][0]["text"]


def test_empty_map_needs_no_model_and_shows_manual_markdown(tmp_path: Path, monkeypatch):
    project = tmp_path / "new-project"
    project.mkdir()
    cli("init", "--project", project)
    page = project / ".brain" / "map.html"
    assert page.exists()
    assert ".brain/map.html" in (project / ".gitignore").read_text().splitlines()
    assert map_data(project)["summary"]["memories"] == 0

    (project / ".brain/project/idea.md").write_text("# Project idea\n\nA local issue tracker.\n", encoding="utf-8")
    cli("map", "--project", project)
    data = map_data(project)
    assert data["summary"]["memories"] == 1
    assert data["summary"]["memory_text_tokens_estimate"] > 0
    assert "A local issue tracker" in data["memories"][0]["body"]
    # Viewing Markdown does not silently index or download an embedding model.
    assert stats(project, load_config(project))["memories"] == 0
    monkeypatch.setenv("BRAIN_HOST_PROJECT", str(tmp_path / "host-named-project"))
    assert snapshot(project)["project"] == "host-named-project"


def test_map_handoff_is_delivered_to_new_and_existing_agents(tmp_path: Path):
    initialize(tmp_path)
    path = tmp_path / ".brain/AGENT_BRAIN.md"
    assert MAP_MARKER in path.read_text()
    for phrase in ("first useful project facts", "brain map", "clickable absolute",
                   "HTML preview", "No local server", "do not reopen"):
        assert phrase in instructions_for(tmp_path)
    # Existing MCP clients receive the section before a user reruns init.
    legacy = path.read_text().replace("\n" + MAP_INSTRUCTIONS, "")
    assert MAP_MARKER not in legacy
    path.write_text(legacy + "\nCustom project rule: keep this.\n")
    before = path.read_bytes()
    assert MAP_MARKER in instructions_for(tmp_path)
    assert path.read_bytes() == before
    initialize(tmp_path)
    initialize(tmp_path)
    upgraded = path.read_text()
    assert upgraded.count(MAP_MARKER) == 1
    assert "Custom project rule: keep this." in upgraded


def test_maps_and_search_stay_inside_each_project_after_new_process(tmp_path: Path):
    first, second = tmp_path / "first", tmp_path / "second"
    first.mkdir()
    second.mkdir()
    initialize(first)
    initialize(second)
    dangerous = "Unique first-project fact: aurora-742. </script><script>window.leak=1</script>"
    one = remember(first, type="decision", title="Authentication plan", content=dangerous,
                   tags=["auth"], importance=0.9)
    remember(first, type="architecture", title="Session storage",
             content="Sessions stay in this project's local database.",
             tags=["auth"], related=[one["id"]])
    remember(second, type="decision", title="Billing plan",
             content="Unique second-project fact: orbit-916.", tags=["billing"])

    first_page = (first / ".brain/map.html").read_text(encoding="utf-8")
    assert "</script><script>window.leak=1</script>" not in first_page
    assert "\\u003c/script\\u003e" in first_page
    first_data, second_data = map_data(first), map_data(second)
    assert first_data["summary"]["memories"] == 2
    assert first_data["summary"]["tag_links"] == 2
    assert first_data["summary"]["explicit_links"] == 1
    assert {link["source"] for link in first_data["links"]} | {link["target"] for link in first_data["links"]} == {
        one["id"], next(item["id"] for item in first_data["memories"] if item["title"] == "Session storage")}
    assert second_data["summary"]["memories"] == 1
    assert "aurora-742" not in json.dumps(second_data)
    assert "orbit-916" not in json.dumps(first_data)

    # New CLI processes read the durable per-project Markdown and SQLite files.
    assert json.loads(cli("status", "--project", first))["memories"] == 2
    assert json.loads(cli("status", "--project", second))["memories"] == 1
    assert "aurora-742" in search(first, "aurora-742")["context"]
    assert all("aurora-742" not in item["content"] for item in search(second, "aurora-742")["results"])
    assert "aurora-742" in mcp_search(first, "authentication plan")
    assert "aurora-742" not in mcp_search(second, "authentication plan")

    (first / one["path"]).unlink()
    assert index(first, load_config(first))["deleted_documents"] == 1
    assert map_data(first)["summary"]["memories"] == 1
    assert map_data(first)["links"] == []
    assert map_data(second)["summary"]["memories"] == 1
    assert "orbit-916" in cli("search", "orbit-916", "--project", second)
    assert snapshot(first)["summary"]["memories"] == 1
