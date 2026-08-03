# -*- coding: utf-8 -*-
"""בדיקות ל-stamp_version.py — הזרקת מספר הגרסה למידע הגרסה של ווינדוס."""

import os
import re

import pytest

from stamp_version import (
    VersionInfoError,
    main,
    parse_version,
    stamp,
)


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE_PATH = os.path.join(PROJECT_ROOT, "version_info.txt")


@pytest.fixture(scope="module")
def template():
    with open(TEMPLATE_PATH, encoding="utf-8") as fh:
        return fh.read()


def field(text, name):
    """ערכו של StringStruct מתוך תוכן מידע הגרסה (במרכאות בודדות או כפולות)."""
    match = re.search(
        r"""StringStruct\(\s*u?'%s'\s*,\s*u?(['"])(.*?)\1\s*\)""" % name, text)
    return match.group(2) if match else None


def tuple_field(text, name):
    match = re.search(r"%s\s*=\s*\(([^)]*)\)" % name, text)
    return tuple(int(p) for p in match.group(1).split(",")) if match else None


# ----------------------------------------------------------- parse_version
@pytest.mark.parametrize(
    ("raw", "numbers", "dotted"),
    [
        ("1.2.3", (1, 2, 3, 0), "1.2.3.0"),
        ("v1.2.3", (1, 2, 3, 0), "1.2.3.0"),
        ("V1.2.3", (1, 2, 3, 0), "1.2.3.0"),
        ("  1.2.3  ", (1, 2, 3, 0), "1.2.3.0"),
        ("1.2.3.4", (1, 2, 3, 4), "1.2.3.4"),
        ("2.0", (2, 0, 0, 0), "2.0.0.0"),
        ("7", (7, 0, 0, 0), "7.0.0.0"),
        ("1.2.3-rc1", (1, 2, 3, 0), "1.2.3.0"),
        ("1.2.3+build9", (1, 2, 3, 0), "1.2.3.0"),
        ("v10.20.30", (10, 20, 30, 0), "10.20.30.0"),
    ],
)
def test_parse_version_normalises_to_four_numbers(raw, numbers, dotted):
    assert parse_version(raw) == (numbers, dotted)


@pytest.mark.parametrize(
    "raw",
    ["", "   ", None, "v", "abc", "1.2.x", "1..2", "1.2.3.4.5", "-1.2.3",
     "1.2.3 4", "70000.1.0"],
)
def test_parse_version_rejects_anything_that_is_not_a_version(raw):
    with pytest.raises(VersionInfoError):
        parse_version(raw)


def test_parse_version_strips_a_suffix_from_a_four_part_version():
    assert parse_version("1.2.3.4-rc.5")[0] == (1, 2, 3, 4)


def test_parse_version_allows_the_highest_valid_part():
    assert parse_version("65535.65535.65535.65535")[0] == (65535,) * 4


# ------------------------------------------------------------------- stamp
def test_stamp_writes_the_version_into_both_fixed_info_fields(template):
    result = stamp(template, "2.5.1")
    assert tuple_field(result, "filevers") == (2, 5, 1, 0)
    assert tuple_field(result, "prodvers") == (2, 5, 1, 0)


def test_stamp_writes_the_version_into_both_string_fields(template):
    result = stamp(template, "2.5.1")
    assert field(result, "FileVersion") == "2.5.1.0"
    assert field(result, "ProductVersion") == "2.5.1.0"


def test_stamp_adds_a_file_version_field_when_the_template_lacks_one(template):
    assert field(template, "FileVersion") is None
    assert field(stamp(template, "1.0.0"), "FileVersion") == "1.0.0.0"


def test_stamp_does_not_duplicate_an_existing_file_version_field(template):
    once = stamp(template, "1.0.0")
    twice = stamp(once, "3.0.0")
    assert twice.count("'FileVersion'") == 1
    assert field(twice, "FileVersion") == "3.0.0.0"


def test_stamp_is_idempotent_for_the_same_version(template):
    once = stamp(template, "1.4.0")
    assert stamp(once, "1.4.0") == once


def test_stamp_updates_the_original_filename_when_asked(template):
    result = stamp(template, "1.2.3", "OrechMenachem_v1.2.3.exe")
    assert field(result, "OriginalFilename") == "OrechMenachem_v1.2.3.exe"


