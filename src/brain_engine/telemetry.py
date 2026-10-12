"""LLM usage and cost telemetry shared by Creare, Jarvis and executors."""

import json
from decimal import Decimal
from functools import lru_cache
from pathlib import Path

from .memory import BrainError

FIELDS = ("workflow_id", "project_id", "component", "task", "provider", "model", "input_tokens",
          "cached_tokens", "output_tokens", "reasoning_tokens", "calls", "cost_usd", "duration_ms",
          "status", "meta")


@lru_cache(maxsize=4)
def load_pricing(path: str | None = None) -> dict[str, dict[str, float]]:
    source = Path(path) if path else Path(__file__).with_name("pricing.json")
    return json.loads(source.read_text(encoding="utf-8"))["models"]


def price_for(model: str | None, pricing: dict) -> dict | None:
    if not model:
        return None
    name = model.split("/")[-1] if model not in pricing and "/" in model else model
    matches = [key for key in pricing if model.startswith(key) or name.startswith(key)]
    return pricing[max(matches, key=len)] if matches else None


def estimate_cost(call: dict, pricing: dict) -> tuple[float | None, str]:
    if call.get("cost_usd") is not None:
        return float(call["cost_usd"]), "reported"
    price = price_for(call.get("model"), pricing)
    if not price:
        return None, "unpriced"
    cached = int(call.get("cached_tokens") or 0)
    fresh = max(0, int(call.get("input_tokens") or 0) - cached)
    output = int(call.get("output_tokens") or 0) + int(call.get("reasoning_tokens") or 0)
    cost = (fresh * price["input"] + cached * price["cached_input"] + output * price["output"]) / 1_000_000
    return round(cost, 6), "estimated"


def record_calls(conn, calls: list[dict], pricing: dict, project_resolver=None) -> list[dict]:
    if not calls or len(calls) > 500:
        raise BrainError("send 1..500 telemetry calls per request")
    stored = []
    for raw in calls:
        unknown = set(raw) - set(FIELDS) - {"project"}
        if unknown:
            raise BrainError(f"Unknown telemetry fields: {', '.join(sorted(unknown))}")
        if not raw.get("component"):
            raise BrainError("component is required")
        for field in ("input_tokens", "cached_tokens", "output_tokens", "reasoning_tokens"):
            if int(raw.get(field) or 0) < 0:
                raise BrainError(f"{field} cannot be negative")
        project_id = raw.get("project_id")
        meta = dict(raw.get("meta") or {})
        if not project_id and raw.get("project") and project_resolver:
            project_id = project_resolver(raw["project"])
        if not project_id and raw.get("project"):
            # The project may not exist yet (Creare's first turn); ensure_project backfills it.
            meta["project_ref"] = str(raw["project"])
        cost, cost_source = estimate_cost(raw, pricing)
        row = conn.execute(
            "INSERT INTO llm_calls(workflow_id, project_id, component, task, provider, model, input_tokens, "
            "cached_tokens, output_tokens, reasoning_tokens, calls, cost_usd, cost_source, duration_ms, status, meta) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb) RETURNING id",
            (raw.get("workflow_id"), project_id, raw["component"][:80], (raw.get("task") or None),
             raw.get("provider"), raw.get("model"), int(raw.get("input_tokens") or 0),
             int(raw.get("cached_tokens") or 0), int(raw.get("output_tokens") or 0),
             int(raw.get("reasoning_tokens") or 0), int(raw.get("calls") or 1), cost, cost_source,
             raw.get("duration_ms"), raw.get("status") or "ok", json.dumps(meta))).fetchone()
        stored.append({"id": str(row["id"]), "cost_usd": cost, "cost_source": cost_source})
    return stored


def report(conn, *, workflow_id: str | None = None, project_id=None, task: str | None = None,
           since: str | None = None, group_by: str = "component") -> dict:
    if group_by not in ("component", "model", "task", "workflow_id"):
        raise BrainError("group_by must be component, model, task or workflow_id")
    clauses, params = [], []
    if workflow_id:
        clauses.append("workflow_id = %s")
        params.append(workflow_id)
    if project_id:
        clauses.append("project_id = %s")
        params.append(project_id)
    if task:
        clauses.append("task = %s")
        params.append(task)
    if since:
        clauses.append("created_at >= %s::timestamptz")
        params.append(since)
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    rows = conn.execute(
        f"SELECT COALESCE({group_by}, '(none)') AS name, sum(calls) AS calls, sum(input_tokens) AS input_tokens, "
        "sum(cached_tokens) AS cached_tokens, sum(output_tokens) AS output_tokens, "
        "sum(reasoning_tokens) AS reasoning_tokens, sum(cost_usd) AS cost_usd, "
        "sum(duration_ms) AS duration_ms, bool_or(cost_source = 'unpriced') AS has_unpriced "
        f"FROM llm_calls{where} GROUP BY 1 ORDER BY sum(cost_usd) DESC NULLS LAST, 1", params).fetchall()
    def number(value):
        return float(value) if isinstance(value, Decimal) else (value or 0)
    groups = [{key: number(value) if key not in ("name", "has_unpriced") else value for key, value in row.items()}
              for row in rows]
    total = {key: sum(group[key] for group in groups) for key in
             ("calls", "input_tokens", "cached_tokens", "output_tokens", "reasoning_tokens", "cost_usd", "duration_ms")}
    return {"group_by": group_by, "groups": groups, "total": total, "table": render_table(groups, total, group_by)}


def _k(value) -> str:
    value = float(value or 0)
    return f"{value / 1000:.1f}k" if value >= 1000 else f"{int(value)}"


def render_table(groups: list[dict], total: dict, group_by: str) -> str:
    width = max([len(group_by)] + [len(str(g["name"])) for g in groups] + [5])
    lines = [f"{group_by:<{width}}  calls  in_tok  out_tok      cost"]
    for group in groups:
        cost = f"${group['cost_usd']:.4f}" + ("*" if group["has_unpriced"] else "")
        lines.append(f"{str(group['name']):<{width}}  {int(group['calls']):>5}  {_k(group['input_tokens']):>6}  "
                     f"{_k(group['output_tokens'] + group['reasoning_tokens']):>7}  {cost:>9}")
    lines.append("-" * len(lines[0]))
    lines.append(f"{'total':<{width}}  {int(total['calls']):>5}  {_k(total['input_tokens']):>6}  "
                 f"{_k(total['output_tokens'] + total['reasoning_tokens']):>7}  ${total['cost_usd']:.4f}")
    if any(group["has_unpriced"] for group in groups):
        lines.append("* includes calls without a known price (tokens counted, cost unknown)")
    return "\n".join(lines)
