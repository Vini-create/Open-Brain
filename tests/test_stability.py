"""Acceptance of durable storage, actual cosine retrieval and agent transport."""

import json
import shutil
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import subprocess
import sys

import pytest

from second_brain.config import load_config
from second_brain.core import ACCESS_MARKER, initialize, remember, search
from second_brain.embedding import embed
from second_brain.mcp_tools import call_tool
from second_brain.remote import LocalBackend
from second_brain.storage import connect, db_path, index, stats, vector_scores


def assert_consistent(root, expected):
    with connect(root, load_config(root)) as db:
        assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []
        assert db.execute("SELECT COUNT(*) FROM documents").fetchone()[0] == expected
        chunks = {row[0] for row in db.execute("SELECT id FROM chunks")}
        vectors = {row[0] for row in db.execute("SELECT rowid FROM vec_chunks")}
        assert chunks == vectors


def test_clone_without_ignored_directories_and_noop_reindex(tmp_path):
    initialize(tmp_path)
    saved = remember(tmp_path, type="rule", title="Session lifetime",
                     content="Idle sessions expire after 37 minutes.")
    shutil.rmtree(tmp_path / ".brain/history")
    shutil.rmtree(tmp_path / ".brain/index")
    assert "37 minutes" in search(tmp_path, "When does an idle session end?")["context"]
    shutil.rmtree(tmp_path / ".brain/history")
    remember(tmp_path, type="rule", title="Pinned sessions",
             content="Pinned sessions are kept until manually removed.")
    # Even an idempotent remember must restore a missing disposable index.
    shutil.rmtree(tmp_path / ".brain/index")
    assert not remember(tmp_path, type="rule", title="Session lifetime",
                        content="Idle sessions expire after 37 minutes.")["changed"]
    assert_consistent(tmp_path, 2)
    assert (tmp_path / saved["path"]).exists()


def test_rename_swap_duplicate_and_delete_keep_vectors_in_sync(tmp_path):
    initialize(tmp_path)
    a = remember(tmp_path, type="rule", title="Retention", content="Retain audit events for 91 days.")
    b = remember(tmp_path, type="rule", title="Payments", content="Deduplicate payments by event identifier.")
    first, second = tmp_path / a["path"], tmp_path / b["path"]
    body_a, body_b = first.read_bytes(), second.read_bytes()
    first.write_bytes(body_b)
    second.write_bytes(body_a)
    index(tmp_path, load_config(tmp_path))
    assert_consistent(tmp_path, 2)
    moved = second.with_name("moved.md")
    second.rename(moved)
    assert index(tmp_path, load_config(tmp_path))["deleted_documents"] == 0
    assert "91 days" in search(tmp_path, "How long are audit events retained?")["context"]
    assert_consistent(tmp_path, 2)
    second.write_bytes(body_a)
    before = db_path(tmp_path, load_config(tmp_path)).read_bytes()
    with pytest.raises(ValueError, match="Duplicate memory id"):
        index(tmp_path, load_config(tmp_path))
    assert db_path(tmp_path, load_config(tmp_path)).read_bytes() == before
    second.unlink()
    moved.unlink()
    assert index(tmp_path, load_config(tmp_path))["deleted_documents"] == 1
    assert_consistent(tmp_path, 1)


@pytest.mark.parametrize("rebuild", [False, True])
def test_embedding_failure_preserves_last_index(tmp_path, monkeypatch, rebuild):
    initialize(tmp_path)
    saved = remember(tmp_path, type="rule", title="Retention", content="Retain audit events for 91 days.")
    config = load_config(tmp_path)
    before = db_path(tmp_path, config).read_bytes()
    path = tmp_path / saved["path"]
    path.write_text(path.read_text().replace("91 days", "62 days"))

    def fail(*args, **kwargs):
        raise RuntimeError("simulated model failure")

    monkeypatch.setattr("second_brain.storage.embed", fail)
    with pytest.raises(RuntimeError, match="simulated model failure"):
        index(tmp_path, config, rebuild=rebuild)
    assert db_path(tmp_path, config).read_bytes() == before
    assert_consistent(tmp_path, 1)
    assert not list((tmp_path / ".brain/index").glob("rebuild-*.db"))
    monkeypatch.undo()
    index(tmp_path, config, rebuild=rebuild)
    assert "62 days" in search(tmp_path, "audit retention")["context"]
    assert_consistent(tmp_path, 1)


