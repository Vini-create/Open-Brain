# Open Brain

**Persistent, searchable project memory for coding agents.** Store durable decisions, architecture, rules, and next steps as Markdown. An agent retrieves relevant snippets through local vector search instead of receiving the whole memory on every request. Explore what it knows in an interactive, offline project map. Embeddings run on CPU with a public model; no LLM provider, API key, or hosted database is required.

The application is a Python CLI plus a small stdio MCP server. It works in any project directory after one local installation. Docker is optional.

## Token savings by project size

Four questions in one session, with **one copy of the agent instructions and MCP tool schemas recorded in that benchmark run included** on the Brain side. Each measured project document has a corresponding indexed memory. All four facts were recovered at every size. Percentages compare the text given to an agent for retrieval, counted with `cl100k_base`; they are **not measured savings on a complete LLM task or bill**. The onboarding protocol has since expanded; reproducing the benchmark measures its current setup cost.

| Project documents / memories | Brain context incl. setup | Broad search context | Saved vs broad search | Saved if broad output is capped at 8k/question | Median Brain search |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 4 | 1,342 tokens | 1,156 tokens | −16.09% | −16.09% | 16 ms |
| 44 | 1,342 tokens | 2,276 tokens | 41.04% | 41.04% | 30 ms |
| 164 | 1,342 tokens | 5,636 tokens | 76.19% | 76.19% | 74 ms |
| 1,000 | 1,342 tokens | 29,044 tokens | 95.38% | 95.38% | 409 ms |
| 5,000 | 1,342 tokens | 157,028 tokens | 99.15% | 95.81% | 2,057 ms |
| 10,000 | 1,342 tokens | 317,028 tokens | 99.58% | 95.81% | 3,963 ms |

The broad baseline is actual `rg` path discovery plus one selected file for each question. Its uncapped output becomes too large for a practical prompt. The 8k/question column **simulates a cap on that measured output**; it does not show whether a truncated search still finds the right file. A precise keyword search used only **1,115 tokens** across the same four questions and beat Brain after its setup cost. The [growth report](GROWTH_REPORT.md) gives the raw method, full measurements, and limits; [benchmarking](docs/BENCHMARKS.md) explains how to interpret the claims.

## Install once, then use it in any project

On Linux, install Git, Bash and Python 3.10+ with `venv` (Python 3.12/3.13 is a conservative choice). Clone the repository into your home directory and run the installer once:

```bash
cd ~
git clone https://github.com/Vini-create/Open-Brain.git
cd Open-Brain
./scripts/install.sh
export PATH="$HOME/.local/bin:$PATH" # Make brain available in this terminal too.
brain --help
```

