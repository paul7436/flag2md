from __future__ import annotations

import shlex
import sys
from pathlib import Path

import pytest

from flag2md.models import Challenge, Ctf


def test_full_session(workspace: Path, cli, monkeypatch: pytest.MonkeyPatch):
    cli("init", "Hero CTF 2026", "--team", "us", "--start", "2026-06-01")
    ctf_root = workspace / "hero-ctf-2026"
    assert Ctf.load(ctf_root).team == "us"

    monkeypatch.chdir(ctf_root)
    cli("new", "Baby ROP", "-c", "pwn", "-p", "250", "-t", "rop", "-n", "nc host 1")
    chal_dir = ctf_root / "pwn" / "baby-rop"
    assert (chal_dir / "notes.md").read_text() == ""
    cli("new", "Baby ROP", "-c", "pwn", code=1)

    monkeypatch.chdir(chal_dir)
    result = cli("run", sys.executable, "-c", "print('hello')")
    assert "hello" in result.output
    cli("run", f"{shlex.quote(sys.executable)} -c 'import sys; sys.exit(3)'", code=3)
    cli("note", "first", "idea")
    cli("note", input="from stdin\n")
    script = workspace / "solve.py"
    script.write_text("print('pwned')\n")
    cli("add", str(script))
    cli("flag", "HERO{ok}")
    cli("build")

    readme = (chal_dir / "README.md").read_text()
    assert f"$ {sys.executable} -c 'print('\"'\"'hello'\"'\"')'\nhello\n" in readme
    assert "[exit 3]" in readme
    assert "first idea\n\nfrom stdin\n" in readme
    assert "```python\nprint('pwned')\n```" in readme
    assert "```text\nHERO{ok}\n```" in readme

    challenge = Challenge.load(chal_dir)
    assert challenge.solved and challenge.solved_at

    index = (ctf_root / "README.md").read_text()
    assert "- [x] [Baby ROP](pwn/baby-rop/README.md) (250 pts)" in index

    monkeypatch.chdir(ctf_root)
    result = cli("ls")
    assert "[x] pwn/baby-rop    250  Baby ROP" in result.output
    assert "1/1 solved, 250 pts" in result.output


def test_build_all_from_ctf_root(workspace: Path, cli, monkeypatch: pytest.MonkeyPatch):
    cli("init", "Demo", "--dir", "demo")
    monkeypatch.chdir(workspace / "demo")
    cli("new", "One", "-c", "web")
    cli("new", "Two", "-c", "crypto")
    result = cli("build")
    assert "web/one/README.md" in result.output
    assert "crypto/two/README.md" in result.output
    assert (workspace / "demo" / "README.md").is_file()


def test_commands_outside_a_challenge_fail(workspace: Path, cli):
    assert "flag2md init" in cli("new", "x", code=1).output
    assert "flag2md new" in cli("note", "x", code=1).output
    cli("build", code=1)


def test_run_unknown_command(workspace: Path, cli, monkeypatch: pytest.MonkeyPatch):
    cli("init", "Demo", "--dir", "demo")
    monkeypatch.chdir(workspace / "demo")
    cli("new", "One")
    result = cli("run", "--chal", "misc/one", "definitely-not-a-command-xyz", "arg", code=1)
    assert "cannot run" in result.output


def test_version(cli):
    assert cli("--version").output.startswith("flag2md ")
