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


def load_spec():
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
    # המרשם פותר נתיבים יחסית לשורש המאגר, כמו PyInstaller עצמו.
    previous = os.getcwd()
    os.chdir(PROJECT_ROOT)
    try:
        exec(compile(source, SPEC_PATH, "exec"), namespace)
    finally:
        os.chdir(previous)
    namespace["_calls"] = calls
    return namespace


@pytest.fixture(scope="module")
def spec():
    return load_spec()


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


# ---------------------------------------------------- שם, אייקון ומידע גרסה
def test_the_exe_name_can_be_set_from_the_environment(monkeypatch):
    monkeypatch.setenv("OM_EXE_NAME", "OrechMenachem_v9.9.9")
    assert load_spec()["_calls"]["exe"]["name"] == "OrechMenachem_v9.9.9"


def test_an_empty_name_variable_falls_back_to_the_default(monkeypatch):
    monkeypatch.setenv("OM_EXE_NAME", "")
    assert load_spec()["_calls"]["exe"]["name"] == "OrechMenachem"


def test_the_version_file_is_passed_through_when_it_exists(monkeypatch, tmp_path):
    version_file = tmp_path / "version_info.generated.txt"
    version_file.write_text("VSVersionInfo()", encoding="utf-8")
    monkeypatch.setenv("OM_VERSION_FILE", str(version_file))
    assert load_spec()["_calls"]["exe"]["version"] == str(version_file)


def test_no_version_file_is_used_by_default(monkeypatch):
    monkeypatch.delenv("OM_VERSION_FILE", raising=False)
    assert load_spec()["_calls"]["exe"]["version"] is None


def test_a_missing_version_file_stops_the_build(monkeypatch, tmp_path):
    """שגיאה שקטה כאן הייתה מפיקה EXE בלי מספר גרסה בלי שאיש ישים לב."""
    monkeypatch.setenv("OM_VERSION_FILE", str(tmp_path / "absent.txt"))
    with pytest.raises(SystemExit, match="OM_VERSION_FILE"):
        load_spec()


def test_the_icon_is_used_once_the_file_exists(monkeypatch, tmp_path):
    icon = tmp_path / "icon.ico"
    icon.write_bytes(b"\x00\x00\x01\x00")
    monkeypatch.setenv("OM_ICON", str(icon))
    assert load_spec()["_calls"]["exe"]["icon"] == str(icon)


def test_a_missing_icon_does_not_break_the_build(monkeypatch, tmp_path):
    monkeypatch.setenv("OM_ICON", str(tmp_path / "absent.ico"))
    assert load_spec()["_calls"]["exe"]["icon"] is None


def test_the_default_icon_location_is_the_assets_folder(spec):
    assert spec["DEFAULT_ICON"] == os.path.join("assets", "icon.ico")


def test_the_icon_matches_whether_the_assets_file_is_present(monkeypatch, spec):
    """כשיתווסף assets/icon.ico הוא ייכנס לבנייה מעצמו, בלי לשנות קוד."""
    monkeypatch.delenv("OM_ICON", raising=False)
    present = os.path.isfile(os.path.join(PROJECT_ROOT, spec["DEFAULT_ICON"]))
    icon = load_spec()["_calls"]["exe"]["icon"]
    assert (icon is not None) == present


def test_the_spec_analyses_the_gui_entry_point(spec):
    assert spec["_calls"]["analysis"].args[0] == ["app.py"]


def test_the_spec_passes_its_exclude_list_to_the_analysis(spec):
    assert spec["_calls"]["analysis"].kwargs["excludes"] == spec["EXCLUDES"]


def test_the_spec_does_not_collect_whole_packages(spec):
    """מלבד האייקון אין נתונים או בינאריים שנוספים ביד."""
    analysis = spec["_calls"]["analysis"]
    assert analysis.kwargs["binaries"] == []
    assert analysis.kwargs["hiddenimports"] == []
    assert analysis.kwargs["datas"] == spec["ICON_DATA"]
    assert len(spec["ICON_DATA"]) <= 1


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


# -------------------------------------------- שם עם גרסה, מידע גרסה וחתימה
def release_steps(workflows):
    return {step["name"]: step
            for step in workflows["release.yml"]["jobs"]["release"]["steps"]}


