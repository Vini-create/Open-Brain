---
id: constraint-measured-retrieval-budgets-and-missing-details-fac353f0
type: constraint
title: Measured retrieval budgets and missing details
tags:
- stability
importance: 0.9
status: active
created_at: '2026-10-15T08:39:44-03:00'
updated_at: '2026-10-15T08:39:44-03:00'
related: []
---

# Measured retrieval budgets and missing details

Current authored fixtures in benchmarks/results/stability-retrieval.json: 47 memories, 12 questions. At budgets500/900, 12/12 complete answers and 36/36 facts. At budget180, 10/12 complete and 30/36 facts. In stability-robustness.json, 1000 memories with 996 distractors and 12 English/Portuguese questions: correct memory first and fact present12/12 at budgets180/400. These are synthetic authored sets, not universal recall. Search returns one passage per document, so keep memories independently answerable; a compound question may require focused subquestions or a larger budget. Scores are relative ranks, not confidence. Source: benchmarks/retrieval_quality.py, robustness.py, core.search; STABILITY_REPORT.md.
