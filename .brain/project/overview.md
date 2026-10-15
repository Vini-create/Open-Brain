# Project overview

A Python package provides the `brain` CLI and a stdio MCP server. `brain init` creates independent `.brain/` project memory, agent instructions, local MCP configuration, and a standalone `.brain/map.html` view. Markdown with YAML front matter is canonical; SQLite + sqlite-vec is a rebuildable index. An optional Docker wrapper runs the same CLI against a host project.

The stability audit adds transactional indexing, atomic rebuild replacement, per-project write locks, explicit vector consistency status, MCP tag/key/data persistence and agent CLI fallback with post-write retrieval checks. See STABILITY_REPORT.md and tests/test_stability.py. Optional remote.py supports linked-service reads and queued writes; the local audit does not validate a deployed remote service.

Public onboarding is available in README.md and README.pt-BR.md, with a tested demo, MCP setup and feedback links. docs/INSTALLATION.md covers upgrades/troubleshooting; docs/REMOTE.md isolates optional service behavior. GitHub issue forms accept bug reports and trial feedback. Historical benchmark figures remain explicitly separated from current local verification.

The default 384-dimensional `intfloat/multilingual-e5-small` embedding model runs on CPU from a local cache after one public download. `brain remember` saves and indexes a memory. `brain search` checks changed Markdown before ranking with vector similarity, keywords, importance, and recency under an approximate token budget. The full-scan hybrid ranker works beyond the vec0 KNN limit of 4,096 but gets slower as memory grows.

The map is regenerated after indexing or remembering and shows searchable memory content, explicit relations, shared tags, and approximate stored text size. It reads only the selected project's Markdown and works offline without embedding weights. English-first guides, automated tests, CI, and reproducible reports support public use. A measured 10,000-document synthetic corpus recovered 4/4 facts but took 3.96 seconds per warm search on the benchmark machine; the generated map was 3.76 MiB. No LLM API, automatic source-code capture, or end-to-end builder token saving is claimed.
