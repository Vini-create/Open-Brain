# Existing project memory coverage

Project summaries provide entry points. When adopting an established project,
or when memory contains only summaries, audit coverage even if `brain_status`
reports indexed records. Search existing memory first, then:

1. Inspect the source tree, manifests, documentation, entry points and relevant
   tests to identify major subsystems and critical flows. Skip generated files,
   dependencies and secrets. Read implementation where facts need verification.
2. Save focused `architecture` or `feature` memories for each major subsystem:
   responsibilities, source paths, interfaces, dependencies and important flows.
   Record documented choices and reasons as `decision` memories; mark unknown
   reasons explicitly. Use shared tags and related memory IDs for connections.
3. Capture confirmed invariants as `rule` or `constraint` memories, setup and
   validation commands, known bugs, and current next steps. Keep facts concise
   and independently retrievable; use existing type/title to update a memory.
4. Test coverage with specific `brain_search` queries about the main flow,
   module boundaries, data storage, external integrations, important rules,
   validation commands and unfinished work, where applicable. Compare returned
   facts with the sources. For missing facts, inspect code, save and search again.
5. Save a `constraint` memory titled "Memory coverage" listing areas covered,
   sources checked, retrieval checks and remaining gaps. Distinguish retrieval
   checks from application tests. Report partial coverage honestly.

Use relevant fact recovery as the readiness criterion. Record counts alone do
not establish coverage; avoid a fixed document quota or a whole-codebase dump.
This initial audit costs context once. Later tasks fill gaps and update changed
facts incrementally, including after a new session or context compaction.
