# -*- coding: utf-8 -*-
"""
בדיקות למרשם הבנייה OrechMenachem.spec ולזרימות ה-CI.

המרשם הוא מה שמונע מה-EXE לתפוח בחזרה מ-18MB ל-70MB, ולכן הכללים שבו
נבדקים כאן כמו כל קוד אחר: שאינו מוציא מודול שהאפליקציה מייבאת, ושמסנן
בפועל את מה שהוא מתיימר לסנן.
"""

import ast
import os

import pytest
import yaml


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SPEC_PATH = os.path.join(PROJECT_ROOT, "OrechMenachem.spec")
WORKFLOW_DIR = os.path.join(PROJECT_ROOT, ".github", "workflows")
SOURCES = ("app.py", "converter.py", "theme.py")


class _FakeAnalysis:
    """מחזיק את השדות שהמרשם מסנן, כדי שאפשר יהיה להריץ אותו בבדיקה."""

    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        self.binaries = []
        self.datas = []
        self.pure = []
        self.scripts = []


@pytest.fixture(scope="module")
def spec():
    """מריץ את המרשם עם תחליפים ל-API של PyInstaller ומחזיר את המרחב שלו."""
    calls = {}

    def fake_exe(*args, **kwargs):
        calls["exe"] = kwargs
        return object()

    namespace = {
        "__file__": SPEC_PATH,
        "SPECPATH": PROJECT_ROOT,
        "Analysis": lambda *a, **k: calls.setdefault("analysis", _FakeAnalysis(*a, **k)),
        "PYZ": lambda *a, **k: object(),
        "EXE": fake_exe,
    }
    with open(SPEC_PATH, encoding="utf-8") as fh:
        source = fh.read()
    exec(compile(source, SPEC_PATH, "exec"), namespace)
    namespace["_calls"] = calls
    return namespace


@pytest.fixture(scope="module")
def keep(spec):
    return spec["_keep"]


@pytest.fixture(scope="module")
def workflows():
    loaded = {}
    for name in os.listdir(WORKFLOW_DIR):
        with open(os.path.join(WORKFLOW_DIR, name), encoding="utf-8") as fh:
            loaded[name] = yaml.safe_load(fh)
    return loaded


def imported_modules():
    """כל מה שקבצי המקור מייבאים, כולל שמות מנוקדים."""
    found = set()
    for name in SOURCES:
        with open(os.path.join(PROJECT_ROOT, name), encoding="utf-8") as fh:
            tree = ast.parse(fh.read(), name)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                found.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
                found.add(node.module)
                found.update("%s.%s" % (node.module, a.name) for a in node.names)
    return found


# ------------------------------------------------------------ המרשם נטען
def test_the_spec_file_is_valid_python(spec):
    assert callable(spec["_keep"])
    assert spec["EXCLUDES"]


def test_the_spec_builds_a_windowed_single_file_executable(spec):
    exe = spec["_calls"]["exe"]
    assert exe["name"] == "OrechMenachem"
    assert exe["console"] is False
    assert exe["debug"] is False


def test_the_spec_analyses_the_gui_entry_point(spec):
    assert spec["_calls"]["analysis"].args[0] == ["app.py"]


def test_the_spec_passes_its_exclude_list_to_the_analysis(spec):
    assert spec["_calls"]["analysis"].kwargs["excludes"] == spec["EXCLUDES"]


def test_the_spec_does_not_collect_whole_packages(spec):
    analysis = spec["_calls"]["analysis"]
    assert analysis.kwargs["binaries"] == []
    assert analysis.kwargs["datas"] == []
    assert analysis.kwargs["hiddenimports"] == []


# --------------------------------------------- ההוצאות אינן פוגעות באפליקציה
@pytest.mark.parametrize("module", sorted(imported_modules()))
def test_no_module_the_sources_import_is_excluded(spec, module):
    for excluded in spec["EXCLUDES"]:
        assert module != excluded, module
        assert not module.startswith(excluded + "."), (module, excluded)


