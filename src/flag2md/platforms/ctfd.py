"""CTFd REST API client (api/v1)."""

from __future__ import annotations

from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import unquote, urljoin, urlsplit

import requests

from flag2md import __version__
from flag2md.platforms.base import ChallengeRef, Platform, PlatformError, RemoteChallenge, RemoteFile


def _file_name(url: str) -> str:
    name = PurePosixPath(unquote(urlsplit(url).path)).name
    return name if name not in ("", ".", "..") else "file"


def _int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


class CTFd(Platform):
    name = "ctfd"

    def __init__(
        self,
        url: str,
        token: str | None = None,
        session: str | None = None,
        timeout: float = 30,
        http: requests.Session | None = None,
        anon: requests.Session | None = None,
    ) -> None:
        self.base = url.rstrip("/") + "/"
        self.timeout = timeout
        self.http = http or requests.Session()
        self.http.headers["User-Agent"] = f"flag2md/{__version__}"
        if token:
            # CTFd only accepts token auth together with a JSON content type.
            self.http.headers["Authorization"] = f"Token {token}"
            self.http.headers["Content-Type"] = "application/json"
        if session:
            host = urlsplit(self.base).hostname or ""
            # The cookie is bound to the CTF host so a redirect elsewhere never carries it.
            # http.cookiejar matches dotless hosts (localhost) as "<host>.local".
            self.http.cookies.set("session", session, domain=host if "." in host else f"{host}.local")
        # Attachments hosted elsewhere (S3, CDN) must not receive our credentials.
        self.anon = anon or requests.Session()
        self.anon.headers["User-Agent"] = f"flag2md/{__version__}"

    def _same_origin(self, url: str) -> bool:
        target, base = urlsplit(url), urlsplit(self.base)
        return (target.scheme, target.netloc) == (base.scheme, base.netloc)

    def _get(self, path: str) -> Any:
        url = urljoin(self.base, path)
        try:
            resp = self.http.get(url, timeout=self.timeout, allow_redirects=False)
        except requests.RequestException as exc:
            raise PlatformError(f"cannot reach {url}: {exc}") from exc
        if resp.status_code in (301, 302, 303, 307, 308, 401, 403):
            raise PlatformError(f"access denied on {url} (HTTP {resp.status_code}), check your token or session")
        if resp.status_code == 404:
            raise PlatformError(f"not found: {url}")
        if resp.status_code >= 400:
            raise PlatformError(f"HTTP {resp.status_code} on {url}")
        try:
            payload = resp.json()
        except ValueError as exc:
            raise PlatformError(f"{url} did not answer with JSON, is it a CTFd instance?") from exc
        if not isinstance(payload, dict) or not payload.get("success", False):
            raise PlatformError(f"unexpected answer from {url}")
        return payload.get("data")

    def list_challenges(self) -> list[ChallengeRef]:
        data = self._get("api/v1/challenges") or []
        refs = []
        for item in data:
            # Locked challenges (unmet prerequisites) are listed as "hidden" with no details.
            if item.get("type") == "hidden":
                continue
            name, category = str(item.get("name", "")), str(item.get("category", ""))
            refs.append(ChallengeRef(id=item["id"], name=name, category=category))
        return refs

    def get_challenge(self, challenge_id: int | str) -> RemoteChallenge:
        data = self._get(f"api/v1/challenges/{challenge_id}") or {}
        tags = []
        for tag in data.get("tags") or []:
            value = tag.get("value") if isinstance(tag, dict) else tag
            if value:
                tags.append(str(value))
        hints = []
        for hint in data.get("hints") or []:
            # Paid hints that were not unlocked come without content.
            content = hint.get("content") if isinstance(hint, dict) else hint
            if content:
                hints.append(str(content).strip())
        files = [RemoteFile(name=_file_name(url), url=urljoin(self.base, url)) for url in data.get("files") or []]
        return RemoteChallenge(
            id=data.get("id", challenge_id),
            name=str(data.get("name", "")),
            category=str(data.get("category", "")) or "misc",
            points=_int(data.get("value")),
            solves=_int(data.get("solves")),
            author=str(data.get("attribution") or ""),
            description=str(data.get("description") or "").replace("\r\n", "\n").strip(),
            connection_info=str(data.get("connection_info") or "").strip(),
            tags=tags,
            hints=hints,
            files=files,
            solved=bool(data.get("solved_by_me")),
        )

    def download(self, remote: RemoteFile, dest: Path, max_bytes: int = 0) -> int:
        client = self.http if self._same_origin(remote.url) else self.anon
        partial = dest.with_name(dest.name + ".part")
        size = 0
        try:
            with client.get(remote.url, stream=True, timeout=self.timeout) as resp:
                if resp.status_code >= 400:
                    raise PlatformError(f"HTTP {resp.status_code} while downloading {remote.name}")
                with partial.open("wb") as fh:
                    for chunk in resp.iter_content(1 << 16):
                        size += len(chunk)
                        if max_bytes and size > max_bytes:
                            limit = max_bytes // (1024 * 1024)
                            raise PlatformError(f"{remote.name} is bigger than {limit} MB, skipped")
                        fh.write(chunk)
        except requests.RequestException as exc:
            partial.unlink(missing_ok=True)
            raise PlatformError(f"download of {remote.name} failed: {exc}") from exc
        except PlatformError:
            partial.unlink(missing_ok=True)
            raise
        partial.replace(dest)
        return size
