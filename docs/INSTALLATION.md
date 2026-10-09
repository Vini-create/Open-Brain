# Installation and project setup

Second Brain is a local CLI and MCP server. Install the application once, then run `brain init` inside each software project that needs its own memory. No LLM provider, API key, FAISS server, or cloud account is required. The first installation and first embedding-model download require internet access.

## Choose your operating system

The package requires Python 3.10+, Git, and disk space for PyTorch and the embedding model. **Python 3.12 or 3.13 is a conservative choice** when installing; a newer Python release may not yet have wheels for every dependency. No GPU is needed.

| Environment | Installation path | Verification |
| --- | --- | --- |
| Linux x86_64 with glibc | [Linux installer](#linux) | Native installation and project isolation tested on the development Linux host. |
| macOS Apple Silicon (M-series) | [macOS instructions](#macos-apple-silicon) | Documented; not tested on a Mac. |
| Windows x64, native PowerShell | [Windows instructions](#windows-powershell) | Documented; not tested on Windows. |
| Windows with WSL2 | [WSL instructions](#windows-with-wsl2) | Documented; not tested under WSL. |
| macOS Intel | [Docker](#docker) | Native current PyTorch wheels unavailable; Docker host setup not tested on a Mac. |
| Linux ARM64 | Linux installer if all dependency wheels are available; otherwise a compatible Docker image | Not tested on ARM64; depends on upstream binary availability. |
| Alpine Linux / musl | Docker with this repository's Debian-based image | Native binary installation is not a supported path. |

The Bash installer uses Unix `.venv/bin/` paths. Git Bash on native Windows does not turn it into a Windows installer; use PowerShell or WSL instead. Only the Linux host and Linux x86_64 Docker path have been exercised here; this table does not claim testing on every listed distribution.

## Linux

Install the prerequisites for your distribution, then use the same installer. Run only the block for your distribution.

**Ubuntu, Debian, Linux Mint:**

```bash
sudo apt update
sudo apt install git bash python3 python3-pip python3-venv
```

**Fedora, current RHEL-compatible distributions:**

```bash
sudo dnf install git bash python3 python3-pip
```

**Arch Linux, EndeavourOS:**

```bash
sudo pacman -Syu git bash python python-pip
```

On other distributions, including openSUSE, install Git, Bash and a Python 3.10+ package with `pip` and `venv` through the distribution's package manager. Package names vary with the distribution and Python version. Check `python3 --version` before continuing; on an older system choose a supported Python explicitly with `BRAIN_PYTHON` as shown below. Ubuntu's [Python setup guide](https://documentation.ubuntu.com/ubuntu-for-developers/howto/python-setup/) covers its virtual-environment prerequisites.

Install Open Brain into your home directory:

```bash
cd ~
git clone https://github.com/Vini-create/Open-Brain.git
cd Open-Brain
bash scripts/install.sh
export PATH="$HOME/.local/bin:$PATH"
brain --help
```

If you already cloned it at `~/Open-Brain`, use `cd ~/Open-Brain` and run the installer there instead of cloning again. The installer creates `.venv`, installs CPU PyTorch and the application, downloads the model, and links `brain` into `~/.local/bin`. It configures supported shell startup files for new terminals; the `export` in the block also updates the current Bash/Zsh terminal. Installation is for your user. No virtual environment activation is needed afterwards.

To choose another installed Python, replace the installer invocation with:

```bash
BRAIN_PYTHON=python3.12 bash scripts/install.sh
```

Current PyTorch Linux binaries require a compatible architecture and glibc version; see the [official platform requirements](https://pytorch.org/get-started/locally/). Older distributions and Alpine's musl environment may not satisfy them. Use [Docker](#docker) on a host capable of running the provided image if native wheels cannot be installed. ARM64 also requires compatible PyTorch and sqlite-vec binaries; it has not been validated here.

## macOS Apple Silicon

Use an ARM64 Terminal session (`uname -m` should report `arm64`) and a Python build that supports SQLite extensions. The system Python may omit that feature, which Open Brain needs for sqlite-vec. The [sqlite-vec macOS guide](https://alexgarcia.xyz/sqlite-vec/python.html#macos-blocks-sqlite-extensions-by-default) recommends Homebrew Python.

With [Homebrew](https://brew.sh/) already installed:

```bash
brew install git python@3.12
cd ~
git clone https://github.com/Vini-create/Open-Brain.git
cd Open-Brain
BRAIN_PYTHON="$(brew --prefix)/bin/python3.12" bash scripts/install.sh
export PATH="$HOME/.local/bin:$PATH"
brain --help
```

The [Homebrew Python 3.12 formula](https://formulae.brew.sh/formula/python@3.12) supplies the executable used above. The installer obtains PyTorch through the package's normal dependencies on macOS and runs embeddings on CPU. It does not use the Linux CPU-wheel index on a Mac. If using another Python distribution, check its SQLite-extension support first and set `BRAIN_PYTHON` to its executable.

**Intel Macs:** use the [Docker path](#docker) with a compatible Docker Desktop installation. PyTorch [stopped publishing official macOS x86_64 binaries starting with release 2.3](https://dev-discuss.pytorch.org/t/pytorch-macos-x86-builds-deprecation-starting-january-2024/1690); the unpinned native install cannot be presented as a reliable current path for Intel Macs. The Docker image uses Linux dependencies and has been tested on Linux x86_64, rather than on macOS.

## Make the Unix command available in new terminals

The installer now adds a marked `Open Brain PATH` block automatically. Zsh uses `.zshrc` and `.zprofile` (respecting `ZDOTDIR`); Bash uses `.bashrc` and its existing login profile, falling back to `.profile`; Fish uses `conf.d/open-brain.fish`. Repeated installation updates the block without duplicating it. Other settings are preserved. Open a new terminal to load the change. `BRAIN_BIN_DIR` selects another launcher directory and the generated block uses that directory.

The installer cannot change the already running parent terminal. For the current Bash/Zsh terminal, run:

```bash
export PATH="$HOME/.local/bin:$PATH"
brain --help
```

For Fish, use `fish_add_path ~/.local/bin`. If you installed with an older version, update the clone and repair shell setup without reinstalling dependencies or downloading the model again:

```bash
cd ~/Open-Brain
git pull --ff-only
python3 scripts/setup-shell-path.py "$HOME/.local/bin"
export PATH="$HOME/.local/bin:$PATH"
```

Use `bash scripts/install.sh --no-shell-setup` to opt out of startup-file changes, then add the launcher directory to your shell configuration yourself. Unsupported shells receive manual PATH guidance.

Then initialize each existing project:

```bash
cd /absolute/path/to/your-project
brain init
brain status
```

The installer downloads `intfloat/multilingual-e5-small` once. If you chose `bash scripts/install.sh --skip-model`, run `brain model download` after your first `brain init`, before indexing or searching.

## Windows PowerShell

Install Git for Windows from its [official download page](https://git-scm.com/downloads/win) and 64-bit Python 3.12 from [Python.org](https://www.python.org/downloads/windows/), including the `py` command. Open a new PowerShell terminal and confirm `git --version` and `py -3.12 --version` work. These instructions target x64 Windows; native Windows ARM64 has not been validated and depends on upstream wheels.

```powershell
Set-Location $env:USERPROFILE
git clone https://github.com/Vini-create/Open-Brain.git
Set-Location Open-Brain
py -3.12 -m venv .venv
& ".\.venv\Scripts\python.exe" -m pip install torch --index-url https://download.pytorch.org/whl/cpu
& ".\.venv\Scripts\python.exe" -m pip install -e .
$brainScripts = Join-Path $env:USERPROFILE "Open-Brain\.venv\Scripts"
$env:Path = "$brainScripts;$env:Path"
brain --help
```

If using an installed Python 3.13 instead, replace `py -3.12` with `py -3.13`. Explicit selection avoids picking a newer interpreter whose dependency wheels may not be ready. The block calls the virtual environment's Python directly, so it does not require `Activate.ps1` or changing PowerShell's execution policy. The CPU-wheel installation follows the [PyTorch installation guide](https://pytorch.org/get-started/locally/).

Make `brain` available in future terminals by opening Windows **Edit environment variables for your account**, editing the **user** `Path`, and adding `%USERPROFILE%\Open-Brain\.venv\Scripts`. Restart the terminal and your coding client after changing it. The `$env:Path` command above already handles the current terminal.

Now initialize your project and download the embedding model once:

```powershell
Set-Location "C:\path\to\your-project"
brain init
brain model download
brain status
```

In subsequent projects, run only `brain init`; the cached model is reused. If you prefer to avoid editing `Path`, call the executable directly from any project:

```powershell
& "$env:USERPROFILE\Open-Brain\.venv\Scripts\brain.exe" init
```

The generated MCP configuration uses the absolute Windows Python executable and project path. A native Windows MCP client can use that configuration. No Bash script is needed for this path.

## Windows with WSL2

For a Linux workflow on Windows, install WSL using [Microsoft's instructions](https://learn.microsoft.com/en-us/windows/wsl/install). In an administrator PowerShell terminal:

```powershell
wsl --install -d Ubuntu
```

Restart if prompted, open Ubuntu, and follow the [Linux instructions](#linux) inside that shell. Keep the clone and your project paths consistent with the WSL environment. The Unix launcher belongs to WSL and is not a native PowerShell command.

A client running inside WSL can use the generated Linux MCP configuration. A client running on the Windows host must launch it through `wsl.exe` instead; for example, adapt these paths and the distribution name in its MCP settings:

```json
{
  "mcpServers": {
    "second-brain": {
      "command": "wsl.exe",
      "args": [
        "--distribution", "Ubuntu", "--",
        "/home/YOUR_WSL_USER/Open-Brain/.venv/bin/python",
        "-m", "second_brain", "mcp", "--project",
        "/home/YOUR_WSL_USER/your-project"
      ]
    }
  }
}
```

Both paths must exist inside WSL. An absolute Linux command copied unchanged into a native Windows client's settings will not launch successfully.

## Manual Python alternative on Linux/macOS

For an existing clone, you can manage the virtual environment yourself:

```bash
cd ~/Open-Brain
python3 -m venv .venv
source .venv/bin/activate
```

On Linux, install CPU PyTorch first:

```bash
python -m pip install torch --index-url https://download.pytorch.org/whl/cpu
```

On macOS Apple Silicon, omit that command; `pip install -e .` resolves PyTorch. Use a Python with SQLite-extension support as described in the macOS section. Then, on either system:

```bash
python -m pip install -e .
cd /absolute/path/to/your-project
brain init
brain model download
```

This manual path requires activating `~/Open-Brain/.venv/bin/activate` in each new terminal, or calling `~/Open-Brain/.venv/bin/brain` directly. Generated MCP settings use absolute paths and do not require terminal activation.

## Docker

Requirements: Bash and Docker with a running Linux-container daemon. The wrapper and image have been tested on Linux x86_64. On macOS use Docker Desktop and Terminal; on Windows use a WSL2 shell with Docker Desktop's WSL integration enabled. The Bash wrapper is not a native PowerShell wrapper. macOS, WSL and ARM64 host setups remain untested here.

From an existing clone:

```bash
cd ~/Open-Brain
bash scripts/brain-docker build
```

Then, from any project in the same host environment:

```bash
cd /absolute/path/to/your-project
~/Open-Brain/scripts/brain-docker init
~/Open-Brain/scripts/brain-docker model download
~/Open-Brain/scripts/brain-docker status
```

For an Intel Mac, this uses an x86_64 Linux container rather than Intel macOS PyTorch binaries. The image's build still needs compatible Linux CPU wheels. The script mounts the current project into `/workspace`, uses your UID/GID, and keeps model files under `~/.cache/second-brain-local/huggingface`. Its generated MCP configuration points to the script on the **host**. The MCP client must be able to run Bash in that same environment; Windows-host clients using WSL need a `wsl.exe` launch configuration. Use `--project /absolute/path/to/another-project` to target a different directory.

The Docker image and model cache are separate from the native Python installation. Ordinary commands disable container networking; `model download` permits it. The wrapper uses shared SELinux volume labels (`:z`) on Linux.

## Installation checks and troubleshooting

After installation, run `brain init`, `brain status`, `brain remember --type decision --title "Install check" --content "This project has its own local Brain."`, and `brain search "local Brain"` in a disposable project directory. These check local storage and actual embedding retrieval, beyond `brain --help`. Open `.brain/map.html` to inspect the resulting memory.

| Symptom | Action |
| --- | --- |
| `brain` command not found in a different terminal | The earlier `export` applied only to the installation terminal. Open a new terminal after shell setup, or use the repair block above for older installations. Windows uses the user `Path` steps. `~/.local/bin/brain` is also usable by absolute path on Unix. |
| `No module named venv` / `ensurepip` unavailable | Install your distribution's Python virtual-environment package; Ubuntu/Debian use `python3-venv`. |
| No matching distribution for `torch` or another dependency | Check Python version, OS and CPU architecture; choose an installed Python 3.12/3.13, consult the upstream wheel support, or use a compatible Docker host. |
| macOS `enable_load_extension` missing | Recreate the virtual environment using Homebrew Python as described above; this is a Python/SQLite build issue. |
| Model unavailable locally | Run `brain model download` once with network access from an initialized project. |
| Existing `~/.local/bin/brain` belongs to another clone | Keep the intended clone and remove only its obsolete launcher, or install with a different `BRAIN_BIN_DIR`; the installer refuses to overwrite another command. |
| Clone moved or deleted | Recreate its virtual environment at the final path, repair the launcher, and rerun `brain init` in each project to refresh absolute MCP paths. Virtual environments are not portable directories. |

`brain init` creates an empty `.brain/`, `AGENTS.md`, and `.mcp.json` in the selected project and also creates `.brain/map.html`. The map needs no model download. Your memories stay in that project's directory when the terminal closes.

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
