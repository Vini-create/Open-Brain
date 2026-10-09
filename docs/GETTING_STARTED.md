# Getting started

Second Brain is a local CLI and MCP server. Install the application once, then run `brain init` inside each software project that needs its own memory. No LLM provider, API key, FAISS server, or cloud account is required. The first installation and first embedding-model download require internet access.

## Option A: native Python (recommended)

Requirements: Python 3.10 or newer, `pip`, and enough disk space for PyTorch, its dependencies, and the public embedding model. On Linux x86_64:

```bash
git clone https://github.com/Vini-create/Open-Brain.git
cd Open-Brain
python -m venv .venv
source .venv/bin/activate
python -m pip install torch --index-url https://download.pytorch.org/whl/cpu
python -m pip install -e .
brain --help
```

On macOS, omit the PyTorch CPU-index command and run `python -m pip install -e .` in the virtual environment. On Windows PowerShell, activate with `.venv\Scripts\Activate.ps1`; install a CPU build of PyTorch using its [official instructions](https://pytorch.org/get-started/locally/) before `pip install -e .`. The Docker script below requires Bash and has been tested on Linux x86_64.

Initialize an **existing, separate project**:

```bash
cd /absolute/path/to/your-project
brain init
brain model download
brain status
```

`brain init` creates an empty `.brain/`, `AGENTS.md`, and `.mcp.json` in the current project. `brain model download` fetches the public `intfloat/multilingual-e5-small` weights once into the local Hugging Face cache. Later embedding and search commands load those files locally. Reuse the same installation in another project by changing directory and running `brain init` again. Keep the virtual environment active to type `brain`; the generated MCP configuration points to the absolute Python path and does not depend on terminal activation.

If `brain` is not found, activate the virtual environment in that terminal or run `/absolute/path/to/Open-Brain/.venv/bin/brain`. If the clone or virtual environment moves, rerun `brain init` in each project to refresh its MCP command path.

## Option B: Docker

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
```

You can also run `brain init --idea "..."` **after** the model is downloaded. `brain remember` writes a structured Markdown file and indexes it immediately. `brain index` synchronizes manual Markdown edits. `brain search` also notices and indexes changed Markdown before retrieving context. For Docker, replace `brain` with the absolute path to `scripts/brain-docker`.

## Connect an MCP client

Initialization generates `.brain/mcp.json` and a project-root `.mcp.json`, both containing a `second-brain` stdio server with its exact host command and arguments. If your client reads `.mcp.json`, open the project in that client and restart it. Otherwise, copy the `command` and `args` from `.brain/mcp.json` into that client's stdio MCP configuration. Confirm that `brain_status`, `brain_search`, and `brain_remember` are listed.

`AGENTS.md` points coding agents to `.brain/AGENT_BRAIN.md`. The MCP server also sends those instructions during initialization. Whether an agent sees either path depends on its client. Ask the agent to consult `brain_search` before rediscovering project decisions and to call `brain_remember` after meaningful changes. The agent still needs to read source code to implement and test edits.

## What to commit in your project

Commit `.brain/project/`, `.brain/knowledge/`, `.brain/config.json`, `.brain/AGENT_BRAIN.md`, `AGENTS.md`, and `.brain/README.md` if you want to share the memory. Do not commit the generated SQLite index, local history, or absolute-path MCP configuration. `brain init` adds those paths to `.gitignore`. A teammate can clone the project, install Second Brain, run `brain init`, download the model, and run `brain index` to reconstruct the index from Markdown. Keep secrets out of memory files.

## Common commands

| Command | Purpose |
| --- | --- |
| `brain init` | Create or refresh the local Brain and MCP configuration. |
| `brain model download` | Fetch the default CPU embedding model once. |
| `brain remember --type decision --title ... --content ...` | Save and index durable knowledge. |
| `brain search "question" --token-budget 500` | Retrieve bounded context. |
| `brain status` | Show document and index counts. |
| `brain index` | Index changed Markdown only. |
| `brain rebuild` | Recreate SQLite from Markdown. |
| `brain mcp --project /absolute/path` | Run the stdio MCP server. |

See [architecture](ARCHITECTURE.md) for the data flow and [benchmarking](BENCHMARKS.md) for the measured and projected token numbers.
