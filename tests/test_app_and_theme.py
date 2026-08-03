from pathlib import Path

import app
import theme


def test_theme_builds_complete_stylesheet():
    stylesheet = theme.build_stylesheet()
    assert theme.default_font().family() == theme.FONT_FAMILY
    assert theme.PRIMARY in stylesheet
    assert "QPushButton#sizeStepButton" in stylesheet
    assert "{" in stylesheet and "{primary" not in stylesheet


def test_size_control_steps_and_disables_at_limits(qapp):
    control = app.SizeControl(3, 4, 3)
    assert not control.btn_decrease.isEnabled()
    assert control.btn_increase.isEnabled()
    control.btn_increase.click()
    assert control.value() == 3.5
    control.setValue(4)
    assert not control.btn_increase.isEnabled()
    assert control.btn_decrease.isEnabled()


def test_main_window_file_actions_and_jobs(qapp, tmp_path):
    window = app.MainWindow()
    assert not window.btn_remove.isEnabled()
    assert not window.btn_clear.isEnabled()
    assert not window.btn_suggest.isEnabled()

    first = window._add_file_row(str(tmp_path / "one.docx"), 11, 10)
    window._add_file_row(str(tmp_path / "two.docx"), 12, 9.5)
    window._update_file_actions()
    assert window._all_files() == [str(tmp_path / "one.docx"), str(tmp_path / "two.docx")]
    assert window._all_jobs() == [
        (str(tmp_path / "one.docx"), 11.0, 10.0),
        (str(tmp_path / "two.docx"), 12.0, 9.5),
    ]
    first.setSelected(True)
    qapp.processEvents()
    assert window.btn_remove.isEnabled()
    window.remove_selected()
    assert window.file_tree.topLevelItemCount() == 1
    window.clear_files()
    assert window.file_tree.topLevelItemCount() == 0
    assert not window.btn_clear.isEnabled()


def test_main_window_uses_tall_aligned_size_rows(qapp, tmp_path):
    window = app.MainWindow()
    item = window._add_file_row(str(tmp_path / "one.docx"), 11, 10)
    window.show()
    qapp.processEvents()
    control = window.file_tree.itemWidget(item, 1)
    rect = window.file_tree.visualItemRect(item)
    assert rect.height() == 44
    assert control.spin.height() == 36
    assert control.btn_increase.height() == 36
    window.close()


def test_suggest_sizes_updates_row_and_log(qapp, monkeypatch, tmp_path):
    class SuggestedConverter:
        def __init__(self, path):
            self.path = path

        def suggest_body_size(self):
            return 12.5

        def suggest_notes_size(self):
            return 9.5

    monkeypatch.setattr(app, "DocxConverter", SuggestedConverter)
    window = app.MainWindow()
    item = window._add_file_row(str(tmp_path / "one.docx"), 11, 10)
    window.suggest_sizes()
    assert window.file_tree.itemWidget(item, 1).value() == 12.5
    assert window.file_tree.itemWidget(item, 2).value() == 9.5
    assert "סיום זיהוי: 1 מתוך 1 קבצים זוהו." in window.log.toPlainText()


def test_worker_reports_success_and_failure(monkeypatch, tmp_path):
    def fake_convert(path, *args, **kwargs):
        if path.endswith("bad.docx"):
            raise RuntimeError("broken")
        return {"notes_path": None, "n_footnotes": 0}

    monkeypatch.setattr(app, "convert_file", fake_convert)
    worker = app.Worker(
        [(str(tmp_path / "good.docx"), 11, 10), (str(tmp_path / "bad.docx"), 11, 10)],
        "",
        True,
        True,
    )
    messages, progress, finished = [], [], []
    worker.message.connect(messages.append)
    worker.progress.connect(lambda done, total: progress.append((done, total)))
    worker.finished_all.connect(lambda ok, fail: finished.append((ok, fail)))
    worker.run()
    assert finished == [(1, 1)]
    assert progress == [(1, 2), (2, 2)]
    assert any("good.docx" in message for message in messages)
    assert any("broken" in message for message in messages)


def test_worker_honors_cancellation_before_first_file(monkeypatch, tmp_path):
    monkeypatch.setattr(app, "convert_file", lambda *args, **kwargs: AssertionError("must not run"))
    worker = app.Worker([(str(tmp_path / "one.docx"), 11, 10)], "", True, True)
    messages, finished = [], []
    worker.message.connect(messages.append)
    worker.finished_all.connect(lambda ok, fail: finished.append((ok, fail)))
    worker.stop()
    worker.run()
    assert messages == ["— בוטל על ידי המשתמש —"]
    assert finished == [(0, 0)]