def test_the_exe_name_carries_the_release_version(workflows):
    validate = release_steps(workflows)["Validate release version"]["run"]
    assert 'OrechMenachem_$version' in validate
    assert "OM_EXE_NAME=$exeName" in validate
    assert "EXE_PATH=dist\\$exeName.exe" in validate


def test_the_release_tag_and_the_file_name_come_from_one_input(workflows):
    validate = release_steps(workflows)["Validate release version"]["run"]
    # שני הערכים נגזרים מאותו $version, ולכן אינם יכולים להתפצל.
    assert "RELEASE_TAG=$version" in validate
    assert validate.count("$exeName = ") == 1


def test_the_version_info_is_stamped_before_the_build(workflows):
    steps = [s["name"] for s in
             workflows["release.yml"]["jobs"]["release"]["steps"]]
    assert steps.index("Stamp Windows version info") < \
        steps.index("Build single-file portable EXE")


def test_the_stamped_version_info_is_generated_from_the_tag(workflows):
    stamp = release_steps(workflows)["Stamp Windows version info"]["run"]
    assert "stamp_version.py" in stamp
    assert "$env:RELEASE_TAG" in stamp
    assert "$env:OM_EXE_NAME.exe" in stamp


def test_the_build_receives_the_generated_version_file(workflows):
    build = release_steps(workflows)["Build single-file portable EXE"]
    assert build["env"]["OM_VERSION_FILE"] == "build\\version_info.generated.txt"


def test_the_build_never_overwrites_the_version_info_template(workflows):
    """התבנית שבמאגר היא קלט; הפלט נכתב תחת build/."""
    commands = " ".join(
        step.get("run", "")
        for step in workflows["release.yml"]["jobs"]["release"]["steps"])
    assert "--output \"build\\version_info.generated.txt\"" in commands \
        or "--output `\n            \"build" in commands \
        or "build\\version_info.generated.txt" in commands
    assert "--output version_info.txt" not in commands


def test_the_verify_step_checks_the_version_actually_landed(workflows):
    verify = release_steps(workflows)["Verify build output"]["run"]
    assert "FileVersion" in verify
    assert "RELEASE_TAG" in verify


def test_signing_runs_only_when_the_certificate_secret_is_configured(workflows):
    job = workflows["release.yml"]["jobs"]["release"]
    assert job["env"]["SIGNING_CERT_BASE64"] == \
        "${{ secrets.SIGNING_CERT_BASE64 }}"
    sign = release_steps(workflows)["Sign the EXE"]
    # הקשר secrets אינו זמין ב-if של שלב, ולכן הבדיקה היא על env.
    assert sign["if"] == "env.SIGNING_CERT_BASE64 != ''"


def test_a_skipped_signature_is_announced(workflows):
    skip = release_steps(workflows)["Report that signing was skipped"]
    assert skip["if"] == "env.SIGNING_CERT_BASE64 == ''"
    assert "::warning::" in skip["run"]


def test_signing_uses_sha256_and_a_timestamp_server(workflows):
    sign = release_steps(workflows)["Sign the EXE"]["run"]
    assert '"/fd", "SHA256"' in sign
    assert '"/td", "SHA256"' in sign
    assert "timestamp.digicert.com" in sign


def test_signing_confirms_a_signature_actually_landed(workflows):
    sign = release_steps(workflows)["Sign the EXE"]["run"]
    assert "Get-AuthenticodeSignature" in sign
    assert 'NotSigned' in sign


def test_an_untrusted_certificate_chain_warns_instead_of_failing(workflows):
    """תעודה עצמית נחתמת בהצלחה אך אינה נאמנת; אין להפיל על כך Release."""
    sign = release_steps(workflows)["Sign the EXE"]["run"]
    assert "::warning::" in sign
    assert "verify /pa" not in sign


def test_the_secret_is_cleaned_before_it_is_decoded(workflows):
    """base64 שהודבק מקובץ UTF-16 נושא BOM, ו-FromBase64String נופל עליו."""
    sign = release_steps(workflows)["Sign the EXE"]["run"]
    assert "-replace '\\s', ''" in sign
    assert "0xFEFF" in sign


def test_a_malformed_secret_explains_how_to_produce_a_good_one(workflows):
    sign = release_steps(workflows)["Sign the EXE"]["run"]
    assert "ToBase64String" in sign
    assert "Set-Clipboard" in sign


