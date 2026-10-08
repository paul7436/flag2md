"""Append steps (notes, commands, files) to a challenge notes.md while solving."""

from __future__ import annotations

import re
import shutil
from pathlib import Path
from urllib.parse import quote

INCLUDE_PREFIX = "<!-- flag2md:include "
INCLUDE_RE = re.compile(r"^<!-- flag2md:include (.+?) -->[ \t]*$", re.MULTILINE)

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".bmp"}
MAX_INCLUDE_BYTES = 200_000

_ANSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)|\x1b[@-Z\\-_]")


def strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text)


def fence_for(text: str) -> str:
    """A backtick fence longer than any fence already inside text."""
    longest = max((len(run) for run in re.findall(r"`{3,}", text)), default=0)
    return "`" * max(3, longest + 1)


def clean_output(output: str, max_lines: int) -> list[str]:
    text = strip_ansi(output).replace("\r\n", "\n")
    # Progress bars redraw the line with \r, only the last state is worth keeping.
    lines = [line.split("\r")[-1].rstrip() for line in text.rstrip("\n").split("\n")]
    while lines and not lines[0]:
        lines.pop(0)
    if not lines or max_lines <= 0 or len(lines) <= max_lines:
        return lines
    head = max_lines // 2
    tail = max_lines - head
    skipped = len(lines) - max_lines
    return [*lines[:head], f"[... {skipped} lines truncated ...]", *lines[-tail:]]


def append(notes: Path, block: str) -> None:
    current = notes.read_text(encoding="utf-8") if notes.exists() else ""
    if not current or current.endswith("\n\n"):
        separator = ""
    elif current.endswith("\n"):
        separator = "\n"
    else:
        separator = "\n\n"
    with notes.open("a", encoding="utf-8") as fh:
        fh.write(separator + block.strip("\n") + "\n")


def add_note(notes: Path, text: str) -> None:
    append(notes, text.strip())


def add_command(notes: Path, command: str, output: str, exit_code: int, max_lines: int) -> None:
    body = "\n".join([f"$ {command}", *clean_output(output, max_lines)])
    if exit_code:
        body += f"\n[exit {exit_code}]"
    fence = fence_for(body)
    append(notes, f"{fence}console\n{body}\n{fence}")


def is_image(path: Path) -> bool:
    return path.suffix.lower() in IMAGE_EXTENSIONS


def is_text(path: Path) -> bool:
    with path.open("rb") as fh:
        head = fh.read(8192)
    return b"\0" not in head


def add_file(challenge_dir: Path, notes: Path, source: Path, subdir: str | None = None, caption: str = "") -> Path:
    """Copy source into the challenge folder (unless it is already inside) and reference it in notes.

    Images are embedded, text files get an include marker that build replaces with the
    file content at build time, so the write-up always shows the latest version.
    """
    source = source.resolve()
    root = challenge_dir.resolve()
    if source.is_relative_to(root) and subdir is None:
        target = source
    else:
        folder = subdir or ("assets" if is_image(source) else "solve")
        target = root / folder / source.name
        target.parent.mkdir(parents=True, exist_ok=True)
        if target != source:
            shutil.copy2(source, target)

    relative = target.relative_to(root).as_posix()
    current = notes.read_text(encoding="utf-8") if notes.exists() else ""

    if is_image(target):
        reference = f"![{caption or target.stem}]({quote(relative)})"
    elif is_text(target) and target.stat().st_size <= MAX_INCLUDE_BYTES:
        reference = f"{INCLUDE_PREFIX}{relative} -->"
    else:
        reference = f"[{target.name}]({quote(relative)})"

    if reference not in current:
        append(notes, reference)
    return target
