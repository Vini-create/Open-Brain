---
id: feature-agent-memory-access-and-mcp-persistence-1d4ff0e0
type: feature
title: Agent memory access and MCP persistence
tags:
- stability
importance: 0.9
status: implemented
created_at: '2026-10-15T08:38:23-03:00'
updated_at: '2026-10-15T08:39:43-03:00'
related: []
---

# Agent memory access and MCP persistence

AGENTS.md points to .brain/AGENT_BRAIN.md, and MCP initialize returns the protocol. Agents must search before work, save verified changes/reasons/validation after meaningful work, and check recovery using a paraphrased question. If MCP tools are unavailable, use the CLI fallback: brain search and brain remember; report an error if neither works. brain init upgrades instructions while preserving custom rules and refreshes local paths after cloning. Search logs in .brain/history/searches.jsonl and write logs in changes.jsonl demonstrate actual use; configuration alone cannot guarantee client compliance. This session used the CLI fallback and separately tested real stdio MCP persistence and restart. Source: core.py, mcp.py; tests/test_stability.py.
