# -*- coding: utf-8 -*-
"""
בדיקות האייקון — קובץ האייקון עצמו, טעינתו בזמן ריצה, ואריזתו ל-EXE.

האייקון צריך להופיע בשלושה מקומות: על קובץ ה-EXE בסייר הקבצים (משאב של
הקובץ), בפס הכותרת של החלון, ובשורת המשימות. שני האחרונים נטענים בזמן ריצה
מקובץ ארוז, ולכן הוא חייב להיות גם ב-datas של מרשם הבנייה ולא רק בפרמטר
icon. הקובץ גם נעלם פעם אחת מהתיקייה, ולכן יש כאן בדיקה שהוא במקומו.
"""

import os
import struct
import subprocess

import pytest

import app


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ICON_PATH = os.path.join(PROJECT_ROOT, "assets", "icon.ico")


def ico_images(path):
    """רשימת (רוחב, גובה, סיביות) של התמונות שבקובץ ICO."""
    with open(path, "rb") as fh:
        data = fh.read()
    reserved, kind, count = struct.unpack("<HHH", data[:6])
    assert reserved == 0 and kind == 1, "אינו קובץ ICO תקין"
    images = []
    for i in range(count):
        entry = data[6 + i * 16:22 + i * 16]
        width, height, _colors, _res, _planes, bits, _size, _off = \
            struct.unpack("<BBBBHHII", entry)
        images.append((width or 256, height or 256, bits))
    return images


# ------------------------------------------------------- קובץ האייקון
def test_the_icon_file_is_in_place():
    """הקובץ נעלם פעם אחת; בלעדיו ה-EXE והחלון יוצאים בלי אייקון."""
    assert os.path.isfile(ICON_PATH), "assets/icon.ico חסר"


def test_the_icon_is_tracked_in_git():
    """קובץ שאינו במעקב git נעלם בכל ניקוי של עץ העבודה."""
    result = subprocess.run(
        ["git", "ls-files", "--", "assets/icon.ico"],
        cwd=PROJECT_ROOT, capture_output=True, text=True,
    )
    assert result.stdout.strip() == "assets/icon.ico"


def test_the_icon_is_a_valid_ico_container():
    assert ico_images(ICON_PATH), "אין תמונות בקובץ האייקון"


def test_the_icon_is_not_ignored_by_git():
    result = subprocess.run(
        ["git", "check-ignore", "-q", "--no-index", "--", "assets/icon.ico"],
        cwd=PROJECT_ROOT, capture_output=True, text=True,
    )
    assert result.returncode != 0, "assets/icon.ico מסונן ב-.gitignore"


# ------------------------------------------------------ טעינה בזמן ריצה
def test_the_icon_relative_path_matches_the_repository_layout():
    assert app.ICON_RELATIVE_PATH == os.path.join("assets", "icon.ico")
    assert os.path.isfile(os.path.join(PROJECT_ROOT, app.ICON_RELATIVE_PATH))


def test_resource_path_resolves_next_to_the_source_when_not_frozen(monkeypatch):
    monkeypatch.delattr("sys._MEIPASS", raising=False)
    assert app.resource_path("assets/icon.ico") == \
        os.path.join(PROJECT_ROOT, "assets/icon.ico")


def test_resource_path_uses_the_pyinstaller_extraction_folder(monkeypatch, tmp_path):
    """ב-onefile הקבצים נפרשים לתיקייה זמנית, ולא ליד קובץ המקור."""
    monkeypatch.setattr("sys._MEIPASS", str(tmp_path), raising=False)
    assert app.resource_path(app.ICON_RELATIVE_PATH) == \
        str(tmp_path / app.ICON_RELATIVE_PATH)


def test_app_icon_loads_the_real_file(qapp):
    icon = app.app_icon()
    assert not icon.isNull()
    assert icon.availableSizes(), "Qt לא הצליח לפענח את קובץ האייקון"


def test_app_icon_is_empty_when_the_file_is_missing(qapp, monkeypatch, tmp_path):
    """אייקון חסר אינו מפיל את התוכנה — היא פשוט עולה בלעדיו."""
    monkeypatch.setattr("sys._MEIPASS", str(tmp_path), raising=False)
    assert app.app_icon().isNull()


# --------------------------------------------------------- החלון עצמו
def test_the_main_window_carries_the_icon(qapp):
    window = app.MainWindow()
    try:
        assert not window.windowIcon().isNull()
    finally:
        window.close()


def test_the_window_icon_can_render_the_title_bar_size(qapp):
    """פס הכותרת מבקש 16x16; אם Qt אינו מצליח לייצר אותו לא יופיע כלום."""
    icon = app.app_icon()
    for size in (16, 32, 48):
        pixmap = icon.pixmap(size, size)
        assert not pixmap.isNull(), size
        assert pixmap.width() == size


# ------------------------------------------ זהות התהליך בשורת המשימות
def test_the_application_id_is_stable_and_specific():
    assert app.APP_ID == "otzaria.OrechMenachem"


