# -*- coding: utf-8 -*-
"""בדיקות ל-make_icon.py — יצירת ICO רב-גדלים עם רקע שקוף."""

import struct

import pytest

import make_icon
from make_icon import (
    DEFAULT_SIZES,
    IconError,
    build_ico,
    content_bounds,
    crop_to_content,
    main,
    remove_background,
    scale_down,
)


def alpha_at(image, x, y):
    from PyQt5.QtGui import QColor

    return QColor.fromRgba(image.pixel(x, y)).alpha()


def color_at(image, x, y):
    from PyQt5.QtGui import QColor

    return QColor(image.pixel(x, y)).name()


@pytest.fixture
def sample(qapp):
    """
    ריבוע אדום על רקע לבן, ובתוך האדום כתם לבן.

    הכתם הפנימי הוא הבדיקה החשובה: הוא בהיר בדיוק כמו הרקע, וחייב לשרוד —
    בדיוק כמו דפי הספר באיור האמיתי.
    """
    from PyQt5.QtGui import QImage, QPainter, QColor

    image = QImage(64, 64, QImage.Format_ARGB32)
    image.fill(QColor("white"))
    painter = QPainter(image)
    painter.fillRect(16, 16, 32, 32, QColor(220, 20, 20))
    painter.fillRect(26, 26, 12, 12, QColor("white"))
    painter.end()
    return image


@pytest.fixture
def cleaned(sample):
    return remove_background(sample)


def parse_ico(data):
    """מפרק קובץ ICO ומחזיר רשימת (רוחב, גובה, סיביות, גודל, היסט, סוג)."""
    reserved, kind, count = struct.unpack("<HHH", data[:6])
    assert (reserved, kind) == (0, 1)
    entries = []
    for i in range(count):
        chunk = data[6 + i * 16:22 + i * 16]
        w, h, colors, res, planes, bits, size, offset = struct.unpack(
            "<BBBBHHII", chunk)
        payload = data[offset:offset + size]
        fmt = "PNG" if payload[:8] == b"\x89PNG\r\n\x1a\n" else "DIB"
        entries.append((w or 256, h or 256, bits, size, offset, fmt))
    return entries


# --------------------------------------------------------- remove_background
def test_the_outer_background_becomes_transparent(cleaned):
    for x, y in ((0, 0), (63, 0), (0, 63), (63, 63), (32, 2), (2, 32)):
        assert alpha_at(cleaned, x, y) == 0, (x, y)


def test_the_artwork_itself_is_untouched(cleaned):
    assert alpha_at(cleaned, 20, 20) == 255
    assert color_at(cleaned, 20, 20) == "#dc1414"


def test_a_light_area_enclosed_by_artwork_survives(cleaned):
    """דפי הספר לבנים כמו הרקע, ובלי מילוי מהשוליים הם היו נעלמים."""
    assert alpha_at(cleaned, 32, 32) == 255
    assert color_at(cleaned, 32, 32) == "#ffffff"


def test_removing_the_background_does_not_change_the_dimensions(sample, cleaned):
    assert (cleaned.width(), cleaned.height()) == (sample.width(), sample.height())


def test_an_image_without_a_light_background_is_left_alone(qapp, capsys):
    from PyQt5.QtGui import QImage, QColor

    image = QImage(16, 16, QImage.Format_ARGB32)
    image.fill(QColor(10, 10, 10))
    result = remove_background(image)
    assert alpha_at(result, 0, 0) == 255
    assert "לא זוהה רקע" in capsys.readouterr().out


def test_a_saturated_border_colour_is_not_mistaken_for_background(qapp):
    """הזהב באיור בהיר אך רווי; אין להסיר אותו גם כשהוא נוגע בשוליים."""
    from PyQt5.QtGui import QImage, QColor

    image = QImage(16, 16, QImage.Format_ARGB32)
    image.fill(QColor(230, 190, 60))   # זהב בהיר
    assert alpha_at(remove_background(image), 0, 0) == 255


def test_the_threshold_can_be_relaxed(qapp):
    from PyQt5.QtGui import QImage, QColor

    image = QImage(16, 16, QImage.Format_ARGB32)
    image.fill(QColor(150, 150, 150))   # אפור בינוני
    assert alpha_at(remove_background(image), 0, 0) == 255
    assert alpha_at(remove_background(image, min_lightness=120), 0, 0) == 0


# ------------------------------------------------------------ content_bounds
def test_content_bounds_finds_the_artwork(cleaned):
    assert content_bounds(cleaned) == (16, 16, 47, 47)


def test_content_bounds_returns_none_for_an_empty_image(qapp):
    from PyQt5.QtGui import QImage

    image = QImage(8, 8, QImage.Format_ARGB32)
    image.fill(0)
    assert content_bounds(image) is None


# ----------------------------------------------------------- crop_to_content
def test_cropping_produces_a_square_that_hugs_the_artwork(cleaned):
    cropped = crop_to_content(cleaned, padding_ratio=0)
    assert (cropped.width(), cropped.height()) == (32, 32)
    assert alpha_at(cropped, 0, 0) == 255


def test_padding_leaves_a_transparent_margin(cleaned):
    cropped = crop_to_content(cleaned, padding_ratio=0.125)
    assert cropped.width() == 32 + 2 * 4
    assert alpha_at(cropped, 0, 0) == 0
    assert alpha_at(cropped, 4, 4) == 255


def test_cropping_an_empty_image_is_an_error(qapp):
    from PyQt5.QtGui import QImage

    image = QImage(8, 8, QImage.Format_ARGB32)
    image.fill(0)
    with pytest.raises(IconError, match="שקופה"):
        crop_to_content(image)


