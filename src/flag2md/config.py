"""Settings: built-in defaults, then the global config file, then ctf.yml."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from flag2md.i18n import LABELS
from flag2md.models import Ctf, read_yaml

DEFAULTS: dict[str, Any] = {
    "author": "",
    "lang": "fr",
    "frontmatter": "none",
    "writeup_file": "README.md",
    "index_file": "README.md",
    "max_output_lines": 80,
    "templates_dir": "",
}

FRONTMATTER_STYLES = ("none", "hugo", "jekyll")


class ConfigError(Exception):
    pass


def config_dir() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "flag2md"


def global_config_path() -> Path:
    return config_dir() / "config.yml"


def load_settings(ctf: Ctf | None = None) -> dict[str, Any]:
    settings = dict(DEFAULTS)
    try:
        settings.update(read_yaml(global_config_path()))
    except ValueError as exc:
        raise ConfigError(str(exc)) from exc
    if ctf is not None:
        settings.update(ctf.settings)

    if settings["frontmatter"] not in FRONTMATTER_STYLES:
        styles = ", ".join(FRONTMATTER_STYLES)
        raise ConfigError(f"frontmatter must be one of {styles}, got {settings['frontmatter']!r}")
    if settings["lang"] not in LABELS:
        raise ConfigError(f"lang must be one of {', '.join(LABELS)}, got {settings['lang']!r}")
    try:
        settings["max_output_lines"] = int(settings["max_output_lines"])
    except (TypeError, ValueError) as exc:
        raise ConfigError("max_output_lines must be an integer") from exc
    return settings


def template_dirs(settings: dict[str, Any], ctf: Ctf | None) -> list[Path]:
    """Folders searched for custom templates, before the built-in ones."""
    dirs = []
    custom = settings.get("templates_dir")
    if custom:
        path = Path(custom).expanduser()
        if not path.is_absolute() and ctf is not None and ctf.path is not None:
            path = ctf.path / path
        dirs.append(path)
    dirs.append(config_dir() / "templates")
    return dirs


def resolve_token(settings: dict[str, Any], url: str) -> str | None:
    """Look up an API token for url in the 'tokens' mapping of the global config.

    Tokens live outside the CTF folder so they never end up in a published write-up repo.
    """
    tokens = settings.get("tokens") or {}
    if not isinstance(tokens, dict):
        return None
    host = urlsplit(url).netloc
    for key in (url.rstrip("/"), host):
        if key and tokens.get(key):
            return str(tokens[key])
    return None
