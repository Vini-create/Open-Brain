---
id: constraint-scaling-and-benchmark-evidence-f49724ad
type: constraint
title: Scaling and benchmark evidence
tags: []
importance: 0.95
status: active
created_at: '2026-10-09T12:12:18-03:00'
updated_at: '2026-10-09T12:48:42-03:00'
related: []
---

# Scaling and benchmark evidence

Changed: Open Brain is published at https://github.com/Vini-create/Open-Brain.git on main; the initial release commit is 9417273. README and Getting started use the real clone URL and folder, and Publishing describes normal maintenance. README and GROWTH_REPORT.md lead with size-to-retrieval-context savings derived from measured benchmarks/results/growth.json. In a shared four-question session, Brain includes one 760-token MCP setup copy. At 4/44/164/1000/5000/10000 paired source documents and memories, savings versus broad uncapped rg are -16.09/41.04/76.19/95.38/99.15/99.58 percent; with an 8000-token cap simulated per conventional search response, they are -16.09/41.04/76.19/95.38/95.81/95.81 percent. Why: public users need exact clone steps and clear size-to-benefit figures. Impact: these are retrieval-context comparisons, not total LLM usage or cost; the cap does not validate fact recovery, targeted rg can beat Brain after setup, and warm search at 10000 memories took 4.17 seconds. Full growth retrieved 4/4 facts and the 1000-memory multilingual check recovered 12/12 fixed questions at both budgets. Quick growth writes ignored outputs. Validation: 13 pytest tests passed in the publication checkout, Markdown links passed, and the initial main branch hash was verified remotely. The original /home/vini/projectbrain workspace has an empty read-only .git; publication was made from a writable temporary clone.
