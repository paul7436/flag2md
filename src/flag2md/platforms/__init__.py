"""Platforms challenges can be pulled from."""

from __future__ import annotations

from typing import Any

from flag2md.platforms.base import ChallengeRef, Platform, PlatformError, RemoteChallenge, RemoteFile
from flag2md.platforms.ctfd import CTFd

PLATFORMS: dict[str, type[Platform]] = {
    "ctfd": CTFd,
}


def get_platform(name: str, url: str, **auth: Any) -> Platform:
    try:
        cls = PLATFORMS[name.lower()]
    except KeyError:
        raise PlatformError(f"unsupported platform {name!r} (available: {', '.join(PLATFORMS)})") from None
    return cls(url, **auth)


__all__ = [
    "PLATFORMS",
    "ChallengeRef",
    "Platform",
    "PlatformError",
    "RemoteChallenge",
    "RemoteFile",
    "get_platform",
]