def test_an_empty_secret_is_caught_before_signing(workflows):
    sign = release_steps(workflows)["Sign the EXE"]["run"]
    assert "$encoded.Length -eq 0" in sign


def test_an_expired_certificate_fails_with_a_clear_message(workflows):
    """signtool מדווח על תעודה פגה בהודעה סתומה; הזרימה מסבירה במקומו."""
    sign = release_steps(workflows)["Sign the EXE"]["run"]
    assert "NotAfter" in sign
    assert "NotBefore" in sign
    assert "פגה" in sign


def test_a_certificate_about_to_expire_is_flagged_early(workflows):
    sign = release_steps(workflows)["Sign the EXE"]["run"]
    assert "AddDays(30)" in sign


def test_the_password_is_optional_because_a_pfx_may_have_none(workflows):
    sign = release_steps(workflows)["Sign the EXE"]["run"]
    assert 'if ($env:SIGNING_CERT_PASSWORD) {' in sign
    assert '$arguments += @("/p", $env:SIGNING_CERT_PASSWORD)' in sign


def test_the_private_key_is_always_deleted_from_the_runner(workflows):
    sign = release_steps(workflows)["Sign the EXE"]["run"]
    assert "finally" in sign
    assert "Remove-Item $pfx -Force" in sign


def test_the_certificate_never_comes_from_the_repository(workflows):
    """קובץ pfx במאגר הוא מפתח פרטי חשוף; הוא נקרא מסוד בלבד."""
    commands = " ".join(
        step.get("run", "")
        for step in workflows["release.yml"]["jobs"]["release"]["steps"])
    assert "$env:SIGNING_CERT_BASE64" in commands
    assert "FromBase64String($encoded)" in commands
    # התעודה נכתבת לתיקייה הזמנית של הרנר, ו-signtool מקבל רק אותה.
    assert 'Join-Path $env:RUNNER_TEMP "signing.pfx"' in commands
    assert '"/f", $pfx' in commands
    for repo_path in ("/f certificate.pfx", '"/f", "certificate.pfx"',
                      ".\\certificate.pfx"):
        assert repo_path not in commands


def test_signing_happens_before_publishing(workflows):
    steps = [s["name"] for s in
             workflows["release.yml"]["jobs"]["release"]["steps"]]
    assert steps.index("Sign the EXE") < steps.index("Upload build artifact")
    assert steps.index("Sign the EXE") < \
        steps.index("Create GitHub Release and upload EXE")


def test_the_release_publishes_the_versioned_file(workflows):
    steps = release_steps(workflows)
    assert "$env:EXE_PATH" in steps["Create GitHub Release and upload EXE"]["run"]
    assert steps["Upload build artifact"]["with"]["path"] == \
        "dist/OrechMenachem_v*.exe"


# ---------------------------------------------------------- שמירת התעודה
@pytest.mark.parametrize(
    "pattern", ["*.pfx", "*.p12", "*.key", "*base64*", "*.b64"],
)
def test_signing_secrets_are_gitignored(pattern):
    with open(os.path.join(PROJECT_ROOT, ".gitignore"), encoding="utf-8") as fh:
        assert pattern in fh.read().split()


@pytest.mark.parametrize(
    "name",
    ["certificate.pfx", "cert.p12", "signing.key", "cert.b64",
     "base64 של קובץ ה-pfx.txt", "2base64 של קובץ ה-pfx.txt",
     "my-base64-cert.txt"],
)
def test_git_would_ignore_every_shape_of_certificate_file(name):
    """base64 של pfx הוא מפתח פרטי לכל דבר; שם הקובץ לא אמור לשנות."""
    import subprocess

    result = subprocess.run(
        ["git", "check-ignore", "-q", "--no-index", "--", name],
        cwd=PROJECT_ROOT, capture_output=True, text=True,
    )
    assert result.returncode == 0, "%s אינו מסונן" % name


def test_no_certificate_material_is_tracked_in_git():
    import subprocess

    result = subprocess.run(
        ["git", "ls-files"], cwd=PROJECT_ROOT, capture_output=True, text=True,
    )
    tracked = result.stdout.lower().split()
    assert not [f for f in tracked
                if f.endswith((".pfx", ".p12", ".key", ".b64"))
                or "base64" in f]
