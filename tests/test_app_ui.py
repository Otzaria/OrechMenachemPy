# -*- coding: utf-8 -*-
"""בדיקות ממשק: בקר הגודל, טבלת הקבצים, פעולות החלון וחוט העבודה."""

import os

import pytest
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QAbstractItemView, QDoubleSpinBox, QFileDialog, QHeaderView, QMessageBox,
)

import app
import theme
from converter import ConversionError


@pytest.fixture
def window(qapp):
    win = app.MainWindow()
    yield win
    win.close()


@pytest.fixture
def silent_dialogs(monkeypatch):
    """אוסף קריאות לתיבות הודעה במקום להציג אותן."""
    calls = []
    monkeypatch.setattr(QMessageBox, "information",
                        lambda *args, **kwargs: calls.append(("information", args[2])))
    monkeypatch.setattr(QMessageBox, "warning",
                        lambda *args, **kwargs: calls.append(("warning", args[2])))
    return calls


# --------------------------------------------------------------- SizeControl
def test_size_control_configures_its_spin_box(qapp):
    control = app.SizeControl(3.0, 72.0, 11.0)
    assert control.spin.minimum() == 3.0
    assert control.spin.maximum() == 72.0
    assert control.spin.singleStep() == 0.5
    assert control.spin.decimals() == 1
    assert control.spin.value() == 11.0
    assert control.spin.buttonSymbols() == QDoubleSpinBox.NoButtons
    assert control.spin.alignment() & Qt.AlignCenter


def test_size_control_reads_left_to_right_even_in_an_rtl_window(qapp):
    control = app.SizeControl(3.0, 72.0, 11.0)
    assert control.layoutDirection() == Qt.LeftToRight
    assert control.objectName() == "sizeControl"


def test_size_control_step_buttons_are_large_and_repeat_when_held(qapp):
    control = app.SizeControl(3.0, 72.0, 11.0)
    for button in (control.btn_decrease, control.btn_increase):
        assert button.objectName() == "sizeStepButton"
        assert button.width() == app.SizeControl.BUTTON_SIZE
        assert button.height() == app.SizeControl.BUTTON_SIZE
        assert button.autoRepeat()
        assert button.toolTip()


def test_size_control_exposes_accessible_names_for_screen_readers(qapp):
    control = app.SizeControl(3.0, 72.0, 11.0)
    assert control.btn_decrease.accessibleName() == "הקטנת גודל"
    assert control.btn_increase.accessibleName() == "הגדלת גודל"
    assert control.spin.accessibleName() == "גודל בנקודות"
    assert control.spin.accessibleDescription()


def test_size_control_decrease_button_steps_down_by_half_a_point(qapp):
    control = app.SizeControl(3.0, 72.0, 11.0)
    control.btn_decrease.click()
    assert control.value() == 10.5


def test_size_control_set_value_is_clamped_to_the_range(qapp):
    control = app.SizeControl(3.0, 72.0, 11.0)
    control.setValue(500)
    assert control.value() == 72.0
    control.setValue(0)
    assert control.value() == 3.0


def test_size_control_keeps_both_buttons_active_inside_the_range(qapp):
    control = app.SizeControl(3.0, 72.0, 11.0)
    assert control.btn_decrease.isEnabled()
    assert control.btn_increase.isEnabled()


def test_size_control_size_hint_keeps_the_row_tall_enough(qapp):
    control = app.SizeControl(3.0, 72.0, 11.0)
    assert control.sizeHint().height() == 40
    assert control.height() == 40


# ------------------------------------------------------------- מבנה החלון
def test_main_window_uses_a_right_to_left_hebrew_layout(window):
    assert window.layoutDirection() == Qt.RightToLeft
    assert window.windowTitle() == "עורך מנחם — המרת וורד לטקסט בפורמט אוצריא"


def test_main_window_opens_at_the_designed_size(window):
    assert (window.width(), window.height()) == (835, 670)


def test_file_table_is_a_flat_three_column_table(window):
    tree = window.file_tree
    assert tree.columnCount() == 3
    labels = [tree.headerItem().text(i) for i in range(3)]
    assert labels == ["שם הקובץ", "גודל טקסט", "גודל הערות"]
    assert not tree.rootIsDecorated()
    assert not tree.uniformRowHeights()
    assert tree.selectionMode() == QAbstractItemView.ExtendedSelection