def test_stamp_leaves_the_original_filename_alone_by_default(template):
    result = stamp(template, "1.2.3")
    assert field(result, "OriginalFilename") == "OrechMenachem.exe"


def test_stamp_keeps_the_hebrew_product_metadata(template):
    result = stamp(template, "1.2.3")
    assert field(result, "ProductName") == "עורך מנחם"
    assert field(result, "CompanyName") == "אוצריא"
    assert field(result, "InternalName") == "OrechMenachem"
    assert "מתנדבי אוצריא" in result


def test_stamp_keeps_the_hebrew_language_code(template):
    result = stamp(template, "1.2.3")
    assert "040D04B0" in result
    assert "[1037, 1200]" in result


def test_stamp_keeps_the_file_a_valid_version_resource(template):
    """התוצאה חייבת להישאר ביטוי פייתון שאותו PyInstaller מריץ."""
    result = stamp(template, "1.2.3")
    # PyInstaller מריץ eval על התוכן ללא שורות ההערה.
    body = "\n".join(line for line in result.splitlines()
                     if not line.strip().startswith("#"))
    compile(body, "version_info", "eval")


def test_stamp_preserves_the_trailing_comments(template):
    result = stamp(template, "1.2.3")
    assert "# גרסת המוצר" in result
    assert "# מסכה" in result


def test_stamp_rejects_a_bad_version(template):
    with pytest.raises(VersionInfoError):
        stamp(template, "not-a-version")


@pytest.mark.parametrize(
    "missing", ["filevers", "prodvers", "ProductVersion", "OriginalFilename"],
)
def test_stamp_fails_loudly_when_the_template_is_missing_a_field(template, missing):
    broken = template.replace(missing, "somethingElse")
    with pytest.raises(VersionInfoError, match=missing):
        stamp(broken, "1.2.3", "x.exe")


# -------------------------------------------------------------------- main
def test_main_writes_the_stamped_file(tmp_path, capsys):
    out = tmp_path / "nested" / "version_info.generated.txt"
    code = main(["--version", "v3.1.4", "--template", TEMPLATE_PATH,
                 "--output", str(out), "--exe-name", "OrechMenachem_v3.1.4.exe"])
    assert code == 0
    text = out.read_text(encoding="utf-8")
    assert tuple_field(text, "filevers") == (3, 1, 4, 0)
    assert field(text, "OriginalFilename") == "OrechMenachem_v3.1.4.exe"
    assert "3.1.4.0" in capsys.readouterr().out


def test_main_creates_the_output_directory(tmp_path):
    out = tmp_path / "a" / "b" / "c.txt"
    assert main(["--version", "1.0.0", "--template", TEMPLATE_PATH,
                 "--output", str(out)]) == 0
    assert out.is_file()


def test_main_reports_a_missing_template(tmp_path, capsys):
    code = main(["--version", "1.0.0", "--template", str(tmp_path / "nope.txt"),
                 "--output", str(tmp_path / "out.txt")])
    assert code == 2
    assert "שגיאה" in capsys.readouterr().err


def test_main_reports_a_bad_version(tmp_path, capsys):
    code = main(["--version", "banana", "--template", TEMPLATE_PATH,
                 "--output", str(tmp_path / "out.txt")])
    assert code == 2
    assert "שגיאה" in capsys.readouterr().err
    assert not (tmp_path / "out.txt").exists()


def test_main_reports_a_template_missing_a_field(tmp_path, capsys):
    broken = tmp_path / "broken.txt"
    broken.write_text("VSVersionInfo(ffi=FixedFileInfo())", encoding="utf-8")
    code = main(["--version", "1.0.0", "--template", str(broken),
                 "--output", str(tmp_path / "out.txt")])
    assert code == 2
    assert "filevers" in capsys.readouterr().err


def test_main_requires_a_version_argument():
    with pytest.raises(SystemExit):
        main(["--output", "out.txt"])


# ------------------------------------------------- התבנית שבמאגר
def test_the_repository_template_is_usable(template):
    """שומר על התבנית תקינה — היא הקלט של כל בנייה."""
    assert "VSVersionInfo" in template
    for name in ("filevers", "prodvers"):
        assert tuple_field(template, name) is not None
    for name in ("CompanyName", "FileDescription", "InternalName",
                 "OriginalFilename", "ProductName", "LegalCopyright",
                 "ProductVersion"):
        assert field(template, name), name
