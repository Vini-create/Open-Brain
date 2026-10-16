---
id: decision-present-the-local-map-during-onboarding-0eb33a9d
type: decision
title: Present the local map during onboarding
tags:
- onboarding
- visualization
importance: 0.9
status: active
created_at: '2026-10-16T20:36:15-03:00'
updated_at: '2026-10-16T20:36:15-03:00'
related: []
---

# Present the local map during onboarding

User requested that people see their Brain as soon as agents begin saving useful facts. core.MAP_INSTRUCTIONS with second-brain-user-map:v1 directs agents to run brain map, provide a clickable absolute .brain/map.html path and open once in a local browser/HTML preview when supported. Otherwise provide the path; the file works offline without hosting or an HTTP server. Explain snapshot reload and textual versus CLI/MCP semantic search; avoid reopening on every write. initialize upgrades disk instructions idempotently, and mcp.instructions_for injects the section for legacy files without rewriting them. Tests cover new, legacy, custom-rule preservation and real stdio delivery; full suite34 passed/1 Fish skip. docs/images holds public screenshots rather than temporary validation files.
