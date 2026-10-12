"""Intent-based hybrid retrieval over the knowledge base and project memory.

query → intent → expansion → multi-query (pgvector HNSW + Postgres FTS) → RRF fusion
→ explicit boosts → MMR diversity → token-budgeted context with citations.
Every score component is returned so a ranking can be explained.
"""

import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone

import numpy as np

from .embeddings import vector_literal
from .intent import Intent
from .taxonomy import DOMAIN_BY_ID, TASK_KIND_PRIORS
from .text import CHARS_PER_TOKEN, estimate_tokens, excerpt, tokens

RRF_K = 60
CANDIDATES_PER_LIST = 40
EXPANSION_WEIGHT = 0.6
MMR_LAMBDA = 0.72
STATUS_PENALTY = {"superseded": 0.6, "rejected": 0.55, "deprecated": 0.6, "done": 0.75, "dropped": 0.5,
                  "fixed": 0.8, "wontfix": 0.6, "refuted": 0.7, "invalid": 0.5, "archived": 0.4}


@dataclass
class Hit:
    source: str
    chunk_id: int
    parent_id: str
    title: str
    section: str
    content: str
    meta: dict
    vector: np.ndarray
    rrf: float = 0.0
    boost: float = 1.0
    ranks: dict = field(default_factory=dict)

    @property
    def score(self) -> float:
        return self.rrf * self.boost

    def label(self) -> str:
        if self.source == "knowledge":
            module = self.meta.get("module")
            head = f"{module} · " if module else ""
            return f"kb · {head}{self.section or self.title}"
        return f"{self.meta['kind']} · {self.title}"

    def citation(self) -> dict:
        if self.source == "knowledge":
            return {"source": "knowledge", "collection": self.meta["collection_id"], "path": self.meta["path"],
                    "module": self.meta.get("module"), "section": self.section, "anchor": self.meta.get("anchor"),
                    "document": self.title, "chunk_id": self.chunk_id}
        return {"source": "project", "key": self.meta["key"], "kind": self.meta["kind"], "id": self.parent_id,
                "status": self.meta.get("status")}


def _parse_vector(text: str) -> np.ndarray:
    return np.fromstring(text.strip("[]"), sep=",", dtype=np.float32)


def tsquery(text: str, limit: int = 14) -> str | None:
    terms = [t for t in sorted(tokens(text), key=len, reverse=True) if re.fullmatch(r"[a-z0-9]+", t)][:limit]
    return " | ".join(terms) if terms else None


def _prepare(conn) -> None:
    conn.execute("SET LOCAL hnsw.ef_search = 100")
    conn.execute("SET LOCAL hnsw.iterative_scan = relaxed_order")


KB_SELECT = ("SELECT k.id, k.document_id, k.heading_path, k.anchor, k.content, k.topics, k.embedding::text AS emb, "
             "d.title, d.module, d.category, d.path, d.collection_id FROM kb_chunks k "
             "JOIN kb_documents d ON d.id = k.document_id")
REC_SELECT = ("SELECT c.id, c.record_id, c.content, c.embedding::text AS emb, r.kind, r.key, r.title, r.status, "
              "r.importance, r.updated_at, r.tags, r.source FROM record_chunks c JOIN records r ON r.id = c.record_id")


def _filters_kb(collections, modules) -> tuple[str, list]:
    clauses, params = [], []
    if collections:
        clauses.append("k.collection_id = ANY(%s)")
        params.append(list(collections))
    if modules:
        clauses.append("d.module = ANY(%s)")
        params.append(list(modules))
    return (" AND ".join(clauses), params)


def _filters_records(project_id, kinds, include_archived) -> tuple[str, list]:
    clauses, params = ["c.project_id = %s"], [project_id]
    if kinds:
        clauses.append("r.kind = ANY(%s)")
        params.append(list(kinds))
    if not include_archived:
        clauses.append("NOT r.archived")
    return (" AND ".join(clauses), params)


