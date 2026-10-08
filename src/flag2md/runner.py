"""Run a command while mirroring its output to the terminal."""

from __future__ import annotations

import subprocess
import sys


def _echo(chunk: bytes) -> None:
    stream = getattr(sys.stdout, "buffer", None)
    if stream is not None:
        stream.write(chunk)
        stream.flush()
    else:
        sys.stdout.write(chunk.decode("utf-8", "replace"))
        sys.stdout.flush()


def run_command(command: str | list[str], shell: bool = False) -> tuple[str, int]:
    """Run command with stdout and stderr merged, print it live and return (output, exit code)."""
    proc = subprocess.Popen(command, shell=shell, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    assert proc.stdout is not None
    chunks: list[bytes] = []
    try:
        while chunk := proc.stdout.read1(65536):
            chunks.append(chunk)
            _echo(chunk)
    except KeyboardInterrupt:
        # Ctrl+C also reached the child: keep what it printed so far and log it anyway.
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
    code = proc.wait()
    proc.stdout.close()
    return b"".join(chunks).decode("utf-8", "replace"), code
