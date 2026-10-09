#!/usr/bin/env python3
"""Persist the launcher's directory without changing unrelated shell settings."""

import argparse
import os
from pathlib import Path
import shlex
import sys

START = "# >>> Open Brain PATH >>>"
END = "# <<< Open Brain PATH <<<"


def startup_files(shell: str) -> list[Path]:
    user_home = Path.home()
    if shell == "zsh":
        directory = Path(os.environ.get("ZDOTDIR") or user_home)
        return [directory / ".zshrc", directory / ".zprofile"]
    if shell == "bash":
        login = next((user_home / name for name in (".bash_profile", ".bash_login", ".profile")
                      if (user_home / name).exists()), user_home / ".profile")
        return [user_home / ".bashrc", login]
    if shell == "fish":
        directory = Path(os.environ.get("XDG_CONFIG_HOME") or user_home / ".config")
        return [directory / "fish" / "conf.d" / "open-brain.fish"]
    return []


def add_path(profile: Path, bin_dir: Path, shell: str) -> bool:
    quoted_dir = shlex.quote(str(bin_dir))
    if shell == "fish":
        # Fish single quotes escape apostrophes with a backslash, unlike POSIX.
        fish_dir = "'" + str(bin_dir).replace("\\", "\\\\").replace("'", "\\'") + "'"
        command = f"fish_add_path --path {fish_dir}"
    else:
        pattern = shlex.quote(f":{bin_dir}:")
        command = (f'case ":$PATH:" in\n  *{pattern}*) ;;\n'
                   f'  *) export PATH={quoted_dir}:"$PATH" ;;\nesac')
    block = f"{START}\n{command}\n{END}\n"
    current = profile.read_text() if profile.exists() else ""
    if START in current or END in current:
        if current.count(START) != 1 or current.count(END) != 1 or current.index(END) < current.index(START):
            raise ValueError(f"Malformed Open Brain PATH block in {profile}; no changes made.")
        start = current.index(START)
        end = current.index(END) + len(END)
        if current[end:end + 1] == "\n":
            end += 1
        updated = current[:start] + block + current[end:]
    else:
        updated = current + ("\n" if current and not current.endswith("\n") else "") + block
    if updated == current:
        return False
    profile.parent.mkdir(parents=True, exist_ok=True)
    profile.write_text(updated)
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bin_dir", type=Path)
    parser.add_argument("--shell", default=Path(os.environ.get("SHELL", "")).name)
    parser.add_argument("--profile", type=Path, help="Use an explicit startup file instead of detecting it.")
    args = parser.parse_args()
    bin_dir = args.bin_dir.resolve()
    if args.shell not in ("bash", "zsh", "fish"):
        print(f"Shell {args.shell or '(unknown)'}: configure PATH manually for {bin_dir}.")
        return 0
    profiles = [args.profile] if args.profile else startup_files(args.shell)
    try:
        for profile in profiles:
            changed = add_path(profile, bin_dir, args.shell)
            print(f"Shell PATH {'updated' if changed else 'already configured'}: {profile}")
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
