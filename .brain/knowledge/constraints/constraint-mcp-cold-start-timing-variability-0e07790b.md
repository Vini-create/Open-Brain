---
id: constraint-mcp-cold-start-timing-variability-0e07790b
type: constraint
title: MCP cold-start timing variability
tags:
- mcp
- validation
importance: 0.8
status: active
created_at: '2026-10-15T09:03:55-03:00'
updated_at: '2026-10-15T09:03:55-03:00'
related: []
---

# MCP cold-start timing variability

Follow-up before publication on 2026-10-15: one full-suite run timed out after 120 seconds in tests/test_visualization.py fresh-process MCP search (32 passed, 1 failed, 1 skipped; 150.02s). The isolated test then passed in 27.50s. A full rerun passed 33 tests with 1 Fish skip in 84.84s, without increasing the deadline. Root cause was not established; do not infer a confirmed deadlock or claim a cold-start latency guarantee. The failure showed no data-integrity or fact mismatch. Existing earlier full runs also passed. See STABILITY_REPORT.md. Separately, three existing local Brains passed canonical-file preservation, operational retrieval and real MCP initialize/status checks after protocol/runtime updates.
