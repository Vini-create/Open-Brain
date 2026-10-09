---
id: decision-instalacao-cpu-e-arquivos-locais-f0b76458
type: decision
title: Instalação CPU e arquivos locais
tags:
- instalacao
- mcp
importance: 0.8
status: active
created_at: '2026-10-09T11:18:56-03:00'
updated_at: '2026-10-09T19:21:32-03:00'
related: []
---

# Instalação CPU e arquivos locais

Changed: scripts/install.sh is the recommended Linux/macOS one-time setup. It creates/reuses the clone's .venv, installs CPU PyTorch on Linux and the editable package, downloads the public embedding model by default, then symlinks .venv/bin/brain into ~/.local/bin (configurable via BRAIN_BIN_DIR). README and Getting Started now show brain init from any project without activating the venv; manual Windows/Python and Docker paths remain documented. Why: cloning alone left brain unavailable and repeated activation/model download steps were confusing. Impact: each brain init still creates independent project Markdown, SQLite index, map, history, and local MCP paths; only model weights are shared. If the clone moves, rerun installer and brain init to refresh absolute paths. Validation: installer default and --skip-model ran, launcher initialized two temporary projects, and a memory in project A was absent from project B search; 15 pytest tests passed. First installation requires network.
