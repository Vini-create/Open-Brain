"""PostgreSQL + pgvector storage: connection pool and versioned schema migrations.

Everything lives in one schema (``brain`` by default), so the Brain can share a local
Postgres server with Creare today and move to a managed database later unchanged.
"""

import re
from contextlib import contextmanager

from psycopg import sql
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

SCHEMA_NAME = re.compile(r"^[a-z_][a-z0-9_]{0,40}$")

MIGRATIONS: list[str] = [
    # 1 — knowledge base, project memory, history, telemetry
    """
    CREATE TABLE IF NOT EXISTS {s}.meta (key text PRIMARY KEY, value text NOT NULL);

    CREATE TABLE IF NOT EXISTS {s}.projects (
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      workspace text NOT NULL DEFAULT 'local',
      slug text NOT NULL,
      name text NOT NULL,
      description text NOT NULL DEFAULT '',
      external_ref text UNIQUE,
      root_path text,
      created_at timestamptz NOT NULL DEFAULT now(),
      updated_at timestamptz NOT NULL DEFAULT now(),
      UNIQUE (workspace, slug)
    );

    CREATE TABLE IF NOT EXISTS {s}.records (
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      project_id uuid NOT NULL REFERENCES {s}.projects(id) ON DELETE CASCADE,
      kind text NOT NULL,
      key text NOT NULL,
      title text NOT NULL,
      body text NOT NULL DEFAULT '',
      status text NOT NULL DEFAULT 'active',
      status_source text,
      importance real NOT NULL DEFAULT 0.5,
      tags text[] NOT NULL DEFAULT '{{}}',
      source text NOT NULL,
      origin text,
      data jsonb NOT NULL DEFAULT '{{}}',
      version integer NOT NULL DEFAULT 1,
      archived boolean NOT NULL DEFAULT false,
      created_at timestamptz NOT NULL DEFAULT now(),
      updated_at timestamptz NOT NULL DEFAULT now(),
      UNIQUE (project_id, key)
    );
    CREATE INDEX IF NOT EXISTS records_project_kind ON {s}.records (project_id, kind, status);

    CREATE TABLE IF NOT EXISTS {s}.record_versions (
      id bigserial PRIMARY KEY,
      record_id uuid NOT NULL REFERENCES {s}.records(id) ON DELETE CASCADE,
      version integer NOT NULL,
      title text NOT NULL,
      body text NOT NULL,
      status text NOT NULL,
      data jsonb NOT NULL,
      source text NOT NULL,
      changed_at timestamptz NOT NULL DEFAULT now()
    );
    CREATE INDEX IF NOT EXISTS record_versions_record ON {s}.record_versions (record_id, version);

    CREATE TABLE IF NOT EXISTS {s}.relations (
      project_id uuid NOT NULL REFERENCES {s}.projects(id) ON DELETE CASCADE,
      src uuid NOT NULL REFERENCES {s}.records(id) ON DELETE CASCADE,
      dst uuid NOT NULL REFERENCES {s}.records(id) ON DELETE CASCADE,
      type text NOT NULL,
      source text NOT NULL,
      created_at timestamptz NOT NULL DEFAULT now(),
      PRIMARY KEY (src, dst, type)
    );
    CREATE INDEX IF NOT EXISTS relations_dst ON {s}.relations (dst);

    CREATE TABLE IF NOT EXISTS {s}.record_chunks (
      id bigserial PRIMARY KEY,
      record_id uuid NOT NULL REFERENCES {s}.records(id) ON DELETE CASCADE,
      project_id uuid NOT NULL REFERENCES {s}.projects(id) ON DELETE CASCADE,
      ordinal integer NOT NULL,
      content text NOT NULL,
      tsv tsvector NOT NULL,
      embedding vector({dim}) NOT NULL
    );
    CREATE INDEX IF NOT EXISTS record_chunks_project ON {s}.record_chunks (project_id);
    CREATE INDEX IF NOT EXISTS record_chunks_tsv ON {s}.record_chunks USING gin (tsv);
    CREATE INDEX IF NOT EXISTS record_chunks_embedding ON {s}.record_chunks
      USING hnsw (embedding vector_cosine_ops);

    CREATE TABLE IF NOT EXISTS {s}.events (
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      project_id uuid NOT NULL REFERENCES {s}.projects(id) ON DELETE CASCADE,
      type text NOT NULL,
      summary text NOT NULL,
      actor text NOT NULL,
      data jsonb NOT NULL DEFAULT '{{}}',
      record_ids uuid[] NOT NULL DEFAULT '{{}}',
      workflow_id text,
      created_at timestamptz NOT NULL DEFAULT now()
    );
    CREATE INDEX IF NOT EXISTS events_project ON {s}.events (project_id, created_at DESC);

    CREATE TABLE IF NOT EXISTS {s}.kb_collections (
      id text PRIMARY KEY,
      title text NOT NULL,
      description text NOT NULL DEFAULT '',
      root text,
      meta jsonb NOT NULL DEFAULT '{{}}',
      updated_at timestamptz NOT NULL DEFAULT now()
    );

    CREATE TABLE IF NOT EXISTS {s}.kb_documents (
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      collection_id text NOT NULL REFERENCES {s}.kb_collections(id) ON DELETE CASCADE,
      path text NOT NULL,
      title text NOT NULL,
      module text,
      category text,
      hash text NOT NULL,
      meta jsonb NOT NULL DEFAULT '{{}}',
      updated_at timestamptz NOT NULL DEFAULT now(),
      UNIQUE (collection_id, path)
    );

    CREATE TABLE IF NOT EXISTS {s}.kb_chunks (
      id bigserial PRIMARY KEY,
      document_id uuid NOT NULL REFERENCES {s}.kb_documents(id) ON DELETE CASCADE,
      collection_id text NOT NULL,
      ordinal integer NOT NULL,
      heading_path text NOT NULL,
      anchor text NOT NULL,
      content text NOT NULL,
      topics text[] NOT NULL DEFAULT '{{}}',
      tsv tsvector NOT NULL,
      embedding vector({dim}) NOT NULL
    );
    CREATE INDEX IF NOT EXISTS kb_chunks_document ON {s}.kb_chunks (document_id);
    CREATE INDEX IF NOT EXISTS kb_chunks_tsv ON {s}.kb_chunks USING gin (tsv);
    CREATE INDEX IF NOT EXISTS kb_chunks_embedding ON {s}.kb_chunks
      USING hnsw (embedding vector_cosine_ops);

    CREATE TABLE IF NOT EXISTS {s}.kb_links (
      src_document uuid NOT NULL REFERENCES {s}.kb_documents(id) ON DELETE CASCADE,
      dst_document uuid NOT NULL REFERENCES {s}.kb_documents(id) ON DELETE CASCADE,
      count integer NOT NULL,
      PRIMARY KEY (src_document, dst_document)
    );

    CREATE TABLE IF NOT EXISTS {s}.llm_calls (
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      created_at timestamptz NOT NULL DEFAULT now(),
      workflow_id text,
      project_id uuid REFERENCES {s}.projects(id) ON DELETE SET NULL,
      component text NOT NULL,
      task text,
      provider text,
      model text,
      input_tokens bigint NOT NULL DEFAULT 0,
      cached_tokens bigint NOT NULL DEFAULT 0,
      output_tokens bigint NOT NULL DEFAULT 0,
      reasoning_tokens bigint NOT NULL DEFAULT 0,
      calls integer NOT NULL DEFAULT 1,
      cost_usd numeric(14, 6),
      cost_source text NOT NULL DEFAULT 'unpriced',
      duration_ms bigint,
      status text NOT NULL DEFAULT 'ok',
      meta jsonb NOT NULL DEFAULT '{{}}'
    );
    CREATE INDEX IF NOT EXISTS llm_calls_workflow ON {s}.llm_calls (workflow_id);
    CREATE INDEX IF NOT EXISTS llm_calls_project ON {s}.llm_calls (project_id, created_at DESC);
    """,
    # 2 — per-project access tokens: only a SHA-256 digest is stored, the secret is shown once
    """
    CREATE TABLE IF NOT EXISTS {s}.access_tokens (
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      project_id uuid NOT NULL REFERENCES {s}.projects(id) ON DELETE CASCADE,
      token_hash text NOT NULL UNIQUE,
      label text NOT NULL,
      created_at timestamptz NOT NULL DEFAULT now(),
      revoked_at timestamptz
    );
    CREATE INDEX IF NOT EXISTS access_tokens_project ON {s}.access_tokens (project_id);
    """,
]


