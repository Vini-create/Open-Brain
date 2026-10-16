---
id: feature-public-documentation-and-tester-onboarding-44082854
type: feature
title: Public documentation and tester onboarding
tags:
- documentation
- onboarding
importance: 0.9
status: implemented
created_at: '2026-10-15T10:11:09-03:00'
updated_at: '2026-10-16T20:43:17-03:00'
related: []
---

# Public documentation and tester onboarding

Changed: README.md now leads with purpose, Linux install, a runnable save/search demo and MCP/CLI adoption; README.pt-BR.md provides Portuguese onboarding. Installation documents upgrades, expected status and troubleshooting; docs/REMOTE.md isolates optional service/network/queue behavior. CONTRIBUTING uses the installed virtualenv. GitHub issue forms collect bugs and trial results. Why: public users need a clear first run and honest evidence. Validation: 95 local links/anchors checked, both READMEs rendered, JSON/Bash/YAML examples checked, four benchmark-claim/scenario tests passed. Extracted English/Portuguese demos passed CLI, fresh-process MCP, vector consistency and reinit preservation on Linux. Other OS instructions were not executed. Historical measurements remain labeled. The actual map screenshot in docs/images/brain-map-desktop.png is placed immediately after the opening introduction in both READMEs, once per file; detail/mobile views remain in the later preview section. Markdown rendering checked the image precedes the first H2.