def test_vectors_match_actual_model_and_cosine_after_update(tmp_path):
    import numpy as np
    initialize(tmp_path)
    saved = remember(tmp_path, type="decision", title="Credential rotation",
                     content="Refresh tokens are single-use and rotate at each renewal.", tags=["auth"])
    remember(tmp_path, type="rule", title="Invoices", content="Invoices are exported as PDF once per month.")
    config = load_config(tmp_path)
    query = embed(["Como invalidar a credencial anterior ao renovar a sessão?"], config, query=True)[0]
    with connect(tmp_path, config) as db:
        scores = vector_scores(db, query)
        rows = db.execute("SELECT c.*, v.embedding AS stored FROM chunks c JOIN vec_chunks v ON v.rowid=c.id").fetchall()
        for row in rows:
            vector = np.frombuffer(row["stored"], dtype=np.float32)
            assert len(vector) == 384
            assert np.isfinite(vector).all()
            assert np.linalg.norm(vector) == pytest.approx(1, abs=1e-5)
            assert vector == pytest.approx(json.loads(row["embedding"]), abs=1e-6)
            cosine = np.dot(vector, query) / (np.linalg.norm(vector) * np.linalg.norm(query))
            assert scores[row["id"]] == pytest.approx(max(0, cosine), abs=1e-6)
        expected = embed(["Credential rotation\nTags: auth\n" + next(r["text"] for r in rows if r["document_id"] == saved["id"])], config)[0]
        actual = next(r["stored"] for r in rows if r["document_id"] == saved["id"])
        assert np.frombuffer(actual, dtype=np.float32) == pytest.approx(expected, abs=1e-6)
        winner = max(scores, key=scores.get)
        assert next(r for r in rows if r["id"] == winner)["document_id"] == saved["id"]
    remember(tmp_path, type="decision", title="Credential rotation",
             content="Refresh tokens expire after 17 minutes and rotate at each renewal.")
    assert "17 minutes" in search(tmp_path, "refresh token lifetime")["context"]
    assert "single-use" not in search(tmp_path, "refresh token lifetime")["context"]
    assert_consistent(tmp_path, 2)


def test_mcp_agent_roundtrip_restart_filters_and_errors(tmp_path):
    initialize(tmp_path)
    remember(tmp_path, type="rule", title="Other project policy", content="Background jobs retry up to 19 times.", tags=["other"])
    requests = [
        {"id": 1, "method": "initialize", "params": {}},
        {"id": 2, "method": "tools/call", "params": {"name": "brain_remember", "arguments": {
            "type": "rule", "title": "Worker retries", "content": "Background jobs retry up to 7 times.", "tags": ["worker"]}}},
        {"id": 3, "method": "tools/call", "params": {"name": "brain_search", "arguments": {
            "query": "How often is a failed job attempted again?", "tags": ["worker"]}}},
        {"id": 4, "method": "tools/call", "params": {"name": "brain_search", "arguments": {"query": "jobs", "limit": 0}}},
        {"id": 5, "method": "tools/call", "params": {"name": "brain_status", "arguments": {}}},
    ]
    run = subprocess.run([sys.executable, "-m", "second_brain", "mcp", "--project", str(tmp_path)],
                         input="\n".join(json.dumps({"jsonrpc": "2.0", **r}) for r in requests) + "\n",
                         text=True, capture_output=True, check=True, timeout=120)
    responses = [json.loads(line)["result"] for line in run.stdout.splitlines()]
    assert ACCESS_MARKER in responses[0]["instructions"]
    assert responses[1]["isError"] is False
    assert "7 times" in responses[2]["content"][0]["text"]
    assert "19 times" not in responses[2]["content"][0]["text"]
    assert responses[3]["isError"] is True
    assert responses[4]["isError"] is False
    assert "7 times" in search(tmp_path, "worker retries", tags=["worker"])["context"]
    assert_consistent(tmp_path, 2)


