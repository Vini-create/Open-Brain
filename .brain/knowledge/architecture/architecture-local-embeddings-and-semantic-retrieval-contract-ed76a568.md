---
id: architecture-local-embeddings-and-semantic-retrieval-contract-ed76a568
type: architecture
title: Local embeddings and semantic retrieval contract
tags:
- stability
importance: 0.9
status: active
created_at: '2026-10-15T08:38:22-03:00'
updated_at: '2026-10-15T08:39:43-03:00'
related: []
---

# Local embeddings and semantic retrieval contract

embedding.py loads cached intfloat/multilingual-e5-small on CPU: 384 dimensions, normalized vectors, query: prefix for questions and passage: for indexed text. Invalid counts/dimensions, non-finite and zero vectors are rejected. Real-model acceptance compared stored float32 vectors with JSON, fresh embeddings and independent NumPy cosine, including Portuguese questions over English facts. storage.vector_scores computes cosine over all chunks without the vec0 4096 KNN cap. core.search synchronizes Markdown and combines relative vector, keyword, importance and recency scores. It returns one best passage per memory within a character-based budget. Source: embedding.py, storage.py, core.py; tests/test_stability.py.
