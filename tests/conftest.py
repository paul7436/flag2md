from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from flag2md.cli import app


@pytest.fixture
def workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.delenv("FLAG2MD_TOKEN", raising=False)
    monkeypatch.delenv("FLAG2MD_SESSION", raising=False)
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.fixture
def cli():
    runner = CliRunner()

    def invoke(*args: str, input: str | None = None, code: int = 0):
        result = runner.invoke(app, list(args), input=input)
        assert result.exit_code == code, result.output
        return result

    return invoke
