"""Render write-ups and CTF indexes from Jinja2 templates."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import quote

from jinja2 import ChoiceLoader, Environment, FileSystemLoader, PackageLoader, StrictUndefined

from flag2md.config import template_dirs
from flag2md.i18n import LABELS
from flag2md.journal import INCLUDE_RE, MAX_INCLUDE_BYTES, fence_for
from flag2md.models import NOTES_FILE, Challenge, Ctf, dump_yaml, sha256_of
from flag2md.workspace import iter_challenges

CODE_LANGUAGES = {
    ".asm": "nasm",
    ".c": "c",
    ".cpp": "cpp",
    ".cs": "csharp",
    ".go": "go",
    ".h": "c",
    ".html": "html",
    ".java": "java",
    ".js": "javascript",
    ".json": "json",
    ".lua": "lua",
    ".md": "markdown",
    ".php": "php",
    ".ps1": "powershell",
    ".py": "python",
    ".rb": "ruby",
    ".rs": "rust",
    ".s": "asm",
    ".sage": "python",
    ".sh": "bash",
    ".sql": "sql",
    ".ts": "typescript",
    ".yaml": "yaml",
    ".yml": "yaml",
}


def _quote_block(text: str) -> str:
    return "\n".join(f"> {line}" if line.strip() else ">" for line in text.splitlines())


def _table_cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _code(value: Any) -> str:
    return f"`{value}`"


def human_size(size: int | None) -> str:
    if size is None:
        return "-"
    value = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{int(value)} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{size} B"


def make_env(search_dirs: list[Path]) -> Environment:
    loaders: list[Any] = [FileSystemLoader(str(path)) for path in search_dirs if path.is_dir()]
    loaders.append(PackageLoader("flag2md", "templates"))
    env = Environment(
        loader=ChoiceLoader(loaders),
        autoescape=False,
        keep_trailing_newline=True,
        trim_blocks=True,
        lstrip_blocks=True,
        undefined=StrictUndefined,
    )
    env.filters["quote_block"] = _quote_block
    env.filters["cell"] = _table_cell
    env.filters["code"] = _code
    env.filters["human_size"] = human_size
    return env


def expand_includes(notes: str, base: Path) -> tuple[str, list[str]]:
    """Replace include markers with the current content of the referenced files."""
    missing: list[str] = []

    def replace(match: Any) -> str:
        relative = match.group(1).strip()
        path = base / relative
        if not path.is_file():
            missing.append(relative)
            return match.group(0)
        if path.stat().st_size > MAX_INCLUDE_BYTES:
            return f"[{path.name}]({quote(relative)})"
        content = path.read_text(encoding="utf-8", errors="replace").rstrip("\n")
        fence = fence_for(content)
        language = CODE_LANGUAGES.get(path.suffix.lower(), "")
        return f"`{relative}`\n\n{fence}{language}\n{content}\n{fence}"

    return INCLUDE_RE.sub(replace, notes), missing


def collect_files(folder: Path, chal: Challenge) -> list[dict[str, Any]]:
    """Attachments found in files/, plus the ones listed in challenge.yml but not downloaded."""
    entries: list[dict[str, Any]] = []
    seen: set[str] = set()
    files_dir = folder / "files"
    if files_dir.is_dir():
        for path in sorted(files_dir.iterdir()):
            if not path.is_file() or path.name.startswith(".") or path.name.endswith(".part"):
                continue
            entries.append(
                {
                    "name": path.name,
                    "size": path.stat().st_size,
                    "sha256": sha256_of(path),
                    "link": f"files/{quote(path.name)}",
                }
            )
            seen.add(path.name)
    for item in chal.files:
        if item.name and item.name not in seen:
            entries.append({"name": item.name, "size": item.size, "sha256": item.sha256, "link": None})
    return entries


def front_matter(style: str, title: str, when: str, tags: list[str], categories: list[str], author: str) -> str:
    if style == "none":
        return ""
    data: dict[str, Any] = {}
    if style == "jekyll":
        data["layout"] = "post"
    data["title"] = title
    data["date"] = when
    if author:
        data["author"] = author
    if categories:
        data["categories"] = categories
    if tags:
        data["tags"] = tags
    if style == "hugo":
        data["draft"] = False
    return f"---\n{dump_yaml(data)}---\n\n"


def _unique(values: list[str]) -> list[str]:
    seen: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.append(value)
    return seen


def _finish(text: str) -> str:
    return text.rstrip("\n") + "\n"


def build_challenge(folder: Path, ctf: Ctf | None, settings: dict[str, Any]) -> tuple[Path, list[str]]:
    """Render the write-up of one challenge. Returns the output path and missing include targets."""
    chal = Challenge.load(folder)
    notes_path = folder / NOTES_FILE
    notes = notes_path.read_text(encoding="utf-8").strip() if notes_path.exists() else ""
    notes, missing = expand_includes(notes, folder)

    when = chal.solved_at or (ctf.start if ctf else "") or date.today().isoformat()
    fm = front_matter(
        settings["frontmatter"],
        title=f"{ctf.name}: {chal.name}" if ctf else chal.name,
        when=when,
        tags=_unique([chal.category.lower(), *chal.tags]),
        categories=[ctf.name] if ctf else [],
        author=settings["author"],
    )

    env = make_env(template_dirs(settings, ctf))
    text = env.get_template("writeup.md.j2").render(
        chal=chal,
        ctf=ctf,
        notes=notes,
        files=collect_files(folder, chal),
        front_matter=fm,
        L=LABELS[settings["lang"]],
        settings=settings,
    )
    output = folder / settings["writeup_file"]
    output.write_text(_finish(text), encoding="utf-8")
    return output, missing


def build_index(ctf: Ctf, settings: dict[str, Any]) -> Path:
    assert ctf.path is not None
    challenges = [Challenge.load(folder) for folder in iter_challenges(ctf.path)]

    groups: dict[str, dict[str, Any]] = {}
    for chal in sorted(challenges, key=lambda c: (c.category.lower(), c.name.lower())):
        assert chal.path is not None
        key = chal.category.lower()
        group = groups.setdefault(key, {"category": chal.category, "challenges": []})
        link = chal.path.relative_to(ctf.path).as_posix() + "/" + settings["writeup_file"]
        group["challenges"].append(
            {"name": chal.name, "points": chal.points, "solved": chal.solved, "link": quote(link)}
        )

    solved = [chal for chal in challenges if chal.solved]
    dates = " / ".join(value for value in (ctf.start, ctf.end) if value) or "-"
    fm = front_matter(
        settings["frontmatter"],
        title=ctf.name,
        when=ctf.start or date.today().isoformat(),
        tags=[],
        categories=[],
        author=settings["author"],
    )

    env = make_env(template_dirs(settings, ctf))
    text = env.get_template("index.md.j2").render(
        ctf=ctf,
        groups=list(groups.values()),
        total=len(challenges),
        solved=len(solved),
        points=sum(chal.points or 0 for chal in solved),
        dates=dates,
        front_matter=fm,
        L=LABELS[settings["lang"]],
        settings=settings,
    )
    output = ctf.path / settings["index_file"]
    output.write_text(_finish(text), encoding="utf-8")
    return output
