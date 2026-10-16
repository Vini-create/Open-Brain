---
id: feature-interactive-project-brain-map-df56b492
type: feature
title: Interactive project Brain map
tags:
- visualization
- local
importance: 0.9
status: implemented
created_at: '2026-10-09T19:05:29-03:00'
updated_at: '2026-10-16T20:36:07-03:00'
related: []
---

# Interactive project Brain map

The offline map is generated from canonical project Markdown by visualization.py using assets/brain_map.html, without loading embeddings. brain init/remember/index generate it; brain map refreshes it. It shows tags, explicit relations, textual search/filter, a graph and a memory inspector. Semantic retrieval remains CLI/MCP. The graph draws at most180 memories. The neutral gray, square-corner theme follows the user preference. Versioned MAP_INSTRUCTIONS now tell agents to present the local HTML after first useful facts and substantial onboarding updates, open once if supported and otherwise hand off its absolute path. No HTTP server is required. Real public screenshots are in docs/images and linked by both READMEs. Validation2026-10-16: 34 pytest passed/1 Fish skip; 112 local links/images checked; browser filtering/selection passed without JS errors.
