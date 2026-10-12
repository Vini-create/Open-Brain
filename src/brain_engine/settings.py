"""Environment configuration for the Brain service. Every value has a local default."""

import os
from dataclasses import dataclass, field
from pathlib import Path


def _bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    return default if value is None else value.strip().lower() in {"1", "true", "yes", "on"}


def _sources(raw: str) -> dict[str, Path]:
    """Parse ``BRAIN_KB_SOURCES="ai-engineering=/knowledge/ai;other=/path"``."""
    result = {}
    for item in filter(None, (part.strip() for part in raw.split(";"))):
        name, _, path = item.partition("=")
        if name.strip() and path.strip():
            result[name.strip()] = Path(path.strip()).expanduser()
    return result


@dataclass(frozen=True)
class Settings:
    database_url: str = "postgresql://creative:creative_local@localhost:55432/creative"
    schema: str = "brain"
    embedder: str = "e5"  # "e5" (local CPU model) or "hash" (deterministic, tests only)
    embedding_model: str = "intfloat/multilingual-e5-small"
    embedding_dimensions: int = 384
    allow_model_download: bool = False
    kb_sources: dict[str, Path] = field(default_factory=dict)
    kb_autoingest: bool = True
    host: str = "127.0.0.1"
    port: int = 8020
    api_token: str = ""
    default_workspace: str = "local"
    pricing_file: Path | None = None
    pool_max_size: int = 8
    environment: str = "local"  # "production" enforces the checks in validate()

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            database_url=os.environ.get("BRAIN_DATABASE_URL", cls.database_url).replace(
                "postgresql+asyncpg://", "postgresql://"),
            schema=os.environ.get("BRAIN_SCHEMA", cls.schema),
            embedder=os.environ.get("BRAIN_EMBEDDER", cls.embedder),
            embedding_model=os.environ.get("BRAIN_EMBEDDING_MODEL", cls.embedding_model),
            embedding_dimensions=int(os.environ.get("BRAIN_EMBEDDING_DIMENSIONS", cls.embedding_dimensions)),
            allow_model_download=_bool("BRAIN_ALLOW_MODEL_DOWNLOAD", False),
            kb_sources=_sources(os.environ.get("BRAIN_KB_SOURCES", "")),
            kb_autoingest=_bool("BRAIN_KB_AUTOINGEST", True),
            host=os.environ.get("BRAIN_HOST", cls.host),
            # BRAIN_PORT wins; PORT is what PaaS hosts such as Railway inject.
            port=int(os.environ.get("BRAIN_PORT") or os.environ.get("PORT") or cls.port),
            api_token=os.environ.get("BRAIN_API_TOKEN", ""),
            default_workspace=os.environ.get("BRAIN_DEFAULT_WORKSPACE", cls.default_workspace),
            pricing_file=Path(os.environ["BRAIN_PRICING_FILE"]) if os.environ.get("BRAIN_PRICING_FILE") else None,
            pool_max_size=int(os.environ.get("BRAIN_POOL_MAX_SIZE", cls.pool_max_size)),
            environment=os.environ.get("BRAIN_ENV", cls.environment).strip().lower(),
        )

    def validate(self) -> None:
        """Refuse unsafe production configurations instead of serving them."""
        if self.environment != "production":
            return
        problems = []
        if len(self.api_token) < 24:
            problems.append("BRAIN_API_TOKEN must be set (24+ characters) in production")
        if self.embedder == "hash":
            problems.append("BRAIN_EMBEDDER=hash is for tests only")
        if "creative_local@" in self.database_url:
            problems.append("BRAIN_DATABASE_URL still uses the local development password")
        if problems:
            raise RuntimeError("Brain production configuration: " + "; ".join(problems))
