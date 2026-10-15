---
id: decision-existing-local-brain-upgrade-procedure-c8b566c3
type: decision
title: Existing local Brain upgrade procedure
tags:
- operations
importance: 0.8
status: active
created_at: '2026-10-15T08:58:17-03:00'
updated_at: '2026-10-15T08:58:17-03:00'
related: []
---

# Existing local Brain upgrade procedure

Changed: existing standalone project Brains were upgraded using the current shared Open-Brain installation. Refresh agent instructions and MCP paths with brain init, synchronize the index, then save a short operational rule and verify it with a paraphrased search. Why: installations can retain old executable paths and miss CLI fallback or retrieval-check instructions. Preserve all existing canonical Markdown by hash and back up configuration/instructions before updating; never copy project knowledge across Brains. Validation on 2026-10-15: three existing standalone Brains upgraded; all prior canonical files preserved, existing context and the operational rule retrieved, index_consistent true with matching chunk/vector counts in all three. Active MCP processes need a restart to load updated code. Optional linked-service fixtures were excluded.
