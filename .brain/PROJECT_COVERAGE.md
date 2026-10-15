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

## Detail coverage checklist

<!-- second-brain-detail-coverage:v1 -->

For each maintained subsystem, inspect the implementation and relevant tests.
Save focused memories with descriptive titles and plain-language descriptions
of what a future user might ask, rather than only code identifiers. Cover:

- Entry points, inputs/outputs, API or event contracts and source paths.
- State transitions and the steps connecting a request to its final outcome.
- Persistence, schema, defaults, configuration and lifecycle after restart.
- Permissions, invariants, error handling, retries, cancellation and edge cases.
- Dependencies, cross-module relationships, reasons for decisions and limits.
- Exact validation commands, tests actually run, known failures and open work.

Use one independently answerable subject per memory. Keep short paragraphs or
bullets; separate large flows into linked memories rather than hiding a detail
at the end of a general overview. Include concrete values and identifiers,
the source paths checked and the conditions under which each fact holds.
Do not invent a reason where none is documented. Never store credentials.

Maintain a module checklist in the "Memory coverage" memory with sources
inspected, details captured, queries checked and unresolved gaps. On changes,
update the affected contract and related flow/rule memories, including removed
or invalidated facts. A new module adds a checklist entry. The agent must do
this work: `brain init` does not read source files or autonomously learn code.

Check retrieval using paraphrased questions without filenames or function
names. Verify the required facts, not just a matching title. If a 500-token
response misses part of a multi-part question, ask focused subquestions or
raise the budget; tags/types are optional refinements. Read source to settle
missing or conflicting details, then save the verified knowledge. Larger
storage does not guarantee coverage or fitting every answer into one response.
