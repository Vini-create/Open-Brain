#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Install Open Brain once, then run brain from any project directory.

Usage: ./scripts/install.sh [--skip-model]

The installer creates .venv in this clone and links its brain command into
${BRAIN_BIN_DIR:-$HOME/.local/bin}. It downloads the public embedding model
unless --skip-model is given. Set BRAIN_PYTHON to choose a Python executable.
EOF
}

skip_model=0
case "${1:-}" in
  "") ;;
  --skip-model) skip_model=1 ;;
  -h|--help) usage; exit 0 ;;
  *) usage >&2; exit 2 ;;
esac
if (( $# > 1 )); then
  usage >&2
  exit 2
fi

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
python_cmd="${BRAIN_PYTHON:-python3}"
bin_dir="${BRAIN_BIN_DIR:-$HOME/.local/bin}"

if ! command -v "$python_cmd" >/dev/null 2>&1; then
  echo "Python executable not found: $python_cmd" >&2
  exit 1
fi
if ! "$python_cmd" -c 'import sys; sys.exit(sys.version_info < (3, 10))'; then
  echo "Open Brain requires Python 3.10 or newer." >&2
  exit 1
fi

if [[ ! -x "$repo_dir/.venv/bin/python" ]]; then
  "$python_cmd" -m venv "$repo_dir/.venv"
fi
venv_python="$repo_dir/.venv/bin/python"
if [[ "$(uname -s)" == Linux ]] && ! "$venv_python" -c 'import torch' >/dev/null 2>&1; then
  "$venv_python" -m pip install torch --index-url https://download.pytorch.org/whl/cpu
fi
"$venv_python" -m pip install -e "$repo_dir"

if (( ! skip_model )); then
  "$venv_python" -c 'from second_brain.config import DEFAULT_CONFIG; from second_brain.embedding import download_model; download_model(DEFAULT_CONFIG["embedding"]["model"])'
fi

mkdir -p "$bin_dir"
bin_dir="$(cd "$bin_dir" && pwd -P)"
launcher="$repo_dir/.venv/bin/brain"
link="$bin_dir/brain"
if [[ -e "$link" || -L "$link" ]]; then
  if [[ ! -L "$link" || "$(readlink "$link")" != "$launcher" ]]; then
    echo "Cannot install $link: it already exists and is not this Open Brain launcher." >&2
    exit 1
  fi
else
  ln -s "$launcher" "$link"
fi

echo "Open Brain installed: $link"
if (( skip_model )); then
  echo "Model download skipped. In a project, run 'brain init' then 'brain model download' before indexing or searching."
fi
case ":$PATH:" in
  *":$bin_dir:"*) ;;
  *) echo "Add the command to this terminal: export PATH=\"$bin_dir:\$PATH\"" ;;
esac
echo "Next: cd /path/to/your-project && $link init"
echo "Once $bin_dir is on PATH, use 'brain init' from any project directory."