def test_size_columns_have_a_fixed_width(window):
    header = window.file_tree.header()
    assert header.sectionResizeMode(0) == QHeaderView.Stretch
    assert header.sectionResizeMode(1) == QHeaderView.Fixed
    assert header.sectionResizeMode(2) == QHeaderView.Fixed
    assert not header.stretchLastSection()
    assert window.file_tree.columnWidth(1) == app.MainWindow.SIZE_COL_WIDTH
    assert window.file_tree.columnWidth(2) == app.MainWindow.SIZE_COL_WIDTH


def test_convert_button_is_the_primary_action(window):
    assert window.btn_convert.objectName() == "btnPrimary"
    assert window.btn_convert.minimumHeight() == 44
    assert not window.btn_cancel.isEnabled()


def test_advanced_options_start_hidden_with_their_defaults(window):
    assert window.spin_normal.value() == 11.0
    assert window.spin_notes.value() == 10.0
    assert window.chk_notes.isChecked()
    assert window.chk_bom.isChecked()
    for widget in (window.spin_normal, window.spin_notes,
                   window.chk_notes, window.chk_bom):
        assert widget.isHidden()


def test_log_is_read_only(window):
    assert window.log.isReadOnly()


def test_divider_is_a_one_pixel_line(qapp):
    divider = app.MainWindow._divider()
    assert divider.objectName() == "divider"
    assert divider.height() == 1


# ------------------------------------------------------------ שורות הקבצים
def test_adding_a_row_stores_the_full_path_and_shows_the_base_name(window, tmp_path):
    path = str(tmp_path / "sub" / "file.docx")
    item = window._add_file_row(path, 11, 10)
    assert item.text(0) == "file.docx"
    assert item.data(0, Qt.UserRole) == path
    assert item.toolTip(0) == path


def test_each_row_gets_its_own_pair_of_size_controls(window, tmp_path):
    item = window._add_file_row(str(tmp_path / "a.docx"), 12.5, 9.5)
    assert window.file_tree.itemWidget(item, 1).value() == 12.5
    assert window.file_tree.itemWidget(item, 2).value() == 9.5


def test_notes_size_may_be_zero_while_body_size_may_not(window, tmp_path):
    item = window._add_file_row(str(tmp_path / "a.docx"), 11, 0)
    assert window.file_tree.itemWidget(item, 1).spin.minimum() == 3.0
    assert window.file_tree.itemWidget(item, 2).spin.minimum() == 0.0
    assert window.file_tree.itemWidget(item, 2).value() == 0.0


def test_editing_one_row_does_not_affect_another(window, tmp_path):
    first = window._add_file_row(str(tmp_path / "a.docx"), 11, 10)
    second = window._add_file_row(str(tmp_path / "b.docx"), 11, 10)
    window.file_tree.itemWidget(first, 1).setValue(14)
    assert window.file_tree.itemWidget(second, 1).value() == 11.0
    assert window._all_jobs()[0][1] == 14.0


def test_removing_several_selected_rows_at_once(window, qapp, tmp_path):
    first = window._add_file_row(str(tmp_path / "a.docx"), 11, 10)
    window._add_file_row(str(tmp_path / "b.docx"), 11, 10)
    third = window._add_file_row(str(tmp_path / "c.docx"), 11, 10)
    first.setSelected(True)
    third.setSelected(True)
    qapp.processEvents()
    window.remove_selected()
    assert [os.path.basename(p) for p in window._all_files()] == ["b.docx"]


def test_removing_with_no_selection_changes_nothing(window, tmp_path):
    window._add_file_row(str(tmp_path / "a.docx"), 11, 10)
    window.remove_selected()
    assert window.file_tree.topLevelItemCount() == 1


def test_list_actions_become_available_once_files_exist(window, tmp_path):
    assert not window.btn_clear.isEnabled()
    assert not window.btn_suggest.isEnabled()
    window._add_file_row(str(tmp_path / "a.docx"), 11, 10)
    window._update_file_actions()
    assert window.btn_clear.isEnabled()
    assert window.btn_suggest.isEnabled()
    assert not window.btn_remove.isEnabled()


