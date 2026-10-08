"""Command line interface."""

from __future__ import annotations

import os
import shlex
import sys
from datetime import date
from pathlib import Path
from typing import Any, NoReturn

import typer

from flag2md import __version__, journal
from flag2md.config import ConfigError, global_config_path, load_settings, resolve_token
from flag2md.models import CHALLENGE_FILE, CTF_FILE, NOTES_FILE, SOLVED, Challenge, Ctf, FileInfo, sha256_of
from flag2md.platforms import PlatformError, RemoteChallenge, get_platform
from flag2md.render import build_challenge, build_index
from flag2md.runner import run_command
from flag2md.workspace import find_upwards, iter_challenges, slugify

app = typer.Typer(
    help="Turn CTF solving sessions into clean Markdown write-ups.",
    no_args_is_help=True,
    pretty_exceptions_enable=False,
)

CHAL_OPTION = typer.Option(None, "--chal", help="Challenge folder (default: the one you are in).")


def fail(message: str) -> NoReturn:
    typer.secho(f"error: {message}", fg=typer.colors.RED, err=True)
    raise typer.Exit(1)


def warn(message: str) -> None:
    typer.secho(f"warning: {message}", fg=typer.colors.YELLOW, err=True)


def done(message: str) -> None:
    typer.secho(message, fg=typer.colors.GREEN)


def shown(path: Path) -> str:
    try:
        return Path(os.path.relpath(path.resolve(), Path.cwd().resolve())).as_posix()
    except ValueError:
        return str(path)


def locate_ctf(start: Path | None = None) -> Ctf | None:
    root = find_upwards(start or Path.cwd(), CTF_FILE)
    if root is None:
        return None
    try:
        return Ctf.load(root)
    except ValueError as exc:
        fail(str(exc))


def require_ctf() -> Ctf:
    ctf = locate_ctf()
    if ctf is None:
        fail(f"no {CTF_FILE} here or in a parent folder, start with 'flag2md init'")
    return ctf


def require_challenge(path: Path | None) -> Path:
    folder = find_upwards(path or Path.cwd(), CHALLENGE_FILE)
    if folder is None:
        fail(f"no {CHALLENGE_FILE} here or in a parent folder, start with 'flag2md new' or use --chal")
    return folder


def settings_for(ctf: Ctf | None) -> dict[str, Any]:
    try:
        return load_settings(ctf)
    except ConfigError as exc:
        fail(str(exc))


def render_challenge(folder: Path, ctf: Ctf | None, settings: dict[str, Any]) -> Path:
    output, missing = build_challenge(folder, ctf, settings)
    for name in missing:
        warn(f"{shown(folder)}: included file not found: {name}")
    return output


def _version(value: bool) -> None:
    if value:
        typer.echo(f"flag2md {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(False, "--version", "-V", callback=_version, is_eager=True, help="Show the version."),
) -> None:
    """Turn CTF solving sessions into clean Markdown write-ups.

    \b
    Typical session:
      flag2md init "FCSC 2026" --url https://ctf.example.org
      flag2md pull                       (or: flag2md new "Baby ROP" -c pwn -p 200)
      cd pwn/baby-rop
      flag2md run checksec --file=./baby_rop
      flag2md note "No canary, NX on: ret2libc"
      flag2md add ~/solve.py
      flag2md flag "FCSC{...}"
      flag2md build
    """


@app.command()
def init(
    name: str = typer.Argument(..., help="CTF name, for example 'FCSC 2026'."),
    url: str = typer.Option("", "--url", "-u", help="Platform URL (CTFd instance), used by 'pull'."),
    team: str = typer.Option("", "--team", help="Your team name."),
    start: str = typer.Option("", "--start", help="Start date, YYYY-MM-DD (default: today)."),
    end: str = typer.Option("", "--end", help="End date, YYYY-MM-DD."),
    directory: Path | None = typer.Option(None, "--dir", help="Target folder (default: ./<ctf-name-slug>)."),
) -> None:
    """Create a CTF folder with its ctf.yml."""
    root = directory if directory is not None else Path.cwd() / slugify(name)
    if (root / CTF_FILE).exists():
        fail(f"{shown(root / CTF_FILE)} already exists")
    root.mkdir(parents=True, exist_ok=True)
    ctf = Ctf(
        name=name,
        url=url,
        platform="ctfd" if url else "",
        team=team,
        start=start or date.today().isoformat(),
        end=end,
        path=root,
    )
    ctf.save()
    done(f"created {shown(root / CTF_FILE)}")