Choose the matching instructions in [INSTALLATION.md](docs/INSTALLATION.md): [Linux distributions](docs/INSTALLATION.md#linux), [macOS Apple Silicon](docs/INSTALLATION.md#macos-apple-silicon), [Windows PowerShell](docs/INSTALLATION.md#windows-powershell), or [WSL2](docs/INSTALLATION.md#windows-with-wsl2). The Bash installer does not run natively in PowerShell. Macs need Python with SQLite-extension support; Intel Macs should use the documented [Docker alternative](docs/INSTALLATION.md#docker). Native setup and Docker have been tested on Linux x86_64; other host environments are documented but not yet tested.

This puts the installation in `~/Open-Brain`, outside your other projects. The installer creates a virtual environment in the clone, installs the CLI, downloads the public embedding model, and links `brain` into `~/.local/bin`. It adds a marked PATH block to your Bash, Zsh or Fish startup files so **new terminals find `brain` automatically**. The `export` above also makes it available in the current Bash/Zsh terminal; an installer process cannot change its parent terminal's environment. Use `--no-shell-setup` if you manage shell configuration yourself. **Cloning alone does not install the command.**

Now, from **any** project directory:

```bash
cd /absolute/path/to/your-project
brain init
brain status
brain map
```

`brain init` creates an **independent** `.brain/` in the project where you run it, plus `AGENTS.md` and local MCP configuration. Run it in another project to create a new, empty Brain there. No terminal activation or second download is needed. The public `intfloat/multilingual-e5-small` embedding model is shared across projects; their memories are not. Normal indexing and search run locally and offline. Installation and model download need internet access. See the [installation guide](docs/INSTALLATION.md) for Windows, manual installation, Docker, MCP setup, and what to commit.

Add verified project facts to `.brain/project/idea.md` and run `brain index`, or start with `brain init --idea "A short description"`. Then use `brain search "What is this project for?"` to retrieve them.

### Docker instead of local Python dependencies

Tested on Linux x86_64 with Bash and a running Docker daemon:

```bash
# In the cloned Open Brain repository:
./scripts/brain-docker build

# In your separate project:
cd /absolute/path/to/your-project
/absolute/path/to/Open-Brain/scripts/brain-docker init
/absolute/path/to/Open-Brain/scripts/brain-docker model download
/absolute/path/to/Open-Brain/scripts/brain-docker status
/absolute/path/to/Open-Brain/scripts/brain-docker map
```

The wrapper mounts your project and a persistent model cache, then writes MCP configuration using **host paths**. Use the same wrapper for `search`, `remember`, `index`, and `rebuild`. It does not need network access after the model download. Docker adds startup time per command; native Python is the simpler choice for frequent CLI use.

## See what your Brain knows

Open **`.brain/map.html`** in a browser. This standalone, offline map is created by `brain init` and refreshed after `brain remember`, `brain index`, and changed Markdown discovered by search. Use `brain map` to refresh it manually, then click **Reload map** if the page is already open. Search and filter memories, click nodes to read their content, and pan or zoom the graph. Strong links come from shared tags and explicit `--related` references; the faint hub lines show project membership. The graph displays up to 180 matching memories at once, while search covers all stored memories.

The map shows the count of memories and links, Markdown and index size, and **approximate stored text tokens**. Stored text is not automatically sent to an LLM. The map is generated from this project's Markdown and requires no model download. It is a local file ignored by Git because it contains the project's memory content. After editing Markdown by hand, run `brain index` to make those changes searchable; `brain map` only refreshes the view.

Each project has its own `.brain/` with its own Markdown, SQLite index, history, and map. Closing the CLI or agent does not erase it. Running `brain init` in another project creates a separate, empty Brain; only the downloaded **model weights** are shared in the installation cache, not project knowledge.

## How project memory works

1. Fill `.brain/project/idea.md`, `overview.md`, and `goals.md` with verified project facts, then run `brain index`. `brain init --idea "..."` can add the initial idea after the model is available.
2. Save durable knowledge with `brain remember --type decision --title "..." --content "..."`, or let an MCP-connected agent call `brain_remember`. The Markdown file is indexed automatically.
3. Ask `brain search "question" --token-budget 500` or let the agent call `brain_search`. Search combines vector similarity, keywords, importance, and recency and returns a bounded response.
4. After meaningful changes, the generated `.brain/AGENT_BRAIN.md` tells the agent to record **what changed, why, impact, and actual validation**. It also tells a new agent how to populate an empty Brain.

For an established codebase, ask the agent to [audit memory coverage](docs/INSTALLATION.md#adopt-an-existing-project) after the initial summaries. Save focused knowledge about major modules, critical flows, constraints and active work, then check that specific searches recover the expected facts. Four records alone do not establish readiness. The generated protocol includes this audit even when the Brain already has indexed summaries; ongoing changes update the relevant memories incrementally.

The coverage checklist also asks the agent to preserve **contracts, state
transitions, permissions, failure cases, exact commands and source paths** in
focused memories. Search uses smaller passages and reserves room for multiple
memories at normal budgets, helping details compete with general summaries.
See the [retrieval quality comparison](RETRIEVAL_QUALITY_REPORT.md) for measured
results and remaining gaps. No tool automatically understands every source
file: adoption requires a source audit and later changes require memory updates.
Run `brain init` again in an existing project after upgrading to add the new
checklist without replacing your memories or custom instructions. The next
index/search refreshes the older passage format locally; restart a running MCP
client to load the updated server.

A [cross-project check](CROSS_PROJECT_REPORT.md) uses five different synthetic
domains and 30 new English/Portuguese questions. At 500 estimated tokens,
**29/30 answers contained all expected facts** with the default search limit;
one paraphrase required refinement. All 30 operational checks passed, covering
isolated project storage, updates, deletion, reopening and MCP. These are
bounded development tests, not a guarantee of recall for every project.

Markdown in `.brain/project/` and `.brain/knowledge/` is canonical. `.brain/index/brain.db` is a rebuildable SQLite + `sqlite-vec` index. `brain rebuild` reconstructs it from Markdown; unchanged files are not re-embedded by `brain index`. The product does **not** automatically read every source file, watch Git, or save every conversation. An agent must still inspect code before editing and validate its work. See [architecture](docs/ARCHITECTURE.md).

## MCP integration

`brain init` generates `.brain/mcp.json` and a project-root `.mcp.json` with the exact stdio command for that installation. If your client does not read `.mcp.json`, copy its `command` and `args` into the client's stdio MCP settings. Restart the client and verify these three tools: `brain_status`, `brain_search`, and `brain_remember`. The generated `AGENTS.md` directs agents to `.brain/AGENT_BRAIN.md`; MCP initialization also returns those instructions. A client's behavior determines whether it presents them to the agent. Details are in [Installation guide](docs/INSTALLATION.md#connect-an-mcp-client).

## What the benchmarks actually show

The [measured growth benchmark](GROWTH_REPORT.md) creates up to 10,000 project documents and 10,000 corresponding indexed memories: four fact-bearing pairs plus synthetic distractors. It checks exact facts in the returned text and counts that text with `cl100k_base`. The Brain returned **582 tokens** for four questions; one copy of the instructions and MCP schemas adds **760 tokens** to the table above. At 10,000 memories, adding the last 5,000 and regenerating the map took **90 seconds**; the SQLite index occupied **104 MiB** and the map **3.76 MiB**. Token savings therefore come with a real latency and indexing cost at this scale.

A separate [multilingual query test](ROBUSTNESS_REPORT.md) recovered the exact fact in **12/12 fixed direct and paraphrased questions** against 1,000 indexed memories, at both approximate budgets of 180 and 400 tokens per query. Its authored distractors are repetitive, so this is a limited retrieval check. The [large-project scenario report](docs/SCENARIOS.md) projects 20,000 to 1,000,000 documents with explicit assumptions, including a capped discovery output, repeated sessions, common prompt input, and a hypothetical memory-creation cost. **Those figures are projections, not measurements at those sizes.** The [benchmarking guide](docs/BENCHMARKS.md) explains methods, limitations, reproduction, and how to compare actual paired builder traces. No end-to-end LLM token saving has been measured yet.

## Commands and repository guides

| Command | Purpose |
| --- | --- |
| `brain init` | Create or refresh this project's Brain and MCP paths. |
| `brain model download` | Fetch public CPU embedding weights once. |
| `brain remember --type decision --title ... --content ...` | Save and index a durable fact. |
| `brain search "question" --token-budget 500` | Retrieve bounded context. |
| `brain status`, `brain index`, `brain rebuild` | Inspect, incrementally index, or rebuild the local index. |
| `brain map` | Refresh the standalone, interactive `.brain/map.html` view. |

- [Installation guide](docs/INSTALLATION.md): exact clone, install, project setup, Docker, and MCP steps.
- [Architecture](docs/ARCHITECTURE.md): files, data flow, storage, and scaling boundaries.
- [Benchmarking](docs/BENCHMARKS.md): evidence levels, reproduction, and fair comparisons.
- [Repository benchmark](BENCHMARK_REPORT.md), [growth benchmark](GROWTH_REPORT.md), [query robustness](ROBUSTNESS_REPORT.md), and [large-project scenarios](docs/SCENARIOS.md).
- [Contributing](CONTRIBUTING.md) and [MIT license](LICENSE).
- [Publishing](docs/PUBLISHING.md): create the first Git history and GitHub remote.

`SECOND_BRAIN_BUILD_SPEC.md` is the original Portuguese V1 build specification retained as project history. The English guides above describe the current product.
