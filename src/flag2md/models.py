"""On-disk data: ctf.yml, challenge.yml and the YAML helpers around them."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

CTF_FILE = "ctf.yml"
CHALLENGE_FILE = "challenge.yml"
NOTES_FILE = "notes.md"

SOLVED = "solved"
TODO = "todo"


class _Dumper(yaml.SafeDumper):
    pass


def _represent_str(dumper: yaml.SafeDumper, value: str) -> yaml.ScalarNode:
    # Multi-line strings (descriptions) stay readable as literal blocks.
    style = "|" if "\n" in value else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", value, style=style)


_Dumper.add_representer(str, _represent_str)


def dump_yaml(data: Any) -> str:
    return yaml.dump(data, Dumper=_Dumper, sort_keys=False, allow_unicode=True, default_flow_style=False)


def read_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected a mapping at the top level")
    return data


def write_yaml(path: Path, data: Any) -> None:
    path.write_text(dump_yaml(data), encoding="utf-8")


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _str(value: Any) -> str:
    return "" if value is None else str(value)


def _int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _str_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (str, int, float)):
        return [str(value)]
    return [str(item) for item in value if item is not None and str(item) != ""]


@dataclass
class FileInfo:
    name: str
    sha256: str = ""
    size: int | None = None

    @classmethod
    def from_any(cls, value: Any) -> FileInfo:
        if isinstance(value, dict):
            return cls(name=_str(value.get("name")), sha256=_str(value.get("sha256")), size=_int(value.get("size")))
        return cls(name=_str(value))

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "sha256": self.sha256, "size": self.size}


@dataclass
class Ctf:
    name: str
    url: str = ""
    platform: str = ""
    team: str = ""
    start: str = ""
    end: str = ""
    settings: dict[str, Any] = field(default_factory=dict)
    path: Path | None = field(default=None, compare=False, repr=False)

    @classmethod
    def load(cls, folder: Path) -> Ctf:
        data = read_yaml(folder / CTF_FILE)
        settings = data.get("settings") or {}
        if not isinstance(settings, dict):
            raise ValueError(f"{folder / CTF_FILE}: 'settings' must be a mapping")
        return cls(
            name=_str(data.get("name")) or folder.name,
            url=_str(data.get("url")),
            platform=_str(data.get("platform")),
            team=_str(data.get("team")),
            start=_str(data.get("start")),
            end=_str(data.get("end")),
            settings=settings,
            path=folder,
        )

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "name": self.name,
            "url": self.url,
            "platform": self.platform,
            "team": self.team,
            "start": self.start,
            "end": self.end,
        }
        if self.settings:
            data["settings"] = self.settings
        return data

    def save(self) -> None:
        assert self.path is not None
        write_yaml(self.path / CTF_FILE, self.to_dict())


@dataclass
class Challenge:
    name: str
    category: str = "misc"
    points: int | None = None
    solves: int | None = None
    author: str = ""
    description: str = ""
    connection_info: str = ""
    tags: list[str] = field(default_factory=list)
    hints: list[str] = field(default_factory=list)
    files: list[FileInfo] = field(default_factory=list)
    status: str = TODO
    flag: str = ""
    solved_at: str = ""
    source: dict[str, Any] = field(default_factory=dict)
    path: Path | None = field(default=None, compare=False, repr=False)

    @property
    def solved(self) -> bool:
        return self.status == SOLVED

    @classmethod
    def load(cls, folder: Path) -> Challenge:
        data = read_yaml(folder / CHALLENGE_FILE)
        source = data.get("source") or {}
        return cls(
            name=_str(data.get("name")) or folder.name,
            category=_str(data.get("category")) or "misc",
            points=_int(data.get("points")),
            solves=_int(data.get("solves")),
            author=_str(data.get("author")),
            description=_str(data.get("description")).strip("\n"),
            connection_info=_str(data.get("connection_info")).strip(),
            tags=_str_list(data.get("tags")),
            hints=_str_list(data.get("hints")),
            files=[FileInfo.from_any(item) for item in data.get("files") or []],
            status=_str(data.get("status")) or TODO,
            flag=_str(data.get("flag")),
            solved_at=_str(data.get("solved_at")),
            source=source if isinstance(source, dict) else {},
            path=folder,
        )

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "name": self.name,
            "category": self.category,
            "points": self.points,
            "solves": self.solves,
            "author": self.author,
            "description": self.description,
            "connection_info": self.connection_info,
            "tags": self.tags,
            "hints": self.hints,
            "files": [item.to_dict() for item in self.files],
            "status": self.status,
            "flag": self.flag,
            "solved_at": self.solved_at,
        }
        if self.source:
            data["source"] = self.source
        return data

    def save(self) -> None:
        assert self.path is not None
        self.path.mkdir(parents=True, exist_ok=True)
        write_yaml(self.path / CHALLENGE_FILE, self.to_dict())
