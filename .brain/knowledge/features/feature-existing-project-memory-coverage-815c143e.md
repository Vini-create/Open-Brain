---
id: feature-existing-project-memory-coverage-815c143e
type: feature
title: Existing project memory coverage
tags:
- onboarding
- agent
importance: 0.5
status: planned
created_at: '2026-10-09T20:07:43-03:00'
updated_at: '2026-10-09T20:07:43-03:00'
related: []
---

# Existing project memory coverage

Changed: brain init creates .brain/PROJECT_COVERAGE.md with a focused audit for established codebases. A short versioned section in .brain/AGENT_BRAIN.md directs agents to the detailed guide when onboarding or when only summaries exist, even if records are already indexed. The guide asks for major-module responsibilities, source paths, interfaces, critical flows, documented decisions and reasons, rules, validation commands, bugs and next steps, followed by specific retrieval checks and a Memory coverage record with remaining gaps. Why: three project summaries plus one decision demonstrate indexing but do not establish adequate project knowledge. Impact: there is no fixed document quota, automatic source ingestion or LLM API. The detailed guide is outside the indexed project/knowledge folders and is read for an audit; routine instructions stay compact. Repeated init preserves existing memories and custom rules, adding missing protocol sections and creating the guide only if absent. Reports label their historical setup payload; an initial audit and later memory maintenance have agent costs. Validation: the full suite passed 19 tests with one Fish skip before guide separation; after separation, all three focused fresh-init and upgrade tests passed, including preservation of custom rules, populated project facts and customized guide content.
