import json
import os
import re
import sys
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

from .config import DEFAULT_CONFIG, TYPES, load_config
from .documents import document_id, now, parse, render
from .embedding import embed
from .storage import connect, index, stats, vector_scores

CONTEXT_UPDATE_MARKER = "<!-- second-brain-context-update:v2 -->"
BOOTSTRAP_MARKER = "<!-- second-brain-bootstrap:v1 -->"
COVERAGE_MARKER = "<!-- second-brain-project-coverage:v1 -->"
BOOTSTRAP_INSTRUCTIONS = f"""## First use in a new project

{BOOTSTRAP_MARKER}

If `brain_status` shows no memories or only empty templates, ask the user for a
project description or read the essential project files once. Fill
`.brain/project/idea.md`, `overview.md`, and `goals.md` with verified facts, then
run `brain index`. Save durable decisions with `brain_remember`. Do not invent an
architecture or dump the entire codebase into memory. Search the Brain for each
task and read the source files needed for implementation.
"""
PROJECT_COVERAGE_INSTRUCTIONS = f"""## Build coverage for an existing project

{COVERAGE_MARKER}

When adopting an established project or when memory contains only summaries,
read `.brain/PROJECT_COVERAGE.md` and audit the main modules, flows, decisions,
rules, validation commands and remaining work. Check specific fact recovery
through `brain_search` and save sources checked and gaps in "Memory coverage".
Indexed record counts alone do not establish coverage. Read the detailed guide
for this audit; later tasks update relevant memories incrementally.
"""
PROJECT_COVERAGE_GUIDE = """# Existing project memory coverage

Project summaries provide entry points. When adopting an established project,
or when memory contains only summaries, audit coverage even if `brain_status`
reports indexed records. Search existing memory first, then:

1. Inspect the source tree, manifests, documentation, entry points and relevant
   tests to identify major subsystems and critical flows. Skip generated files,
   dependencies and secrets. Read implementation where facts need verification.
2. Save focused `architecture` or `feature` memories for each major subsystem:
   responsibilities, source paths, interfaces, dependencies and important flows.
   Record documented choices and reasons as `decision` memories; mark unknown
   reasons explicitly. Use shared tags and related memory IDs for connections.
3. Capture confirmed invariants as `rule` or `constraint` memories, setup and
   validation commands, known bugs, and current next steps. Keep facts concise
   and independently retrievable; use existing type/title to update a memory.
4. Test coverage with specific `brain_search` queries about the main flow,
   module boundaries, data storage, external integrations, important rules,
   validation commands and unfinished work, where applicable. Compare returned
   facts with the sources. For missing facts, inspect code, save and search again.
5. Save a `constraint` memory titled "Memory coverage" listing areas covered,
   sources checked, retrieval checks and remaining gaps. Distinguish retrieval
   checks from application tests. Report partial coverage honestly.

Use relevant fact recovery as the readiness criterion. Record counts alone do
not establish coverage; avoid a fixed document quota or a whole-codebase dump.
This initial audit costs context once. Later tasks fill gaps and update changed
facts incrementally, including after a new session or context compaction.
"""
CONTEXT_UPDATE_INSTRUCTIONS = f"""## Update context after meaningful changes

{CONTEXT_UPDATE_MARKER}

After a meaningful change, and before ending, compacting, or handing off a
session, use `brain_remember` to save durable knowledge. Update the existing
memory with the same type and title instead of creating a duplicate. Include:

- What changed and the current state, including useful paths or contracts.
- Why it changed: requirement, problem, or decision.
- Impact, constraints, validation actually performed, and remaining work.

Example: "Changed: refresh tokens use HTTPOnly cookies. Why: reduce exposure
to scripts. Impact: the frontend cannot read the token. Validation: refresh
test passed." Never invent tests. Do not save every diff, log, conversation, or
whole source file; save facts useful to a later session that are not obvious
from the code.
"""

