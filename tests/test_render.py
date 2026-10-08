from __future__ import annotations

from pathlib import Path

import pytest

from flag2md.config import ConfigError, load_settings
from flag2md.models import Challenge, Ctf, FileInfo
from flag2md.render import build_challenge, build_index, expand_includes, human_size


@pytest.fixture
def ctf(workspace: Path) -> Ctf:
    root = workspace / "demo"
    root.mkdir()
    ctf = Ctf(name="Demo CTF", start="2026-05-01", team="team|pipe", path=root)
    ctf.save()
    return ctf


def make_challenge(ctf: Ctf, **fields) -> Path:
    folder = ctf.path / fields.get("category", "misc") / "chal"
    Challenge(path=folder, **fields).save()
    return folder


def test_human_size():
    assert human_size(None) == "-"
    assert human_size(12) == "12 B"
    assert human_size(2048) == "2.0 KB"
    assert human_size(5 * 1024**3) == "5.0 GB"


def test_expand_includes(tmp_path: Path):
    (tmp_path / "solve").mkdir()
    (tmp_path / "solve" / "x.py").write_text("print('```')\n")
    text, missing = expand_includes(
        "intro\n<!-- flag2md:include solve/x.py -->\n<!-- flag2md:include gone.c -->", tmp_path
    )
    assert text == (
        "intro\n`solve/x.py`\n\n````python\nprint('```')\n````\n<!-- flag2md:include gone.c -->"
    )
    assert missing == ["gone.c"]


def test_minimal_writeup(ctf: Ctf):
    folder = make_challenge(ctf, name="Sanity")
    output, missing = build_challenge(folder, ctf, load_settings(ctf))
    assert missing == []
    assert output.read_text() == (
        "# Sanity\n\n"
        "| CTF | Cat\u00e9gorie | Points | R\u00e9solutions | Auteur |\n"
        "| --- | --- | --- | --- | --- |\n"
        "| Demo CTF | misc | - | - | - |\n\n"
        "## R\u00e9solution\n\n"
        "_TODO_\n"
    )


def test_full_writeup_in_english_with_hugo_front_matter(ctf: Ctf):
    ctf.settings = {"lang": "en", "frontmatter": "hugo", "author": "me"}
    ctf.save()
    folder = make_challenge(
        ctf,
        name="Baby ROP",
        category="pwn",
        points=200,
        solves=3,
        author="a|b",
        description="Line one\n\nLine two",
        connection_info="nc host 1337",
        tags=["rop"],
        hints=["multi\nline"],
        files=[FileInfo(name="remote_only.zip", size=2048)],
        status="solved",
        flag="FLAG{x}",
        solved_at="2026-05-02",
    )
    (folder / "files").mkdir()
    (folder / "files" / "bin").write_bytes(b"abc")
    (folder / "notes.md").write_text("Some notes.\n")

    output, _ = build_challenge(folder, Ctf.load(ctf.path), load_settings(Ctf.load(ctf.path)))
    assert output.read_text() == (
        "---\n"
        "title: 'Demo CTF: Baby ROP'\n"
        "date: '2026-05-02'\n"
        "author: me\n"
        "categories:\n- Demo CTF\n"
        "tags:\n- pwn\n- rop\n"
        "draft: false\n"
        "---\n\n"
        "# Baby ROP\n\n"
        "| CTF | Category | Points | Solves | Author |\n"
        "| --- | --- | --- | --- | --- |\n"
        "| Demo CTF | pwn | 200 | 3 | a\\|b |\n\n"
        "**Tags:** `rop`\n\n"
        "## Description\n\n"
        "> Line one\n>\n> Line two\n\n"
        "## Files\n\n"
        "| File | Size | SHA256 |\n"
        "| --- | --- | --- |\n"
        "| [bin](files/bin) | 3 B | `ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad` |\n"
        "| remote_only.zip | 2.0 KB | - |\n\n"
        "## Connection\n\n"
        "```text\nnc host 1337\n```\n\n"
        "## Hints\n\n"
        "- multi\n  line\n\n"
        "## Solution\n\n"
        "Some notes.\n\n"
        "## Flag\n\n"
        "```text\nFLAG{x}\n```\n"
    )


def test_custom_template_overrides_builtin(ctf: Ctf):
    templates = ctf.path / "tpl"
    templates.mkdir()
    (templates / "writeup.md.j2").write_text("{{ chal.name }} by {{ settings.author }}\n")
    ctf.settings = {"templates_dir": "tpl", "author": "me"}
    ctf.save()
    folder = make_challenge(ctf, name="Custom")
    ctf = Ctf.load(ctf.path)
    output, _ = build_challenge(folder, ctf, load_settings(ctf))
    assert output.read_text() == "Custom by me\n"


def test_index_groups_by_category(ctf: Ctf):
    Challenge(name="B web", category="Web", points=100, status="solved", path=ctf.path / "web" / "b").save()
    Challenge(name="A web", category="web", path=ctf.path / "web" / "a").save()
    Challenge(name="Rop", category="pwn", points=300, status="solved", path=ctf.path / "pwn" / "rop").save()
    ctf.url = "https://ctf.example"
    output = build_index(ctf, load_settings(ctf))
    assert output == ctf.path / "README.md"
    assert output.read_text() == (
        "# Demo CTF\n\n"
        "| Date | \u00c9quipe | R\u00e9solus | Points |\n"
        "| --- | --- | --- | --- |\n"
        "| 2026-05-01 | team\\|pipe | 2/3 | 400 |\n\n"
        "<https://ctf.example>\n\n"
        "## pwn\n\n"
        "- [x] [Rop](pwn/rop/README.md) (300 pts)\n\n"
        "## web\n\n"
        "- [ ] [A web](web/a/README.md)\n"
        "- [x] [B web](web/b/README.md) (100 pts)\n"
    )


def test_invalid_settings_are_rejected(ctf: Ctf):
    ctf.settings = {"frontmatter": "wordpress"}
    with pytest.raises(ConfigError):
        load_settings(ctf)
    ctf.settings = {"lang": "de"}
    with pytest.raises(ConfigError):
        load_settings(ctf)
