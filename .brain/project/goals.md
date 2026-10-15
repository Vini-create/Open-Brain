# Goals

## Current priorities

- Keep the core save/retrieve contract stable: atomic vector updates, recoverable rebuilds, real multilingual retrieval and observable agent usage.
- Preserve the storage and MCP acceptance tests plus fact-recovery gates in CI; see STABILITY_REPORT.md for the current evidence and limits.

- Collect public trial feedback using the English/Portuguese quickstarts and GitHub issue forms; improve onboarding from reproducible reports.
- Preserve durable decisions across sessions while reducing retrieved context in measured scenarios.
- Keep Markdown canonical, local CPU embeddings, and a rebuildable SQLite + sqlite-vec index.
- Measure fact recall, token payload, MCP setup cost, search latency, and index size as corpora grow.

## Out of scope

Text generation, automatic whole-repository ingestion, and paid LLM APIs inside the local Brain. An optional linked-service client exists; the standalone memory path stays local.

## Next steps

Test MCP integration in additional real clients. Collect paired builder traces with and without Brain on equivalent tasks to measure actual input, cache, output, task quality, and memory-maintenance cost. Evaluate faster indexing and retrieval if larger-memory workloads justify the complexity.