AGENT_INSTRUCTIONS = """# Second Brain — Agent Instructions

Persistent memory: `.brain/`. MCP: `brain_search`, `brain_remember`, `brain_status`.

## Before exploring the project

Use `brain_search` for the project's purpose, architecture, decisions, rules,
bugs, current state, and next steps before rereading the repository. Verify
implementation details in source code before editing or testing. Keep
`project/idea.md`, `overview.md`, and `goals.md` accurate. `brain index` syncs
manual Markdown edits.

Search before rediscovering. Remember after learning.
""" + "\n" + BOOTSTRAP_INSTRUCTIONS + "\n" + PROJECT_COVERAGE_INSTRUCTIONS + "\n" + CONTEXT_UPDATE_INSTRUCTIONS


def _ensure_agent_instructions(path: Path) -> None:
    if not path.exists():
        path.write_text(AGENT_INSTRUCTIONS, encoding="utf-8")
        return
    existing = path.read_text(encoding="utf-8")
    additions = [section for marker, section in (
        (BOOTSTRAP_MARKER, BOOTSTRAP_INSTRUCTIONS),
        (COVERAGE_MARKER, PROJECT_COVERAGE_INSTRUCTIONS),
        (CONTEXT_UPDATE_MARKER, CONTEXT_UPDATE_INSTRUCTIONS),
    ) if marker not in existing]
    if additions:
        path.write_text(existing.rstrip("\n") + "\n\n" + "\n\n".join(additions), encoding="utf-8")

PROJECT_TEMPLATES = {
    "idea.md": "# Project idea\n\n## What it is\n\n## Problem\n\n## Audience\n\n## Value proposition\n\n## Vision\n",
    "overview.md": "# Project overview\n\n## Stack\n\n## Architecture\n\n## Components and flows\n\n## Current state\n",
    "goals.md": "# Goals\n\n## Current priorities\n\n## Out of scope\n\n## Next steps\n",
}

CHARS_PER_TOKEN = 3  # Conservative local estimate for Portuguese Markdown.
SEARCH_ALIASES = (
    ("embedding", {"embed", "vetor"}),
    ("credential", {"chave", "key", "crede"}),
    ("cpu", {"cpu", "maqui"}),
    ("ranking", {"ranki", "formu", "prior", "score", "peso", "relev"}),
    ("budget", {"budge", "orcam", "limit", "corto", "taman"}),
    ("history", {"histo", "versa", "snaps"}),
)


