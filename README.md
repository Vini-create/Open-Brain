# Open Brain

**Local, persistent project memory for coding agents.** Save decisions, architecture,
rules and next steps as Markdown. Retrieve the relevant context with semantic
search when the next task or session needs it.

![Open Brain map with neutral dark surfaces, project metrics, memory graph and searchable list](docs/images/brain-map-desktop.png)

[English](README.md) · [Português brasileiro](README.pt-BR.md)

[![CI](https://github.com/Vini-create/Open-Brain/actions/workflows/ci.yml/badge.svg)](https://github.com/Vini-create/Open-Brain/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

Open Brain is a Python CLI (`brain`) and a stdio MCP server. Embeddings run
locally on CPU. The standalone workflow needs **no LLM API key, hosted database
or GPU**. Installation and the initial public-model download need internet;
normal local indexing and search use the cached model.

**Early release (0.1.0): feedback welcome.** Native Linux x86_64 is the verified
path. Other platform instructions and their verification limits are in the
[installation guide](docs/INSTALLATION.md#choose-your-operating-system).

[Quickstart](#quickstart) · [Preview](#see-your-brain) · [Use with an agent](#use-with-an-agent) ·
[How it works](#how-it-works) · [Troubleshooting](#troubleshooting) ·
[Evidence](#validation-and-benchmarks) · [Give feedback](#try-it-and-give-feedback)

## What you get

- **Memory across sessions:** project facts live in your project's `.brain/`,
  independently of a chat history or an agent's context window.
- **Semantic retrieval:** ask a question in English or Portuguese; the local
  multilingual model combines vector similarity with keyword and metadata ranking.
- **Readable files:** Markdown is canonical. SQLite + sqlite-vec is a rebuildable
  index, and previous memory versions are kept locally.
- **CLI and MCP access:** compatible agents can search and save; the CLI also works
  without an MCP connection.
- **An offline memory map:** open `.brain/map.html` to browse facts and their links.

The agent chooses what to save. Open Brain does not automatically ingest the
repository or record every conversation. Relevant memory helps an agent find
context; source inspection and application tests still establish correctness.

## Quickstart

### 1. Install once

On **Linux**, with Git, Bash and Python 3.10+ with `venv` installed:

```bash
cd ~
git clone https://github.com/Vini-create/Open-Brain.git
cd Open-Brain
bash scripts/install.sh
export PATH="$HOME/.local/bin:$PATH"
brain --help
```

The installer creates `.venv` in this clone, installs dependencies, downloads the
public embedding model, and links `brain` into `~/.local/bin`. It also configures
supported shell startup files; the `export` handles the current Bash/Zsh terminal.
Keep the installation clone in place: the launcher and generated MCP commands use
it. Cloning alone does not install the command.

For prerequisites and alternatives: [Linux](docs/INSTALLATION.md#linux),
[macOS](docs/INSTALLATION.md#macos-apple-silicon),
[Windows PowerShell](docs/INSTALLATION.md#windows-powershell),
[WSL2](docs/INSTALLATION.md#windows-with-wsl2),
[Docker](docs/INSTALLATION.md#docker). The Bash installer is not a native
PowerShell installer. PyTorch and model downloads can take time and disk space.

### 2. Verify save and search in a demo project

These are example facts for the demo folder:

```bash
mkdir -p ~/open-brain-demo
cd ~/open-brain-demo
brain init
brain remember --type rule --title "Session expiration" --content "Idle sessions expire after 37 minutes. Pinned sessions never expire." --tag sessions
brain search "When does an inactive session end?" --token-budget 500
brain status
brain map
```

The search should contain **37 minutes**. Status should show a saved memory,
matching `indexed_chunks` / `indexed_vectors`, and `"index_consistent": true`.
An empty Brain immediately after `init` is normal. Open `.brain/map.html` in a
browser to inspect the saved fact. These checks exercise storage and retrieval,
not just command installation.

### 3. Initialize your real project

```bash
cd /absolute/path/to/your-project
brain init
```

Each project gets its own independent Brain. Fill `.brain/project/idea.md`,
`overview.md` and `goals.md` with verified facts, then run `brain index`; or have
your agent perform the [existing-project audit](docs/INSTALLATION.md#adopt-an-existing-project).
The public model cache is shared; project memories are not.

## Use with an agent

### Connect MCP

MCP (Model Context Protocol) lets a compatible client expose Brain operations as
tools the agent can call. Configure it in the client where you run the agent:

1. Run `brain init` in the project.
2. Open `.brain/mcp.json`. It contains the absolute executable and project paths
   for this installation. A project-root `.mcp.json` is also generated.
3. If your client reads `.mcp.json`, use it. Otherwise copy the generated `command`
   and `args` into the client's **stdio MCP** settings, using its configuration format.
4. Restart the MCP connection/client and confirm `brain_status`, `brain_search`
   and `brain_remember` are available.
5. Ask the agent to save a test fact and recover it in a fresh session.

`AGENTS.md` points to `.brain/AGENT_BRAIN.md`; MCP initialization returns the
protocol too. Client support and instruction delivery vary. A generated config
alone does not prove that the agent uses memory. See
[MCP setup and verification](docs/INSTALLATION.md#connect-an-mcp-client).

Use this prompt to establish the routine:

> Read `.brain/AGENT_BRAIN.md`. Before this task, search the Brain for relevant
> context. Verify implementation details in source. After meaningful work, update
> the relevant memories with what changed, why, validation actually run and open
> work. Confirm the saved facts with a paraphrased search. If MCP is unavailable,
> use `brain search` and `brain remember` through the project terminal.

### CLI fallback and actual-use checks

An agent with terminal access can use the same `brain search` and `brain remember`
commands as the demo. Run them from the project directory, or pass
`--project /absolute/path/to/your-project`. No MCP connection is needed for this path.

Actual searches are logged in `.brain/history/searches.jsonl`; writes in
`.brain/history/changes.jsonl`. Check tool calls or these logs when verifying
adoption. Instructions cannot force every external agent to comply. For an
existing codebase, summaries alone are a start: ask the agent to save focused
contracts, decisions and failure cases, then check specific facts are recoverable.

## See your Brain

The preview at the top shows the real offline map of Open Brain's own public
project memory.

After saving the first useful facts, the agent protocol tells the agent to run
`brain map`, show the absolute path and open `.brain/map.html` in a local browser
or HTML preview when available. If it cannot open a viewer, it gives you the path.
**No local web server, hosting or account is needed.** You can open the HTML
directly from your project folder; `brain map` also prints its location.

Click a memory in the graph or list to read it. The map's search is textual;
semantic retrieval is available through CLI/MCP. The HTML is a generated snapshot:
run `brain map` and click **Reload map** to view the latest data. The agent should
present it during onboarding, rather than reopen the browser for every save.

<details>
<summary>Memory details and mobile view</summary>

![Selecting a memory displays its source, tags and saved content](docs/images/brain-map-detail.png)

<img src="docs/images/brain-map-mobile.png" alt="Brain map and memory inspector stacked on a narrow screen" width="390">

</details>

The screenshots live in [`docs/images/`](docs/images/README.md) and are part of
the repository. Your generated `.brain/map.html` remains local and ignored by
Git because it contains your project's memories.

## How it works

`remember` → canonical Markdown → local embeddings → SQLite vectors → `search` → ranked excerpts.

The default model is `intfloat/multilingual-e5-small` (384 dimensions, CPU).
Search first synchronizes changed Brain Markdown, then ranks passages using
vectors, keywords, importance and recency. Unchanged files are not re-embedded.
Scores are relative ranks, not confidence probabilities. A search returns the
best passage per memory, so multi-part questions can require focused subqueries.
The token budget is an approximation, not an exact tokenizer limit.

Saving the same type and title updates a memory and keeps its previous version.
Use a stable `--key` if the title needs to change. Manual Markdown edits become
searchable with `brain index` or the next search. `brain map` only refreshes the
view; its links represent shared tags and explicit relations, not vector similarity.
The graph draws up to 180 matching memories; its list searches all saved memories.

Keep one independently answerable subject per memory. Include source paths,
reasons, confirmed constraints and actual validation; keep it current when code
changes. Larger storage alone does not establish useful coverage.

For sharing, commit canonical Markdown and portable instructions if appropriate
for your project. The generated map, index, history and machine-specific MCP
paths are ignored by `brain init`. Memory files can contain project information;
review them before making them public. See [what to commit](docs/INSTALLATION.md#what-to-commit-in-your-project).

## Common commands

| Command | Purpose |
| --- | --- |
| `brain init` | Create or refresh project instructions and local MCP paths. |
| `brain remember --type decision --title "Subject" --content "Verified fact"` | Save and index a memory. |
| `brain search "question" --token-budget 500` | Retrieve relevant context. |
| `brain search "question" --tag auth --json` | Filter by tag and inspect structured results. |
| `brain status` | Inspect indexed counts and vector consistency. |
| `brain index` | Synchronize changed/deleted Markdown. |
| `brain rebuild` | Rebuild the index from canonical Markdown. |
| `brain map` | Refresh the offline memory map. |
| `brain model download` | Download the public model into the local cache. |

Use `brain --help` and `brain <command> --help` for options. The CLI also includes
an optional linked-service client; [remote service integration](docs/REMOTE.md)
is separate from the standalone workflow and requires a compatible service.

## Troubleshooting

| Symptom | What to check |
| --- | --- |
| `brain: command not found` | Open a new terminal or add `~/.local/bin` to PATH. See [shell setup](docs/INSTALLATION.md#make-the-unix-command-available-in-new-terminals). |
| Model unavailable locally | In an initialized project, run `brain model download` once with internet access. |
| Agent does not use memory | Verify MCP tools or CLI access, make sure the protocol is loaded, and check actual calls/logs. |
| Search misses a fact | Check that it was saved, run `brain index`, then try a focused query or a larger budget. A missing fact may need a new memory. |
| `index_consistent` is false | Run `brain rebuild`, then check `brain status`. Canonical Markdown remains the source of truth. |
| First search takes longer | A new process loads the model. MCP can reuse it; CPU speed, disk and corpus size affect latency. See [timing limits](STABILITY_REPORT.md). |

For moved clones, dependency/platform issues and upgrades, use the
[installation guide](docs/INSTALLATION.md#update-an-existing-installation).

## Validation and benchmarks

The [local stability audit](STABILITY_REPORT.md) records real embedding/cosine
checks, clone recovery, transactional index failures, concurrent writes and MCP
persistence. The final full suite passed 33 tests with one Fish skip on the
recorded Linux environment. A prior cold-start timeout and unverified platforms
are disclosed there; this is bounded evidence, not a universal stability claim.

Current authored retrieval checks recovered all expected facts for **12/12
questions at 500 estimated tokens**. At 180, two detailed answers omitted facts.
A separate 1,000-memory fixture recovered the expected fact for all 12 fixed
English/Portuguese questions. These synthetic sets do not establish recall on
every real project. Use your own facts and queries when evaluating the tool.

### Historical token-savings measurements

The table below preserves the [published growth benchmark](GROWTH_REPORT.md).
It compares retrieval text for four questions, including one historical copy of
the Brain protocol/MCP setup, with broad `rg` discovery plus selected files.
**It does not measure total LLM tokens, task quality or bills.** The current
protocol and tool schemas have changed since this run.

| Project documents / memories | Brain context incl. setup | Broad search context | Saved vs broad search | Saved if broad output is capped at 8k/question | Median Brain search |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 4 | 1,342 tokens | 1,156 tokens | −16.09% | −16.09% | 16 ms |
| 44 | 1,342 tokens | 2,276 tokens | 41.04% | 41.04% | 30 ms |
| 164 | 1,342 tokens | 5,636 tokens | 76.19% | 76.19% | 74 ms |
| 1,000 | 1,342 tokens | 29,044 tokens | 95.38% | 95.38% | 409 ms |
| 5,000 | 1,342 tokens | 157,028 tokens | 99.15% | 95.81% | 2,057 ms |
| 10,000 | 1,342 tokens | 317,028 tokens | 99.58% | 95.81% | 3,963 ms |

All four authored facts were recovered at every size in that run. The capped
column simulates truncation of the conventional output; it does not verify facts
survive that cap. A precise keyword baseline used 1,115 tokens and beat Brain
after setup cost. Search scores every chunk, so latency grows with corpus size.
Measurements stop at 10,000 memories; larger scenarios are projections.
[Methods, raw data and limits](docs/BENCHMARKS.md) explain these comparisons.

## Try it and give feedback

Start with the demo, then try a real project and a fresh agent session. Check
whether saved facts survive restart and whether paraphrased questions return
the details needed for work. Share a small reproducible example when something
fails, including OS/architecture, Python version, command, expected result and
actual output. For retrieval issues, include a non-sensitive memory, query and
budget. Do not include credentials or private project context.

[Report a problem or test result](https://github.com/Vini-create/Open-Brain/issues/new/choose) ·
[Browse issues](https://github.com/Vini-create/Open-Brain/issues) ·
[Contribute](CONTRIBUTING.md)

## Documentation

| Guide | What it covers |
| --- | --- |
| [Installation](docs/INSTALLATION.md) | OS setup, Docker, MCP, upgrades and troubleshooting. |
| [Português brasileiro](README.pt-BR.md) | Introdução, instalação e primeiro teste em português. |
| [Architecture](docs/ARCHITECTURE.md) | Markdown, embeddings, vectors, retrieval and boundaries. |
| [Benchmarking](docs/BENCHMARKS.md) | Measured vs projected results and reproduction commands. |
| [Stability audit](STABILITY_REPORT.md) | Verified local flows and remaining limits. |
| [Remote integration](docs/REMOTE.md) | Optional linked service, local mirror and offline queue. |
| [Contributing](CONTRIBUTING.md) | Development environment, validation and PR guidance. |
| [Publishing](docs/PUBLISHING.md) | Maintainer workflow for GitHub changes. |

The [original Portuguese V1 build spec](SECOND_BRAIN_BUILD_SPEC.md) is retained
as project history; the guides above describe current behavior. Open Brain is
available under the [MIT license](LICENSE).
