"""Shared fixtures for Brain Engine tests that need PostgreSQL + pgvector."""

import os
import uuid
from pathlib import Path

import pytest

ADMIN_URL = os.environ.get("BRAIN_TEST_ADMIN_URL", "postgresql://creative:creative_local@localhost:55432/creative")
TEST_DB = "brain_test"


def _database_url() -> str | None:
    try:
        import psycopg
    except ImportError:
        return None
    try:
        with psycopg.connect(ADMIN_URL, autocommit=True, connect_timeout=3) as conn:
            if not conn.execute("SELECT 1 FROM pg_database WHERE datname=%s", (TEST_DB,)).fetchone():
                conn.execute(f"CREATE DATABASE {TEST_DB}")
    except Exception:
        return None
    return ADMIN_URL.rsplit("/", 1)[0] + "/" + TEST_DB


@pytest.fixture(scope="session")
def database_url():
    url = os.environ.get("BRAIN_TEST_DATABASE_URL") or _database_url()
    if not url:
        pytest.skip("PostgreSQL with pgvector is not available (start it with `make db` in create-hack)")
    return url


@pytest.fixture
def service(database_url):
    import psycopg

    from brain_engine.embeddings import HashEmbedder
    from brain_engine.service import BrainService
    from brain_engine.settings import Settings

    schema = f"t_{uuid.uuid4().hex[:10]}"
    settings = Settings(database_url=database_url, schema=schema, embedder="hash", kb_autoingest=False)
    brain = BrainService(settings, embedder=HashEmbedder(384))
    brain.migrate()
    yield brain
    brain.close()
    with psycopg.connect(database_url, autocommit=True) as conn:
        conn.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE")


KB_FILES = {
    "README_MASTER_INDEX.md": """# Índice\n\n| Fase | Módulos | Objetivo |\n|---|---|---|\n| Fundação | `00` | Base |\n| RAG e agentes | `09`, `10` | Recuperação e agentes |\n| Produção segura | `14`, `15` | Bancos e custo |\n""",
    "09_RAG_PRODUCTION_GRADE.md": """# 09_RAG_PRODUCTION_GRADE.md\n\n## 09.1 Chunking\n\nChunking semântico divide documentos por estrutura de cabeçalhos. Chunks pequenos melhoram a precisão da recuperação, chunks grandes preservam contexto. Veja também 14_DATABASES_VECTOR_SEARCH_MEMORY.md para memória.\n\n## 09.2 Busca híbrida\n\nBusca híbrida combina BM25 lexical com busca densa por embeddings e funde rankings com RRF. Reranking com cross-encoder melhora a precisão do topo.\n\n```python\ndef rrf(rank, k=60):\n    return 1 / (k + rank)\n```\n""",
    "14_DATABASES_VECTOR_SEARCH_MEMORY.md": """# 14_DATABASES_VECTOR_SEARCH_MEMORY.md\n\n## 14.1 Memória de longo prazo para agentes\n\nMemória episódica guarda eventos e conversas; memória semântica guarda fatos consolidados. Agentes recuperam memória com embeddings em um vector store como pgvector.\n\n## 14.2 Índices vetoriais\n\nHNSW oferece recall alto com latência baixa; IVFFlat exige treino. pgvector suporta HNSW dentro do Postgres.\n""",
    "15_DEPLOY_SCALE_LATENCY_COST.md": """# 15_DEPLOY_SCALE_LATENCY_COST.md\n\n## 15.1 Custo\n\nCusto de inferência depende de tokens de entrada e saída. Cache de prompt reduz custo. Docker facilita deploy local.\n""",
}


@pytest.fixture
def kb_dir(tmp_path: Path) -> Path:
    root = tmp_path / "kb"
    root.mkdir()
    for name, content in KB_FILES.items():
        (root / name).write_text(content, encoding="utf-8")
    return root