# ---------------------------------------------------------------- scale_down
@pytest.mark.parametrize("size", [16, 24, 32, 48, 64, 128, 256])
def test_scaling_hits_the_requested_size_exactly(qapp, sample, size):
    scaled = scale_down(sample, size)
    assert (scaled.width(), scaled.height()) == (size, size)


def test_scaling_up_still_returns_the_requested_size(qapp, sample):
    assert scale_down(sample, 512).width() == 512


def test_scaling_preserves_transparency(cleaned):
    assert alpha_at(scale_down(cleaned, 32), 0, 0) == 0


# ----------------------------------------------------------------- build_ico
def test_the_container_holds_every_requested_size(cleaned):
    entries = parse_ico(build_ico(cleaned, sizes=(16, 32, 256)))
    assert [(w, h) for w, h, *_ in entries] == [(16, 16), (32, 32), (256, 256)]


def test_sizes_are_sorted_and_deduplicated(cleaned):
    entries = parse_ico(build_ico(cleaned, sizes=(32, 16, 32)))
    assert [w for w, *_ in entries] == [16, 32]


def test_every_image_is_thirty_two_bit(cleaned):
    for _w, _h, bits, *_ in parse_ico(build_ico(cleaned, sizes=(16, 48))):
        assert bits == 32


def test_the_size_256_is_stored_as_zero_in_the_directory(cleaned):
    data = build_ico(cleaned, sizes=(256,))
    width_byte, height_byte = data[6], data[7]
    assert (width_byte, height_byte) == (0, 0)


def test_small_images_use_dib_and_large_ones_use_png(cleaned):
    entries = parse_ico(build_ico(cleaned, sizes=(16, 64, 128, 256),
                                 png_from=128))
    formats = {w: fmt for w, _h, _b, _s, _o, fmt in entries}
    assert formats == {16: "DIB", 64: "DIB", 128: "PNG", 256: "PNG"}


def test_the_offsets_and_lengths_describe_the_real_payloads(cleaned):
    data = build_ico(cleaned, sizes=DEFAULT_SIZES)
    entries = parse_ico(data)
    expected = 6 + 16 * len(entries)
    for _w, _h, _b, size, offset, _fmt in entries:
        assert offset == expected
        assert size > 0
        expected += size
    assert expected == len(data)


def test_the_result_is_reproducible(cleaned):
    assert build_ico(cleaned, sizes=(16, 32)) == build_ico(cleaned, sizes=(16, 32))


def test_qt_can_read_back_what_the_tool_writes(qapp, cleaned, tmp_path):
    from PyQt5.QtGui import QIcon

    path = tmp_path / "out.ico"
    path.write_bytes(build_ico(cleaned, sizes=(16, 32, 48)))
    icon = QIcon(str(path))
    assert sorted(s.width() for s in icon.availableSizes()) == [16, 32, 48]
    assert alpha_at(icon.pixmap(32, 32).toImage(), 0, 0) == 0


# --------------------------------------------------------------------- main
@pytest.fixture
def source_file(qapp, tmp_path, sample):
    path = tmp_path / "source.png"
    sample.save(str(path))
    return path


def test_main_writes_a_multi_size_icon(source_file, tmp_path, capsys):
    out = tmp_path / "nested" / "icon.ico"
    assert main(["--source", str(source_file), "--output", str(out)]) == 0
    entries = parse_ico(out.read_bytes())
    assert [w for w, *_ in entries] == sorted(DEFAULT_SIZES)
    assert "נכתב" in capsys.readouterr().out


def test_main_honours_a_custom_size_list(source_file, tmp_path):
    out = tmp_path / "icon.ico"
    assert main(["--source", str(source_file), "--output", str(out),
                 "--sizes", "32,16"]) == 0
    assert [w for w, *_ in parse_ico(out.read_bytes())] == [16, 32]


def test_main_can_keep_the_background(source_file, tmp_path, qapp):
    from PyQt5.QtGui import QIcon

    out = tmp_path / "icon.ico"
    assert main(["--source", str(source_file), "--output", str(out),
                 "--keep-background", "--no-crop", "--sizes", "64"]) == 0
    image = QIcon(str(out)).pixmap(64, 64).toImage()
    assert alpha_at(image, 0, 0) == 255


def test_main_can_skip_the_crop(source_file, tmp_path, qapp):
    from PyQt5.QtGui import QIcon

    out = tmp_path / "icon.ico"
    assert main(["--source", str(source_file), "--output", str(out),
                 "--no-crop", "--sizes", "64"]) == 0
    image = QIcon(str(out)).pixmap(64, 64).toImage()
    # בלי חתיכה השוליים נשארים שקופים ורחבים
    assert alpha_at(image, 2, 2) == 0


def test_main_reports_a_missing_source(tmp_path, capsys):
    code = main(["--source", str(tmp_path / "nope.png"),
                 "--output", str(tmp_path / "icon.ico")])
    assert code == 2
    assert "לא ניתן לקרוא" in capsys.readouterr().err


def test_main_rejects_an_empty_size_list(source_file, tmp_path, capsys):
    code = main(["--source", str(source_file),
                 "--output", str(tmp_path / "icon.ico"), "--sizes", " "])
    assert code == 2
    assert "גדלים" in capsys.readouterr().err


def test_main_requires_a_source():
    with pytest.raises(SystemExit):
        main(["--output", "icon.ico"])


def test_the_default_sizes_cover_what_windows_asks_for():
    """16 לפס הכותרת, 32 לשורת המשימות, 48 בסייר, 256 לתצוגה מוגדלת."""
    for size in (16, 32, 48, 256):
        assert size in DEFAULT_SIZES


def test_the_module_documents_the_real_source_file():
    assert "אייקון לעורך מנחם בפייתון.jpeg" in make_icon.__doc__
