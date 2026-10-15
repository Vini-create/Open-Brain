---
id: rule-vector-integrity-and-recovery-command-8e99ed50
type: rule
title: Vector integrity and recovery command
tags:
- stability
importance: 0.9
status: active
created_at: '2026-10-15T08:39:44-03:00'
updated_at: '2026-10-15T08:39:44-03:00'
related: []
---

# Vector integrity and recovery command

brain status exposes indexed_chunks, indexed_vectors, index_consistent, missing_vectors and orphaned_vectors. core.search reads chunk/vector IDs in one SQLite snapshot and refuses mismatches with a brain rebuild instruction. brain rebuild creates a temporary replacement before swapping the index, preserving the old database when embedding fails. An unchanged brain remember also rebuilds a missing disposable index. Ignored history folders are recreated on search/write, fixing fresh-clone failures. Validation: missing-vector injection, successful repair and failed incremental/rebuild preservation passed tests/test_stability.py. Source: storage.py, core.py. Status consistency checks index structure, not project fact coverage.
