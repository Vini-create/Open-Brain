---
id: constraint-scaling-and-benchmark-evidence-f49724ad
type: constraint
title: Scaling and benchmark evidence
tags: []
importance: 0.95
status: active
created_at: '2026-10-09T12:12:18-03:00'
updated_at: '2026-10-09T12:47:19-03:00'
related: []
---

# Scaling and benchmark evidence

Changed: public product name is Open Brain and the target GitHub repository is https://github.com/Vini-create/Open-Brain.git. README and Getting started now use the real clone URL and folder; Publishing describes normal maintenance. The README and GROWTH_REPORT.md lead with project-size-to-retrieval-context savings derived from measured benchmarks/results/growth.json. The Brain side includes one 760-token MCP setup copy in a shared four-question session. At 4/44/164/1000/5000/10000 paired source documents and indexed memories, savings versus broad uncapped rg are -16.09/41.04/76.19/95.38/99.15/99.58 percent; with an 8000-token cap simulated per conventional search response, they are -16.09/41.04/76.19/95.38/95.81/95.81 percent. Why: public users need exact clone instructions and size-to-benefit numbers. Impact: percentages describe retrieval context, not total LLM usage or cost; the cap does not validate fact recovery, targeted rg can beat Brain after setup, and warm search at 10000 memories took 4.17 seconds. Full growth retrieved 4/4 facts and the 1000-memory multilingual check recovered 12/12 fixed questions at both budgets. Quick growth runs write ignored quick outputs. Validation: 13 pytest tests passed after public URL updates; prior full growth, quick growth, Docker image/init/status, link, compilation, and Git ignore checks passed. The GitHub repository was confirmed empty before initial publication.
