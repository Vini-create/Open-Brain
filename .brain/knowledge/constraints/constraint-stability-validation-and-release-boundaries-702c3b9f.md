---
id: constraint-stability-validation-and-release-boundaries-702c3b9f
type: constraint
title: Stability validation and release boundaries
tags:
- stability
importance: 0.9
status: active
created_at: '2026-10-15T08:38:23-03:00'
updated_at: '2026-10-15T08:39:44-03:00'
related: []
---

# Stability validation and release boundaries

2026-10-15 local audit: 33 pytest tests passed, one Fish skip, on Linux x86_64/Python3.14.7. Run OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 python -m pytest -q. STABILITY_REPORT.md records real embeddings/cosine, fault recovery, index integrity, clone recovery, concurrent writes and stdio MCP restart. CI also gates detailed and multilingual fact recovery with benchmark --check. Obsolete imports now use mcp.LOCAL_TOOLS. Not verified this run: live linked remote service, external-client GUI setup, Docker, Windows/macOS, power loss, universal recall or paired LLM task cost. remote.py contains optional HTTP/outbox/mirror behavior outside the standalone readiness claim. Historical reports retain older engine measurements.
