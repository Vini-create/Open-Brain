"""Project token payload scenarios from measured growth results.

These are arithmetic counterfactuals, not measured LLM usage or retrieval tests.
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def measured_size_savings(report: dict, *, cap_per_query: int = 8_000,
                          sessions: int = 1) -> list[dict]:
    """Reaccount measured search payloads with a per-query baseline cap.

    Capping changes token accounting only. It does not test whether the
    conventional search would still recover the fact from the clipped output.
    """
    if cap_per_query < 1 or sessions < 1:
        raise ValueError("The cap and session count must be positive")
    protocol = report["agent_instruction_tokens"] + report["mcp_tool_schema_tokens"]
    rows = []
    for level in report["levels"]:
        cases = level["cases"]
        if not cases or len(cases) != report["fresh_process_queries"]:
            raise ValueError("Every level must contain the measured questions")
        uncapped = sum(case["broad_rg_tokens"] for case in cases)
        if uncapped != level["broad_rg_tokens"]:
            raise ValueError("Per-question baseline does not match the measured total")
        capped = sum(min(case["broad_rg_tokens"], cap_per_query) for case in cases)
        brain = level["brain_tokens"] + protocol * sessions
        rows.append({"documents": level["source_documents"],
                     "facts_found": level["facts_found"],
                     "questions": len(cases),
                     "baseline_uncapped_tokens": uncapped,
                     "baseline_capped_tokens": capped,
                     "brain_with_setup_tokens": brain,
                     "uncapped_reduction_pct": round(100 * (1 - brain / uncapped), 2),
                     "capped_reduction_pct": round(100 * (1 - brain / capped), 2),
                     "median_search_ms": level["median_search_ms"]})
    return rows


def project(report: dict, *, documents: int, queries: int, sessions: int,
            common_tokens_per_query: int = 0, discovery_cap_per_query: int | None = None,
            memory_setup_tokens: int = 0) -> dict:
    levels = report["levels"]
    if len(levels) < 2 or any(value < 0 for value in (documents, common_tokens_per_query, memory_setup_tokens)):
        raise ValueError("Two measured levels and nonnegative token inputs are required")
    if queries < 1 or sessions < 1 or sessions > queries or (discovery_cap_per_query is not None and discovery_cap_per_query < 1):
        raise ValueError("Invalid query, session, or discovery cap count")
    low, high = levels[-2:]
    if high["source_documents"] <= low["source_documents"]:
        raise ValueError("Measured levels must increase in size")
    reference_queries = report["fresh_process_queries"]
    slope = ((high["broad_rg_tokens"] - low["broad_rg_tokens"])
             / (high["source_documents"] - low["source_documents"]))
    projected_discovery = max(0, high["broad_rg_tokens"]
                              + slope * (documents - high["source_documents"]))
    baseline_payload = projected_discovery * queries / reference_queries
    if discovery_cap_per_query is not None:
        baseline_payload = min(baseline_payload, discovery_cap_per_query * queries)
    brain_payload = high["brain_tokens"] * queries / reference_queries
    protocol = report["agent_instruction_tokens"] + report["mcp_tool_schema_tokens"]
    shared = common_tokens_per_query * queries
    baseline = baseline_payload + shared
    brain = brain_payload + protocol * sessions + memory_setup_tokens + shared
    return {"documents": documents, "queries": queries, "sessions": sessions,
            "common_tokens_per_query": common_tokens_per_query,
            "discovery_cap_per_query": discovery_cap_per_query,
            "memory_setup_tokens": memory_setup_tokens,
            "baseline_tokens": round(baseline), "brain_tokens": round(brain),
            "reduction_pct": round(100 * (1 - brain / baseline), 4) if baseline else None,
            "calibration_documents": [low["source_documents"], high["source_documents"]],
            "discovery_tokens_per_document": round(slope, 3)}


def markdown(report: dict) -> str:
    high = report["levels"][-1]
    measured = project(report, documents=high["source_documents"], queries=4, sessions=1)
    rows = [project(report, documents=documents, queries=4, sessions=1,
                    discovery_cap_per_query=cap)
            for documents in (20_000, 100_000, 1_000_000)
            for cap in (None, 8_000)]
    repetitions = [project(report, documents=100_000, queries=queries, sessions=sessions,
                           common_tokens_per_query=common, discovery_cap_per_query=8_000,
                           memory_setup_tokens=setup)
                   for queries, sessions, common, setup in ((4, 1, 0, 0), (20, 5, 2_000, 0),
                                                            (20, 5, 2_000, 5_000),
                                                            (100, 25, 5_000, 5_000))]
    lines = ["# Large-project token scenarios", "",
             "**Projected, not measured.** This report applies explicit arithmetic assumptions to the "
             "measured growth benchmark. It does not run an LLM or prove retrieval quality beyond the "
             "largest measured corpus.", "",
             f"Calibration: {report['fresh_process_queries']} measured questions, last two corpus sizes "
             f"{report['levels'][-2]['source_documents']:,} and {high['source_documents']:,} project documents, "
             "each paired with an indexed Brain memory; "
             f"broad `rg` output grows by {measured['discovery_tokens_per_document']} tokens per "
             "document in this synthetic corpus. Assume Brain returns the same number of tokens per "
             "query as at the largest measured level, with the same fact recall. These are assumptions, "
             "not observations above the largest measured corpus.", "",
             "## One four-question session", "",
             "The Brain side includes the measured instruction and MCP tool schema size once. The "
             "uncapped baseline assumes every matching path is returned and one file is read; this "
             "can exceed a model's context window. The capped baseline limits that combined "
             "retrieval payload to 8,000 tokens per query; coverage after capping is unknown.", "",
             "| Projected documents | Baseline cap/query | Baseline tokens | Brain tokens | Payload reduction |",
             "| ---: | ---: | ---: | ---: | ---: |"]
    for row in rows:
        cap = "none" if row["discovery_cap_per_query"] is None else f"{row['discovery_cap_per_query']:,}"
        lines.append(f"| {row['documents']:,} | {cap} | {row['baseline_tokens']:,} | "
                     f"{row['brain_tokens']:,} | {row['reduction_pct']:.4f}% |")
    lines += ["", "## Repeated work with bounded discovery", "",
              "The following scenarios cap baseline retrieval at 8,000 tokens per query. Common tokens are "
              "added equally to both workflows. A 5,000-token memory setup cost is hypothetical and "
              "charged only to the Brain side where shown.", "",
              "| Queries | Sessions | Common tokens/query | Brain setup tokens | Baseline | Brain | Total input reduction |",
              "| ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for row in repetitions:
        lines.append(f"| {row['queries']} | {row['sessions']} | "
                     f"{row['common_tokens_per_query']:,} | {row['memory_setup_tokens']:,} | "
                     f"{row['baseline_tokens']:,} | {row['brain_tokens']:,} | "
                     f"{row['reduction_pct']:.4f}% |")
    lines += ["", "## What this cannot establish", "",
              "- Search quality, indexing time, and latency above the largest measured corpus are unmeasured. "
              "The current implementation ranks every indexed chunk, so latency may rise substantially.",
              "- A builder may choose a narrower search than this broad `rg` baseline; targeted search "
              "can use fewer tokens than the Brain after MCP setup.",
              "- Tool schemas may be resent or cached differently by each client. Memory creation and "
              "maintenance costs are absent unless the hypothetical setup cost is included.",
              "- These figures exclude model reasoning, output, retries, and task quality. Paired "
              "builder traces are required to claim end-to-end LLM savings.", "",
              "Reproduce after `python benchmarks/growth.py --profile full` with "
              "`python benchmarks/project_scenarios.py`. Raw inputs: "
              "`benchmarks/results/growth.json`."]
    return "\n".join(lines) + "\n"


def main() -> None:
    report = json.loads((ROOT / "benchmarks/results/growth.json").read_text(encoding="utf-8"))
    output = ROOT / "docs" / "SCENARIOS.md"
    output.parent.mkdir(exist_ok=True)
    output.write_text(markdown(report), encoding="utf-8")
    print(f"Wrote {output}")


if __name__ == "__main__":
    main()