@app.command()
def new(
    name: str = typer.Argument(..., help="Challenge name."),
    category: str = typer.Option("misc", "--category", "-c", help="Category (pwn, web, crypto, ...)."),
    points: int | None = typer.Option(None, "--points", "-p", help="Challenge value."),
    author: str = typer.Option("", "--author", "-a", help="Challenge author."),
    description: str = typer.Option("", "--description", "-d", help="Challenge statement."),
    connection: str = typer.Option("", "--connection", "-n", help="Connection info, for example 'nc host 1337'."),
    tags: list[str] | None = typer.Option(None, "--tag", "-t", help="Tag, repeatable."),
) -> None:
    """Create a challenge folder inside the current CTF."""
    ctf = require_ctf()
    assert ctf.path is not None
    folder = ctf.path / slugify(category) / slugify(name)
    if (folder / CHALLENGE_FILE).exists():
        fail(f"{shown(folder)} already exists")
    chal = Challenge(
        name=name,
        category=category,
        points=points,
        author=author,
        description=description,
        connection_info=connection,
        tags=list(tags or []),
        path=folder,
    )
    chal.save()
    (folder / NOTES_FILE).touch()
    done(f"created {shown(folder)}")


@app.command(context_settings={"allow_interspersed_args": False, "ignore_unknown_options": True})
def run(
    command: list[str] = typer.Argument(
        ..., help="Command to run. One quoted string goes through the shell, so pipes work."
    ),
    chal: Path | None = CHAL_OPTION,
) -> None:
    """Run a command, show its output and log both into notes.md."""
    folder = require_challenge(chal)
    settings = settings_for(locate_ctf(folder))
    use_shell = len(command) == 1
    display = command[0] if use_shell else shlex.join(command)
    try:
        output, code = run_command(command[0] if use_shell else command, shell=use_shell)
    except (FileNotFoundError, PermissionError) as exc:
        fail(f"cannot run {command[0]!r}: {exc.strerror or exc}")
    journal.add_command(folder / NOTES_FILE, display, output, code, settings["max_output_lines"])
    if code:
        warn(f"exit code {code}, logged anyway")
    raise typer.Exit(code if 0 <= code < 256 else 1)


@app.command()
def note(
    text: list[str] | None = typer.Argument(None, help="Note text. Without it, reads stdin or opens $EDITOR."),
    chal: Path | None = CHAL_OPTION,
) -> None:
    """Add a free text note (Markdown) to notes.md."""
    folder = require_challenge(chal)
    if text:
        body = " ".join(text)
    elif not sys.stdin.isatty():
        body = sys.stdin.read()
    else:
        body = typer.edit("") or ""
    if not body.strip():
        fail("empty note, nothing logged")
    journal.add_note(folder / NOTES_FILE, body)
    done("note logged")


@app.command()
def add(
    paths: list[Path] = typer.Argument(..., exists=True, dir_okay=False, help="Files to attach."),
    to: str | None = typer.Option(None, "--to", help="Subfolder to copy into (default: assets/ or solve/)."),
    caption: str = typer.Option("", "--caption", help="Image caption."),
    chal: Path | None = CHAL_OPTION,
) -> None:
    """Attach scripts or screenshots: images are embedded, scripts are inlined at build time."""
    folder = require_challenge(chal)
    for path in paths:
        target = journal.add_file(folder, folder / NOTES_FILE, path, subdir=to, caption=caption)
        done(f"added {target.relative_to(folder.resolve()).as_posix()}")


@app.command()
def flag(
    value: str = typer.Argument(..., help="The flag."),
    chal: Path | None = CHAL_OPTION,
) -> None:
    """Save the flag and mark the challenge as solved."""
    folder = require_challenge(chal)
    challenge = Challenge.load(folder)
    challenge.flag = value
    challenge.status = SOLVED
    challenge.solved_at = challenge.solved_at or date.today().isoformat()
    challenge.save()
    done(f"{challenge.name}: solved")


@app.command()
def build(
    all_: bool = typer.Option(False, "--all", "-a", help="Rebuild every challenge of the CTF."),
    chal: Path | None = CHAL_OPTION,
) -> None:
    """Generate the write-up(s) and the CTF index.

    The write-up file is regenerated each time: write in notes.md, not in README.md.
    """
    start = chal or Path.cwd()
    chal_dir = find_upwards(start, CHALLENGE_FILE)
    ctf = locate_ctf(start)
    if chal_dir is not None and not all_:
        folders = [chal_dir]
    elif ctf is not None and ctf.path is not None:
        folders = iter_challenges(ctf.path)
    else:
        fail("nothing to build here, run it inside a CTF or a challenge folder")
    settings = settings_for(ctf)
    for folder in folders:
        done(f"built {shown(render_challenge(folder, ctf, settings))}")
    if ctf is not None:
        done(f"built {shown(build_index(ctf, settings))}")