def test_concurrent_writers_and_rebuild(tmp_path):
    initialize(tmp_path)
    config = load_config(tmp_path)

    def write(i):
        return remember(tmp_path, type="rule", title=f"Worker {i} policy",
                        content=f"Worker {i} uses a timeout of {30 + i} seconds.")

    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(write, i) for i in range(6)]
        futures.append(pool.submit(index, tmp_path, config, rebuild=True))
        for future in futures:
            future.result(timeout=120)
    assert_consistent(tmp_path, 6)
    assert index(tmp_path, config)["changed_documents"] == 0


def test_missing_vector_is_reported_and_rebuild_repairs_it(tmp_path):
    initialize(tmp_path)
    remember(tmp_path, type="rule", title="Recovery", content="Use the canonical Markdown to rebuild the index.")
    config = load_config(tmp_path)
    with connect(tmp_path, config) as db:
        db.execute("DELETE FROM vec_chunks")
    health = stats(tmp_path, config)
    assert health["index_consistent"] is False
    assert health["missing_vectors"] == 1
    with pytest.raises(ValueError, match="brain rebuild"):
        search(tmp_path, "How is the index recovered?")
    index(tmp_path, config, rebuild=True)
    assert stats(tmp_path, config)["index_consistent"] is True
    assert_consistent(tmp_path, 1)


def test_separate_process_writers_share_the_project_lock(tmp_path):
    initialize(tmp_path)
    # Fault/concurrency tests use fixed vectors; semantic acceptance above uses
    # the real model. This isolates cross-process storage without three models.
    script = """
import sys
from pathlib import Path
import second_brain.storage as storage
from second_brain.core import remember
storage.embed = lambda texts, config: [[1.0] + [0.0] * 383 for _ in texts]
for i in range(3):
    remember(Path(sys.argv[1]), type='rule', title=f'Process {sys.argv[2]} record {i}',
             content=f'Process {sys.argv[2]} preserves durable fact number {i}.')
"""
    processes = [subprocess.Popen([sys.executable, "-c", script, str(tmp_path), str(i)],
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for i in range(3)]
    for process in processes:
        stdout, stderr = process.communicate(timeout=60)
        assert process.returncode == 0, stdout + stderr
    assert_consistent(tmp_path, 9)


def test_mcp_key_updates_title_and_keeps_metadata_and_status_body(tmp_path):
    initialize(tmp_path)
    backend = LocalBackend(tmp_path)
    created = json.loads(call_tool(backend, "brain_record", {
        "kind": "feature", "key": "retry-policy", "title": "Retry policy", "body": "Retry failed jobs 7 times.",
        "tags": ["worker"], "data": {"owner": "scheduler"}, "importance": 0.8}))
    updated = json.loads(call_tool(backend, "brain_record", {
        "kind": "feature", "key": "retry-policy", "title": "Worker retry policy", "body": "Retry failed jobs 9 times."}))
    assert created["id"] == updated["id"]
    call_tool(backend, "brain_update_status", {"ref": "retry-policy", "status": "implemented"})
    record = backend.get(None, "retry-policy")
    assert record["title"] == "Worker retry policy"
    assert record["status"] == "implemented"
    assert "9 times" in record["body"]
    assert record["data"] == {"owner": "scheduler"}
    assert record["tags"] == ["worker"]
    # The status tool also accepts existing title-identified V1 records.
    old = remember(tmp_path, type="feature", title="Legacy worker", content="Legacy workers retry one time.")
    backend.update_status(None, old["id"], "implemented", "")
    assert backend.get(None, old["id"])["status"] == "implemented"
    assert_consistent(tmp_path, 2)
