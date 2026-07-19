# -*- coding: utf-8 -*-
"""
app.py — ממשק גרפי (PyQt5) ל"עורך מנחם" — המרת קובצי Word לטקסט עם תגיות עיצוב.

הממשק:
    • בחירת קובץ אחד או כמה קבצי .docx
    • הגדרת גודל טקסט רגיל וגודל הערות ברירת מחדל
    • בחירת תיקיית פלט (או שמירה ליד קובץ המקור)
    • כפתור "המר" שמריץ את ההמרה ברקע ומציג התקדמות ויומן

מריצים:  python app.py
"""

import os
import sys

from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QListWidget, QListWidgetItem, QLabel, QDoubleSpinBox,
    QLineEdit, QFileDialog, QPlainTextEdit, QProgressBar, QCheckBox,
    QGroupBox, QMessageBox, QAbstractItemView,
)

from converter import convert_file, DocxConverter, ConversionError


class Worker(QThread):
    """מבצע את ההמרה בחוט נפרד כדי לא להקפיא את הממשק."""
    progress = pyqtSignal(int, int)      # (הושלמו, סה"כ)
    message = pyqtSignal(str)            # שורת יומן
    finished_all = pyqtSignal(int, int)  # (הצליחו, נכשלו)

    def __init__(self, files, normal_pt, notes_pt, out_dir, add_bom, make_notes):
        super().__init__()
        self.files = files
        self.normal_pt = normal_pt
        self.notes_pt = notes_pt
        self.out_dir = out_dir
        self.add_bom = add_bom
        self.make_notes = make_notes
        self._stop = False

    def stop(self):
        self._stop = True

    def run(self):
        total = len(self.files)
        ok = 0
        fail = 0
        for i, path in enumerate(self.files):
            if self._stop:
                self.message.emit("— בוטל על ידי המשתמש —")
                break
            name = os.path.basename(path)
            try:
                res = convert_file(
                    path, self.normal_pt, self.notes_pt,
                    out_dir=self.out_dir or None,
                    add_bom=self.add_bom, make_notes=self.make_notes,
                )
                ok += 1
                msg = "✓ %s" % name
                if res["notes_path"]:
                    msg += "   (+ %d הערות)" % res["n_footnotes"]
                self.message.emit(msg)
            except ConversionError as e:
                fail += 1
                self.message.emit("✗ %s — %s" % (name, e))
            except Exception as e:  # noqa: BLE001
                fail += 1
                self.message.emit("✗ %s — שגיאה: %s" % (name, e))
            self.progress.emit(i + 1, total)
        self.finished_all.emit(ok, fail)


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.worker = None
        self.setWindowTitle("עורך מנחם — המרה לטקסט עם תגיות")
        self.setLayoutDirection(Qt.RightToLeft)
        self.resize(760, 620)
        self._build_ui()

    # ------------------------------------------------------------------ בניית ממשק
    def _build_ui(self):
        root = QVBoxLayout(self)

        # --- רשימת קבצים ---
        files_box = QGroupBox("קבצים להמרה (.docx)")
        fb = QVBoxLayout(files_box)
        self.file_list = QListWidget()
        self.file_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        fb.addWidget(self.file_list)

        btn_row = QHBoxLayout()
        self.btn_add = QPushButton("בחירת קבצים…")
        self.btn_add.clicked.connect(self.pick_files)
        self.btn_remove = QPushButton("הסרת נבחרים")
        self.btn_remove.clicked.connect(self.remove_selected)
        self.btn_clear = QPushButton("ניקוי הרשימה")
        self.btn_clear.clicked.connect(self.file_list.clear)
        btn_row.addWidget(self.btn_add)
        btn_row.addWidget(self.btn_remove)
        btn_row.addWidget(self.btn_clear)
        btn_row.addStretch(1)
        fb.addLayout(btn_row)
        root.addWidget(files_box)

        # --- הגדרות ---
        opt_box = QGroupBox("הגדרות")
        grid = QGridLayout(opt_box)

        grid.addWidget(QLabel("גודל טקסט רגיל:"), 0, 0)
        self.spin_normal = QDoubleSpinBox()
        self.spin_normal.setRange(3.0, 72.0)
        self.spin_normal.setSingleStep(0.5)
        self.spin_normal.setDecimals(1)
        self.spin_normal.setValue(16.0)
        grid.addWidget(self.spin_normal, 0, 1)

        grid.addWidget(QLabel("גודל הערות רגיל:"), 0, 2)
        self.spin_notes = QDoubleSpinBox()
        self.spin_notes.setRange(0.0, 72.0)
        self.spin_notes.setSingleStep(0.5)
        self.spin_notes.setDecimals(1)
        self.spin_notes.setValue(14.0)
        grid.addWidget(self.spin_notes, 0, 3)

        self.btn_suggest = QPushButton("זהה גדלים מהקובץ הראשון")
        self.btn_suggest.clicked.connect(self.suggest_sizes)
        grid.addWidget(self.btn_suggest, 0, 4)

        grid.addWidget(QLabel("תיקיית פלט:"), 1, 0)
        self.edit_out = QLineEdit()
        self.edit_out.setPlaceholderText("ריק = שומר ליד קובץ המקור")
        grid.addWidget(self.edit_out, 1, 1, 1, 3)
        self.btn_out = QPushButton("בחירה…")
        self.btn_out.clicked.connect(self.pick_out_dir)
        grid.addWidget(self.btn_out, 1, 4)

        self.chk_notes = QCheckBox("יצירת קובץ הערות נפרד (\"הערות על …\")")
        self.chk_notes.setChecked(True)
        grid.addWidget(self.chk_notes, 2, 0, 1, 3)

        self.chk_bom = QCheckBox("שמירה עם BOM (כמו המאקרו)")
        self.chk_bom.setChecked(True)
        grid.addWidget(self.chk_bom, 2, 3, 1, 2)

        root.addWidget(opt_box)

        # --- כפתור המרה + התקדמות ---
        run_row = QHBoxLayout()
        self.btn_convert = QPushButton("המר לטקסט")
        self.btn_convert.setMinimumHeight(38)
        f = self.btn_convert.font()
        f.setPointSize(f.pointSize() + 2)
        f.setBold(True)
        self.btn_convert.setFont(f)
        self.btn_convert.clicked.connect(self.start_convert)
        run_row.addWidget(self.btn_convert, 2)

        self.btn_cancel = QPushButton("ביטול")
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.clicked.connect(self.cancel_convert)
        run_row.addWidget(self.btn_cancel, 1)
        root.addLayout(run_row)

        self.progress = QProgressBar()
        self.progress.setValue(0)
        root.addWidget(self.progress)

        # --- יומן ---
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setFont(QFont("Consolas", 10))
        root.addWidget(self.log, 1)

    # ------------------------------------------------------------------ פעולות
    def pick_files(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "בחירת קובצי Word", "",
            "מסמכי Word (*.docx *.docm);;כל הקבצים (*.*)")
        existing = {self.file_list.item(i).data(Qt.UserRole)
                    for i in range(self.file_list.count())}
        for p in paths:
            if p in existing:
                continue
            item = QListWidgetItem(os.path.basename(p))
            item.setData(Qt.UserRole, p)
            item.setToolTip(p)
            self.file_list.addItem(item)

    def remove_selected(self):
        for item in self.file_list.selectedItems():
            self.file_list.takeItem(self.file_list.row(item))

    def pick_out_dir(self):
        d = QFileDialog.getExistingDirectory(self, "בחירת תיקיית פלט")
        if d:
            self.edit_out.setText(d)

    def _all_files(self):
        return [self.file_list.item(i).data(Qt.UserRole)
                for i in range(self.file_list.count())]

    def suggest_sizes(self):
        files = self._all_files()
        if not files:
            QMessageBox.information(self, "עורך מנחם",
                                    "יש לבחור קובץ תחילה.")
            return
        try:
            conv = DocxConverter(files[0])
        except Exception as e:  # noqa: BLE001
            QMessageBox.warning(self, "עורך מנחם", "לא ניתן לקרוא את הקובץ:\n%s" % e)
            return
        normal = conv.suggest_body_size()
        notes = conv.suggest_notes_size()
        parts = []
        if normal:
            self.spin_normal.setValue(normal)
            parts.append("טקסט רגיל: %g" % normal)
        if notes:
            self.spin_notes.setValue(notes)
            parts.append("הערות: %g" % notes)
        if parts:
            self.log_msg("זוהו גדלים מ‑%s — %s" %
                         (os.path.basename(files[0]), " · ".join(parts)))
        else:
            self.log_msg("לא זוהו גדלים אוטומטית; יש להזין ידנית.")

    def log_msg(self, text):
        self.log.appendPlainText(text)

    def start_convert(self):
        files = self._all_files()
        if not files:
            QMessageBox.information(self, "עורך מנחם",
                                    "יש לבחור לפחות קובץ אחד.")
            return
        self.log.clear()
        self.progress.setMaximum(len(files))
        self.progress.setValue(0)
        self.btn_convert.setEnabled(False)
        self.btn_cancel.setEnabled(True)
        self.log_msg("מתחיל בהמרת %d קבצים…" % len(files))

        self.worker = Worker(
            files,
            self.spin_normal.value(),
            self.spin_notes.value(),
            self.edit_out.text().strip(),
            self.chk_bom.isChecked(),
            self.chk_notes.isChecked(),
        )
        self.worker.progress.connect(self.on_progress)
        self.worker.message.connect(self.log_msg)
        self.worker.finished_all.connect(self.on_finished)
        self.worker.start()

    def cancel_convert(self):
        if self.worker:
            self.worker.stop()
            self.btn_cancel.setEnabled(False)

    def on_progress(self, done, total):
        self.progress.setValue(done)

    def on_finished(self, ok, fail):
        self.btn_convert.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        self.log_msg("")
        self.log_msg("הסתיים: %d הצליחו, %d נכשלו." % (ok, fail))
        if fail == 0:
            QMessageBox.information(self, "עורך מנחם",
                                    "ההמרה הושלמה בהצלחה (%d קבצים)." % ok)
        else:
            QMessageBox.warning(self, "עורך מנחם",
                                "הסתיים עם שגיאות:\n%d הצליחו, %d נכשלו." % (ok, fail))


def main():
    app = QApplication(sys.argv)
    app.setLayoutDirection(Qt.RightToLeft)
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
