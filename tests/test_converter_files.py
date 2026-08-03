# -*- coding: utf-8 -*-
"""בדיקות שמירת הפלט לקבצים ובדיקות ממשק שורת הפקודה."""

import os
import subprocess
import sys

import pytest

from converter import _sanitize_filename, convert_file

from conftest import footnote, footnotes_xml, para, run


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read_exact(path):
    """קורא את הקובץ בלי תרגום מעברי שורה, כדי לבדוק CRLF כפי שנכתב."""
    return path.read_bytes().decode("utf-8-sig")


@pytest.fixture
def docx_with_note(write_docx):
    body = para(run("גוף") + '<w:r><w:footnoteReference w:id="1"/></w:r>')
    footnotes = footnotes_xml(footnote("1", para(run("הערה"))))
    return write_docx(body=body, footnotes=footnotes)


# --------------------------------------------------------- _sanitize_filename
@pytest.mark.parametrize(
    ("raw", "clean"),
    [
        ("simple", "simple"),
        ("a\\b", "ab"),
        ("a/b", "ab"),
        ("a:b", "ab"),
        ("a*b", "ab"),
        ("a?b", "ab"),
        ('a"b', "ab"),
        ("a<b>c", "abc"),
        ("a|b", "ab"),
        ("  padded  ", "padded"),
        ("***", ""),
        ("", ""),
        ("שם בעברית", "שם בעברית"),
    ],
)
def test_sanitize_filename_removes_illegal_characters(raw, clean):
    assert _sanitize_filename(raw) == clean


# ------------------------------------------------------------- convert_file
def test_convert_file_writes_both_files_next_to_the_source(docx_with_note, tmp_path):
    result = convert_file(docx_with_note, 11, 10)
    assert result["body_path"] == str(tmp_path / "sample.txt")
    assert result["notes_path"] == str(tmp_path / "הערות על sample.txt")
    assert result["n_footnotes"] == 1
    assert read_exact(tmp_path / "sample.txt") == "גוף<sup>1</sup>"
    assert read_exact(tmp_path / "הערות על sample.txt") == "<sup>1</sup> הערה\r\n"


def test_convert_file_can_write_without_a_bom(docx_with_note, tmp_path):
    convert_file(docx_with_note, 11, 10, add_bom=False)
    assert not (tmp_path / "sample.txt").read_bytes().startswith(b"\xef\xbb\xbf")


def test_convert_file_creates_a_missing_output_directory(docx_with_note, tmp_path):
    out = tmp_path / "deep" / "nested"
    result = convert_file(docx_with_note, 11, 10, out_dir=str(out))
    assert out.is_dir()
    assert result["body_path"] == str(out / "sample.txt")
    assert result["notes_path"] == str(out / "הערות על sample.txt")