@app.command("ls")
def list_challenges() -> None:
    """List the challenges of the current CTF."""
    ctf = require_ctf()
    assert ctf.path is not None
    challenges = [Challenge.load(folder) for folder in iter_challenges(ctf.path)]
    if not challenges:
        typer.echo("no challenge yet")
        return
    paths = [chal.path.relative_to(ctf.path).as_posix() for chal in challenges if chal.path]
    width = max(len(path) for path in paths)
    for chal, path in zip(challenges, paths, strict=True):
        mark = "x" if chal.solved else " "
        points = "" if chal.points is None else str(chal.points)
        typer.echo(f"[{mark}] {path:<{width}}  {points:>5}  {chal.name}")
    solved = [chal for chal in challenges if chal.solved]
    typer.echo(f"\n{len(solved)}/{len(challenges)} solved, {sum(chal.points or 0 for chal in solved)} pts")


def _apply_remote(chal: Challenge, remote: RemoteChallenge, platform: str) -> None:
    chal.name = remote.name
    chal.category = remote.category
    chal.points = remote.points
    chal.solves = remote.solves
    chal.author = remote.author or chal.author
    chal.description = remote.description
    chal.connection_info = remote.connection_info
    chal.tags = remote.tags
    chal.hints = remote.hints
    chal.source = {"platform": platform, "id": remote.id}
    if remote.solved and not chal.solved:
        chal.status = SOLVED
        chal.solved_at = chal.solved_at or date.today().isoformat()


@app.command()
def pull(
    url: str | None = typer.Option(None, "--url", "-u", help="Platform URL (default: url from ctf.yml)."),
    token: str | None = typer.Option(None, "--token", "-t", envvar="FLAG2MD_TOKEN", help="API token."),
    session: str | None = typer.Option(None, "--session", envvar="FLAG2MD_SESSION", help="Session cookie value."),
    categories: list[str] | None = typer.Option(None, "--category", "-c", help="Only this category, repeatable."),
    no_files: bool = typer.Option(False, "--no-files", help="Do not download attachments."),
    max_size: int = typer.Option(100, "--max-size", help="Skip attachments bigger than this, in MB (0: no limit)."),
    force: bool = typer.Option(False, "--force", help="Download attachments again even if present."),
) -> None:
    """Fetch challenges (statement, files, hints) from the CTF platform.

    Local work (notes.md, flag, status) is kept when pulling again.
    Tokens can also be stored in the global config under 'tokens', keyed by host.
    """
    ctf = require_ctf()
    assert ctf.path is not None
    settings = settings_for(ctf)
    base = url or ctf.url
    if not base:
        fail("no platform URL, pass --url or set url in ctf.yml")
    if url and not ctf.url:
        ctf.url = url
        ctf.platform = ctf.platform or "ctfd"
        ctf.save()

    platform_name = ctf.platform or "ctfd"
    try:
        platform = get_platform(platform_name, base, token=token or resolve_token(settings, base), session=session)
        refs = platform.list_challenges()
    except PlatformError as exc:
        fail(str(exc))

    wanted = {name.lower() for name in categories or []}
    pulled = created = 0
    for ref in refs:
        if wanted and ref.category.lower() not in wanted:
            continue
        try:
            remote = platform.get_challenge(ref.id)
        except PlatformError as exc:
            warn(f"skipped {ref.name}: {exc}")
            continue

        folder = ctf.path / slugify(remote.category) / slugify(remote.name)
        is_new = not (folder / CHALLENGE_FILE).exists()
        chal = Challenge(name=remote.name, path=folder) if is_new else Challenge.load(folder)
        _apply_remote(chal, remote, platform_name)
        folder.mkdir(parents=True, exist_ok=True)
        (folder / NOTES_FILE).touch(exist_ok=True)

        files = []
        for remote_file in remote.files:
            dest = folder / "files" / remote_file.name
            if not no_files and (force or not dest.exists()):
                dest.parent.mkdir(exist_ok=True)
                try:
                    platform.download(remote_file, dest, max_bytes=max_size * 1024 * 1024)
                except PlatformError as exc:
                    warn(f"{remote.name}: {exc}")
            if dest.is_file():
                files.append(FileInfo(name=dest.name, sha256=sha256_of(dest), size=dest.stat().st_size))
            else:
                files.append(FileInfo(name=remote_file.name))
        chal.files = files
        chal.save()
        render_challenge(folder, ctf, settings)

        pulled += 1
        created += is_new
        typer.echo(f"{'new ' if is_new else 'sync'} {shown(folder)}")

    build_index(ctf, settings)
    done(f"{pulled} challenge(s) pulled, {created} new")


@app.command()
def config() -> None:
    """Show where settings come from and their current values."""
    path = global_config_path()
    typer.echo(f"global config: {path}{'' if path.is_file() else ' (not created)'}")
    ctf = locate_ctf()
    if ctf is not None and ctf.path is not None:
        typer.echo(f"ctf config:    {ctf.path / CTF_FILE} (settings section)")
    typer.echo("")
    for key, value in settings_for(ctf).items():
        if key == "tokens" and isinstance(value, dict):
            value = ", ".join(f"{host}=***" for host in value) or "{}"
        typer.echo(f"{key}: {value}")
