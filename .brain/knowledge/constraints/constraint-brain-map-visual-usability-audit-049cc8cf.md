---
id: constraint-brain-map-visual-usability-audit-049cc8cf
type: constraint
title: Brain map visual usability audit
tags:
- visualization
- usability
importance: 0.85
status: active
created_at: '2026-10-16T20:19:13-03:00'
updated_at: '2026-10-16T20:19:13-03:00'
related: []
---

# Brain map visual usability audit

Visual audit 2026-10-16 of the real generated .brain/map.html with 19 memories in isolated headless Chrome at 1440x1050 and 390x844. Screenshot and CDP interactions confirmed selection, textual search, decision-type filtering, no horizontal page overflow and no JavaScript errors. Desktop graph labels overlap even at 19 memories; mobile fit minimum zoom clips graph nodes and the memory list starts below the first screen. Detail shows raw Markdown in a scrollable pre element, the interface is English and metrics emphasize technical storage counts. A zero-match filter retains the previously selected detail, which can mislead. HTML search is substring matching, not the CLI/MCP semantic ranker; the map is a generated snapshot. No interface code was changed. Source: src/second_brain/assets/brain_map.html.
