"""MCP stdio server. Every line is one JSON-RPC 2.0 message.

Standalone projects use the local ``.brain/``; linked projects (``brain link``) use the
Brain service with the local mirror as offline fallback. Tools come from
``second_brain.mcp_tools`` so stdio and HTTP expose the same contract.
"""

import json
import sys
from pathlib import Path

from . import mcp_tools

from .config import load_config
from .core import (AGENT_INSTRUCTIONS, BOOTSTRAP_INSTRUCTIONS, BOOTSTRAP_MARKER, CONTEXT_UPDATE_INSTRUCTIONS,
                   CONTEXT_UPDATE_MARKER, COVERAGE_MARKER, DETAIL_INSTRUCTIONS, DETAIL_MARKER,
                   PROJECT_COVERAGE_INSTRUCTIONS)
from .remote import backend_for, remote_settings

LOCAL_ONLY_EXCLUDED = {"brain_relate"}


def instructions_for(root: Path) -> str:
    path = root / ".brain" / "AGENT_BRAIN.md"
    instructions = path.read_text(encoding="utf-8") if path.exists() else AGENT_INSTRUCTIONS
    for marker, section in ((BOOTSTRAP_MARKER, BOOTSTRAP_INSTRUCTIONS),
                            (CONTEXT_UPDATE_MARKER, CONTEXT_UPDATE_INSTRUCTIONS),
                            (COVERAGE_MARKER, PROJECT_COVERAGE_INSTRUCTIONS), (DETAIL_MARKER, DETAIL_INSTRUCTIONS)):
        if marker not in instructions:
            instructions = instructions.rstrip("\n") + "\n\n" + section
    return instructions


def serve(root: Path) -> None:
    root = root.resolve()
    load_config(root)
    linked = remote_settings(root)
    backend = backend_for(root, source="mcp")
    instructions = instructions_for(root)
    tools = mcp_tools.TOOLS
    if linked:
        instructions += "\n\n" + mcp_tools.SERVER_INSTRUCTIONS
    else:
        tools = [tool for tool in tools if tool["name"] not in LOCAL_ONLY_EXCLUDED]
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            message = json.loads(line)
        except ValueError as exc:
            print(f"MCP input error: {exc}", file=sys.stderr)
            continue
        response = mcp_tools.handle(message, backend, instructions=instructions, server_name="second-brain-local",
                                    tools=tools)
        if response is not None:
            sys.stdout.write(json.dumps(response, ensure_ascii=False, default=str) + "\n")
            sys.stdout.flush()
