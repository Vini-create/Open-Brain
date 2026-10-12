"""Local embeddings. The e5 model is the same CPU model used by the V1 local Brain."""

import hashlib
import math
import threading
from typing import Protocol

from .text import normalized


class Embedder(Protocol):
    model_name: str
    dimensions: int

    def embed(self, texts: list[str], *, query: bool = False) -> list[list[float]]: ...


class E5Embedder:
    """``intfloat/multilingual-e5-*`` on CPU with the required query/passage prefixes."""

    def __init__(self, model_name: str, dimensions: int, *, local_files_only: bool = True,
                 batch_size: int = 32):
        self.model_name = model_name
        self.dimensions = dimensions
        self.local_files_only = local_files_only
        self.batch_size = batch_size
        self._lock = threading.Lock()

    def _model(self):
        from second_brain.embedding import _model

        return _model(self.model_name, self.local_files_only)

    def embed(self, texts: list[str], *, query: bool = False) -> list[list[float]]:
        if not texts:
            return []
        prefix = ("query: " if query else "passage: ") if "e5" in self.model_name.lower() else ""
        model = self._model()
        # SentenceTransformer.encode is not documented as thread-safe; requests and the
        # background ingester share one model instance.
        with self._lock:
            vectors = model.encode([prefix + text for text in texts], batch_size=self.batch_size,
                                   normalize_embeddings=True, show_progress_bar=False)
        result = [list(map(float, vector)) for vector in vectors]
        if len(result[0]) != self.dimensions:
            raise ValueError(f"Model {self.model_name} returned {len(result[0])} dimensions; "
                             f"BRAIN_EMBEDDING_DIMENSIONS is {self.dimensions}")
        return result


class HashEmbedder:
    """Deterministic bag-of-words hashing embedder for tests and model-less smoke runs.

    Texts that share words get a positive cosine similarity, which is enough to test
    ranking, isolation and fusion without loading a neural model.
    """

    model_name = "hash-bow-v1"

    def __init__(self, dimensions: int = 384):
        self.dimensions = dimensions

    def embed(self, texts: list[str], *, query: bool = False) -> list[list[float]]:
        result = []
        for text in texts:
            vector = [0.0] * self.dimensions
            words = normalized(text).split()
            for word in words:
                for token in (word, word[:5]):
                    digest = hashlib.sha1(token.encode()).digest()
                    index = int.from_bytes(digest[:4], "little") % self.dimensions
                    vector[index] += 1.0 if digest[4] % 2 else -1.0
            norm = math.sqrt(sum(value * value for value in vector)) or 1.0
            result.append([value / norm for value in vector])
        return result


def build_embedder(settings) -> Embedder:
    if settings.embedder == "hash":
        return HashEmbedder(settings.embedding_dimensions)
    return E5Embedder(settings.embedding_model, settings.embedding_dimensions,
                      local_files_only=not settings.allow_model_download)


def vector_literal(vector: list[float]) -> str:
    return "[" + ",".join(f"{value:.6f}" for value in vector) + "]"
