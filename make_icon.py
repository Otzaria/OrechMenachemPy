# -*- coding: utf-8 -*-
"""
make_icon.py — מייצר את assets/icon.ico מקובץ האיור המקורי.

למה צריך כלי ולא פשוט לשמור ICO מעורך תמונות:

    • ווינדוס מבקש את האייקון בגדלים שונים לפי ההקשר — 16 לפס הכותרת של
      החלון, 32 לשורת המשימות, 48 בסייר הקבצים, 256 בתצוגה מוגדלת. קובץ
      שמכיל רק 256x256 מאלץ את ווינדוס להקטין בזמן אמת, והתוצאה מרוחה.
      כאן כל גודל מוכן מראש בהקטנה מדורגת, שנותנת תוצאה חדה בהרבה.
    • קובץ האיור הוא JPEG, שאינו יכול להכיל שקיפות, ולכן הרקע הלבן הופך
      את האייקון לריבוע לבן בשורת המשימות. הסרת הרקע נעשית במילוי מהשוליים
      פנימה בלבד, כך שהלבן שבתוך האיור (דפי הספר) נשאר במקומו.

מריצים:
    python make_icon.py --source "assets/אייקון לעורך מנחם בפייתון.jpeg"
"""

import argparse
import os
import struct
import sys
from collections import deque


DEFAULT_SIZES = (16, 24, 32, 48, 64, 128, 256)
# מעל הגודל הזה התמונות נשמרות כ-PNG בתוך ה-ICO במקום DIB, כדי לא לנפח
# את הקובץ. ווינדוס תומך ב-PNG בתוך ICO מ-Vista והלאה.
PNG_FROM_SIZE = 128

# זיהוי רקע: פיקסל בהיר וחיוור. הזהב רווי מאוד ולכן אינו נכנס לטווח,
# והצל האפור שסביב הספר כן — וזה רצוי, כי אייקון של ווינדוס לא אמור
# לכלול צל מודפס.
BACKGROUND_MAX_SATURATION = 46
BACKGROUND_MIN_LIGHTNESS = 170


class IconError(Exception):
    pass


# ------------------------------------------------------------------ עזרי תמונה
def _argb_buffer(image):
    """מחזיר (bytearray, bytes_per_line) של תמונת ARGB32 — B,G,R,A לפיקסל."""
    pointer = image.bits()
    pointer.setsize(image.byteCount())
    return bytearray(pointer.asstring()), image.bytesPerLine()


def load_source(path):
    from PyQt5.QtGui import QImage

    image = QImage(path)
    if image.isNull():
        raise IconError("לא ניתן לקרוא את קובץ האיור: %s" % path)
    if image.width() != image.height():
        print("אזהרה: האיור אינו מרובע (%dx%d); האייקון ירובע בריפוד."
              % (image.width(), image.height()))
    return image.convertToFormat(QImage.Format_ARGB32)


