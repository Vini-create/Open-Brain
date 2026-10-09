# Second Brain — Agent Instructions

Persistent memory: `.brain/`. MCP: `brain_search`, `brain_remember`, `brain_status`.

## Before exploring the project

Use `brain_search` for the project's purpose, architecture, decisions, rules,
bugs, current state, and next steps before rereading the repository. Verify
implementation details in source code before editing or testing. Keep
`project/idea.md`, `overview.md`, and `goals.md` accurate. `brain index` syncs
manual Markdown edits.

Search before rediscovering. Remember after learning.

## First use in a new project

<!-- second-brain-bootstrap:v1 -->

If `brain_status` shows no memories or only empty templates, ask the user for a
project description or read the essential project files once. Fill
`.brain/project/idea.md`, `overview.md`, and `goals.md` with verified facts, then
run `brain index`. Save durable decisions with `brain_remember`. Do not invent an
architecture or dump the entire codebase into memory. Search the Brain for each
task and read the source files needed for implementation.

## Update context after meaningful changes

<!-- second-brain-context-update:v2 -->

After a meaningful change, and before ending, compacting, or handing off a
session, use `brain_remember` to save durable knowledge. Update the existing
memory with the same type and title instead of creating a duplicate. Include:

- What changed and the current state, including useful paths or contracts.
- Why it changed: requirement, problem, or decision.
- Impact, constraints, validation actually performed, and remaining work.

Example: "Changed: refresh tokens use HTTPOnly cookies. Why: reduce exposure
to scripts. Impact: the frontend cannot read the token. Validation: refresh
test passed." Never invent tests. Do not save every diff, log, conversation, or
whole source file; save facts useful to a later session that are not obvious
from the code.
