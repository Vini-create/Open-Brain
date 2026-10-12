"""Pure text helpers shared by the local CLI and the Brain service.

Extracted from the V1 ``second_brain.core`` ranking code; behaviour is unchanged.
"""

import re
import unicodedata

CHARS_PER_TOKEN = 3  # Conservative local estimate for Portuguese Markdown.
STOP_WORDS = set("""the and for with from this that what where when how which into
are was were have has does can should after before about project please
como onde quando quais qual para por com uma uns umas dos das aos que
isso esse essa este esta pelo pela ficam fazer devo depois antes projeto
seus suas mais tambem sobre entre sem ao seu sua ele ela nao nos nas""".split())
SEARCH_ALIASES = (
    ("embedding", {"embed", "vetor"}),
    ("credential", {"chave", "key", "crede"}),
    ("cpu", {"cpu", "maqui"}),
    ("ranking", {"ranki", "formu", "prior", "score", "peso", "relev"}),
    ("budget", {"budge", "orcam", "limit", "corto", "taman"}),
    ("history", {"histo", "versa", "snaps"}),
)


def normalized(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().casefold()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", text)).strip()


def tokens(text: str) -> set[str]:
    return {word for word in normalized(text).split() if len(word) > 2 and word not in STOP_WORDS}


def word_root(word: str) -> str:
    if word.startswith("re") and len(word) >= 8:
        word = word[2:]
    root = word[:5] if len(word) >= 6 else word
    for canonical, aliases in SEARCH_ALIASES:
        if root in aliases:
            return canonical
    return root


def estimate_tokens(text: str) -> int:
    return (len(text) + CHARS_PER_TOKEN - 1) // CHARS_PER_TOKEN


def excerpt(source: str, available: int, query_terms: set[str]) -> str:
    """Return the sentence window of ``source`` that best covers the query terms."""
    if len(source) <= available:
        return source
    roots = {word_root(term) for term in query_terms}
    starts = [0] + [match.end() for match in re.finditer(r"\n+|[.!?]\s+(?=[A-ZÀ-Ý])", source)]

    def relevance(start):
        terms = tokens(source[start:start + available])
        return (len(query_terms & terms), len(roots & {word_root(term) for term in terms}), -start)

    start = max(starts, key=relevance)
    snippet = source[start:start + available].strip()
    if start + available < len(source):
        snippet = snippet.rsplit(" ", 1)[0].rstrip() + "…"
    return snippet


def keyword_coverage(query_terms: set[str], text: str, query: str = "") -> float:
    """Exact term coverage, with partial credit for shared word roots (V1 formula)."""
    if not query_terms:
        return 0.0
    candidate_terms = tokens(text)
    exact = len(query_terms & candidate_terms) / len(query_terms)
    candidate_roots = {word_root(term) for term in candidate_terms}
    related = sum(word_root(term) in candidate_roots for term in query_terms) / len(query_terms)
    score = max(exact, 0.85 * related)
    if query and normalized(query) in normalized(text):
        score = 1.0
    return score


def slug(value: str, limit: int = 65) -> str:
    ascii_text = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", ascii_text).strip("-")[:limit] or "item"
