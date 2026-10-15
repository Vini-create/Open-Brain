# Contributing

Thanks for improving Open Brain. The standalone product aims to keep project
memory local, readable and easy to retrieve through the CLI or MCP.

## Local setup

Follow the [installation guide](docs/INSTALLATION.md), then work from the
installation clone. On Linux/macOS, use its virtual environment explicitly:

```bash
cd ~/Open-Brain
.venv/bin/python -m pip install -e '.[test,benchmark]'
brain init
brain model download
.venv/bin/python -m pytest -q
```

On native Windows, replace `.venv/bin/python` with
`& ".\.venv\Scripts\python.exe"` in PowerShell. These commands do not assume
that the system `python` uses the installation's environment.

Tests that embed text require the public model to be cached. Tests run in
temporary project directories and do not ingest your repository automatically.
CI runs on Linux with CPU PyTorch, using Python 3.10 and 3.12. Pull requests also
run repository, multilingual and detailed retrieval checks, plus quick growth;
the workflow's manual trigger runs full growth and scenario generation.

For documentation-only changes, verify local links/anchors, shell syntax and the
documented commands relevant to the edit. Do not relabel historical measurements
as current results without reproducing them. Native runtime verification and
cross-platform verification are separate claims.

## Benchmark changes

Keep measured output, assumptions and projections separate. A retrieval payload
reduction is not an end-to-end LLM bill reduction. For ranking, schema, protocol
or corpus changes, run the relevant retrieval gates using the same virtual
environment:

```bash
.venv/bin/python benchmarks/retrieval_quality.py --label current --output /tmp/open-brain-retrieval.json --check
.venv/bin/python benchmarks/robustness.py --check
```

The tokenizer may require one initial public download. Use a platform-appropriate
output path on Windows. To update published token-savings claims, reproduce the
repository benchmark, full growth and scenario commands in
[Benchmarking](docs/BENCHMARKS.md). Keep a separately named report for a new
engine comparison when preserving historical numbers. State CPU, tokenizer,
question set, baseline, fact coverage, latency and any selection made after
observing the results.

## Code and memory

Keep Markdown as the source of truth, the SQLite index rebuildable, and normal indexing/search offline after the model download. Add tests for behavior changes, especially CLI setup, MCP, incremental indexing, and retrieval. Read `.brain/AGENT_BRAIN.md` before working in this repository; save durable decisions with `brain remember` after meaningful changes. Do not commit model weights, local indexes, histories, or machine-specific MCP paths.

## Pull requests

Describe what changed, why, how it was validated, and any remaining limitation.
Keep [English](README.md) and [Portuguese](README.pt-BR.md) onboarding consistent
when commands or behavior change. Small, focused changes are easier to review.
Do not include secrets or private project context in examples or benchmark fixtures.

To report a problem or a trial result without a PR, use the
[issue templates](https://github.com/Vini-create/Open-Brain/issues/new/choose).
Include environment, reproduction steps and expected/actual behavior. For search
issues, a minimal non-sensitive memory plus query and budget is more useful than
a screenshot alone. English and Portuguese reports are welcome.