def initialize(root: Path, idea: str | None = None) -> dict:
    root = root.resolve()
    brain = root / ".brain"
    for folder in ("project", "index", "history", *(f"knowledge/{name}" for name in TYPES.values())):
        (brain / folder).mkdir(parents=True, exist_ok=True)
    config_path = brain / "config.json"
    if not config_path.exists():
        config_path.write_text(json.dumps(DEFAULT_CONFIG, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for name, template in PROJECT_TEMPLATES.items():
        (brain / "project" / name).write_text(template, encoding="utf-8") if not (brain / "project" / name).exists() else None
    if idea:
        path = brain / "project" / "idea.md"
        current = path.read_text(encoding="utf-8")
        if current == PROJECT_TEMPLATES["idea.md"]:
            path.write_text(f"# Project idea\n\n{idea.strip()}\n", encoding="utf-8")
        elif idea.strip() not in current:
            raise ValueError("idea.md already contains text; edit the file directly")
    _ensure_agent_instructions(brain / "AGENT_BRAIN.md")
    coverage_guide = brain / "PROJECT_COVERAGE.md"
    if not coverage_guide.exists():
        coverage_guide.write_text(PROJECT_COVERAGE_GUIDE, encoding="utf-8")
    readme = brain / "README.md"
    if not readme.exists():
        readme.write_text("# Local Second Brain\n\nDescribe this project in `project/idea.md`, "
                          "`overview.md`, and `goals.md`, then run `brain index`. Use `brain search` "
                          "to retrieve context and `brain remember` for durable knowledge. Markdown "
                          "files are canonical; rebuild `index/brain.db` with `brain rebuild`.\n\n"
                          "The default `intfloat/multilingual-e5-small` embedding model runs locally "
                          "on CPU, without a provider or API key. Run `brain model download` once to "
                          "fetch its public weights. Vectors are indexed with SQLite + sqlite-vec.\n\n"
                          "The MCP server uses stdio. Adapt `mcp.json` to your client if needed. "
                          "`AGENT_BRAIN.md` tells the agent when to search and save.\n\n"
                          "Open `map.html` in a browser to explore this project's memories, links, "
                          "and approximate stored context size. Run `brain map` to refresh it.\n", encoding="utf-8")
    ignore = root / ".gitignore"
    original = ignore.read_text(encoding="utf-8") if ignore.exists() else ""
    local_paths = (".brain/index/", ".brain/history/", ".brain/mcp.json", ".brain/map.html", ".mcp.json")
    missing = [entry for entry in local_paths if entry not in original.splitlines()]
    if missing:
        ignore.write_text(original.rstrip("\n") + ("\n" if original else "")
                          + "\n".join(missing) + "\n", encoding="utf-8")
    agents = root / "AGENTS.md"
    if not agents.exists():
        agents.write_text("# Agent instructions\n\nRead `.brain/AGENT_BRAIN.md` before exploring this project. "
                          "Search the Brain first for persistent project context.\n", encoding="utf-8")
    elif ".brain/AGENT_BRAIN.md" not in agents.read_text(encoding="utf-8"):
        with agents.open("a", encoding="utf-8") as file:
            file.write("\n## Second Brain\n\nRead `.brain/AGENT_BRAIN.md` before exploring this project.\n")
    docker_wrapper = os.environ.get("BRAIN_DOCKER_WRAPPER")
    host_project = os.environ.get("BRAIN_HOST_PROJECT")
    if docker_wrapper and host_project:
        server = {"command": docker_wrapper, "args": ["mcp", "--project", host_project]}
    else:
        server = {"command": sys.executable, "args": ["-m", "second_brain", "mcp", "--project", str(root)]}
    mcp_config = {"mcpServers": {"second-brain": server}}
    (brain / "mcp.json").write_text(json.dumps(mcp_config, indent=2) + "\n", encoding="utf-8")
    root_mcp = root / ".mcp.json"
    if not root_mcp.exists():
        root_mcp.write_text(json.dumps(mcp_config, indent=2) + "\n", encoding="utf-8")
    else:
        try:
            existing = json.loads(root_mcp.read_text(encoding="utf-8"))
            if isinstance(existing, dict) and isinstance(existing.get("mcpServers"), dict):
                existing["mcpServers"]["second-brain"] = mcp_config["mcpServers"]["second-brain"]
                root_mcp.write_text(json.dumps(existing, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        except (ValueError, OSError):
            pass  # The generated .brain/mcp.json remains available for manual setup.
    config = load_config(root)
    from .storage import connect
    connect(root, config).close()
    result = index(root, config) if idea else stats(root, config)
    from .visualization import write_map
    write_map(root)
    return result


def _normalized(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().casefold()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", text)).strip()


def remember(root: Path, *, type: str, title: str, content: str, tags: list[str] | None = None,
             importance: float | None = None, related: list[str] | None = None, status: str | None = None) -> dict:
    root = root.resolve()
    config = load_config(root)
    if type not in TYPES:
        raise ValueError(f"Invalid type: {type}. Use: {', '.join(TYPES)}")
    title, content = title.strip(), content.strip()
    if len(title) < 3 or len(content) < 8:
        raise ValueError("Title must have at least 3 characters and content at least 8")
    doc_id = document_id(type, title)
    db = connect(root, config)
    try:
        for existing in db.execute("SELECT id,title,body FROM documents WHERE type=? AND id<>?", (type, doc_id)):
            existing_content = re.sub(r"^# [^\n]+\n*", "", existing["body"]).strip()
            if _normalized(existing_content) == _normalized(content):
                raise ValueError(f"Duplicate content from '{existing['title']}' ({existing['id']})")
        prior = db.execute("SELECT path FROM documents WHERE id=?", (doc_id,)).fetchone()
    finally:
        db.close()
    path = root / prior["path"] if prior else root / ".brain" / "knowledge" / TYPES[type] / f"{doc_id}.md"
    previous = path.read_text(encoding="utf-8") if path.exists() else None
    parsed_previous = parse(path, root) if previous else None
    previous_meta = parsed_previous["metadata"] if parsed_previous else None
    tags = previous_meta.get("tags", []) if tags is None and previous_meta else (tags or [])
    related = previous_meta.get("related", []) if related is None and previous_meta else (related or [])
    importance = previous_meta.get("importance", 0.5) if importance is None and previous_meta else (0.5 if importance is None else importance)
    status = previous_meta.get("status") if status is None and previous_meta else (status or ("planned" if type == "feature" else "active"))
    if not 0 <= importance <= 1:
        raise ValueError("importance must be between 0 and 1")
    if type == "feature" and status not in {"idea", "planned", "in_progress", "implemented", "deprecated", "blocked"}:
        raise ValueError("Invalid feature status")
    if not isinstance(tags, list) or not all(isinstance(tag, str) for tag in tags):
        raise ValueError("tags must be a list of strings")
    if not isinstance(related, list) or not all(isinstance(item, str) for item in related):
        raise ValueError("related must be a list of strings")
    tags = list(dict.fromkeys(tag.strip() for tag in tags if tag.strip()))
    related = list(dict.fromkeys(item.strip() for item in related if item.strip()))
    if any(len(tag) > 64 for tag in tags):
        raise ValueError("Tag is too long")
    if previous_meta and previous_meta.get("title") == title and previous_meta.get("type") == type:
        old_body = parsed_previous["body"]
        if (old_body == f"# {title}\n\n{content}" and previous_meta.get("tags") == tags
                and previous_meta.get("related") == related and previous_meta.get("importance") == importance
                and previous_meta.get("status") == status):
            return {"id": doc_id, "path": path.relative_to(root).as_posix(), "changed": False}
    timestamp = now()
    meta = {**(previous_meta or {}), "id": doc_id, "type": type, "title": title, "tags": tags, "importance": importance,
            "status": status, "created_at": previous_meta.get("created_at", timestamp) if previous_meta else timestamp,
            "updated_at": timestamp, "related": related}
    markdown = render(meta, f"# {title}\n\n{content}")
    if previous == markdown:
        return {"id": doc_id, "path": path.relative_to(root).as_posix(), "changed": False}
    if previous:
        version_dir = root / ".brain" / "history" / "versions" / doc_id
        version_dir.mkdir(parents=True, exist_ok=True)
        version = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        (version_dir / f"{version}.md").write_text(previous, encoding="utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".md.tmp")
    tmp.write_text(markdown, encoding="utf-8")
    tmp.replace(path)
    event = {"timestamp": timestamp, "document_id": doc_id, "path": path.relative_to(root).as_posix(),
             "action": "updated" if previous else "created", "previous_version": bool(previous)}
    with (root / ".brain" / "history" / "changes.jsonl").open("a", encoding="utf-8") as log:
        log.write(json.dumps(event, ensure_ascii=False) + "\n")
    result = index(root, config)
    return {"id": doc_id, "path": event["path"], "changed": True, "index": result}


def _tokens(text: str) -> set[str]:
    return {word for word in _normalized(text).split() if len(word) > 2}


def _word_root(word: str) -> str:
    if word.startswith("re") and len(word) >= 8:
        word = word[2:]
    root = word[:5] if len(word) >= 6 else word
    for canonical, aliases in SEARCH_ALIASES:
        if root in aliases:
            return canonical
    return root


def _recency(timestamp: str) -> float:
    try:
        date = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        age = max(0, (datetime.now(timezone.utc) - date.astimezone(timezone.utc)).total_seconds()) / 86400
        return 1 / (1 + age / 180)
    except (ValueError, TypeError):
        return 0.5


def search(root: Path, query: str, *, types: list[str] | None = None, tags: list[str] | None = None,
           limit: int | None = None, token_budget: int | None = None) -> dict:
    started = time.monotonic()
    root = root.resolve()
    config = load_config(root)
    query = query.strip()
    if not query:
        raise ValueError("Empty query")
    retrieval = config["retrieval"]
    limit = retrieval["default_limit"] if limit is None else limit
    token_budget = retrieval["default_token_budget"] if token_budget is None else token_budget
    if not 1 <= limit <= 100 or not 16 <= token_budget <= 100000:
        raise ValueError("limit must be 1..100 and token_budget 16..100000")
    if types and any(kind not in {*TYPES, "project"} for kind in types):
        raise ValueError("Invalid type filter")
    index(root, config)
    vector = embed([query], config, query=True)[0]
    db = connect(root, config)
    try:
        similarities = vector_scores(db, vector)
        rows = db.execute("SELECT d.*, c.id AS chunk_id, c.text AS chunk FROM chunks c JOIN documents d ON d.id=c.document_id").fetchall()
    finally:
        db.close()
    query_terms = _tokens(query)
    selected = {}
    weights = retrieval
    weight_sum = sum(weights[f"{name}_weight"] for name in ("vector", "keyword", "importance", "recency"))
    for row in rows:
        if types and row["type"] not in types:
            continue
        row_tags = json.loads(row["tags"])
        if tags and not set(tags).issubset(row_tags):
            continue
        candidate_terms = _tokens(row["title"] + " " + row["chunk"] + " " + " ".join(row_tags))
        exact = len(query_terms & candidate_terms) / len(query_terms) if query_terms else 0
        candidate_roots = {_word_root(term) for term in candidate_terms}
        related = sum(_word_root(term) in candidate_roots for term in query_terms) / len(query_terms) if query_terms else 0
        keyword = max(exact, 0.85 * related)
        if _normalized(query) in _normalized(row["title"] + " " + row["chunk"]):
            keyword = 1.0
        score = (
            weights["vector_weight"] * similarities.get(row["chunk_id"], 0.0)
            + weights["keyword_weight"] * keyword
            + weights["importance_weight"] * row["importance"]
            + weights["recency_weight"] * _recency(row["updated_at"])
        ) / weight_sum
        item = {"id": row["id"], "type": row["type"], "title": row["title"], "path": row["path"],
                "score": round(score, 4), "content": row["chunk"], "tags": row_tags}
        if row["id"] not in selected or selected[row["id"]]["score"] < item["score"]:
            selected[row["id"]] = item
    ranked = sorted(selected.values(), key=lambda item: (-item["score"], item["id"]))
    heading = f"QUERY\n{query}\n\nRESULTS\n"
    if len(heading) > token_budget * CHARS_PER_TOKEN:
        heading = heading[:token_budget * CHARS_PER_TOKEN]
    remaining = token_budget * CHARS_PER_TOKEN - len(heading)
    results = []
    context = heading
    for item in ranked[:limit]:
        prefix = f"\n[{item['type']} | {item['score']:.2f}]\n{item['title']}\n"
        available = remaining - len(prefix) - 2
        if available < 24:
            break
        source = re.sub(r"^# [^\n]+\n*", "", item["content"]).strip() or item["content"]
        snippet = source[:available]
        if len(snippet) < len(source):
            snippet = snippet.rsplit(" ", 1)[0].rstrip() + "…"
        context += prefix + snippet + "\n"
        context = context[:token_budget * CHARS_PER_TOKEN]
        remaining = token_budget * CHARS_PER_TOKEN - len(context)
        results.append({**item, "content": snippet})
    elapsed_ms = round((time.monotonic() - started) * 1000, 2)
    estimated_tokens = (len(context) + CHARS_PER_TOKEN - 1) // CHARS_PER_TOKEN
    log = {"timestamp": now(), "query": query, "results": [{"id": item["id"], "score": item["score"]} for item in results],
           "estimated_tokens": estimated_tokens, "duration_ms": elapsed_ms, "memories_consulted": len(selected)}
    with (root / ".brain" / "history" / "searches.jsonl").open("a", encoding="utf-8") as file:
        file.write(json.dumps(log, ensure_ascii=False) + "\n")
    return {"context": context, "results": results, "estimated_tokens": estimated_tokens,
            "duration_ms": elapsed_ms, "memories_consulted": len(selected)}
