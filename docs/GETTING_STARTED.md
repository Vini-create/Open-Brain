# Getting started

Second Brain is a local CLI and MCP server. Install the application once, then run `brain init` inside each software project that needs its own memory. No LLM provider, API key, FAISS server, or cloud account is required. The first installation and first embedding-model download require internet access.

## Option A: one-time installer (Linux/macOS, recommended)

Requirements: Python 3.10 or newer with `venv`, Bash, and enough disk space for PyTorch, its dependencies, and the public embedding model. The installer has been tested on Linux x86_64.

```bash
git clone https://github.com/Vini-create/Open-Brain.git
cd Open-Brain
./scripts/install.sh
export PATH="$HOME/.local/bin:$PATH" # Only needed if this directory is not already on PATH.
brain --help
```

The installer creates `.venv` inside the clone, installs the CLI, downloads `intfloat/multilingual-e5-small`, and links `brain` into `~/.local/bin`. Cloning alone does not install the command. If `brain --help` says command not found, add that directory to `PATH` in this terminal with `export PATH="$HOME/.local/bin:$PATH"`. Add the same line to your shell profile to keep it available in new terminals. You can set `BRAIN_BIN_DIR` when installing to choose a different command directory; that directory must be on `PATH`. No virtual environment activation is needed afterwards.

Initialize an **existing, separate project**:

```bash
cd /absolute/path/to/your-project
brain init
brain status
```

`brain init` creates an empty `.brain/`, `AGENTS.md`, and `.mcp.json` in the current project. Reuse the same installation in another project by changing directory and running `brain init` again. Each project gets separate memory; only the public model weights are shared. If you run `./scripts/install.sh --skip-model`, use `brain init` then `brain model download` before indexing or searching.

`brain init` also creates `.brain/map.html`. Open it directly in a browser to inspect this project's memories and approximate stored context size. No model download is needed to create or refresh the map. The page is self-contained and makes no network request.

If the clone or virtual environment moves, rerun the installer and `brain init` in each project to refresh absolute MCP command paths.

## Option B: manual Python setup (including Windows)

From the cloned repository, create and activate a Python 3.10+ virtual environment. On Linux/macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

On Windows PowerShell, use `py -m venv .venv` followed by `.venv\Scripts\Activate.ps1`. On Linux, install a CPU build of PyTorch with `python -m pip install torch --index-url https://download.pytorch.org/whl/cpu`. On Windows, follow the [official PyTorch instructions](https://pytorch.org/get-started/locally/). Then run:

```bash
python -m pip install -e .
cd /absolute/path/to/your-project
brain init
brain model download
```

Keep the virtual environment active to type `brain` with this manual setup. The generated MCP configuration uses the absolute Python path, so the client does not need terminal activation. On macOS, `pip install -e .` installs the required PyTorch dependency.

## Option C: Docker

Requirements: Docker with a running daemon and Bash. From the cloned repository:

```bash
./scripts/brain-docker build
```

Then, from any project:

```bash
cd /absolute/path/to/your-project
/absolute/path/to/Open-Brain/scripts/brain-docker init
/absolute/path/to/Open-Brain/scripts/brain-docker model download
/absolute/path/to/Open-Brain/scripts/brain-docker status
```

The script mounts the current project into `/workspace`, uses your UID/GID, and keeps model files under `~/.cache/second-brain-local/huggingface`. Its generated MCP configuration points to the script on the **host**, not to a Python binary inside the container. Use `--project /absolute/path/to/another-project` to target a different directory. The Docker image and model cache are separate from the native Python installation. The wrapper disables container networking for ordinary commands; `model download` permits network access. It uses shared SELinux volume labels (`:z`) on Linux.

## Give the Brain its first facts

`brain init` does not scan or summarize the repository. Edit these generated files, using only known facts:

- `.brain/project/idea.md`: purpose, audience, problem, and value.
- `.brain/project/overview.md`: stack, architecture, and current state.
- `.brain/project/goals.md`: priorities and next steps.

Then index them:

```bash
brain index
brain remember --type decision --title "Authentication" --content "Refresh tokens are rotated and stored in HTTPOnly cookies."
brain search "How do refresh tokens work?" --token-budget 500
brain map
```

You can also run `brain init --idea "..."` **after** the model is downloaded. `brain remember` writes a structured Markdown file and indexes it immediately. `brain index` synchronizes manual Markdown edits. `brain search` also notices and indexes changed Markdown before retrieving context. For Docker, replace `brain` with the absolute path to `scripts/brain-docker`.

Open `.brain/map.html` to browse the saved content. It updates after indexing or remembering. If the page is already open, click **Reload map**. Use `--tag auth` when remembering related facts, and `--related <memory-id>` to create an explicit link; both appear in the map. The list searches all memories, while the graph displays up to 180 at a time. `brain map` refreshes the view from Markdown but does not index manual edits; run `brain index` for those.

## Separate Brain for every project

Run `brain init` from each project's directory. Project A's `.brain/` never becomes Project B's data source: Markdown, SQLite index, local history, and map all live under the selected project path. The model cache only contains reusable public embedding weights. You can close the terminal or agent and reopen the project later; its Brain stays on disk. `brain init` is safe to rerun and does not reset saved memories. To share memory with a teammate, commit the canonical Markdown as described below; to keep it private, keep those files out of your project's Git history.

## Connect an MCP client

Initialization generates `.brain/mcp.json` and a project-root `.mcp.json`, both containing a `second-brain` stdio server with its exact host command and arguments. If your client reads `.mcp.json`, open the project in that client and restart it. Otherwise, copy the `command` and `args` from `.brain/mcp.json` into that client's stdio MCP configuration. Confirm that `brain_status`, `brain_search`, and `brain_remember` are listed.

`AGENTS.md` points coding agents to `.brain/AGENT_BRAIN.md`. The MCP server also sends those instructions during initialization. Whether an agent sees either path depends on its client. Ask the agent to consult `brain_search` before rediscovering project decisions and to call `brain_remember` after meaningful changes. The agent still needs to read source code to implement and test edits.

## What to commit in your project

Commit `.brain/project/`, `.brain/knowledge/`, `.brain/config.json`, `.brain/AGENT_BRAIN.md`, `AGENTS.md`, and `.brain/README.md` if you want to share the memory. Do not commit the generated map, SQLite index, local history, or absolute-path MCP configuration. `brain init` adds those paths to `.gitignore`. A teammate can clone the project, install Open Brain, run `brain init` and `brain index` to reconstruct the index and map from Markdown. Keep secrets out of memory files.

## Common commands

| Command | Purpose |
| --- | --- |
| `brain init` | Create or refresh the local Brain and MCP configuration. |
| `brain model download` | Fetch the default CPU embedding model once. |
| `brain remember --type decision --title ... --content ...` | Save and index durable knowledge. |
| `brain search "question" --token-budget 500` | Retrieve bounded context. |
| `brain status` | Show document and index counts. |
| `brain map` | Refresh `.brain/map.html` for local visual inspection. |
| `brain index` | Index changed Markdown only. |
| `brain rebuild` | Recreate SQLite from Markdown. |
| `brain mcp --project /absolute/path` | Run the stdio MCP server. |

See [architecture](ARCHITECTURE.md) for the data flow and [benchmarking](BENCHMARKS.md) for the measured and projected token numbers.
