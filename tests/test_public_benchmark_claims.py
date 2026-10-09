import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmarks"))
from project_scenarios import measured_size_savings  # noqa: E402


def test_cap_is_applied_per_question_and_protocol_once():
    report = {"agent_instruction_tokens": 40, "mcp_tool_schema_tokens": 60,
              "fresh_process_queries": 2,
              "levels": [{"source_documents": 20, "facts_found": 2,
                          "brain_tokens": 600, "broad_rg_tokens": 1600,
                          "median_search_ms": 10,
                          "cases": [{"broad_rg_tokens": 1500}, {"broad_rg_tokens": 100}]}]}
    row = measured_size_savings(report, cap_per_query=1000)[0]
    assert row["brain_with_setup_tokens"] == 700
    assert row["baseline_uncapped_tokens"] == 1600
    assert row["baseline_capped_tokens"] == 1100
    assert row["uncapped_reduction_pct"] == 56.25
    assert row["capped_reduction_pct"] == pytest.approx(36.36, abs=0.01)


def test_readme_size_claims_match_committed_measurements():
    report = json.loads((ROOT / "benchmarks/results/growth.json").read_text(encoding="utf-8"))
    readme = (ROOT / "README.md").read_text(encoding="utf-8").replace("−", "-")
    for row in measured_size_savings(report):
        expected = (f"| {row['documents']:,} | {row['brain_with_setup_tokens']:,} tokens | "
                    f"{row['baseline_uncapped_tokens']:,} tokens | "
                    f"{row['uncapped_reduction_pct']:.2f}% | "
                    f"{row['capped_reduction_pct']:.2f}% |")
        assert expected in readme
