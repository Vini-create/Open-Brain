"""Structure-aware Markdown chunking for knowledge-base documents.

Sections follow headings; code fences are never split across chunks unless a single
fence alone exceeds the limit. Each chunk keeps its heading path, which is prepended to
the embedded text so that retrieval sees *where* a passage lives in the document.
"""

import re
from dataclasses import dataclass, field

HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
FENCE = re.compile(r"^\s*(```|~~~)")
MODULE_FILE = re.compile(r"\b(\d{2})_[A-Z0-9_]+\.md\b")
MODULE_MENTION = re.compile(r"\b[Mm][oó]dulos?\s+(\d{2})\b")


@dataclass
class Section:
    level: int
    heading_path: list[str]
    anchor: str
    text: str


@dataclass
class Chunk:
    ordinal: int
    heading_path: list[str]
    anchor: str
    text: str
    has_code: bool = False
    meta: dict = field(default_factory=dict)

    @property
    def path_label(self) -> str:
        return " › ".join(self.heading_path)


def anchor(heading: str) -> str:
    """GitHub-style anchor: lowercase, punctuation removed, spaces become hyphens."""
    text = re.sub(r"[`*_~\[\]()]", "", heading.strip().lower())
    text = re.sub(r"[^\w\- ]", "", text, flags=re.UNICODE)
    return re.sub(r" ", "-", text)


def sections(markdown: str) -> list[Section]:
    result: list[Section] = []
    stack: list[tuple[int, str]] = []
    buffer: list[str] = []
    in_fence = False
    current_level, current_anchor = 0, ""

    def flush():
        text = "\n".join(buffer).strip()
        if text:
            result.append(Section(current_level, [title for _, title in stack], current_anchor, text))
        buffer.clear()

    for line in markdown.splitlines():
        if FENCE.match(line):
            in_fence = not in_fence
            buffer.append(line)
            continue
        match = None if in_fence else HEADING.match(line)
        if match:
            flush()
            level, title = len(match.group(1)), match.group(2).strip()
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, title))
            current_level, current_anchor = level, anchor(title)
            continue
        buffer.append(line)
    flush()
    return result


def _blocks(text: str) -> list[str]:
    """Paragraphs and whole code fences, in order."""
    blocks, current, in_fence = [], [], False
    for line in text.splitlines():
        if FENCE.match(line):
            if not in_fence and current:
                blocks.append("\n".join(current))
                current = []
            current.append(line)
            in_fence = not in_fence
            if not in_fence:
                blocks.append("\n".join(current))
                current = []
            continue
        if not in_fence and not line.strip():
            if current:
                blocks.append("\n".join(current))
                current = []
            continue
        current.append(line)
    if current:
        blocks.append("\n".join(current))
    return [block for block in blocks if block.strip()]


def _split_long(block: str, max_chars: int) -> list[str]:
    from second_brain.documents import chunks as sentence_chunks

    return sentence_chunks(block, max_chars=max_chars, overlap=0)


def _tail(text: str, overlap: int) -> str:
    if overlap <= 0 or len(text) <= overlap:
        return ""
    window = text[-overlap:]
    boundary = re.search(r"(?<=[.!?])\s+", window)
    return window[boundary.end():].strip() if boundary else ""


def chunk_markdown(markdown: str, max_chars: int = 1400, overlap: int = 160,
                   min_section_chars: int = 160) -> list[Chunk]:
    chunks: list[Chunk] = []
    pending_prefix = ""
    for section in sections(markdown):
        text = section.text
        if pending_prefix:
            text = pending_prefix + "\n\n" + text
            pending_prefix = ""
        # A heading with a single short line reads better merged into its first child.
        if len(text) < min_section_chars and not FENCE.search(text):
            pending_prefix = (section.heading_path[-1] + ": " if section.heading_path else "") + text
            continue
        current = ""
        for block in _blocks(text):
            pieces = [block] if len(block) <= max_chars else _split_long(block, max_chars)
            for piece in pieces:
                if current and len(current) + len(piece) + 2 > max_chars:
                    chunks.append(Chunk(len(chunks), section.heading_path, section.anchor, current.strip(),
                                        "```" in current or "~~~" in current))
                    tail = _tail(current, overlap) if not FENCE.match(piece) else ""
                    current = (tail + "\n\n" if tail else "") + piece
                else:
                    current = (current + "\n\n" + piece) if current else piece
        if current.strip():
            chunks.append(Chunk(len(chunks), section.heading_path, section.anchor, current.strip(),
                                "```" in current or "~~~" in current))
    if pending_prefix:
        chunks.append(Chunk(len(chunks), [], "", pending_prefix.strip()))
    return chunks


def module_references(markdown: str) -> dict[str, int]:
    """Count references to other modules (``09_RAG_X.md`` or "módulo 09")."""
    counts: dict[str, int] = {}
    for pattern in (MODULE_FILE, MODULE_MENTION):
        for match in pattern.finditer(markdown):
            counts[match.group(1)] = counts.get(match.group(1), 0) + 1
    return counts


def document_title(markdown: str, fallback: str) -> str:
    for line in markdown.splitlines()[:30]:
        match = HEADING.match(line)
        if match and len(match.group(1)) == 1:
            title = match.group(2).strip()
            return re.sub(r"\.md$", "", title)
    return fallback
