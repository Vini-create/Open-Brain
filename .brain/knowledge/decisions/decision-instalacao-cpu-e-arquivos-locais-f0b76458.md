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
updated_at: '2026-10-09T12:12:18-03:00'
related: []
---

# Instalação CPU e arquivos locais

Changed: Linux setup installs CPU PyTorch in a virtual environment before this package; brain init creates local MCP configuration using the active Python or Docker host wrapper. The public embedding model is downloaded once per installation mode. Why: avoid unnecessary CUDA downloads, cloud dependencies, and invalid absolute paths after cloning. Impact: Markdown is canonical; .brain/index, .brain/history, and local MCP path files stay out of Git and can be regenerated. Validation: native end-to-end tests and final Docker smoke tests passed.
