---
id: feature-mcp-record-keys-filters-data-and-status-9b974ea4
type: feature
title: MCP record keys filters data and status
tags:
- stability
importance: 0.9
status: implemented
created_at: '2026-10-15T08:39:44-03:00'
updated_at: '2026-10-15T08:39:44-03:00'
related: []
---

# MCP record keys filters data and status

mcp_tools.py dispatches schemas to remote.LocalBackend for standalone memory. brain_search now forwards tags to core.search and explicit limit0 returns an error rather than silently using a default. brain_record supports stable key identity across title changes and persists data in YAML; brain_get returns data and related records. brain_remember without a key retains type/title identity. update_status preserves body, tags, data and existing identity for both keyed and legacy records. These contracts passed tests/test_stability.py, including real stdio initialize/remember/filter/error/status and retrieval after process exit. Typed relations still require a linked service. Source: mcp_tools.py, remote.py, core.py.