class Database:
    def __init__(self, url: str, schema: str = "brain", dimensions: int = 384, max_size: int = 8):
        if not SCHEMA_NAME.match(schema):
            raise ValueError("Invalid schema name")
        self.schema = schema
        self.dimensions = dimensions
        self.pool = ConnectionPool(url, min_size=1, max_size=max_size, open=True,
                                   kwargs={"row_factory": dict_row, "autocommit": False},
                                   configure=self._configure)

    def _configure(self, connection):
        connection.autocommit = True
        connection.execute(sql.SQL("SET search_path TO {}, public").format(sql.Identifier(self.schema)))
        connection.autocommit = False

    @contextmanager
    def connect(self):
        """One transaction; committed on success, rolled back on error."""
        with self.pool.connection() as connection:
            yield connection

    def close(self):
        self.pool.close()

    def migrate(self, embedding_model: str) -> int:
        with self.connect() as conn:
            conn.execute("SELECT pg_advisory_xact_lock(hashtext('brain-migrate'))")
            conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
            conn.execute(sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(sql.Identifier(self.schema)))
            conn.execute(sql.SQL("CREATE TABLE IF NOT EXISTS {}.meta (key text PRIMARY KEY, value text NOT NULL)")
                         .format(sql.Identifier(self.schema)))
            row = conn.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
            current = int(row["value"]) if row else 0
            for version, statement in enumerate(MIGRATIONS[current:], start=current + 1):
                conn.execute(statement.format(s=self.schema, dim=self.dimensions))
                conn.execute("INSERT INTO meta(key,value) VALUES('schema_version',%s) "
                             "ON CONFLICT (key) DO UPDATE SET value=excluded.value", (str(version),))
            recorded = {row["key"]: row["value"] for row in conn.execute(
                "SELECT key, value FROM meta WHERE key IN ('embedding_model','embedding_dimensions')")}
            if not recorded:
                for key, value in (("embedding_model", embedding_model),
                                   ("embedding_dimensions", str(self.dimensions))):
                    conn.execute("INSERT INTO meta(key,value) VALUES(%s,%s)", (key, value))
            elif (recorded.get("embedding_model") != embedding_model
                  or recorded.get("embedding_dimensions") != str(self.dimensions)):
                raise RuntimeError(
                    f"Brain index was built with {recorded.get('embedding_model')} "
                    f"({recorded.get('embedding_dimensions')} dims); configured {embedding_model} "
                    f"({self.dimensions}). Run 'brain kb reindex' after changing models.")
            return len(MIGRATIONS)