# ------------------------------------------------------------ תיבות בחירה
def test_pick_files_adds_the_chosen_paths_with_the_default_sizes(
        window, monkeypatch, tmp_path):
    chosen = [str(tmp_path / "a.docx"), str(tmp_path / "b.docx")]
    monkeypatch.setattr(QFileDialog, "getOpenFileNames",
                        staticmethod(lambda *args, **kwargs: (chosen, "")))
    window.spin_normal.setValue(13.0)
    window.spin_notes.setValue(9.0)
    window.pick_files()
    assert window._all_files() == chosen
    assert window._all_jobs()[0] == (chosen[0], 13.0, 9.0)
    assert window.btn_clear.isEnabled()


def test_pick_files_does_not_add_a_file_already_in_the_list(
        window, monkeypatch, tmp_path):
    first = str(tmp_path / "a.docx")
    second = str(tmp_path / "b.docx")
    monkeypatch.setattr(QFileDialog, "getOpenFileNames",
                        staticmethod(lambda *args, **kwargs: ([first, second], "")))
    window.pick_files()
    window.pick_files()
    assert window._all_files() == [first, second]


def test_pick_files_adds_one_row_when_the_same_file_is_chosen_twice(
        window, monkeypatch, tmp_path):
    path = str(tmp_path / "a.docx")
    monkeypatch.setattr(QFileDialog, "getOpenFileNames",
                        staticmethod(lambda *args, **kwargs: ([path, path], "")))
    window.pick_files()
    assert window._all_files() == [path]


def test_pick_files_keeps_the_sizes_already_set_on_an_existing_row(
        window, monkeypatch, tmp_path):
    path = str(tmp_path / "a.docx")
    monkeypatch.setattr(QFileDialog, "getOpenFileNames",
                        staticmethod(lambda *args, **kwargs: ([path], "")))
    window.pick_files()
    window.file_tree.itemWidget(window.file_tree.topLevelItem(0), 1).setValue(15)
    window.pick_files()
    assert window._all_jobs() == [(path, 15.0, 10.0)]


def test_pick_files_with_a_cancelled_dialog_adds_nothing(window, monkeypatch):
    monkeypatch.setattr(QFileDialog, "getOpenFileNames",
                        staticmethod(lambda *args, **kwargs: ([], "")))
    window.pick_files()
    assert window._all_files() == []


def test_pick_out_dir_fills_in_the_chosen_directory(window, monkeypatch, tmp_path):
    monkeypatch.setattr(QFileDialog, "getExistingDirectory",
                        staticmethod(lambda *args, **kwargs: str(tmp_path)))
    window.pick_out_dir()
    assert window.edit_out.text() == str(tmp_path)


def test_pick_out_dir_keeps_the_previous_value_when_cancelled(window, monkeypatch):
    window.edit_out.setText("C:/keep")
    monkeypatch.setattr(QFileDialog, "getExistingDirectory",
                        staticmethod(lambda *args, **kwargs: ""))
    window.pick_out_dir()
    assert window.edit_out.text() == "C:/keep"


def test_output_directory_field_explains_the_empty_default(window):
    assert window.edit_out.placeholderText() == "ריק = שומר ליד קובץ המקור"


# ------------------------------------------------------------- זיהוי גדלים
class FakeConverter:
    """מדמה DocxConverter עם גדלים קבועים לצורכי בדיקה."""
    body = 12.5
    notes = 9.5

    def __init__(self, path):
        self.path = path

    def suggest_body_size(self):
        return self.body

    def suggest_notes_size(self):
        return self.notes


def test_suggest_sizes_without_files_asks_to_choose_one(window, silent_dialogs):
    window.suggest_sizes()
    assert silent_dialogs == [("information", "יש לבחור קובץ תחילה.")]
    assert window.log.toPlainText() == ""


def test_suggest_sizes_fills_only_the_values_it_found(window, monkeypatch, tmp_path):
    class BodyOnly(FakeConverter):
        notes = None

    monkeypatch.setattr(app, "DocxConverter", BodyOnly)
    item = window._add_file_row(str(tmp_path / "a.docx"), 11, 10)
    window.suggest_sizes()
    assert window.file_tree.itemWidget(item, 1).value() == 12.5
    assert window.file_tree.itemWidget(item, 2).value() == 10.0
    assert "טקסט רגיל: 12.5" in window.log.toPlainText()
    assert "הערות:" not in window.log.toPlainText()


