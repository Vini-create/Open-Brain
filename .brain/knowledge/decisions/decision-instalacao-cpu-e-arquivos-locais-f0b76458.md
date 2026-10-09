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
updated_at: '2026-10-09T19:42:34-03:00'
related: []
---

# Instalação CPU e arquivos locais

Changed: docs/INSTALLATION.md now provides explicit Linux distribution prerequisites, macOS Apple Silicon with Homebrew Python, native Windows PowerShell, WSL2 MCP bridging, manual Python, Docker, PATH persistence and troubleshooting. README links to each platform. scripts/install.sh remains a Unix Bash installer: it creates a clone-local .venv, downloads CPU embeddings and symlinks brain into ~/.local/bin; BRAIN_PYTHON and BRAIN_BIN_DIR customize it. Why: a single Linux command was ambiguous for Windows and Macs. Constraints: native Windows uses .venv/Scripts executables; macOS Python must support SQLite extensions; Intel Macs use Linux Docker because current official PyTorch macOS x86_64 wheels are discontinued; Linux ARM64 depends on upstream wheels, and Alpine uses Docker. Memories remain isolated per project and only model weights share a cache. Validation: local documentation links and anchors passed, 17 Bash examples parsed, and WSL MCP JSON matched the CLI. Prior Linux installer and two-project isolation tests passed, as did 15 pytest tests. Windows, macOS, WSL and ARM64 execution has not been tested here. Python 3.12/3.13 is the documented conservative choice; installation and model download need network access.
