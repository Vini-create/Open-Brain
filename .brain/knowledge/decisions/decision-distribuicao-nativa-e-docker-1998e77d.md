---
id: decision-distribuicao-nativa-e-docker-1998e77d
type: decision
title: Distribuição nativa e Docker
tags: []
importance: 0.5
status: active
created_at: '2026-10-09T11:43:01-03:00'
updated_at: '2026-10-09T12:12:13-03:00'
related: []
---

# Distribuição nativa e Docker

Changed: the public repository now has English-first README and guides, a clone-to-project quickstart, Docker wrapper, MCP instructions, CI, contribution and publishing guides. Why: a new GitHub user must be able to install once and initialize an independent Brain in any project without an LLM API. Impact: native and Docker modes use local CPU embeddings and generate host-valid MCP paths; Docker uses :z volume labels on SELinux. Validation: 11 pytest tests passed; the final Docker image built and initialized a new project, then remembered, searched, and answered MCP initialize/tools/list/brain_status. The Git publication dry run excluded indexes, history, and machine-specific MCP files.
