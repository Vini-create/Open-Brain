---
id: architecture-canonical-memory-and-transactional-vector-storage-7edb3908
type: architecture
title: Canonical memory and transactional vector storage
tags:
- stability
importance: 0.9
status: active
created_at: '2026-10-15T08:38:18-03:00'
updated_at: '2026-10-15T08:39:39-03:00'
related: []
---

# Canonical memory and transactional vector storage

Markdown in .brain/project and .brain/knowledge is canonical. documents.py parses YAML, hashes content and chunks bodies. storage.py synchronizes changed hashes into documents/chunks and sqlite-vec vec_chunks with matching IDs in one transaction. Moving or swapping Markdown paths preserves memory identity; duplicate IDs are rejected. Rebuild stages a sibling database and replaces the live index only after success; failed embedding preserves the last index. locking.py serializes remember/index/rebuild across threads/processes. Source: storage.py, documents.py, locking.py. Validation: tests/test_stability.py passed rename/swap/delete, fault injection, concurrent writers and rebuild. Markdown may persist before an indexing error; fix the cause and run brain index.
