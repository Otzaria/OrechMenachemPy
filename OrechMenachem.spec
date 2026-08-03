# -*- mode: python ; coding: utf-8 -*-
"""
OrechMenachem.spec — מרשם בנייה ל-PyInstaller המפיק EXE נייד וקטן.

הרקע: הבנייה המקורית השתמשה ב-`--collect-all PyQt5`, שגורר את *כל* Qt לתוך
החבילה — כולל Qt5WebEngineCore (97MB), OpenGL בתוכנה, QML/Quick, כל
התרגומים וכל תוספי התמונות. האפליקציה מייבאת רק QtCore/QtGui/QtWidgets
(ראו app.py) ו-lxml.etree (ראו converter.py), ולכן כמעט כל זה מבוזבז.

הקובץ הזה עובד בשתי שכבות:
    1. excludes — מונע מהניתוח לגלות מודולים שאינם בשימוש מלכתחילה.
    2. סינון a.binaries/a.datas — מסיר קבצים בינאריים ונתונים ששרדו את
       הניתוח כתלות עקיפה, אף שאין להם צורך באפליקציית QtWidgets.

מריצים:  python -m PyInstaller --noconfirm --clean OrechMenachem.spec
"""

import os


# ─────────────────────────────────────────────── מודולים שאינם בשימוש
# חלקי Qt שאינם נדרשים לאפליקציית QtWidgets. QtWebEngine* ו-QtQml/QtQuick
# הם החוסכים הגדולים; היתר מונעים גרירת DLL עקיפה.
EXCLUDED_QT = [
    "PyQt5.QtWebEngine", "PyQt5.QtWebEngineCore", "PyQt5.QtWebEngineWidgets",
    "PyQt5.QtWebKit", "PyQt5.QtWebKitWidgets", "PyQt5.QtWebChannel",
    "PyQt5.QtWebSockets", "PyQt5.QtQml", "PyQt5.QtQuick", "PyQt5.QtQuick3D",
    "PyQt5.QtQuickWidgets", "PyQt5.QtMultimedia", "PyQt5.QtMultimediaWidgets",
    "PyQt5.QtSql", "PyQt5.QtTest", "PyQt5.QtDesigner", "PyQt5.QtHelp",
    "PyQt5.QtBluetooth", "PyQt5.QtNfc", "PyQt5.QtSerialPort",
    "PyQt5.QtPositioning", "PyQt5.QtLocation", "PyQt5.QtSensors",
    "PyQt5.QtOpenGL", "PyQt5.QtSvg", "PyQt5.QtXml", "PyQt5.QtXmlPatterns",
    "PyQt5.QtDBus", "PyQt5.QtNetwork", "PyQt5.QtPrintSupport",
    "PyQt5.QAxContainer", "PyQt5.Qsci", "PyQt5.QtChart",
    "PyQt5.QtDataVisualization", "PyQt5.uic", "PyQt5.QtRemoteObjects",
]

# converter.py משתמש ב-lxml.etree בלבד. lxml.html גורר urllib/ssl ואיתם
# libcrypto ו-libssl (1.3MB), ולכן ההוצאה שלו חוסכת פעמיים.
EXCLUDED_LXML = [
    "lxml.html", "lxml.objectify", "lxml.isoschematron", "lxml.cssselect",
    "lxml.builder", "lxml.usedoctest", "cssselect", "cchardet",
    "charset_normalizer",
]

# ספריית תקן ותלויות פיתוח שאינן נוגעות לאפליקציה.
EXCLUDED_STDLIB = [
    "tkinter", "unittest", "doctest", "pydoc", "pdb", "bdb", "profile",
    "cProfile", "pstats", "asyncio", "ssl", "_ssl", "email", "http",
    "xmlrpc", "sqlite3", "_sqlite3", "curses", "lib2to3", "distutils",
    "setuptools", "pkg_resources", "pip", "pytest", "_pytest",
    "numpy", "PIL", "matplotlib", "IPython",
]

EXCLUDES = EXCLUDED_QT + EXCLUDED_LXML + EXCLUDED_STDLIB


# ───────────────────────────────── בינאריים ונתונים שמסירים אחרי הניתוח
# DLL-ים שנגררים כתלות עקיפה אף שאפליקציית QtWidgets לעולם אינה טוענת
# אותם: OpenGL בתוכנה (Mesa) ומימוש ANGLE נדרשים רק להקשר OpenGL, וכאן
# כל הציור נעשה במנוע ה-raster.
DROP_BINARIES = {
    "pyqt5/qt5/bin/opengl32sw.dll",       # Mesa llvmpipe — 5.5MB
    "pyqt5/qt5/bin/d3dcompiler_47.dll",   # ANGLE
    "pyqt5/qt5/bin/libglesv2.dll",        # ANGLE
    "pyqt5/qt5/bin/libegl.dll",           # ANGLE
    "pyqt5/qt5/bin/qt5quick.dll",
    "pyqt5/qt5/bin/qt5qml.dll",
    "pyqt5/qt5/bin/qt5qmlmodels.dll",
    "pyqt5/qt5/bin/qt5network.dll",
    "pyqt5/qt5/bin/qt5websockets.dll",
    "pyqt5/qt5/bin/qt5dbus.dll",
    "pyqt5/qt5/bin/qt5svg.dll",
    "libcrypto-1_1.dll",
    "libssl-1_1.dll",
}

# תיקיות שלמות שאין בהן צורך. התרגומים של Qt (4.6MB) נטענים רק דרך
# QTranslator, והאפליקציה אינה יוצרת אחד — הממשק כתוב עברית בקוד.
DROP_PREFIXES = (
    "pyqt5/qt5/translations/",
    "pyqt5/qt5/plugins/platformthemes/",   # qxdgdesktopportal — לינוקס
    "pyqt5/qt5/plugins/generic/",          # qtuiotouchplugin
    "pyqt5/qt5/plugins/iconengines/",      # qsvgicon — אין אייקוני SVG
)

# מבין תוספי הפלטפורמה נדרש qwindows בלבד; qminimal/qoffscreen/qwebgl
# משמשים בדיקות ושרתים ולא הפעלה על שולחן העבודה.
KEEP_PLATFORM_PLUGINS = {"qwindows.dll"}

# האפליקציה אינה טוענת תמונות; qico ו-qgif נשארים כרשת ביטחון לאייקוני
# חלון, והכבדים (webp/tiff/jpeg) יורדים.
KEEP_IMAGEFORMAT_PLUGINS = {"qico.dll", "qgif.dll"}


def _keep(dest_name):
    """מחליט אם רשומת TOC נשארת בחבילה."""
    dest = dest_name.replace("\\", "/").lower()
    if dest in DROP_BINARIES or dest.startswith(DROP_PREFIXES):
        return False
    for folder, keep in (("platforms", KEEP_PLATFORM_PLUGINS),
                         ("imageformats", KEEP_IMAGEFORMAT_PLUGINS)):
        prefix = "pyqt5/qt5/plugins/%s/" % folder
        if dest.startswith(prefix):
            return os.path.basename(dest) in keep
    return True


a = Analysis(
    ["app.py"],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=EXCLUDES,
    noarchive=False,
)

a.binaries = [entry for entry in a.binaries if _keep(entry[0])]
a.datas = [entry for entry in a.datas if _keep(entry[0])]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="OrechMenachem",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
