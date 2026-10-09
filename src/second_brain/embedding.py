from functools import lru_cache
import os


@lru_cache(maxsize=2)
def _model(name: str, local_files_only: bool):
    if local_files_only:
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["HF_HUB_DISABLE_IMPLICIT_TOKEN"] = "1"
    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise RuntimeError("Install dependencies with 'pip install -e .' to generate local embeddings.") from exc
    try:
        return SentenceTransformer(name, device="cpu", local_files_only=local_files_only)
    except Exception as exc:
        raise RuntimeError(
            f"Model '{name}' is unavailable locally. Run 'brain model download' "
            f"once with network access, then reuse the local cache."
        ) from exc


def embed(texts: list[str], config: dict, *, query: bool = False) -> list[list[float]]:
    if not texts:
        return []
    setting = config["embedding"]
    model = _model(setting["model"], setting.get("local_files_only", True))
    prefix = "query: " if query and "e5" in setting["model"].lower() else "passage: " if "e5" in setting["model"].lower() else ""
    vectors = model.encode([prefix + text for text in texts], normalize_embeddings=True, show_progress_bar=False)
    result = [list(map(float, vector)) for vector in vectors]
    if result and len(result[0]) != setting["dimensions"]:
        raise ValueError("Model dimension differs from config.json; fix the configuration and run 'brain rebuild'")
    return result


def download_model(name: str) -> None:
    os.environ["HF_HUB_DISABLE_IMPLICIT_TOKEN"] = "1"
    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
    try:
        from sentence_transformers import SentenceTransformer
        SentenceTransformer(name, device="cpu", local_files_only=False)
    except Exception as exc:
        raise RuntimeError(
            f"Could not download '{name}'. Check network access and ensure HF_HUB_OFFLINE is not set."
        ) from exc
