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
updated_at: '2026-10-09T19:47:35-03:00'
related: []
---

# Instalação CPU e arquivos locais

Changed: Unix scripts/install.sh now invokes scripts/setup-shell-path.py to persist a marked PATH block in Zsh .zshrc/.zprofile, Bash .bashrc/login profile or Fish conf.d. Repeated setup is idempotent and preserves unrelated settings; --no-shell-setup opts out and can combine with --skip-model. README installation includes export PATH for the current parent terminal, while new terminals load the persisted path. docs/INSTALLATION.md includes a dependency-free repair command for older clones, OS-specific Linux/macOS/Windows/WSL instructions and verified-platform limitations. Why: installation succeeded but another project terminal could not resolve brain because the export was temporary. Impact: the launcher still points into the installation clone, project memories remain isolated, and MCP uses absolute executable paths. Validation: the real installation at ~/Open-Brain initialized two independent temporary projects from fresh Zsh login shells. Shell regression tests passed for Bash and Zsh plus malformed-profile preservation (3 passed); Fish runtime test skipped because Fish is unavailable. Installer and documentation shell syntax plus links checked. Windows/macOS/WSL/ARM64 execution remains untested; earlier native Linux core suite had 15 passing tests. Installation requires network, and model weights run locally after download.