def _collect(conn, select: str, where: str, params: list, vector: list[float], text: str, source: str,
             weight: float, hits: dict, list_name: str) -> None:
    literal = vector_literal(vector)
    where_sql = f" WHERE {where}" if where else ""
    column = "k.embedding" if source == "knowledge" else "c.embedding"
    vector_rows = conn.execute(f"{select}{where_sql} ORDER BY {column} <=> %s::vector LIMIT %s",
                               [*params, literal, CANDIDATES_PER_LIST]).fetchall()
    query = tsquery(text)
    lexical_rows = []
    if query:
        tsv = "k.tsv" if source == "knowledge" else "c.tsv"
        lexical_where = f"{where} AND {tsv} @@ to_tsquery('simple', %s)" if where else \
            f"{tsv} @@ to_tsquery('simple', %s)"
        lexical_rows = conn.execute(
            f"{select} WHERE {lexical_where} ORDER BY ts_rank_cd({tsv}, to_tsquery('simple', %s)) DESC LIMIT %s",
            [*params, query, query, CANDIDATES_PER_LIST]).fetchall()
    for kind, rows in (("vector", vector_rows), ("lexical", lexical_rows)):
        for rank, row in enumerate(rows, 1):
            hit = hits.get(row["id"])
            if hit is None:
                hit = hits[row["id"]] = _hit(row, source)
            hit.rrf += weight / (RRF_K + rank)
            name = f"{list_name}.{kind}"
            hit.ranks[name] = min(rank, hit.ranks.get(name, rank))


def _hit(row: dict, source: str) -> Hit:
    if source == "knowledge":
        return Hit("knowledge", row["id"], str(row["document_id"]), row["title"], row["heading_path"],
                   row["content"], {"module": row["module"], "category": row["category"], "path": row["path"],
                                    "collection_id": row["collection_id"], "anchor": row["anchor"],
                                    "topics": row["topics"]}, _parse_vector(row["emb"]))
    return Hit("project", row["id"], str(row["record_id"]), row["title"], row["kind"], row["content"],
               {"kind": row["kind"], "key": row["key"], "status": row["status"], "importance": row["importance"],
                "updated_at": row["updated_at"], "tags": row["tags"], "source": row["source"]},
               _parse_vector(row["emb"]))


def _recency(value: datetime) -> float:
    age_days = max(0.0, (datetime.now(timezone.utc) - value).total_seconds() / 86400)
    return 1 / (1 + age_days / 90)


def _apply_boosts(hits: list[Hit], intent: Intent, related_modules: set[str]) -> None:
    domain_scores = dict(intent.domains)
    priors = TASK_KIND_PRIORS.get(intent.task, {})
    for hit in hits:
        boost, reasons = 1.0, {}
        if hit.source == "knowledge":
            module = hit.meta.get("module")
            for domain_id, score in domain_scores.items():
                modules = DOMAIN_BY_ID[domain_id].modules
                if module in modules:
                    factor = 1 + 0.35 * score * (1 - 0.12 * modules.index(module))
                    boost *= factor
                    reasons[f"module:{domain_id}"] = round(factor, 3)
            if module and module in related_modules:
                boost *= 1.05
                reasons["linked_module"] = 1.05
            if "_toc" in (hit.meta.get("topics") or []):
                boost *= 0.3
                reasons["table_of_contents"] = 0.3
            overlap = len(set(hit.meta.get("topics") or []) & set(domain_scores))
            if overlap:
                boost *= 1 + 0.06 * overlap
                reasons["topics"] = overlap
        else:
            importance = float(hit.meta.get("importance") or 0.5)
            boost *= 0.8 + 0.4 * importance
            recency = _recency(hit.meta["updated_at"])
            boost *= 0.9 + 0.2 * recency
            if priors:
                prior = priors.get(hit.meta["kind"], 0.4)
                boost *= 0.8 + 0.4 * prior
                reasons["kind_prior"] = prior
            penalty = STATUS_PENALTY.get(hit.meta.get("status") or "")
            if penalty:
                boost *= penalty
                reasons["status"] = penalty
            reasons.update(importance=importance, recency=round(recency, 3))
        hit.boost = boost
        hit.ranks["boosts"] = reasons