@pytest.mark.parametrize(
    "module", ["PyQt5.QtCore", "PyQt5.QtGui", "PyQt5.QtWidgets", "lxml.etree"],
)
def test_the_modules_the_app_needs_stay_in_the_bundle(spec, module):
    assert module not in spec["EXCLUDES"]


def test_the_heaviest_qt_parts_are_excluded(spec):
    for module in ("PyQt5.QtWebEngineCore", "PyQt5.QtWebEngineWidgets",
                   "PyQt5.QtQml", "PyQt5.QtQuick"):
        assert module in spec["EXCLUDES"]


def test_the_exclude_list_has_no_duplicates(spec):
    assert len(spec["EXCLUDES"]) == len(set(spec["EXCLUDES"]))


# ---------------------------------------------------------- סינון בינאריים
@pytest.mark.parametrize(
    "dest",
    ["PyQt5/Qt5/bin/opengl32sw.dll", "PyQt5/Qt5/bin/d3dcompiler_47.dll",
     "PyQt5/Qt5/bin/libGLESv2.dll", "PyQt5/Qt5/bin/libEGL.dll",
     "PyQt5/Qt5/bin/Qt5Quick.dll", "PyQt5/Qt5/bin/Qt5Qml.dll",
     "PyQt5/Qt5/bin/Qt5QmlModels.dll", "PyQt5/Qt5/bin/Qt5Network.dll",
     "PyQt5/Qt5/bin/Qt5WebSockets.dll", "PyQt5/Qt5/bin/Qt5DBus.dll",
     "PyQt5/Qt5/bin/Qt5Svg.dll", "libcrypto-1_1.dll", "libssl-1_1.dll"],
)
def test_unused_libraries_are_dropped(keep, dest):
    assert not keep(dest)


@pytest.mark.parametrize(
    "dest",
    ["PyQt5/Qt5/bin/Qt5Core.dll", "PyQt5/Qt5/bin/Qt5Gui.dll",
     "PyQt5/Qt5/bin/Qt5Widgets.dll", "PyQt5/Qt5/bin/MSVCP140.dll",
     "PyQt5/Qt5/bin/VCRUNTIME140.dll", "PyQt5/QtCore.pyd",
     "PyQt5/QtGui.pyd", "PyQt5/QtWidgets.pyd", "PyQt5/sip.cp310-win_amd64.pyd",
     "lxml/etree.cp310-win_amd64.pyd", "python310.dll", "base_library.zip",
     "ucrtbase.dll", "unicodedata.pyd"],
)
def test_everything_the_app_runs_on_is_kept(keep, dest):
    assert keep(dest)


@pytest.mark.parametrize(
    "dest",
    ["PyQt5/Qt5/translations/qtbase_he.qm", "PyQt5/Qt5/translations/qt_gl.qm",
     "PyQt5/Qt5/plugins/platformthemes/qxdgdesktopportal.dll",
     "PyQt5/Qt5/plugins/generic/qtuiotouchplugin.dll",
     "PyQt5/Qt5/plugins/iconengines/qsvgicon.dll"],
)
def test_whole_unused_folders_are_dropped(keep, dest):
    assert not keep(dest)


def test_only_the_windows_platform_plugin_survives(keep):
    assert keep("PyQt5/Qt5/plugins/platforms/qwindows.dll")
    for name in ("qminimal.dll", "qoffscreen.dll", "qwebgl.dll", "qdirect2d.dll"):
        assert not keep("PyQt5/Qt5/plugins/platforms/" + name)


def test_only_the_light_image_format_plugins_survive(keep):
    for name in ("qico.dll", "qgif.dll"):
        assert keep("PyQt5/Qt5/plugins/imageformats/" + name)
    for name in ("qwebp.dll", "qtiff.dll", "qjpeg.dll", "qicns.dll",
                 "qtga.dll", "qwbmp.dll", "qsvg.dll"):
        assert not keep("PyQt5/Qt5/plugins/imageformats/" + name)