def test_setting_the_taskbar_identity_never_raises(monkeypatch):
    app.set_taskbar_identity()  # על ווינדוס אמיתי


def test_the_taskbar_identity_is_skipped_off_windows(monkeypatch):
    monkeypatch.setattr("sys.platform", "linux")
    app.set_taskbar_identity()


def test_a_failing_shell_call_does_not_break_startup(monkeypatch):
    """נוי בלבד: אם ווינדוס דוחה את הקריאה התוכנה חייבת להמשיך לעלות."""
    import ctypes

    def explode(*args, **kwargs):
        raise OSError("nope")

    monkeypatch.setattr(ctypes, "windll", property(explode), raising=False)
    app.set_taskbar_identity()


# --------------------------------------------------- אריזה ל-EXE
def test_the_spec_ships_the_icon_both_as_resource_and_as_a_file():
    """
    שני שימושים נפרדים: הפרמטר icon קובע את מה שרואים על הקובץ בסייר,
    ו-datas מאפשר ל-app.py לטעון אותו בזמן ריצה לחלון ולשורת המשימות.
    """
    from test_build_spec import load_spec

    spec = load_spec()
    exe = spec["_calls"]["exe"]
    assert exe["icon"] == os.path.join("assets", "icon.ico")
    assert spec["ICON_DATA"] == [(os.path.join("assets", "icon.ico"), "assets")]


def test_the_bundled_icon_lands_where_the_app_looks_for_it():
    from test_build_spec import load_spec

    spec = load_spec()
    source, dest_dir = spec["ICON_DATA"][0]
    bundled = os.path.join(dest_dir, os.path.basename(source))
    assert bundled == app.ICON_RELATIVE_PATH


def test_no_icon_means_no_data_entry(monkeypatch, tmp_path):
    from test_build_spec import load_spec

    monkeypatch.setenv("OM_ICON", str(tmp_path / "absent.ico"))
    spec = load_spec()
    assert spec["ICON_DATA"] == []
    assert spec["_calls"]["exe"]["icon"] is None


def test_the_icon_survives_the_binary_filter():
    """מסנן הבינאריים לא אמור להשמיט את האייקון עצמו."""
    from test_build_spec import load_spec

    keep = load_spec()["_keep"]
    assert keep("assets/icon.ico")
    assert keep("assets\\icon.ico")


# --------------------------------------------------------- איכות האייקון
@pytest.mark.parametrize("size", [16, 24, 32, 48, 64, 128, 256])
def test_every_size_windows_asks_for_is_prepared_in_advance(size):
    """
    ווינדוס מבקש גודל אחר לפי ההקשר — 16 לפס הכותרת, 32 לשורת המשימות,
    48 בסייר, 256 בתצוגה מוגדלת. קובץ שמכיל רק 256 מאלץ הקטנה בזמן אמת
    והתוצאה מרוחה, ולכן כל גודל מוכן מראש (ראו make_icon.py).
    """
    assert size in [w for w, _h, _bits in ico_images(ICON_PATH)]


def test_qt_sees_all_the_prepared_sizes(qapp):
    sizes = sorted(s.width() for s in app.app_icon().availableSizes())
    assert sizes == [16, 24, 32, 48, 64, 128, 256]


@pytest.mark.parametrize("size", [16, 32, 48, 256])
def test_windows_can_be_served_every_size_it_asks_for(qapp, size):
    pixmap = app.app_icon().pixmap(size, size)
    assert not pixmap.isNull()
    assert (pixmap.width(), pixmap.height()) == (size, size)


def test_every_image_in_the_file_carries_an_alpha_channel():
    for width, _height, bits in ico_images(ICON_PATH):
        assert bits == 32, "%dx%d אינו 32 סיביות" % (width, width)


@pytest.mark.parametrize("size", [16, 32, 48, 256])
def test_the_background_is_transparent_at_every_size(qapp, size):
    """
    בלי שקיפות האייקון מופיע בשורת המשימות ובפס הכותרת כריבוע לבן ולא
    כאיור מרחף.
    """
    from PyQt5.QtGui import QColor

    image = app.app_icon().pixmap(size, size).toImage()
    for x, y in ((0, 0), (size - 1, 0), (0, size - 1), (size - 1, size - 1)):
        assert QColor.fromRgba(image.pixel(x, y)).alpha() == 0, (size, x, y)


def test_the_artwork_actually_fills_the_canvas(qapp):
    """אחרי חתיכת השוליים האיור אמור לתפוס כמעט את כל הריבוע."""
    from PyQt5.QtGui import QColor

    size = 64
    image = app.app_icon().pixmap(size, size).toImage()
    opaque = sum(
        1 for y in range(size) for x in range(size)
        if QColor.fromRgba(image.pixel(x, y)).alpha() > 128)
    assert opaque > size * size * 0.45, "האיור קטן מדי בתוך הריבוע"


def test_the_icon_generator_is_available_for_regenerating_it():
    """כשהאיור יתעדכן צריך להיות אפשר לייצר את הקובץ מחדש."""
    assert os.path.isfile(os.path.join(PROJECT_ROOT, "make_icon.py"))
