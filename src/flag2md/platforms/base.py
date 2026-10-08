"""Common interface for the platforms challenges can be pulled from."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path


class PlatformError(Exception):
    pass


@dataclass
class ChallengeRef:
    id: int | str
    name: str
    category: str


@dataclass
class RemoteFile:
    name: str
    url: str


@dataclass
class RemoteChallenge:
    id: int | str
    name: str
    category: str
    points: int | None = None
    solves: int | None = None
    author: str = ""
    description: str = ""
    connection_info: str = ""
    tags: list[str] = field(default_factory=list)
    hints: list[str] = field(default_factory=list)
    files: list[RemoteFile] = field(default_factory=list)
    solved: bool = False


class Platform(ABC):
    name: str = ""

    @abstractmethod
    def list_challenges(self) -> list[ChallengeRef]:
        """Every challenge visible to the current user."""

    @abstractmethod
    def get_challenge(self, challenge_id: int | str) -> RemoteChallenge:
        """Full details of one challenge."""

    @abstractmethod
    def download(self, remote: RemoteFile, dest: Path, max_bytes: int = 0) -> int:
        """Save an attachment to dest and return its size. max_bytes=0 means no limit."""