def test_the_widget_style_plugin_is_kept(keep):
    assert keep("PyQt5/Qt5/plugins/styles/qwindowsvistastyle.dll")


def test_the_filter_accepts_windows_path_separators(keep):
    assert not keep("PyQt5\\Qt5\\bin\\opengl32sw.dll")
    assert not keep("PyQt5\\Qt5\\translations\\qtbase_he.qm")
    assert keep("PyQt5\\Qt5\\bin\\Qt5Core.dll")


def test_the_filter_ignores_letter_case(keep):
    assert not keep("pyqt5/qt5/bin/OPENGL32SW.DLL")
    assert not keep("PYQT5/QT5/PLUGINS/PLATFORMS/QMINIMAL.DLL")


def test_the_spec_actually_applies_the_filter_to_both_lists(spec):
    analysis = spec["_calls"]["analysis"]
    assert analysis.binaries == []
    assert analysis.datas == []


# ------------------------------------------------------------- זרימות CI
def test_there_is_a_test_workflow_and_a_release_workflow(workflows):
    assert set(workflows) == {"tests.yml", "release.yml"}


def test_the_test_workflow_runs_on_every_push(workflows):
    triggers = workflows["tests.yml"][True]
    assert "push" in triggers
    assert "workflow_dispatch" not in triggers


def test_the_release_workflow_runs_only_by_hand_with_a_version(workflows):
    triggers = workflows["release.yml"][True]
    assert list(triggers) == ["workflow_dispatch"]
    version = triggers["workflow_dispatch"]["inputs"]["version"]
    assert version["required"] is True


def test_the_test_workflow_only_tests(workflows):
    steps = workflows["tests.yml"]["jobs"]["test"]["steps"]
    commands = " ".join(step.get("run", "") for step in steps)
    assert "pytest" in commands
    assert "PyInstaller" not in commands
    assert "gh release" not in commands


def test_the_release_workflow_does_not_run_the_tests(workflows):
    job = workflows["release.yml"]["jobs"]["release"]
    commands = " ".join(step.get("run", "") for step in job["steps"])
    assert "pytest" not in commands
    assert "needs" not in job


def test_the_release_workflow_builds_from_the_spec_file(workflows):
    steps = workflows["release.yml"]["jobs"]["release"]["steps"]
    commands = " ".join(step.get("run", "") for step in steps)
    assert "OrechMenachem.spec" in commands
    # --collect-all הוא מה שהחזיר את כל Qt לחבילה ושילש את גודל הקובץ.
    assert "--collect-all" not in commands


def test_the_release_workflow_may_write_the_release(workflows):
    assert workflows["release.yml"]["permissions"]["contents"] == "write"
    steps = workflows["release.yml"]["jobs"]["release"]["steps"]
    commands = " ".join(step.get("run", "") for step in steps)
    assert "gh release create" in commands


def test_the_spec_file_is_not_ignored_by_git():
    """`*.spec` מסונן ב-.gitignore; בלי החרגה מפורשת ה-Release נכשל ב-CI."""
    import subprocess

    result = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard", "--", "*.spec"],
        cwd=PROJECT_ROOT, capture_output=True, text=True,
    )
    tracked = subprocess.run(
        ["git", "ls-files", "--", "OrechMenachem.spec"],
        cwd=PROJECT_ROOT, capture_output=True, text=True,
    )
    listed = result.stdout.split() + tracked.stdout.split()
    assert "OrechMenachem.spec" in listed


def test_the_release_workflow_guards_against_the_exe_growing_back(workflows):
    steps = workflows["release.yml"]["jobs"]["release"]["steps"]
    verify = next(s for s in steps if s["name"] == "Verify build output")
    assert "throw" in verify["run"]
    assert "1MB" in verify["run"]
