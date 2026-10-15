---
id: constraint-memory-coverage-9720ea60
type: constraint
title: Memory coverage
tags:
- stability
- coverage
importance: 0.95
status: active
created_at: '2026-10-15T08:39:44-03:00'
updated_at: '2026-10-15T08:39:44-03:00'
related: []
---

# Memory coverage

Audited 2026-10-15: core initialization/remember/search and agent protocol; config types/defaults; documents YAML/hash/chunks; embedding local E5/validation; storage schema/transaction/migration/rebuild/status/cosine; locking; MCP stdio/schema/dispatch; remote.LocalBackend; CLI. Tests: full suite33 passed/1 Fish skip. CI and benchmark imports/gates checked. Saved focused contracts for storage, embeddings, agent access, MCP records, recovery, retrieval budgets and release limits. Four paraphrased queries recovered required durability, vector, fallback and readiness facts at budget1800/limit4. An earlier compound query missed identity in a long memory; records were shortened/split and rechecked successfully. Gaps: no full new visualization audit, live remote integration or external-client/platform verification.
