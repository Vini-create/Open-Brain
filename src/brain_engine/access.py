"""Per-project access tokens. The admin token (BRAIN_API_TOKEN) manages them; project tokens
only reach their own project's memory, the shared knowledge base and MCP for that project."""

import hashlib
import secrets
import uuid

from .memory import BrainError, get_project

PREFIX = "brn_"


def digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def issue(conn, project_ref: str, label: str, workspace: str = "local") -> dict:
    label = (label or "").strip() or "acesso"
    if len(label) > 80:
        raise BrainError("label must have at most 80 characters")
    project = get_project(conn, project_ref, workspace)
    secret = PREFIX + secrets.token_urlsafe(32)
    row = conn.execute(
        "INSERT INTO access_tokens(project_id, token_hash, label) VALUES (%s,%s,%s) "
        "RETURNING id, label, created_at", (project["id"], digest(secret), label)).fetchone()
    return {"id": str(row["id"]), "label": row["label"], "created_at": row["created_at"].isoformat(),
            "project_id": str(project["id"]), "token": secret}


def list_tokens(conn, project_ref: str, workspace: str = "local") -> list[dict]:
    project = get_project(conn, project_ref, workspace)
    rows = conn.execute(
        "SELECT id, label, created_at, revoked_at FROM access_tokens WHERE project_id=%s ORDER BY created_at DESC",
        (project["id"],)).fetchall()
    return [{"id": str(r["id"]), "label": r["label"], "created_at": r["created_at"].isoformat(),
             "revoked": r["revoked_at"] is not None} for r in rows]


def revoke(conn, project_ref: str, token_id: str, workspace: str = "local") -> dict:
    project = get_project(conn, project_ref, workspace)
    try:
        ident = uuid.UUID(token_id)
    except ValueError as exc:
        raise BrainError("invalid token id") from exc
    row = conn.execute(
        "UPDATE access_tokens SET revoked_at=now() WHERE id=%s AND project_id=%s AND revoked_at IS NULL RETURNING id",
        (ident, project["id"])).fetchone()
    return {"revoked": row is not None}


def revoke_by_label(conn, project_id, label_prefix: str) -> int:
    """Rotate: revoke every live token whose label starts with the prefix (e.g. a previous export)."""
    rows = conn.execute(
        "UPDATE access_tokens SET revoked_at=now() WHERE project_id=%s AND revoked_at IS NULL "
        "AND label LIKE %s RETURNING id", (project_id, label_prefix + "%")).fetchall()
    return len(rows)


def scope_of(conn, secret: str) -> str | None:
    """Project id a valid, non-revoked token is bound to; None when unknown or revoked."""
    row = conn.execute("SELECT project_id FROM access_tokens WHERE token_hash=%s AND revoked_at IS NULL",
                       (digest(secret),)).fetchone()
    return str(row["project_id"]) if row else None
