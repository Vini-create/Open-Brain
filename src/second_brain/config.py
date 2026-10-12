import json
from pathlib import Path

DEFAULT_CONFIG = {
    "version": 1,
    "embedding": {
        "model": "intfloat/multilingual-e5-small",
        "dimensions": 384,
        "distance": "cosine",
        "local_files_only": True,
    },
    "retrieval": {
        "default_limit": 8,
        "default_token_budget": 2000,
        "vector_weight": 0.55,
        "keyword_weight": 0.20,
        "importance_weight": 0.15,
        "recency_weight": 0.10,
    },
    "storage": {"database": ".brain/index/brain.db"},
}

TYPES = {
    "architecture": "architecture",
    "decision": "decisions",
    "rule": "rules",
    "dependency": "dependencies",
    "bug": "bugs",
    "feature": "features",
    "constraint": "constraints",
    "rationale": "rationale",
    "next-step": "next-steps",
}
# Folders created by `brain init`. Linked projects also mirror the richer server ontology.
CORE_TYPES = tuple(TYPES)
TYPES.update({
    "idea": "ideas", "objective": "objectives", "problem": "problems", "actor": "actors",
    "hypothesis": "hypotheses", "question": "questions", "alternative": "alternatives",
    "tradeoff": "tradeoffs", "requirement": "requirements", "component": "components", "risk": "risks",
    "state": "state", "experiment": "experiments", "result": "results", "learning": "learnings",
    "implementation": "implementations", "spec": "specs", "doc": "docs",
})


def load_config(root: Path) -> dict:
    path = root / ".brain" / "config.json"
    if not path.exists():
        raise ValueError(f"Brain not initialized at {root}. Run 'brain init'.")
    config = json.loads(path.read_text(encoding="utf-8"))
    if config.get("version") != 1:
        raise ValueError("Unsupported configuration version")
    weights = config["retrieval"]
    for name in ("vector", "keyword", "importance", "recency"):
        value = weights[f"{name}_weight"]
        if not isinstance(value, (int, float)) or value < 0:
            raise ValueError(f"Invalid weight: {name}_weight")
    if sum(weights[f"{name}_weight"] for name in ("vector", "keyword", "importance", "recency")) <= 0:
        raise ValueError("Search weights must have a positive sum")
    return config
