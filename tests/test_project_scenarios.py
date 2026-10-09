import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "benchmarks"))
from project_scenarios import project  # noqa: E402


@pytest.fixture
def measurements():
    return {"fresh_process_queries": 4, "agent_instruction_tokens": 500,
            "mcp_tool_schema_tokens": 300,
            "levels": [{"source_documents": 4, "broad_rg_tokens": 1200, "brain_tokens": 600},
                       {"source_documents": 104, "broad_rg_tokens": 3200, "brain_tokens": 600}]}


def test_projection_separates_protocol_common_input_and_discovery_cap(measurements):
    uncapped = project(measurements, documents=104, queries=4, sessions=1)
    assert uncapped["baseline_tokens"] == 3200
    assert uncapped["brain_tokens"] == 1400
    assert uncapped["reduction_pct"] == 56.25

    repeated = project(measurements, documents=104, queries=4, sessions=4,
                       common_tokens_per_query=1000, discovery_cap_per_query=500,
                       memory_setup_tokens=200)
    assert repeated["baseline_tokens"] == 6000
    assert repeated["brain_tokens"] == 8000
    assert repeated["reduction_pct"] == -33.3333


def test_projection_rejects_invalid_scenario(measurements):
    with pytest.raises(ValueError):
        project(measurements, documents=104, queries=1, sessions=2)
