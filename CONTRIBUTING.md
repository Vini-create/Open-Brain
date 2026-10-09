# Contributing

Thanks for improving Second Brain Local. The project aims to stay local, simple to install, and useful through a small MCP tool set.

## Local setup

Follow [Installation guide](docs/INSTALLATION.md), then install test and benchmark extras:

```bash
python -m pip install -e '.[test,benchmark]'
python -m pytest -q
```

Tests that embed text require the public model to be downloaded once with `brain model download` in an initialized project. CI runs the same tests on Linux with CPU PyTorch. Pull requests run the quick growth benchmark; the full 10,000-document profile can be started with the CI workflow's manual trigger.

## Benchmark changes

Keep measured output, assumptions, and projections separate. A retrieval payload reduction is not an end-to-end LLM bill reduction. If you change the agent instructions, MCP schemas, ranking, or sample corpus, rerun `benchmarks/measure.py`, `benchmarks/robustness.py`, `benchmarks/growth.py --profile full`, and `benchmarks/project_scenarios.py`, and include the generated reports and JSON with your change. State CPU, tokenizer, question set, baseline, fact coverage, latency, and any data selection made after observing the results.

## Code and memory

Keep Markdown as the source of truth, the SQLite index rebuildable, and normal indexing/search offline after the model download. Add tests for behavior changes, especially CLI setup, MCP, incremental indexing, and retrieval. Read `.brain/AGENT_BRAIN.md` before working in this repository; save durable decisions with `brain remember` after meaningful changes. Do not commit model weights, local indexes, histories, or machine-specific MCP paths.

## Pull requests

Describe what changed, why, how it was validated, and any remaining limitation. Small, focused changes are easier to review. Do not include secrets or private project context in examples or benchmark fixtures.
