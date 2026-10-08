from __future__ import annotations

from pathlib import Path

from flag2md import journal
from flag2md.workspace import slugify


def test_slugify():
    assert slugify("Baby ROP") == "baby-rop"
    assert slugify("  Cr\u00e9me br\u00fbl\u00e9e!! ") == "creme-brulee"
    assert slugify("../../etc") == "etc"
    assert slugify("???") == "unnamed"


def test_strip_ansi():
    assert journal.strip_ansi("\x1b[1;31mRED\x1b[0m ok") == "RED ok"


def test_fence_grows_past_inner_fences():
    assert journal.fence_for("plain") == "```"
    assert journal.fence_for("a\n```\nb") == "````"


def test_clean_output_truncates_and_handles_carriage_returns():
    output = "\n".join(f"line {i}" for i in range(10))
    lines = journal.clean_output(output, 4)
    assert lines == ["line 0", "line 1", "[... 6 lines truncated ...]", "line 8", "line 9"]
    assert journal.clean_output("10%\r50%\r100%\n", 10) == ["100%"]
    assert journal.clean_output("a\nb", 0) == ["a", "b"]


def test_append_separates_blocks(tmp_path: Path):
    notes = tmp_path / "notes.md"
    journal.add_note(notes, "first")
    journal.add_note(notes, "\nsecond\n\n")
    assert notes.read_text() == "first\n\nsecond\n"

    notes.write_text("no newline at end")
    journal.add_note(notes, "next")
    assert notes.read_text() == "no newline at end\n\nnext\n"


def test_add_command_logs_command_output_and_exit_code(tmp_path: Path):
    notes = tmp_path / "notes.md"
    journal.add_command(notes, "checksec ./bin", "\x1b[32mNX\x1b[0m enabled\n", 0, 80)
    journal.add_command(notes, "false", "", 1, 80)
    assert notes.read_text() == (
        "```console\n$ checksec ./bin\nNX enabled\n```\n\n```console\n$ false\n[exit 1]\n```\n"
    )


def test_add_file_copies_and_references(tmp_path: Path):
    chal = tmp_path / "chal"
    chal.mkdir()
    notes = chal / "notes.md"
    outside = tmp_path / "outside"
    outside.mkdir()
    script = outside / "solve.py"
    script.write_text("print(1)\n")
    image = outside / "my shot.png"
    image.write_bytes(b"\x89PNG\r\n\x1a\n\0")
    blob = outside / "dump.bin"
    blob.write_bytes(b"\0\1\2")

    assert journal.add_file(chal, notes, script) == chal.resolve() / "solve" / "solve.py"
    journal.add_file(chal, notes, image, caption="leak")
    journal.add_file(chal, notes, blob)
    # Adding the same script again refreshes the copy without a second reference.
    script.write_text("print(2)\n")
    journal.add_file(chal, notes, script)

    assert (chal / "solve" / "solve.py").read_text() == "print(2)\n"
    assert notes.read_text() == (
        "<!-- flag2md:include solve/solve.py -->\n\n"
        "![leak](assets/my%20shot.png)\n\n"
        "[dump.bin](solve/dump.bin)\n"
    )


def test_add_file_already_inside_challenge_is_not_copied(tmp_path: Path):
    chal = tmp_path / "chal"
    chal.mkdir()
    script = chal / "exploit.py"
    script.write_text("x = 1\n")
    target = journal.add_file(chal, chal / "notes.md", script)
    assert target == script.resolve()
    assert not (chal / "solve").exists()
