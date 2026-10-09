"""Compare token usage from paired, independently collected `codex exec --json` traces.

This script never runs Codex or any LLM. Each JSONL file must contain one
completed turn; the caller must verify task success before treating savings as
meaningful.
"""

import argparse
import json
from pathlib import Path


FIELDS = ("input_tokens", "cached_input_tokens", "cache_write_input_tokens",
          "output_tokens", "reasoning_output_tokens")


def parse_trace(path: Path) -> dict:
    completed = []
    with path.open(encoding="utf-8") as stream:
        for number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{number}: invalid JSON") from exc
            if event.get("type") == "turn.completed":
                completed.append(event)
    if len(completed) != 1:
        raise ValueError(f"{path}: expected exactly one turn.completed; found {len(completed)}")
    usage = completed[0].get("usage")
    if not isinstance(usage, dict):
        raise ValueError(f"{path}: turn.completed without usage")
    result = {}
    for field in FIELDS:
        value = usage.get(field, 0 if field not in ("input_tokens", "output_tokens") else None)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise ValueError(f"{path}: {field} missing or invalid")
        result[field] = value
    if result["cached_input_tokens"] + result["cache_write_input_tokens"] > result["input_tokens"]:
        raise ValueError(f"{path}: cached tokens exceed input tokens")
    if result["reasoning_output_tokens"] > result["output_tokens"]:
        raise ValueError(f"{path}: reasoning tokens exceed output tokens")
    result["uncached_input_tokens"] = (result["input_tokens"] - result["cached_input_tokens"]
                                       - result["cache_write_input_tokens"])
    result["total_tokens"] = result["input_tokens"] + result["output_tokens"]
    return result


def compare(without: list[Path], with_brain: list[Path]) -> dict:
    if not without or len(without) != len(with_brain):
        raise ValueError("Provide the same number of --without and --with traces")
    pairs = []
    for baseline_path, brain_path in zip(without, with_brain):
        baseline, brain = parse_trace(baseline_path), parse_trace(brain_path)
        pairs.append({"without": str(baseline_path), "with": str(brain_path),
                      "baseline": baseline, "brain": brain})
    totals = {side: {field: sum(pair["baseline" if side == "without" else "brain"][field]
                                 for pair in pairs)
                     for field in (*FIELDS, "uncached_input_tokens", "total_tokens")}
              for side in ("without", "with")}
    percentages = {}
    for field in ("input_tokens", "uncached_input_tokens", "cached_input_tokens",
                  "output_tokens", "total_tokens"):
        base = totals["without"][field]
        percentages[field] = round(100 * (1 - totals["with"][field] / base), 2) if base else None
    return {"pairs": pairs, "totals": totals, "reduction_pct": percentages}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--without", type=Path, nargs="+", required=True,
                        help="Traces without Brain, in task order")
    parser.add_argument("--with", dest="with_brain", type=Path, nargs="+", required=True,
                        help="Traces with Brain, in task order")
    args = parser.parse_args()
    result = compare(args.without, args.with_brain)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