def test_suggest_sizes_reports_a_file_with_no_size_information(
        window, monkeypatch, tmp_path):
    class Nothing(FakeConverter):
        body = None
        notes = None

    monkeypatch.setattr(app, "DocxConverter", Nothing)
    window._add_file_row(str(tmp_path / "a.docx"), 11, 10)
    window.suggest_sizes()
    log = window.log.toPlainText()
    assert "לא זוהו גדלים" in log
    assert "סיום זיהוי: 0 מתוך 1 קבצים זוהו." in log


def test_suggest_sizes_logs_an_unreadable_file_and_continues(
        window, monkeypatch, tmp_path):
    def converter_factory(path):
        if path.endswith("bad.docx"):
            raise ConversionError("לא ניתן לפתוח")
        return FakeConverter(path)

    monkeypatch.setattr(app, "DocxConverter", converter_factory)
    window._add_file_row(str(tmp_path / "bad.docx"), 11, 10)
    good = window._add_file_row(str(tmp_path / "good.docx"), 11, 10)
    window.suggest_sizes()
    log = window.log.toPlainText()
    assert "bad.docx — לא ניתן לקרוא את הקובץ" in log
    assert window.file_tree.itemWidget(good, 1).value() == 12.5
    assert "סיום זיהוי: 1 מתוך 2 קבצים זוהו." in log


def test_suggest_sizes_scans_every_file_separately(window, monkeypatch, tmp_path):
    scanned = []

    class Recording(FakeConverter):
        def __init__(self, path):
            scanned.append(os.path.basename(path))
            super().__init__(path)

    monkeypatch.setattr(app, "DocxConverter", Recording)
    window._add_file_row(str(tmp_path / "a.docx"), 11, 10)
    window._add_file_row(str(tmp_path / "b.docx"), 11, 10)
    window.suggest_sizes()
    assert scanned == ["a.docx", "b.docx"]


# --------------------------------------------------------------- הרצת המרה
def test_start_convert_without_files_asks_for_one(window, silent_dialogs):
    window.start_convert()
    assert silent_dialogs == [("information", "יש לבחור לפחות קובץ אחד.")]
    assert window.worker is None


def test_start_convert_prepares_the_ui_and_hands_the_rows_to_the_worker(
        window, monkeypatch, tmp_path):
    started = []

    class FakeWorker(app.Worker):
        def start(self):
            started.append(self)

    monkeypatch.setattr(app, "Worker", FakeWorker)
    window._add_file_row(str(tmp_path / "a.docx"), 12, 9)
    window.edit_out.setText("  " + str(tmp_path) + "  ")
    window.start_convert()

    assert len(started) == 1
    worker = started[0]
    assert worker.jobs == [(str(tmp_path / "a.docx"), 12.0, 9.0)]
    assert worker.out_dir == str(tmp_path)
    assert worker.add_bom is True
    assert worker.make_notes is True
    assert window.progress.maximum() == 1
    assert window.progress.value() == 0
    assert not window.btn_convert.isEnabled()
    assert window.btn_cancel.isEnabled()
    assert "מתחיל בהמרת 1 קבצים…" in window.log.toPlainText()


def test_start_convert_passes_the_checkbox_choices_along(
        window, monkeypatch, tmp_path):
    created = []
    monkeypatch.setattr(app, "Worker",
                        lambda *args: created.append(args) or _StubWorker())
    window._add_file_row(str(tmp_path / "a.docx"), 11, 10)
    window.chk_bom.setChecked(False)
    window.chk_notes.setChecked(False)
    window.start_convert()
    assert created[0][2] is False
    assert created[0][3] is False


class _StubWorker:
    """מחליף את Worker בבדיקות שאינן מריצות המרה אמיתית."""

    class _Signal:
        def connect(self, _handler):
            pass

    progress = _Signal()
    message = _Signal()
    finished_all = _Signal()

    def start(self):
        pass

    def stop(self):
        pass


def test_start_convert_clears_the_log_of_a_previous_run(
        window, monkeypatch, tmp_path):
    monkeypatch.setattr(app, "Worker", lambda *args: _StubWorker())
    window.log_msg("שורה ישנה")
    window._add_file_row(str(tmp_path / "a.docx"), 11, 10)
    window.start_convert()
    assert "שורה ישנה" not in window.log.toPlainText()


def test_cancel_convert_stops_the_worker_and_disables_itself(window, monkeypatch):
    stopped = []

    class Recording(_StubWorker):
        def stop(self):
            stopped.append(True)

    window.worker = Recording()
    window.btn_cancel.setEnabled(True)
    window.cancel_convert()
    assert stopped == [True]
    assert not window.btn_cancel.isEnabled()


