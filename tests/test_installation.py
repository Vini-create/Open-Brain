"""Check that persisted PATH works across shells and repeated setup is safe."""

from pathlib import Path
import shutil
import subprocess
import sys

import pytest


SETUP = Path(__file__).resolve().parents[1] / "scripts" / "setup-shell-path.py"


@pytest.mark.parametrize("shell", ["bash", "zsh", "fish"])
def test_new_shell_finds_launcher_and_setup_preserves_profile(tmp_path, shell):
    executable = shutil.which(shell)
    if executable is None:
        pytest.skip(f"{shell} is not installed")
    bin_dir = tmp_path / "command's directory with spaces"
    bin_dir.mkdir()
    launcher = bin_dir / "brain"
    launcher.write_text("#!/bin/sh\nprintf 'Brain launcher works\\n'\n")
    launcher.chmod(0o755)
    profile = tmp_path / "profile"
    original = "# Existing user settings\n"
    profile.write_text(original)
    command = [sys.executable, str(SETUP), str(bin_dir), "--shell", shell, "--profile", str(profile)]
    subprocess.run(command, check=True, capture_output=True)
    first_setup = profile.read_text()
    assert first_setup.startswith(original)
    subprocess.run(command, check=True, capture_output=True)
    assert profile.read_text() == first_setup
    # Start without the launcher directory in PATH, as a separate IDE terminal does.
    if shell == "fish":
        invocation = 'set -gx PATH /usr/bin /bin; source "$argv[1]"; brain'
        args = [executable, "-c", invocation, str(profile)]
    else:
        invocation = 'PATH=/usr/bin:/bin; . "$1"; brain'
        args = [executable, "-c", invocation, "test-shell", str(profile)]
    result = subprocess.run(args, check=True, capture_output=True, text=True)
    assert result.stdout.strip() == "Brain launcher works"


def test_malformed_block_preserves_user_profile(tmp_path):
    profile = tmp_path / "profile"
    original = "# Existing settings\n# >>> Open Brain PATH >>>\nunfinished\n"
    profile.write_text(original)
    result = subprocess.run(
        [sys.executable, str(SETUP), str(tmp_path), "--shell", "zsh", "--profile", str(profile)],
        capture_output=True, text=True,
    )
    assert result.returncode == 1
    assert profile.read_text() == original
