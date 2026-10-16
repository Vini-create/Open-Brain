---
id: decision-brain-map-neutral-visual-style-05e8c63f
type: decision
title: Brain map neutral visual style
tags:
- visualization
- design
importance: 0.9
status: active
created_at: '2026-10-16T20:26:39-03:00'
updated_at: '2026-10-16T20:26:39-03:00'
related: []
---

# Brain map neutral visual style

User preference on 2026-10-16: make the Brain map understated and comfortable for repeated use, with an off-black gray background and square corners; avoid a generic AI-dashboard appearance. Implemented in src/second_brain/assets/brain_map.html: neutral #181818 base, flat gray surfaces, no gradients or rounded controls/panels/chips, restrained typography, muted graph colors and metric dividers instead of card backgrounds. Retain readable contrast and visible keyboard focus. Regenerated the project map with brain map. Validation: Chrome desktop1440x1050 and mobile390x844 screenshots reviewed; selection, textual search and type filtering worked without JavaScript errors; existing model-free visualization test passed. Graph label overlap, mobile clipping and raw Markdown remain separate usability work.