def test_cancel_convert_without_a_running_worker_is_harmless(window):
    window.cancel_convert()
    assert window.worker is None


def test_progress_updates_follow_the_worker(window):
    window.progress.setMaximum(4)
    window.on_progress(3, 4)
    assert window.progress.value() == 3


def test_finishing_without_failures_shows_a_success_message(window, silent_dialogs):
    window.btn_convert.setEnabled(False)
    window.btn_cancel.setEnabled(True)
    window.on_finished(2, 0)
    assert window.btn_convert.isEnabled()
    assert not window.btn_cancel.isEnabled()
    assert "הסתיים: 2 הצליחו, 0 נכשלו." in window.log.toPlainText()
    assert silent_dialogs[0][0] == "information"
    assert "2" in silent_dialogs[0][1]


def test_finishing_with_failures_shows_a_warning(window, silent_dialogs):
    window.on_finished(1, 2)
    assert silent_dialogs[0][0] == "warning"
    assert "1 הצליחו, 2 נכשלו" in silent_dialogs[0][1]


def test_log_messages_are_appended_in_order(window):
    window.log_msg("ראשונה")
    window.log_msg("שנייה")
    assert window.log.toPlainText().splitlines() == ["ראשונה", "שנייה"]


# ------------------------------------------------------------------ Worker
def collect(worker):
    messages, progress, finished = [], [], []
    worker.message.connect(messages.append)
    worker.progress.connect(lambda done, total: progress.append((done, total)))
    worker.finished_all.connect(lambda ok, fail: finished.append((ok, fail)))
    worker.run()
    return messages, progress, finished


def test_worker_logs_the_sizes_actually_used_for_each_file(monkeypatch, tmp_path):
    monkeypatch.setattr(app, "convert_file",
                        lambda *a, **k: {"notes_path": None, "n_footnotes": 0})
    worker = app.Worker([(str(tmp_path / "a.docx"), 12.5, 9.5)], "", True, True)
    messages, _, finished = collect(worker)
    assert messages == ["✓ a.docx   [טקסט 12.5 · הערות 9.5]"]
    assert finished == [(1, 0)]


def test_worker_mentions_the_notes_file_when_one_was_written(monkeypatch, tmp_path):
    monkeypatch.setattr(
        app, "convert_file",
        lambda *a, **k: {"notes_path": "notes.txt", "n_footnotes": 3})
    worker = app.Worker([(str(tmp_path / "a.docx"), 11, 10)], "", True, True)
    messages, _, _ = collect(worker)
    assert messages == ["✓ a.docx   [טקסט 11 · הערות 10]   (+ 3 הערות)"]


def test_worker_reports_a_conversion_error_without_the_generic_prefix(
        monkeypatch, tmp_path):
    def failing(*args, **kwargs):
        raise ConversionError("קובץ פגום")

    monkeypatch.setattr(app, "convert_file", failing)
    worker = app.Worker([(str(tmp_path / "a.docx"), 11, 10)], "", True, True)
    messages, _, finished = collect(worker)
    assert messages == ["✗ a.docx — קובץ פגום"]
    assert finished == [(0, 1)]


def test_worker_reports_an_unexpected_error_with_a_prefix(monkeypatch, tmp_path):
    def failing(*args, **kwargs):
        raise ValueError("משהו אחר")

    monkeypatch.setattr(app, "convert_file", failing)
    worker = app.Worker([(str(tmp_path / "a.docx"), 11, 10)], "", True, True)
    messages, _, finished = collect(worker)
    assert messages == ["✗ a.docx — שגיאה: משהו אחר"]
    assert finished == [(0, 1)]


def test_worker_forwards_the_output_options_to_the_converter(monkeypatch, tmp_path):
    seen = {}

    def spy(path, normal_pt, notes_pt, out_dir=None, add_bom=True, make_notes=True):
        seen.update(path=path, normal_pt=normal_pt, notes_pt=notes_pt,
                    out_dir=out_dir, add_bom=add_bom, make_notes=make_notes)
        return {"notes_path": None, "n_footnotes": 0}

    monkeypatch.setattr(app, "convert_file", spy)
    worker = app.Worker([(str(tmp_path / "a.docx"), 11, 10)],
                        str(tmp_path), False, False)
    collect(worker)
    assert seen["out_dir"] == str(tmp_path)
    assert seen["add_bom"] is False
    assert seen["make_notes"] is False


