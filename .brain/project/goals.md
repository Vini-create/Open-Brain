# Goals

## Current priorities

- Make cloning, installation, `brain init`, and MCP connection clear for a new user.
- Preserve durable decisions across sessions while reducing retrieved context in measured scenarios.
- Keep Markdown canonical, local CPU embeddings, and a rebuildable SQLite + sqlite-vec index.
- Measure fact recall, token payload, MCP setup cost, search latency, and index size as corpora grow.

## Out of scope

Text generation, telemetry, remote databases, automatic whole-repository ingestion, and paid LLM APIs inside the Brain.

## Next steps

Test MCP integration in additional real clients. Collect paired builder traces with and without Brain on equivalent tasks to measure actual input, cache, output, task quality, and memory-maintenance cost. Evaluate faster indexing and retrieval if larger-memory workloads justify the complexity.