def _mmr(hits: list[Hit], limit: int) -> list[Hit]:
    if len(hits) <= 1:
        return hits[:limit]
    top = max(hit.score for hit in hits) or 1.0
    selected: list[Hit] = []
    remaining = list(hits)
    while remaining and len(selected) < limit:
        def value(hit: Hit) -> float:
            redundancy = max((float(np.dot(hit.vector, other.vector)) for other in selected), default=0.0)
            return MMR_LAMBDA * (hit.score / top) - (1 - MMR_LAMBDA) * redundancy
        best = max(remaining, key=value)
        selected.append(best)
        remaining.remove(best)
    return selected


def _dedupe(hits: list[Hit]) -> list[Hit]:
    best: dict[tuple, Hit] = {}
    for hit in hits:
        key = (hit.source, hit.parent_id, hit.section if hit.source == "knowledge" else "")
        if key not in best or best[key].score < hit.score:
            best[key] = hit
    # At most two sections from the same knowledge document keep results varied.
    per_document: dict[str, int] = {}
    result = []
    for hit in sorted(best.values(), key=lambda h: (-h.score, h.chunk_id)):
        if hit.source == "knowledge":
            per_document[hit.parent_id] = per_document.get(hit.parent_id, 0) + 1
            if per_document[hit.parent_id] > 2:
                continue
        result.append(hit)
    return result