def test_worker_turns_an_empty_output_directory_into_none(monkeypatch, tmp_path):
    seen = {}

    def spy(path, *args, **kwargs):
        seen.update(kwargs)
        return {"notes_path": None, "n_footnotes": 0}

    monkeypatch.setattr(app, "convert_file", spy)
    collect(app.Worker([(str(tmp_path / "a.docx"), 11, 10)], "", True, True))
    assert seen["out_dir"] is None


def test_worker_stops_between_files_when_cancelled(monkeypatch, tmp_path):
    worker = app.Worker(
        [(str(tmp_path / "a.docx"), 11, 10), (str(tmp_path / "b.docx"), 11, 10)],
        "", True, True)

    def convert_then_cancel(*args, **kwargs):
        worker.stop()
        return {"notes_path": None, "n_footnotes": 0}

    monkeypatch.setattr(app, "convert_file", convert_then_cancel)
    messages, progress, finished = collect(worker)
    assert messages[-1] == "— בוטל על ידי המשתמש —"
    assert progress == [(1, 2)]
    assert finished == [(1, 0)]


def test_worker_with_no_jobs_finishes_immediately(monkeypatch):
    monkeypatch.setattr(app, "convert_file",
                        lambda *a, **k: pytest.fail("must not be called"))
    messages, progress, finished = collect(app.Worker([], "", True, True))
    assert (messages, progress, finished) == ([], [], [(0, 0)])


def test_worker_counts_successes_and_failures_together(monkeypatch, tmp_path):
    def sometimes(path, *args, **kwargs):
        if "bad" in path:
            raise ConversionError("nope")
        return {"notes_path": None, "n_footnotes": 0}

    monkeypatch.setattr(app, "convert_file", sometimes)
    jobs = [(str(tmp_path / name), 11, 10)
            for name in ("a.docx", "bad1.docx", "b.docx", "bad2.docx")]
    _, progress, finished = collect(app.Worker(jobs, "", True, True))
    assert finished == [(2, 2)]
    assert progress == [(1, 4), (2, 4), (3, 4), (4, 4)]


# -------------------------------------------------------------------- main()
def test_main_applies_the_theme_and_starts_the_event_loop(qapp, monkeypatch):
    calls = {}

    class FakeApplication:
        def __init__(self, argv):
            calls["argv"] = argv

        def setLayoutDirection(self, direction):
            calls["direction"] = direction

        def setStyle(self, name):
            calls["style"] = name

        def setFont(self, font):
            calls["font"] = font.family()

        def setStyleSheet(self, sheet):
            calls["sheet"] = sheet

        def setWindowIcon(self, icon):
            calls["icon"] = icon

        def exec_(self):
            return 0

    class FakeWindow:
        def show(self):
            calls["shown"] = True

    monkeypatch.setattr(app, "QApplication", FakeApplication)
    monkeypatch.setattr(app, "MainWindow", FakeWindow)
    with pytest.raises(SystemExit) as exit_info:
        app.main()

    assert exit_info.value.code == 0
    assert calls["direction"] == Qt.RightToLeft
    assert calls["style"] == "Fusion"
    assert calls["font"] == theme.FONT_FAMILY
    assert theme.PRIMARY in calls["sheet"]
    assert calls["shown"] is True
    # האייקון מוגדר ברמת האפליקציה — משם הוא מגיע לשורת המשימות.
    assert not calls["icon"].isNull()


def test_main_declares_the_taskbar_identity_before_creating_the_window(
        qapp, monkeypatch):
    """סדר הקריאות חשוב: אחרי יצירת החלון ווינדוס כבר קבע את הזהות."""
    order = []

    class FakeApplication:
        def __init__(self, argv):
            order.append("application")

        def __getattr__(self, name):
            return lambda *args, **kwargs: None

        def exec_(self):
            return 0

    class FakeWindow:
        def __init__(self):
            order.append("window")

        def show(self):
            pass

    monkeypatch.setattr(app, "set_taskbar_identity",
                        lambda: order.append("identity"))
    monkeypatch.setattr(app, "QApplication", FakeApplication)
    monkeypatch.setattr(app, "MainWindow", FakeWindow)
    with pytest.raises(SystemExit):
        app.main()
    assert order == ["identity", "application", "window"]