def remove_background(image, max_saturation=BACKGROUND_MAX_SATURATION,
                      min_lightness=BACKGROUND_MIN_LIGHTNESS):
    """
    מסיר את הרקע: מילוי מהשוליים פנימה על פיקסלים בהירים וחיוורים.

    המילוי מהשוליים הוא העיקר — הוא מבטיח שאזורים בהירים שנמצאים *בתוך*
    האיור, כמו דפי הספר, לא ייעלמו רק משום שצבעם דומה לרקע.
    """
    width, height = image.width(), image.height()
    buffer, stride = _argb_buffer(image)

    def is_background(x, y):
        offset = y * stride + x * 4
        blue, green, red = buffer[offset], buffer[offset + 1], buffer[offset + 2]
        lightness = (max(red, green, blue) + min(red, green, blue)) // 2
        saturation = max(red, green, blue) - min(red, green, blue)
        return lightness >= min_lightness and saturation <= max_saturation

    seen = bytearray(width * height)
    queue = deque()

    def push(x, y):
        index = y * width + x
        if not seen[index] and is_background(x, y):
            seen[index] = 1
            queue.append((x, y))

    for x in range(width):
        push(x, 0)
        push(x, height - 1)
    for y in range(height):
        push(0, y)
        push(width - 1, y)

    removed = 0
    while queue:
        x, y = queue.popleft()
        buffer[y * stride + x * 4 + 3] = 0
        removed += 1
        if x > 0:
            push(x - 1, y)
        if x + 1 < width:
            push(x + 1, y)
        if y > 0:
            push(x, y - 1)
        if y + 1 < height:
            push(x, y + 1)

    from PyQt5.QtGui import QImage

    result = QImage(bytes(buffer), width, height, stride, QImage.Format_ARGB32)
    print("הוסרו %d פיקסלים של רקע (%.1f%% מהתמונה)"
          % (removed, 100.0 * removed / (width * height)))
    if removed == 0:
        print("אזהרה: לא זוהה רקע להסרה — ייתכן שהרקע אינו בהיר.")
    return result.copy()   # copy כדי שהתמונה לא תישען על ה-buffer המקומי


def content_bounds(image):
    """תיבת הגבול של הפיקסלים שאינם שקופים, או None אם הכול שקוף."""
    width, height = image.width(), image.height()
    buffer, stride = _argb_buffer(image)
    left, top, right, bottom = width, height, -1, -1
    for y in range(height):
        row = y * stride
        for x in range(width):
            if buffer[row + x * 4 + 3]:
                if x < left:
                    left = x
                if x > right:
                    right = x
                if y < top:
                    top = y
                if y > bottom:
                    bottom = y
    if right < 0:
        return None
    return left, top, right, bottom


def crop_to_content(image, padding_ratio=0.03):
    """
    חותך את השוליים הריקים ומרכז את האיור בריבוע.

    בגודל 16x16 כל פיקסל נחשב, ושוליים ריקים גורמים לאיור להיראות קטן
    ומרוחק. ריפוד קטן נשמר כדי שהאיור לא ייגע בקצה.
    """
    from PyQt5.QtGui import QImage, QPainter

    bounds = content_bounds(image)
    if bounds is None:
        raise IconError("כל התמונה שקופה — אין מה לארוז")
    left, top, right, bottom = bounds
    content_width = right - left + 1
    content_height = bottom - top + 1
    side = max(content_width, content_height)
    padding = int(round(side * padding_ratio))
    canvas_side = side + padding * 2

    canvas = QImage(canvas_side, canvas_side, QImage.Format_ARGB32)
    canvas.fill(0)
    painter = QPainter(canvas)
    painter.drawImage(
        padding + (side - content_width) // 2,
        padding + (side - content_height) // 2,
        image, left, top, content_width, content_height)
    painter.end()
    print("נחתך ל-%dx%d (מתוך %dx%d)"
          % (canvas_side, canvas_side, image.width(), image.height()))
    return canvas


