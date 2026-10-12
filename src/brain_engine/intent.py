"""Deterministic, local intent classification for retrieval.

Combines keyword evidence (PT/EN taxonomy) with embedding similarity to each domain's
descriptor. No LLM call; the result is inspectable and returned with every search.
"""

import re
import threading
from dataclasses import dataclass, field

from .taxonomy import DOMAINS, TASK_VERBS, Domain
from .text import normalized

KEYWORD_WEIGHT = 0.65
EMBEDDING_WEIGHT = 0.35


@dataclass
class Intent:
    task: str  # implement | fix | decide | ask
    domains: list[tuple[str, float]] = field(default_factory=list)
    matched: dict[str, list[str]] = field(default_factory=dict)

    @property
    def domain_ids(self) -> list[str]:
        return [domain for domain, _ in self.domains]

    def as_dict(self) -> dict:
        return {"task": self.task, "domains": [{"id": d, "score": round(s, 3)} for d, s in self.domains],
                "matched_keywords": self.matched}


def _keyword_hits(text: str, domain: Domain) -> list[str]:
    padded = f" {text} "
    hits = []
    for keyword in domain.keywords:
        if keyword.endswith("*"):
            if re.search(r"\b" + re.escape(keyword[:-1]), text):
                hits.append(keyword)
        elif f" {keyword} " in padded:
            hits.append(keyword)
    return hits


def task_type(text: str) -> str:
    """implement | fix | decide | ask. The leading verb wins over words later in the text."""
    words = normalized(text).split()
    for word in words[:3]:
        for task in ("fix", "implement", "decide"):
            if any(word.startswith(verb) for verb in TASK_VERBS[task] if " " not in verb):
                return task
    norm = " ".join(words)
    for task in ("decide", "fix", "implement"):
        if any(re.search(r"\b" + re.escape(verb), norm) for verb in TASK_VERBS[task]):
            return task
    return "ask"


class IntentClassifier:
    def __init__(self, embedder=None):
        self.embedder = embedder
        self._descriptor_vectors: list[list[float]] | None = None
        self._lock = threading.Lock()

    def _descriptors(self) -> list[list[float]] | None:
        if self.embedder is None:
            return None
        with self._lock:
            if self._descriptor_vectors is None:
                self._descriptor_vectors = self.embedder.embed([d.descriptor for d in DOMAINS])
        return self._descriptor_vectors

    def classify(self, text: str, query_vector: list[float] | None = None, top: int = 3) -> Intent:
        norm = normalized(text)
        matched = {d.id: _keyword_hits(norm, d) for d in DOMAINS}
        keyword_scores = {d.id: min(1.0, len(matched[d.id]) / 2) for d in DOMAINS}
        embedding_scores = {d.id: 0.0 for d in DOMAINS}
        descriptors = self._descriptors()
        if descriptors is not None:
            if query_vector is None:
                query_vector = self.embedder.embed([text], query=True)[0]
            similarities = [sum(a * b for a, b in zip(query_vector, vector)) for vector in descriptors]
            low, high = min(similarities), max(similarities)
            if high > low:
                embedding_scores = {d.id: (s - low) / (high - low) for d, s in zip(DOMAINS, similarities)}
        combined = {
            d.id: KEYWORD_WEIGHT * keyword_scores[d.id] + EMBEDDING_WEIGHT * embedding_scores[d.id]
            for d in DOMAINS
        }
        ranked = sorted(combined.items(), key=lambda item: (-item[1], item[0]))
        best = ranked[0][1] if ranked else 0.0
        # Keep domains with real keyword evidence or close to the best score; embedding
        # similarity alone is relative and must not inject an unrelated domain.
        chosen = [(d, s) for d, s in ranked
                  if s > 0 and (keyword_scores[d] > 0 or s >= 0.8 * best) and s >= 0.45 * best][:top]
        if best < 0.2:
            chosen = []
        return Intent(task=task_type(text), domains=chosen,
                      matched={d: hits for d, hits in matched.items() if hits and d in dict(chosen)})
