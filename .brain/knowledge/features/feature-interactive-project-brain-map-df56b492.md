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
updated_at: '2026-10-09T19:05:29-03:00'
related: []
---

# Interactive project Brain map

Changed: brain init creates .brain/map.html and brain remember/index refresh it; brain map regenerates it on demand. The standalone offline page shows stored Markdown text, approximate tokens and disk sizes, shared-tag and explicit related links, plus search, filters, pan, zoom, and details. The map is ignored by Git because it embeds memory content. Every project has its own Markdown, SQLite index, history, MCP path, and map; only public embedding model weights share a cache. Why: users need to inspect what their agent remembers and how facts connect while retaining separate durable Brains per project. Impact: manual Markdown edits still require brain index to become searchable; the graph draws up to 180 matching memories and the list searches all. The 10000-memory growth benchmark still recovered 4/4 facts, with 3.96-second median warm search and a 3.76-MiB map. Validation: 15 pytest tests passed, including two-project CLI/MCP persistence and HTML escaping; a wheel contained the map asset, headless Chrome rendered it, and the rebuilt Docker image created independent alpha and beta maps with correct host project names.