def pack(hits: list[Hit], token_budget: int, query: str, heading: str = "") -> tuple[str, list[dict]]:
    """Render hits within an approximate token budget; reserve room for several sources."""
    terms = tokens(query)
    capacity = token_budget * CHARS_PER_TOKEN
    context = heading
    items = []
    slots_total = min(len(hits), max(1, token_budget // 110))
    for position, hit in enumerate(hits[:slots_total]):
        prefix = f"\n[{hit.label()}]\n"
        remaining = capacity - len(context)
        slots = slots_total - position
        available = (remaining - slots * (len(prefix) + 2)) // max(1, slots) if slots > 1 else remaining - len(prefix) - 2
        if available < 60:
            break
        source = re.sub(r"^#+ [^\n]+\n*", "", hit.content).strip() or hit.content
        snippet = excerpt(source, available, terms)
        context += prefix + snippet + "\n"
        items.append({"label": hit.label(), "title": hit.title, "section": hit.section, "content": snippet,
                      "score": round(hit.score, 5), "citation": hit.citation(),
                      "signals": {k: v for k, v in hit.ranks.items()}})
    return context[:capacity], items


def expansions_for(intent: Intent, limit: int = 3) -> list[str]:
    queries: list[str] = []
    for index, (domain_id, _) in enumerate(intent.domains[:2]):
        take = 2 if index == 0 else 1
        queries.extend(DOMAIN_BY_ID[domain_id].expansions[:take])
    return queries[:limit]


class Retriever:
    def __init__(self, db, embedder, classifier):
        self.db = db
        self.embedder = embedder
        self.classifier = classifier

    def _vectors(self, queries: list[str]) -> list[list[float]]:
        return self.embedder.embed(queries, query=True)

    def search(self, query: str, *, scope: str = "knowledge", project_id=None, kinds=None, collections=None,
               modules=None, limit: int = 6, token_budget: int = 900, expand: bool = True,
               include_archived: bool = False, intent: Intent | None = None) -> dict:
        started = time.monotonic()
        query = (query or "").strip()
        if not query:
            raise ValueError("Empty query")
        if scope not in ("knowledge", "project", "all"):
            raise ValueError("scope must be knowledge, project or all")
        if scope in ("project", "all") and project_id is None:
            raise ValueError("project scope requires a project")
        if not 1 <= limit <= 50 or not 40 <= token_budget <= 20000:
            raise ValueError("limit must be 1..50 and token_budget 40..20000")
        base_vector = self._vectors([query])[0]
        intent = intent or self.classifier.classify(query, base_vector)
        expansions = expansions_for(intent) if expand and scope in ("knowledge", "all") else []
        vectors = [base_vector] + (self._vectors(expansions) if expansions else [])
        hits: dict[int, Hit] = {}
        project_hits: dict[int, Hit] = {}
        related_modules: set[str] = set()
        with self.db.connect() as conn:
            _prepare(conn)
            if scope in ("knowledge", "all"):
                where, params = _filters_kb(collections, modules)
                for index, (text, vector) in enumerate(zip([query, *expansions], vectors)):
                    _collect(conn, KB_SELECT, where, params, vector, text, "knowledge",
                             1.0 if index == 0 else EXPANSION_WEIGHT, hits, f"q{index}")
                top_docs = list(dict.fromkeys(h.parent_id for h in sorted(hits.values(), key=lambda h: -h.rrf)))[:3]
                if top_docs:
                    related_modules = {row["module"] for row in conn.execute(
                        "SELECT d.module FROM kb_links l JOIN kb_documents d ON d.id = l.dst_document "
                        "WHERE l.src_document = ANY(%s::uuid[]) AND d.module IS NOT NULL", (top_docs,))}
            if scope in ("project", "all"):
                where, params = _filters_records(project_id, kinds, include_archived)
                _collect(conn, REC_SELECT, where, params, base_vector, query, "project", 1.0, project_hits, "q0")
        candidates = list(hits.values()) + list(project_hits.values())
        _apply_boosts(candidates, intent, related_modules)
        if scope == "all":
            # Keep the categories distinct: normalize each category before interleaving.
            for group in (list(hits.values()), list(project_hits.values())):
                top = max((h.score for h in group), default=0) or 1
                for hit in group:
                    hit.boost /= top
        ranked = _mmr(_dedupe(candidates), limit)
        heading = f"QUERY\n{query}\n" + (f"INTENT {intent.task}: {', '.join(intent.domain_ids)}\n"
                                          if intent.domains else "") + "\nRESULTS\n"
        context, items = pack(ranked, token_budget, query, heading)
        return {"query": query, "scope": scope, "intent": intent.as_dict(), "expansions": expansions,
                "context": context, "items": items, "estimated_tokens": estimate_tokens(context),
                "candidates": len(candidates), "duration_ms": round((time.monotonic() - started) * 1000, 1)}

    def search_many(self, queries: list[dict], *, collections=None, limit: int = 2,
                    token_budget: int = 220) -> list[dict]:
        """Small focused lookups (one per option/topic) with one batched embedding call."""
        if not queries or len(queries) > 40:
            raise ValueError("search_many accepts 1..40 queries")
        texts = [str(item.get("query", "")).strip() for item in queries]
        if not all(texts):
            raise ValueError("every query needs text")
        vectors = self._vectors(texts)
        results = []
        with self.db.connect() as conn:
            _prepare(conn)
            where, params = _filters_kb(collections, None)
            for item, text, vector in zip(queries, texts, vectors):
                hits: dict[int, Hit] = {}
                _collect(conn, KB_SELECT, where, params, vector, text, "knowledge", 1.0, hits, "q0")
                intent = self.classifier.classify(text, vector)
                candidates = list(hits.values())
                _apply_boosts(candidates, intent, set())
                ranked = _dedupe(candidates)[:limit]
                context, items = pack(ranked, token_budget, text)
                results.append({"id": item.get("id"), "query": text, "items": items, "context": context})
        return results


# ── project context assembly ────────────────────────────────────────────────

def _first_line(text: str, limit: int = 220) -> str:
    line = next((part.strip() for part in text.splitlines() if part.strip() and not part.startswith("#")), "")
    return line if len(line) <= limit else line[:limit].rsplit(" ", 1)[0] + "…"


def core_context(conn, project_id, token_budget: int = 600) -> tuple[str, dict]:
    project = conn.execute("SELECT name, description, slug FROM projects WHERE id=%s", (project_id,)).fetchone()

    def rows(kinds, statuses=None, limit=8):
        query = ("SELECT kind, key, title, body, status FROM records WHERE project_id=%s AND NOT archived "
                 "AND kind = ANY(%s)")
        params: list = [project_id, list(kinds)]
        if statuses:
            query += " AND status = ANY(%s)"
            params.append(list(statuses))
        query += " ORDER BY importance DESC, updated_at DESC LIMIT %s"
        params.append(limit)
        return conn.execute(query, params).fetchall()

    sections = {
        "objective": rows(("objective", "idea", "problem"), limit=3),
        "state": rows(("state",), limit=1),
        "architecture": rows(("architecture",), limit=3),
        "decisions": rows(("decision",), ("accepted", "proposed"), limit=10),
        "constraints": rows(("constraint", "rule"), limit=10),
        "features": rows(("feature",), ("in_progress", "planned", "blocked"), limit=10),
        "bugs": rows(("bug",), ("open",), limit=6),
        "next_steps": rows(("next_step",), ("open",), limit=6),
    }
    lines = [f"# Project: {project['name']} ({project['slug']})"]
    if project["description"]:
        lines.append(project["description"])
    titles = {"objective": "Objective", "state": "Current state", "architecture": "Architecture",
              "decisions": "Decisions", "constraints": "Constraints", "features": "Active features",
              "bugs": "Open bugs", "next_steps": "Next steps"}
    for name, items in sections.items():
        if not items:
            continue
        lines.append(f"\n## {titles[name]}")
        for item in items:
            detail = _first_line(item["body"]) if name in ("objective", "state", "architecture") else ""
            status = f" [{item['status']}]" if name in ("features", "decisions") else ""
            lines.append(f"- {item['title']}{status}" + (f": {detail}" if detail else ""))
    text = "\n".join(lines)
    capacity = token_budget * CHARS_PER_TOKEN
    if len(text) > capacity:
        text = text[:capacity].rsplit("\n", 1)[0] + "\n…"
    summary = {name: [{"key": i["key"], "title": i["title"], "status": i["status"]} for i in items]
               for name, items in sections.items()}
    return text, summary


def relevant_context(retriever: Retriever, project_id, task: str, *, token_budget: int = 1500,
                     knowledge: bool = True, collections=None) -> dict:
    started = time.monotonic()
    vector = retriever.embedder.embed([task], query=True)[0]
    intent = retriever.classifier.classify(task, vector)
    with retriever.db.connect() as conn:
        has_kb = conn.execute("SELECT EXISTS(SELECT 1 FROM kb_chunks) AS v").fetchone()["v"]
        core_text, core = core_context(conn, project_id, max(150, int(token_budget * 0.2)))
    project_budget = int(token_budget * (0.5 if knowledge and has_kb else 0.8))
    project = retriever.search(task, scope="project", project_id=project_id, limit=8,
                               token_budget=max(80, project_budget), expand=False, intent=intent)
    sections = {"core": core_text, "project": project["context"]}
    knowledge_result = None
    if knowledge and has_kb:
        knowledge_result = retriever.search(task, scope="knowledge", collections=collections, limit=4,
                                            token_budget=max(80, token_budget - project_budget -
                                                             estimate_tokens(core_text)), intent=intent)
        sections["knowledge"] = knowledge_result["context"]
    rendered = core_text + "\n\n## Relevant project memory\n" + project["context"].split("RESULTS\n", 1)[-1]
    if knowledge_result and knowledge_result["items"]:
        rendered += "\n\n## Relevant technical knowledge\n" + knowledge_result["context"].split("RESULTS\n", 1)[-1]
    return {"task": task, "intent": intent.as_dict(), "core": core, "project_items": project["items"],
            "knowledge_items": knowledge_result["items"] if knowledge_result else [],
            "context": rendered, "estimated_tokens": estimate_tokens(rendered),
            "duration_ms": round((time.monotonic() - started) * 1000, 1)}

