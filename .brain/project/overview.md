# Project overview

A Python package provides the `brain` CLI and a stdio MCP server. `brain init` creates independent `.brain/` project memory, agent instructions, and local MCP configuration. Markdown with YAML front matter is canonical; SQLite + sqlite-vec is a rebuildable index. An optional Docker wrapper runs the same CLI against a host project.

The default 384-dimensional `intfloat/multilingual-e5-small` embedding model runs on CPU from a local cache after one public download. `brain remember` saves and indexes a memory. `brain search` checks changed Markdown before ranking with vector similarity, keywords, importance, and recency under an approximate token budget. The full-scan hybrid ranker works beyond the vec0 KNN limit of 4,096 but gets slower as memory grows.

English-first guides, automated tests, CI, and reproducible reports support public use. A measured 10,000-document synthetic corpus recovered 4/4 facts but took 4.17 seconds per warm search on the benchmark machine. No LLM API, automatic source-code capture, or end-to-end builder token saving is claimed.
