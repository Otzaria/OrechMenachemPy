# -*- coding: utf-8 -*-
"""
stamp_version.py — מזריק את מספר הגרסה של ה-Release לתוך version_info.txt.

הבעיה שהכלי הזה פותר: version_info.txt מכיל מספר גרסה כתוב בקוד, ובזרימת
ה-Release מזינים מספר גרסה ביד. בלי סנכרון ביניהם ייווצר EXE שבשם הקובץ
שלו כתוב v1.2.3 ובמאפייני הקובץ בווינדוס כתוב 1.1.0.0 — סתירה שמבלבלת
ומקשה על זיהוי הגרסה שמשתמש מריץ בפועל.

לכן מספר הגרסה שמזינים בהרצה הידנית הוא מקור האמת היחיד: הכלי קורא את
version_info.txt כתבנית, מחליף בו את שדות הגרסה ואת שם הקובץ, וכותב עותק
מעודכן שאיתו נבנה ה-EXE. הקובץ המקורי אינו משתנה.

מריצים:
    python stamp_version.py --version 1.2.3 --output build/version_info.txt
"""

import argparse
import os
import re
import sys


DEFAULT_TEMPLATE = "version_info.txt"

_TUPLE_FIELDS = ("filevers", "prodvers")
_STRING_FIELDS = ("FileVersion", "ProductVersion")


class VersionInfoError(Exception):
    pass


def use_utf8_output():
    """
    מכריח את הפלט ל-UTF-8 כדי שהודעות בעברית לא יפילו את הכלי.

    קידוד ברירת המחדל של stdout בפייתון הוא קידוד הקונסולה. על מכונת בנייה
    באנגלית זהו cp1252, שאינו מכיל אותיות עבריות, ולכן print יזרוק
    UnicodeEncodeError ויפיל את הזרימה כולה בגלל הודעת הצלחה.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue  # פלט שהוחלף (למשל בבדיקות) — אין מה להגדיר
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError):
            pass


def parse_version(raw):
    """'v1.2.3' -> ((1, 2, 3, 0), '1.2.3.0'). מקבל 1 עד 4 חלקים מספריים."""
    text = (raw or "").strip()
    if text[:1].lower() == "v":
        text = text[1:]
    # תגיות כמו 1.2.3-rc1 מותרות ב-Release, אבל שדות הגרסה של ווינדוס
    # הם מספריים בלבד, ולכן הסיומת נחתכת.
    text = re.split(r"[-+]", text, 1)[0]
    parts = text.split(".") if text else []
    if not 1 <= len(parts) <= 4 or not all(p.isdigit() for p in parts):
        raise VersionInfoError(
            "מספר גרסה לא תקין: %r (צפוי משהו כמו 1.2.3)" % raw)
    numbers = [int(p) for p in parts] + [0] * (4 - len(parts))
    if any(n > 65535 for n in numbers):
        raise VersionInfoError("כל חלק במספר הגרסה חייב להיות עד 65535: %r" % raw)
    return tuple(numbers), ".".join(str(n) for n in numbers)


def stamp(template_text, version, exe_filename=None):
    """מחזיר את תוכן version_info.txt עם הגרסה (ושם הקובץ) המעודכנים."""
    numbers, dotted = parse_version(version)
    text = template_text

    for field in _TUPLE_FIELDS:
        pattern = re.compile(r"(%s\s*=\s*)\([^)]*\)" % field)
        if not pattern.search(text):
            raise VersionInfoError("לא נמצא השדה %s בתבנית מידע הגרסה" % field)
        text = pattern.sub(r"\g<1>(%s)" % ", ".join(str(n) for n in numbers),
                           text, count=1)

    # FileVersion הוא מה שווינדוס מציג בעמודת "גרסת קובץ"; אם התבנית אינה
    # מכילה אותו הוא נוסף ליד ProductVersion.
    if not re.search(r"StringStruct\(\s*u?'FileVersion'", text):
        product = re.search(
            r"([ \t]*)StringStruct\(\s*u?'ProductVersion'\s*,\s*u?'[^']*'\s*\)",
            text)
        if product is None:
            raise VersionInfoError(
                "לא נמצא השדה ProductVersion בתבנית מידע הגרסה")
        indent = product.group(1)
        text = "%s%sStringStruct(u'FileVersion', u'%s'),\n%s" % (
            text[:product.start()], indent, dotted, text[product.start():])

    for field in _STRING_FIELDS:
        pattern = re.compile(
            r"(StringStruct\(\s*u?'%s'\s*,\s*u?')[^']*(')" % field)
        if not pattern.search(text):
            raise VersionInfoError("לא נמצא השדה %s בתבנית מידע הגרסה" % field)
        text = pattern.sub(r"\g<1>%s\g<2>" % dotted, text, count=1)

    if exe_filename:
        pattern = re.compile(
            r"(StringStruct\(\s*u?'OriginalFilename'\s*,\s*u?')[^']*(')")
        if not pattern.search(text):
            raise VersionInfoError(
                "לא נמצא השדה OriginalFilename בתבנית מידע הגרסה")
        text = pattern.sub(r"\g<1>%s\g<2>" % exe_filename, text, count=1)

    return text


def main(argv=None):
    use_utf8_output()
    ap = argparse.ArgumentParser(
        description="הזרקת מספר הגרסה של ה-Release לתוך version_info.txt")
    ap.add_argument("--version", required=True,
                    help="מספר הגרסה, לדוגמה 1.2.3 (עם או בלי v בהתחלה)")
    ap.add_argument("--template", default=DEFAULT_TEMPLATE,
                    help="קובץ מידע הגרסה לקריאה (ברירת מחדל: %s)"
                         % DEFAULT_TEMPLATE)
    ap.add_argument("--output", required=True, help="קובץ הפלט לכתיבה")
    ap.add_argument("--exe-name", default=None,
                    help="שם קובץ ה-EXE שיירשם בשדה OriginalFilename")
    args = ap.parse_args(argv)

    try:
        with open(args.template, encoding="utf-8") as fh:
            template = fh.read()
    except OSError as e:
        print("שגיאה בקריאת התבנית: %s" % e, file=sys.stderr)
        return 2

    try:
        stamped = stamp(template, args.version, args.exe_name)
    except VersionInfoError as e:
        print("שגיאה: %s" % e, file=sys.stderr)
        return 2

    out_dir = os.path.dirname(os.path.abspath(args.output))
    os.makedirs(out_dir, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as fh:
        fh.write(stamped)
    print("נכתב %s (גרסה %s)" % (args.output, parse_version(args.version)[1]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
