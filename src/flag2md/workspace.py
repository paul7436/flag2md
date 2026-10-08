"""Locate CTF and challenge folders."""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

from flag2md.models import CHALLENGE_FILE


def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-").lower()
    return text or "unnamed"


def find_upwards(start: Path, filename: str) -> Path | None:
    """Return the closest folder, from start up to the root, that contains filename."""
    start = start.resolve()
    for folder in (start, *start.parents):
        if (folder / filename).is_file():
            return folder
    return None


def iter_challenges(ctf_root: Path) -> list[Path]:
    # Fixed depth on purpose: attachments sometimes ship their own challenge.yml.
    return sorted(path.parent for path in ctf_root.glob(f"*/*/{CHALLENGE_FILE}"))