def test_convert_file_reuses_an_existing_output_directory(docx_with_note, tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    convert_file(docx_with_note, 11, 10, out_dir=str(out))
    assert (out / "sample.txt").exists()


def test_convert_file_skips_the_notes_file_when_asked(docx_with_note, tmp_path):
    result = convert_file(docx_with_note, 11, 10, make_notes=False)
    assert result["notes_path"] is None
    assert result["n_footnotes"] == 1
    assert not (tmp_path / "הערות על sample.txt").exists()


def test_convert_file_writes_no_notes_file_without_footnotes(write_docx, tmp_path):
    source = write_docx(body=para(run("גוף")))
    result = convert_file(source, 11, 10)
    assert result["notes_path"] is None
    assert result["n_footnotes"] == 0


def test_convert_file_falls_back_to_output_for_an_unusable_name(
        write_docx, tmp_path, monkeypatch):
    # שם שכולו תווים אסורים אינו יכול להתקיים בווינדוס, ולכן מדמים ניקוי
    # שמחזיר מחרוזת ריקה — המקרה שבו נכנס לתוקף שם ברירת המחדל.
    import converter

    source = write_docx(body=para(run("תוכן")))
    monkeypatch.setattr(converter, "_sanitize_filename", lambda name: "")
    result = convert_file(source, 11, 10)
    assert result["body_path"] == str(tmp_path / "output.txt")
    assert (tmp_path / "output.txt").exists()


def test_convert_file_keeps_crlf_line_endings_verbatim(write_docx, tmp_path):
    source = write_docx(body=para(run("a")) + para(run("b")))
    convert_file(source, 11, 10)
    assert (tmp_path / "sample.txt").read_bytes() == b"\xef\xbb\xbfa\r\nb"


def test_convert_file_overwrites_a_previous_result(write_docx, tmp_path):
    source = write_docx(body=para(run("חדש")))
    (tmp_path / "sample.txt").write_text("ישן וארוך מאוד", encoding="utf-8")
    convert_file(source, 11, 10)
    assert (tmp_path / "sample.txt").read_text(encoding="utf-8-sig") == "חדש"


def test_convert_file_uses_each_files_own_reference_sizes(write_docx, tmp_path):
    source = write_docx(body=para(run("x", '<w:rPr><w:szCs w:val="24"/></w:rPr>')))
    convert_file(source, 12, 10)
    assert (tmp_path / "sample.txt").read_text(encoding="utf-8-sig") == "x"
    convert_file(source, 11, 10)
    assert (tmp_path / "sample.txt").read_text(encoding="utf-8-sig") == "<big>x</big>"


# ------------------------------------------------------------------- CLI
def run_cli(*args, io_encoding=None):
    """
    מריץ את ה-CLI. io_encoding מדמה קונסולה שאינה UTF-8 — כך נבדק שהכלי
    אינו נשען על קידוד הקונסולה של המכונה שמריצה אותו.
    """
    env = dict(os.environ)
    env.pop("PYTHONIOENCODING", None)
    env.pop("PYTHONUTF8", None)
    if io_encoding:
        env["PYTHONIOENCODING"] = io_encoding
    return subprocess.run(
        [sys.executable, "converter.py", *args],
        cwd=PROJECT_ROOT, env=env, capture_output=True, text=True, encoding="utf-8",
    )


def test_cli_converts_a_file_and_reports_both_outputs(docx_with_note, tmp_path):
    result = run_cli(str(docx_with_note), "--normal", "11", "--notes", "10")
    assert result.returncode == 0
    assert "OK:" in result.stdout
    assert "sample.txt" in result.stdout
    assert (tmp_path / "הערות על sample.txt").exists()


def test_cli_honours_the_output_directory_and_no_bom_flags(write_docx, tmp_path):
    source = write_docx(body=para(run("תוכן")))
    out = tmp_path / "cli-out"
    result = run_cli(str(source), "--normal", "11", "--out", str(out), "--no-bom")
    assert result.returncode == 0
    assert not (out / "sample.txt").read_bytes().startswith(b"\xef\xbb\xbf")


def test_cli_reports_an_error_for_an_unreadable_file(tmp_path):
    bad = tmp_path / "bad.docx"
    bad.write_text("not a zip", encoding="utf-8")
    result = run_cli(str(bad), "--normal", "11")
    assert result.returncode == 0
    assert "ERR:" in result.stdout


def test_cli_converts_several_files_in_one_run(write_docx, tmp_path):
    first = write_docx("one.docx", para(run("א")))
    second = write_docx("two.docx", para(run("ב")))
    result = run_cli(str(first), str(second), "--normal", "11")
    assert result.stdout.count("OK:") == 2
    assert (tmp_path / "one.txt").exists() and (tmp_path / "two.txt").exists()


def test_cli_requires_the_normal_size_argument(docx_with_note):
    result = run_cli(str(docx_with_note))
    assert result.returncode != 0
    assert "--normal" in result.stderr


@pytest.mark.parametrize("encoding", ["cp1252", "ascii", "cp862"])
def test_cli_prints_hebrew_paths_on_a_non_hebrew_console(docx_with_note, encoding):
    """
    שם קובץ ההערות עברי, וקידוד ברירת המחדל של stdout הוא קידוד הקונסולה.
    על מכונה באנגלית (וכך על הרנר של GitHub) הוא cp1252, ובלי הגנה מפורשת
    ה-print היה מפיל את הכלי אחרי המרה שהצליחה.
    """
    result = run_cli(str(docx_with_note), "--normal", "11", "--notes", "10",
                     io_encoding=encoding)
    assert result.returncode == 0, result.stderr
    assert "UnicodeEncodeError" not in result.stderr
    assert "OK:" in result.stdout
