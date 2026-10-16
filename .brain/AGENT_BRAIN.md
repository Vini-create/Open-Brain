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

## Build coverage for an existing project

<!-- second-brain-project-coverage:v1 -->

When adopting an established project or when memory contains only summaries,
read `.brain/PROJECT_COVERAGE.md` and audit the main modules, flows, decisions,
rules, validation commands and remaining work. Check specific fact recovery
through `brain_search` and save sources checked and gaps in "Memory coverage".
Indexed record counts alone do not establish coverage. Read the detailed guide
for this audit; later tasks update relevant memories incrementally.

## Preserve implementation details

<!-- second-brain-detail-coverage:v1 -->

Follow the detail checklist in `.brain/PROJECT_COVERAGE.md`: keep contracts,
failure cases and validation independently searchable. For a broad question,
split it into subquestions when the bounded response omits facts. Never assume
that a summary or a successful search establishes complete source coverage.


## Verify access and complete the memory loop

<!-- second-brain-agent-access:v1 -->

If MCP tools are unavailable, use the CLI in the project directory:
`brain search "task question" --token-budget 1000` and
`brain remember --type decision --title "Subject" --content "Verified facts"`.
Do not silently skip memory because a tool is missing. If neither interface
works, report the error. A fresh clone may need `brain init` to refresh local
MCP paths; never replace existing project facts with templates.

Before work, retrieve relevant facts. After meaningful work, update the same
type/title with verified changes, reasons, validation and remaining work.
Search using a paraphrased question to confirm the saved fact is recoverable.
Use focused queries when the answer spans multiple subjects. Search logs in
`.brain/history/searches.jsonl` and writes in `changes.jsonl` provide evidence
of actual use; configuration or record counts alone do not prove agent usage.

## Show the user their local memory map

<!-- second-brain-user-map:v1 -->

After saving the first useful project facts, run `brain map` in that project
(or use `--project` with its absolute path). Show the user a clickable absolute
path to `.brain/map.html` and open it once in a local browser or the client's
HTML preview when available. If opening is unavailable, give the file path
and explain how to open it in a browser. No local server or hosting is required;
the HTML works offline. With Docker, use the generated host path.

Explain that the map shows saved memories, tags and explicit relations. Its
search is textual; semantic search is provided by `brain_search` / `brain search`.
The page is a generated snapshot: refresh it with `brain map` and Reload map
after later changes. Present it again after a substantial onboarding update,
but do not reopen a browser for every save. Never publish a user's generated
map or screenshots without their request; it embeds their project knowledge.
