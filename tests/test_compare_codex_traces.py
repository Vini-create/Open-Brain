import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "benchmarks"))
from compare_codex_traces import compare, parse_trace  # noqa: E402


def trace(path: Path, **usage) -> Path:
    path.write_text(json.dumps({"type": "turn.started"}) + "\n" +
                    json.dumps({"type": "turn.completed", "usage": usage}) + "\n", encoding="utf-8")
    return path


def test_compares_actual_turn_usage_with_cache_and_output(tmp_path: Path):
    baseline = trace(tmp_path / "without.jsonl", input_tokens=1000, cached_input_tokens=200,
                     output_tokens=300, reasoning_output_tokens=100)
    brain = trace(tmp_path / "with.jsonl", input_tokens=700, cached_input_tokens=100,
                  output_tokens=250, reasoning_output_tokens=80)
    result = compare([baseline], [brain])
    assert result["reduction_pct"]["input_tokens"] == 30.0
    assert result["reduction_pct"]["output_tokens"] == 16.67
    assert result["reduction_pct"]["total_tokens"] == 26.92
    assert result["totals"]["without"]["uncached_input_tokens"] == 800
    assert result["totals"]["with"]["uncached_input_tokens"] == 600


def test_rejects_trace_without_usage(tmp_path: Path):
    path = tmp_path / "incomplete.jsonl"
    path.write_text(json.dumps({"type": "turn.completed"}) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="without usage"):
        parse_trace(path)
