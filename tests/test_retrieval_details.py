from pathlib import Path

from second_brain.config import load_config
from second_brain.core import DETAIL_MARKER, _excerpt, _tokens, initialize, remember, search
from second_brain.storage import connect, index


def test_retrieval_preserves_specific_fact_behind_long_summary(tmp_path: Path):
    initialize(tmp_path)
    remember(tmp_path, type="architecture", title="Project overview",
             content="Conversation history persists locally and cleanup manages older messages. " * 25)
    remember(tmp_path, type="rule", title="Conversation history retention",
             content="Conversation history is retained for 45 days. Pinned sessions never expire.")
    found = search(tmp_path, "When is conversation history removed?", token_budget=500, limit=3)
    assert "45 days" in found["context"]
    assert found["estimated_tokens"] <= 500


def test_excerpt_recovers_late_contract_instead_of_only_intro():
    source = "Overview of general product goals. " * 15 + "\nExternal folder access requires single-use human approval for the exact path."
    assert "single-use" in _excerpt(source, 150, _tokens("How is external folder access approved?"))


def test_index_format_upgrade_is_incremental_and_preserves_canonical_memory(tmp_path: Path):
    initialize(tmp_path)
    result = remember(tmp_path, type="rule", title="Permissions", content="Human approval is required.")
    path = tmp_path / result["path"]
    original = path.read_bytes()
    config = load_config(tmp_path)
    with connect(tmp_path, config) as db:
        db.execute("DELETE FROM index_meta WHERE key='format'")
    assert index(tmp_path, config)["changed_documents"] == 1
    assert index(tmp_path, config)["embedded_chunks"] == 0
    assert path.read_bytes() == original


def test_detail_guide_upgrade_retains_user_notes_and_is_idempotent(tmp_path: Path):
    initialize(tmp_path)
    guide = tmp_path / ".brain/PROJECT_COVERAGE.md"
    guide.write_text("# Custom coverage\nKeep the billing audit.\n")
    initialize(tmp_path)
    updated = guide.read_text()
    initialize(tmp_path)
    assert guide.read_text() == updated
    assert "Keep the billing audit" in updated
    assert updated.count(DETAIL_MARKER) == 1
    assert "error handling" in updated
