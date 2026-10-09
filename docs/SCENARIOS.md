# Large-project token scenarios

**Projected, not measured.** This report applies explicit arithmetic assumptions to the measured growth benchmark. It does not run an LLM or prove retrieval quality beyond the largest measured corpus.

Calibration: 4 measured questions, last two corpus sizes 5,000 and 10,000 project documents, each paired with an indexed Brain memory; broad `rg` output grows by 32.0 tokens per document in this synthetic corpus. Assume Brain returns the same number of tokens per query as at the largest measured level, with the same fact recall. These are assumptions, not observations above the largest measured corpus.

## One four-question session

The Brain side includes the measured instruction and MCP tool schema size once. The uncapped baseline assumes every matching path is returned and one file is read; this can exceed a model's context window. The capped baseline limits that combined retrieval payload to 8,000 tokens per query; coverage after capping is unknown.

| Projected documents | Baseline cap/query | Baseline tokens | Brain tokens | Payload reduction |
| ---: | ---: | ---: | ---: | ---: |
| 20,000 | none | 637,028 | 1,342 | 99.7893% |
| 20,000 | 8,000 | 32,000 | 1,342 | 95.8063% |
| 100,000 | none | 3,197,028 | 1,342 | 99.9580% |
| 100,000 | 8,000 | 32,000 | 1,342 | 95.8063% |
| 1,000,000 | none | 31,997,028 | 1,342 | 99.9958% |
| 1,000,000 | 8,000 | 32,000 | 1,342 | 95.8063% |

## Repeated work with bounded discovery

The following scenarios cap baseline retrieval at 8,000 tokens per query. Common tokens are added equally to both workflows. A 5,000-token memory setup cost is hypothetical and charged only to the Brain side where shown.

| Queries | Sessions | Common tokens/query | Brain setup tokens | Baseline | Brain | Total input reduction |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 4 | 1 | 0 | 0 | 32,000 | 1,342 | 95.8063% |
| 20 | 5 | 2,000 | 0 | 200,000 | 46,710 | 76.6450% |
| 20 | 5 | 2,000 | 5,000 | 200,000 | 51,710 | 74.1450% |
| 100 | 25 | 5,000 | 5,000 | 1,300,000 | 538,550 | 58.5731% |

## What this cannot establish

- Search quality, indexing time, and latency above the largest measured corpus are unmeasured. The current implementation ranks every indexed chunk, so latency may rise substantially.
- A builder may choose a narrower search than this broad `rg` baseline; targeted search can use fewer tokens than the Brain after MCP setup.
- Tool schemas may be resent or cached differently by each client. Memory creation and maintenance costs are absent unless the hypothetical setup cost is included.
- These figures exclude model reasoning, output, retries, and task quality. Paired builder traces are required to claim end-to-end LLM savings.

Reproduce after `python benchmarks/growth.py --profile full` with `python benchmarks/project_scenarios.py`. Raw inputs: `benchmarks/results/growth.json`.