def scale_down(image, size):
    """
    הקטנה מדורגת: חצי בכל צעד עד שמגיעים לפחות מפי שניים מהיעד.

    הקטנה ישירה מ-1024 ל-16 בצעד אחד דוגמת מעט מדי פיקסלים ויוצאת מרוחה;
    חצייה חוזרת ממצעת את כל הפיקסלים ושומרת פרטים.
    """
    from PyQt5.QtCore import Qt

    current = image
    while current.width() // 2 > size:
        current = current.scaled(current.width() // 2, current.height() // 2,
                                 Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
    return current.scaled(size, size, Qt.IgnoreAspectRatio,
                          Qt.SmoothTransformation)


# ------------------------------------------------------------------ בניית ICO
def _png_bytes(image):
    from PyQt5.QtCore import QBuffer, QByteArray

    store = QByteArray()
    buffer = QBuffer(store)
    buffer.open(QBuffer.WriteOnly)
    if not image.save(buffer, "PNG"):
        raise IconError("כתיבת PNG נכשלה")
    buffer.close()
    return bytes(store)


def _dib_bytes(image):
    """תמונת DIB בת 32 סיביות: כותרת, שורות BGRA מלמטה למעלה, ומסכת AND."""
    width, height = image.width(), image.height()
    buffer, stride = _argb_buffer(image)
    rows = []
    for y in range(height - 1, -1, -1):
        row = y * stride
        rows.append(bytes(buffer[row:row + width * 4]))
    pixels = b"".join(rows)
    # מסכת AND אינה בשימוש בתמונות 32 סיביות, אך המבנה מחייב אותה.
    mask_stride = ((width + 31) // 32) * 4
    mask = b"\x00" * (mask_stride * height)
    header = struct.pack(
        "<IiiHHIIiiII",
        40, width, height * 2, 1, 32, 0, len(pixels) + len(mask), 0, 0, 0, 0)
    return header + pixels + mask


def build_ico(image, sizes=DEFAULT_SIZES, png_from=PNG_FROM_SIZE):
    """מרכיב קובץ ICO רב-גדלים ומחזיר את הבתים שלו."""
    images = []
    for size in sorted(set(sizes)):
        scaled = scale_down(image, size)
        payload = _png_bytes(scaled) if size >= png_from else _dib_bytes(scaled)
        images.append((size, payload))
        print("  %3dx%-3d  %6d bytes  %s"
              % (size, size, len(payload), "PNG" if size >= png_from else "DIB"))

    header = struct.pack("<HHH", 0, 1, len(images))
    offset = 6 + 16 * len(images)
    entries = []
    for size, payload in images:
        entries.append(struct.pack(
            "<BBBBHHII",
            0 if size >= 256 else size,   # 0 מסמן 256 בפורמט ICO
            0 if size >= 256 else size,
            0, 0, 1, 32, len(payload), offset))
        offset += len(payload)
    return header + b"".join(entries) + b"".join(p for _, p in images)


# ------------------------------------------------------------------ main
def main(argv=None):
    parser = argparse.ArgumentParser(
        description="יצירת assets/icon.ico רב-גדלים עם רקע שקוף")
    parser.add_argument("--source", required=True, help="קובץ האיור המקורי")
    parser.add_argument("--output", default=os.path.join("assets", "icon.ico"),
                        help="קובץ ה-ICO לכתיבה")
    parser.add_argument("--sizes", default=",".join(str(s) for s in DEFAULT_SIZES),
                        help="גדלים מופרדים בפסיקים")
    parser.add_argument("--keep-background", action="store_true",
                        help="לא להסיר את הרקע")
    parser.add_argument("--no-crop", action="store_true",
                        help="לא לחתוך את השוליים הריקים")
    parser.add_argument("--padding", type=float, default=0.03,
                        help="ריפוד סביב האיור כשבר מהצלע (ברירת מחדל 0.03)")
    args = parser.parse_args(argv)

    from PyQt5.QtWidgets import QApplication

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    QApplication.instance() or QApplication([])

    try:
        sizes = [int(s) for s in args.sizes.split(",") if s.strip()]
        if not sizes:
            raise IconError("לא נמסרו גדלים")
        image = load_source(args.source)
        print("מקור: %dx%d" % (image.width(), image.height()))
        if not args.keep_background:
            image = remove_background(image)
        if not args.no_crop:
            image = crop_to_content(image, args.padding)
        data = build_ico(image, sizes)
    except IconError as e:
        print("שגיאה: %s" % e, file=sys.stderr)
        return 2

    directory = os.path.dirname(os.path.abspath(args.output))
    os.makedirs(directory, exist_ok=True)
    with open(args.output, "wb") as fh:
        fh.write(data)
    print("נכתב %s (%d bytes, %d גדלים)" % (args.output, len(data), len(sizes)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
