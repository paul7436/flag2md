from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from flag2md.models import Challenge
from flag2md.platforms import CTFd, PlatformError, RemoteFile

CHALLENGES = {
    1: {
        "id": 1,
        "name": "Baby ROP",
        "category": "Pwn",
        "value": 200,
        "solves": 12,
        "solved_by_me": False,
        "attribution": "toto",
        "description": "Exploit me.\r\n\r\nGood luck",
        "connection_info": "nc localhost 4000",
        "tags": ["rop"],
        "hints": [{"id": 1, "cost": 0, "content": "think libc"}, {"id": 2, "cost": 50}],
        "files": ["/files/abc/baby_rop?token=xyz"],
    },
    2: {
        "id": 2,
        "name": "Cookie",
        "category": "Web",
        "value": 100,
        "solves": 99,
        "solved_by_me": True,
        "description": "Eat it",
        "connection_info": None,
        "tags": [{"value": "cookie"}],
        "hints": [],
        "files": [],
    },
}


class FakeCTFd(BaseHTTPRequestHandler):
    seen: list[dict[str, str | None]] = []

    def log_message(self, *args):
        pass

    def reply(self, code: int, body, content_type: str = "application/json") -> None:
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        FakeCTFd.seen.append(
            {"path": self.path, "auth": self.headers.get("Authorization"), "cookie": self.headers.get("Cookie")}
        )
        if self.path.startswith("/external/"):
            return self.reply(200, b"external", "application/octet-stream")
        authorized = self.headers.get("Authorization") == "Token secret" or self.headers.get("Cookie") == "session=s3"
        if not authorized:
            return self.reply(302, b"", "text/html")
        if self.path == "/api/v1/challenges":
            items = [
                {"id": c["id"], "name": c["name"], "category": c["category"], "type": "standard"}
                for c in CHALLENGES.values()
            ]
            items.append({"id": 3, "name": "???", "category": "Pwn", "type": "hidden"})
            return self.reply(200, {"success": True, "data": items})
        if self.path.startswith("/api/v1/challenges/"):
            return self.reply(200, {"success": True, "data": CHALLENGES[int(self.path.rsplit("/", 1)[1])]})
        if self.path.startswith("/files/abc/baby_rop"):
            return self.reply(200, b"\x7fELF" + b"A" * 60, "application/octet-stream")
        return self.reply(404, {"success": False})


@pytest.fixture
def server():
    FakeCTFd.seen = []
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), FakeCTFd)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()
    httpd.server_close()


def test_client_parses_challenges(server: str):
    client = CTFd(server, token="secret")
    refs = client.list_challenges()
    assert [ref.name for ref in refs] == ["Baby ROP", "Cookie"]

    chal = client.get_challenge(1)
    assert chal.points == 200 and chal.author == "toto"
    assert chal.description == "Exploit me.\n\nGood luck"
    assert chal.hints == ["think libc"]
    assert chal.files == [RemoteFile(name="baby_rop", url=f"{server}/files/abc/baby_rop?token=xyz")]
    assert client.get_challenge(2).tags == ["cookie"]


def test_client_reports_denied_access(server: str):
    with pytest.raises(PlatformError, match="access denied"):
        CTFd(server, token="wrong").list_challenges()


def test_download_limits_and_credentials(server: str, tmp_path: Path):
    client = CTFd(server, token="secret")
    dest = tmp_path / "bin"
    with pytest.raises(PlatformError, match="bigger"):
        client.download(RemoteFile("bin", f"{server}/files/abc/baby_rop"), dest, max_bytes=10)
    assert not dest.exists() and not (tmp_path / "bin.part").exists()
    assert client.download(RemoteFile("bin", f"{server}/files/abc/baby_rop"), dest) == 64

    # Another origin (same host, other name) must not receive the token.
    other = server.replace("127.0.0.1", "localhost")
    client.download(RemoteFile("ext", f"{other}/external/x"), tmp_path / "ext")
    assert FakeCTFd.seen[-1]["path"] == "/external/x"
    assert FakeCTFd.seen[-1]["auth"] is None


def test_pull_command(server: str, workspace: Path, cli, monkeypatch: pytest.MonkeyPatch):
    cli("init", "Fake", "--url", server, "--dir", "fake")
    root = workspace / "fake"
    monkeypatch.chdir(root)

    result = cli("pull", code=1)
    assert "access denied" in result.output

    monkeypatch.setenv("FLAG2MD_SESSION", "s3")
    result = cli("pull")
    assert "2 challenge(s) pulled, 2 new" in result.output
    rop = root / "pwn" / "baby-rop"
    assert (rop / "files" / "baby_rop").read_bytes().startswith(b"\x7fELF")
    assert Challenge.load(root / "web" / "cookie").solved

    # Local work survives a second pull.
    (rop / "notes.md").write_text("my notes\n")
    cli("flag", "FLAG{rop}", "--chal", str(rop))
    result = cli("pull", "--category", "pwn")
    assert "1 challenge(s) pulled, 0 new" in result.output
    chal = Challenge.load(rop)
    assert chal.flag == "FLAG{rop}" and chal.solved
    assert chal.files[0].size == 64
    readme = (rop / "README.md").read_text()
    assert "my notes" in readme and "think libc" in readme
    assert "token=xyz" not in readme


def test_pull_uses_token_from_global_config(server: str, workspace: Path, cli, monkeypatch: pytest.MonkeyPatch):
    config = workspace / "config" / "flag2md"
    config.mkdir(parents=True)
    host = server.split("://", 1)[1]
    (config / "config.yml").write_text(f"tokens:\n  {host}: secret\n")
    cli("init", "Fake", "--url", server, "--dir", "fake")
    monkeypatch.chdir(workspace / "fake")
    result = cli("pull", "--no-files")
    assert "2 challenge(s) pulled" in result.output
    assert not (workspace / "fake" / "pwn" / "baby-rop" / "files").exists()
    assert "***" in cli("config").output
