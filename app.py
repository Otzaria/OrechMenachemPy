# -*- coding: utf-8 -*-
"""
app.py — ממשק גרפי (PyQt5) ל"עורך מנחם" — המרת קובצי Word לטקסט עם תגיות עיצוב.

הממשק:
    • בחירת קובץ אחד או כמה קבצי .docx
    • טבלת קבצים שבה לכל קובץ גודל טקסט וגודל הערות משלו, הניתנים
      לעריכה בשורה של אותו קובץ
    • ערכי ברירת מחדל שכל קובץ חדש שנוסף לרשימה מקבל
    • "זהה גדלים באופן אוטומטי לכל הקבצים" — סורק כל קובץ בנפרד וממלא את שורתו
    • בחירת תיקיית פלט (או שמירה ליד קובץ המקור)
    • כפתור "המר" שמריץ את ההמרה ברקע ומציג התקדמות ויומן

הערה: הגדלים אינם משנים את גודל הטקסט — הם נקודת הייחוס שקובעת מה
נחשב "רגיל" (ללא תגית); טקסט גדול מהם נעטף ב‑<big> וקטן מהם ב‑<small>.

מריצים:  python app.py
"""

import os
import sys

from PyQt5.QtCore import Qt, QThread, pyqtSignal, QSize
from PyQt5.QtGui import QFont, QIcon
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QTreeWidget, QTreeWidgetItem, QHeaderView, QLabel,
    QDoubleSpinBox, QLineEdit, QFileDialog, QPlainTextEdit, QProgressBar,
    QCheckBox, QGroupBox, QMessageBox, QAbstractItemView, QFrame,
)

from converter import convert_file, DocxConverter, ConversionError
import theme


# ------------------------------------------------------------------ אייקון
APP_ID = "otzaria.OrechMenachem"
ICON_RELATIVE_PATH = os.path.join("assets", "icon.ico")


def resource_path(relative):
    """
    נתיב למשאב שנארז עם התוכנה.

    ב-EXE של PyInstaller במצב onefile הקבצים נפרשים לתיקייה זמנית שנתיבה
    ב-sys._MEIPASS, ולכן אי אפשר להסתמך על מקום קובץ המקור.
    """
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, relative)


def app_icon():
    """האייקון של התוכנה, או אייקון ריק אם הקובץ אינו קיים."""
    path = resource_path(ICON_RELATIVE_PATH)
    return QIcon(path) if os.path.isfile(path) else QIcon()


def set_taskbar_identity():
    """
    מזהה את התהליך לווינדוס כאפליקציה עצמאית.

    בלי זה ווינדוס מקבץ את החלון תחת המפרש שהריץ אותו ומציג בשורת המשימות
    את האייקון של python.exe במקום את האייקון שהוגדר לחלון. רלוונטי בעיקר
    להרצה דרך "הפעלה.bat".
    """
    if sys.platform != "win32":
        return
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
    except Exception:  # noqa: BLE001 — נוי בלבד; אין להפיל את התוכנה על זה
        pass


class Worker(QThread):
    """מבצע את ההמרה בחוט נפרד כדי לא להקפיא את הממשק."""
    progress = pyqtSignal(int, int)      # (הושלמו, סה"כ)
    message = pyqtSignal(str)            # שורת יומן
    finished_all = pyqtSignal(int, int)  # (הצליחו, נכשלו)

    def __init__(self, jobs, out_dir, add_bom, make_notes):
        """jobs — רשימת (נתיב, גודל טקסט, גודל הערות) לכל קובץ בנפרד."""
        super().__init__()
        self.jobs = jobs
        self.out_dir = out_dir
        self.add_bom = add_bom
        self.make_notes = make_notes
        self._stop = False

    def stop(self):
        self._stop = True

    def run(self):
        total = len(self.jobs)
        ok = 0
        fail = 0
        for i, (path, normal_pt, notes_pt) in enumerate(self.jobs):
            if self._stop:
                self.message.emit("— בוטל על ידי המשתמש —")
                break
            name = os.path.basename(path)
            try:
                res = convert_file(
                    path, normal_pt, notes_pt,
                    out_dir=self.out_dir or None,
                    add_bom=self.add_bom, make_notes=self.make_notes,
                )
                ok += 1
                # הגדלים שבפועל שימשו לקובץ הזה — כדי שיהיה גלוי שכל
                # קובץ הומר לפי ההגדרה שבשורה שלו ולא לפי ערך גלובלי
                msg = "✓ %s   [טקסט %g · הערות %g]" % (name, normal_pt, notes_pt)
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


class SizeControl(QWidget):
    """בקר גודל עם שדה עריכה ושני כפתורי צעד גדולים ונגישים."""

    BUTTON_SIZE = 36

    def __init__(self, low, high, value, parent=None):
        super().__init__(parent)
        self.setObjectName("sizeControl")
        # מספרים וכפתורי +/- נקראים בצורה טבעית משמאל לימין, גם בממשק RTL.
        self.setLayoutDirection(Qt.LeftToRight)
        self.setFixedHeight(40)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(4)

        self.btn_decrease = QPushButton("−")
        self.btn_decrease.setObjectName("sizeStepButton")
        self.btn_decrease.setFixedSize(self.BUTTON_SIZE, self.BUTTON_SIZE)
        self.btn_decrease.setToolTip("הקטנת הגודל בחצי נקודה")
        self.btn_decrease.setAccessibleName("הקטנת גודל")
        self.btn_decrease.setAccessibleDescription("מקטין את הגודל בחצי נקודה")
        self.btn_decrease.setAutoRepeat(True)
        self.btn_decrease.setAutoRepeatDelay(350)
        self.btn_decrease.setAutoRepeatInterval(80)

        self.spin = QDoubleSpinBox()
        self.spin.setObjectName("rowSpin")
        self.spin.setRange(low, high)
        self.spin.setSingleStep(0.5)
        self.spin.setDecimals(1)
        self.spin.setValue(value)
        self.spin.setAlignment(Qt.AlignCenter)
        self.spin.setButtonSymbols(QDoubleSpinBox.NoButtons)
        self.spin.setFixedHeight(self.BUTTON_SIZE)
        self.spin.setMinimumWidth(56)
        self.spin.setAccessibleName("גודל בנקודות")
        self.spin.setAccessibleDescription(
            "אפשר להקליד ערך, או להשתמש במקשי החץ למעלה ולמטה")

        self.btn_increase = QPushButton("+")
        self.btn_increase.setObjectName("sizeStepButton")
        self.btn_increase.setFixedSize(self.BUTTON_SIZE, self.BUTTON_SIZE)
        self.btn_increase.setToolTip("הגדלת הגודל בחצי נקודה")
        self.btn_increase.setAccessibleName("הגדלת גודל")
        self.btn_increase.setAccessibleDescription("מגדיל את הגודל בחצי נקודה")
        self.btn_increase.setAutoRepeat(True)
        self.btn_increase.setAutoRepeatDelay(350)
        self.btn_increase.setAutoRepeatInterval(80)

        self.btn_decrease.clicked.connect(lambda: self.spin.stepDown())
        self.btn_increase.clicked.connect(lambda: self.spin.stepUp())
        self.spin.valueChanged.connect(self._sync_step_buttons)
        layout.addWidget(self.btn_decrease)
        layout.addWidget(self.spin, 1)
        layout.addWidget(self.btn_increase)
        self._sync_step_buttons()

    def _sync_step_buttons(self):
        """מונע פעולות שאין להן תוצאה כשמגיעים לקצות הטווח."""
        self.btn_decrease.setEnabled(self.spin.value() > self.spin.minimum())
        self.btn_increase.setEnabled(self.spin.value() < self.spin.maximum())

    def value(self):
        """שומר על אותו ממשק ציבורי של QDoubleSpinBox עבור הקוד הקיים."""
        return self.spin.value()

    def setValue(self, value):
        """שומר על אותו ממשק ציבורי של QDoubleSpinBox עבור הקוד הקיים."""
        self.spin.setValue(value)

    def sizeHint(self):
        return QSize(152, 40)


class MainWindow(QWidget):
    # רוחב עמודות הגדלים בטבלת הקבצים
    SIZE_COL_WIDTH = 160

    def __init__(self):
        super().__init__()
        self.worker = None
        self.setWindowTitle("עורך מנחם — המרת וורד לטקסט בפורמט אוצריא")
        # האייקון נקבע גם ברמת החלון וגם ברמת האפליקציה, כדי שיופיע בפס
        # הכותרת של החלון גם כשהוא נוצר בלי לעבור דרך main().
        self.setWindowIcon(app_icon())
        self.setLayoutDirection(Qt.RightToLeft)
        self.resize(835, 670)
        self._build_ui()

    @staticmethod
    def _divider():
        """קו מפריד דק בין קבוצות שורות בתוך כרטיס הגדרות."""
        line = QFrame()
        line.setObjectName("divider")
        line.setFixedHeight(1)
        return line

    @staticmethod
    def _row_spin(low, high, value):
        """בקר גודל מעוצב לשיבוץ בתוך שורה בטבלת הקבצים."""
        return SizeControl(low, high, value)

    def _add_file_row(self, path, normal_pt, notes_pt):
        """מוסיף שורת קובץ עם שתי תיבות גודל משלה."""
        item = QTreeWidgetItem([os.path.basename(path), "", ""])
        item.setData(0, Qt.UserRole, path)
        item.setToolTip(0, path)
        self.file_tree.addTopLevelItem(item)
        # setItemWidget מחזיק בבעלות על הווידג'טים — אין צורך במיפוי נפרד.
        # גובה מפורש מונע מהטבלה לדחוס את אזורי הלחיצה של כפתורי +/-.
        # הוא גם ממרכז את הבקר מול שם הקובץ באותה שורה.
        row_height = 44
        item.setSizeHint(0, QSize(1, row_height))
        item.setSizeHint(1, QSize(self.SIZE_COL_WIDTH, row_height))
        item.setSizeHint(2, QSize(self.SIZE_COL_WIDTH, row_height))
        self.file_tree.setItemWidget(item, 1, self._row_spin(3.0, 72.0, normal_pt))
        self.file_tree.setItemWidget(item, 2, self._row_spin(0.0, 72.0, notes_pt))
        return item

    def _rows(self):
        return [self.file_tree.topLevelItem(i)
                for i in range(self.file_tree.topLevelItemCount())]

    # ------------------------------------------------------------------ בניית ממשק
    def _build_ui(self):
        root = QVBoxLayout(self)

        # --- טבלת קבצים: לכל קובץ גודל טקסט וגודל הערות משלו ---
        files_box = QGroupBox("קבצים להמרה (.docx)")
        fb = QVBoxLayout(files_box)
        self.file_tree = QTreeWidget()
        self.file_tree.setColumnCount(3)
        self.file_tree.setHeaderLabels(["שם הקובץ", "גודל טקסט", "גודל הערות"])
        self.file_tree.setRootIsDecorated(False)   # אין חצי הרחבה — זו טבלה שטוחה
        # נדרש כדי ש-QTreeWidget יכבד את גובה השורה שנקבע לכל פריט.
        self.file_tree.setUniformRowHeights(False)
        self.file_tree.setSelectionMode(QAbstractItemView.ExtendedSelection)
        hdr = self.file_tree.header()
        hdr.setSectionResizeMode(0, QHeaderView.Stretch)
        hdr.setSectionResizeMode(1, QHeaderView.Fixed)
        hdr.setSectionResizeMode(2, QHeaderView.Fixed)
        hdr.setStretchLastSection(False)
        self.file_tree.setColumnWidth(1, self.SIZE_COL_WIDTH)
        self.file_tree.setColumnWidth(2, self.SIZE_COL_WIDTH)
        self.file_tree.setMinimumHeight(180)
        fb.addWidget(self.file_tree)

        btn_row = QHBoxLayout()
        self.btn_add = QPushButton("בחירת קבצים…")
        self.btn_add.clicked.connect(self.pick_files)
        self.btn_remove = QPushButton("הסרת נבחרים")
        self.btn_remove.clicked.connect(self.remove_selected)
        self.btn_clear = QPushButton("ניקוי הרשימה")
        self.btn_clear.clicked.connect(self.clear_files)

        self.btn_suggest = QPushButton("זהה גדלים באופן אוטומטי לכל הקבצים")
        self.btn_suggest.setToolTip(
            "סורק כל קובץ ברשימה בנפרד וממלא בשורה שלו את הגדלים שזוהו בו")
        self.btn_suggest.clicked.connect(self.suggest_sizes)
        self.file_tree.itemSelectionChanged.connect(self._update_file_actions)
        self._update_file_actions()

        btn_row = QHBoxLayout()

        btn_row.addWidget(self.btn_add)
        btn_row.addWidget(self.btn_remove)
        btn_row.addWidget(self.btn_clear)
        btn_row.addWidget(self.btn_suggest)
        btn_row.addStretch(1)
        fb.addLayout(btn_row)
        # הכפתור הארוך בשורה משלו: כך החלון יכול להישאר צר בלי לקצר את הטקסט.
        # טבלת הקבצים היא לב המסך — היא מקבלת את רוב המקום הפנוי, והיומן מעט
        root.addWidget(files_box, 3)

        # --- הגדרות ---
        opt_box = QGroupBox("הגדרות")
        grid = QGridLayout(opt_box)

        # שורת ברירת המחדל — הערכים שכל קובץ חדש שנוסף לרשימה יקבל.
        # אחרי ההוספה כל שורה בטבלה ניתנת לשינוי בנפרד.
        lbl_defaults = QLabel("ברירת מחדל לקבצים חדשים:")
        lbl_defaults.setObjectName("sectionHint")
        lbl_defaults.hide()  # מסתיר את תיבת הסימון
        grid.addWidget(lbl_defaults, 0, 0, 1, 5)

        # grid.addWidget(QLabel("גודל טקסט רגיל:"), 1, 0)
        self.spin_normal = QDoubleSpinBox()
        self.spin_normal.setRange(3.0, 72.0)
        self.spin_normal.setSingleStep(0.5)
        self.spin_normal.setDecimals(1)
        self.spin_normal.setValue(11.0)
        self.spin_normal.hide()  # מסתיר את תיבת הסימון
        grid.addWidget(self.spin_normal, 1, 1)

        # grid.addWidget(QLabel("גודל הערות רגיל:"), 1, 2)
        self.spin_notes = QDoubleSpinBox()
        self.spin_notes.setRange(0.0, 72.0)
        self.spin_notes.setSingleStep(0.5)
        self.spin_notes.setDecimals(1)
        self.spin_notes.setValue(10.0)
        self.spin_notes.hide()  # מסתיר את תיבת הסימון
        grid.addWidget(self.spin_notes, 1, 3)

        # grid.addWidget(self._divider(), 2, 0, 1, 5)

        grid.addWidget(QLabel("תיקיית פלט:"), 3, 0)
        self.edit_out = QLineEdit()
        self.edit_out.setPlaceholderText("ריק = שומר ליד קובץ המקור")
        grid.addWidget(self.edit_out, 3, 1, 1, 3)
        self.btn_out = QPushButton("בחירה…")
        self.btn_out.clicked.connect(self.pick_out_dir)
        grid.addWidget(self.btn_out, 3, 4)

        # grid.addWidget(self._divider(), 4, 0, 1, 5)

        self.chk_notes = QCheckBox("יצירת קובץ הערות נפרד (\"הערות על …\")")
        self.chk_notes.setChecked(True)
        self.chk_notes.hide()  # מסתיר את תיבת הסימון
        grid.addWidget(self.chk_notes, 5, 0, 1, 3)

        self.chk_bom = QCheckBox("שמירה עם BOM (כמו המאקרו)")
        self.chk_bom.setChecked(True)
        self.chk_bom.hide()  # מסתיר את תיבת הסימון
        grid.addWidget(self.chk_bom, 5, 3, 1, 2)

        root.addWidget(opt_box)

        # --- כפתור המרה + התקדמות ---
        run_row = QHBoxLayout()
        self.btn_convert = QPushButton("המר לטקסט")
        self.btn_convert.setObjectName("btnPrimary")
        self.btn_convert.setMinimumHeight(44)
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
        self.log.setMinimumHeight(230)
        root.addWidget(self.log, 1)

    # ------------------------------------------------------------------ פעולות
    def pick_files(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "בחירת קובצי Word", "",
            "מסמכי Word (*.docx *.docm);;כל הקבצים (*.*)")
        existing = set(self._all_files())
        # קבצים חדשים מקבלים את ערכי ברירת המחדל שבקטע "הגדרות";
        # אחר כך ניתן לשנות כל שורה בנפרד
        default_normal = self.spin_normal.value()
        default_notes = self.spin_notes.value()
        for p in paths:
            if p in existing:
                continue
            existing.add(p)   # מונע שורה כפולה גם כשאותו קובץ נבחר פעמיים
            self._add_file_row(p, default_normal, default_notes)
        self._update_file_actions()

    def remove_selected(self):
        for item in self.file_tree.selectedItems():
            idx = self.file_tree.indexOfTopLevelItem(item)
            if idx >= 0:
                self.file_tree.takeTopLevelItem(idx)
        self._update_file_actions()

    def clear_files(self):
        """מנקה את הרשימה ומרענן את מצבי כפתורי הפעולה שלה."""
        self.file_tree.clear()
        self._update_file_actions()

    def _update_file_actions(self):
        """פעולות רשימה זמינות רק כשיש להן יעד."""
        has_files = self.file_tree.topLevelItemCount() > 0
        self.btn_remove.setEnabled(bool(self.file_tree.selectedItems()))
        self.btn_clear.setEnabled(has_files)
        self.btn_suggest.setEnabled(has_files)

    def pick_out_dir(self):
        d = QFileDialog.getExistingDirectory(self, "בחירת תיקיית פלט")
        if d:
            self.edit_out.setText(d)

    def _all_files(self):
        return [item.data(0, Qt.UserRole) for item in self._rows()]

    def _all_jobs(self):
        """(נתיב, גודל טקסט, גודל הערות) לכל שורה — הגדלים נלקחים מהשורה עצמה."""
        jobs = []
        for item in self._rows():
            jobs.append((
                item.data(0, Qt.UserRole),
                self.file_tree.itemWidget(item, 1).value(),
                self.file_tree.itemWidget(item, 2).value(),
            ))
        return jobs

    def suggest_sizes(self):
        """סורק כל קובץ ברשימה בנפרד וממלא בשורה שלו את הגדלים שזוהו בו."""
        rows = self._rows()
        if not rows:
            QMessageBox.information(self, "עורך מנחם",
                                    "יש לבחור קובץ תחילה.")
            return
        detected = 0
        for item in rows:
            path = item.data(0, Qt.UserRole)
            name = os.path.basename(path)
            try:
                conv = DocxConverter(path)
            except Exception as e:  # noqa: BLE001
                self.log_msg("✗ %s — לא ניתן לקרוא את הקובץ: %s" % (name, e))
                continue
            normal = conv.suggest_body_size()
            notes = conv.suggest_notes_size()
            parts = []
            if normal:
                self.file_tree.itemWidget(item, 1).setValue(normal)
                parts.append("טקסט רגיל: %g" % normal)
            if notes:
                self.file_tree.itemWidget(item, 2).setValue(notes)
                parts.append("הערות: %g" % notes)
            if parts:
                detected += 1
                self.log_msg("זוהו גדלים ב‑%s — %s" % (name, " · ".join(parts)))
            else:
                self.log_msg("— %s: לא זוהו גדלים; יש להזין ידנית." % name)
        self.log_msg("סיום זיהוי: %d מתוך %d קבצים זוהו." % (detected, len(rows)))

    def log_msg(self, text):
        self.log.appendPlainText(text)

    def start_convert(self):
        jobs = self._all_jobs()
        if not jobs:
            QMessageBox.information(self, "עורך מנחם",
                                    "יש לבחור לפחות קובץ אחד.")
            return
        self.log.clear()
        self.progress.setMaximum(len(jobs))
        self.progress.setValue(0)
        self.btn_convert.setEnabled(False)
        self.btn_cancel.setEnabled(True)
        self.log_msg("מתחיל בהמרת %d קבצים…" % len(jobs))

        self.worker = Worker(
            jobs,
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
    # חייב לרוץ לפני יצירת החלון, אחרת ווינדוס כבר קבע את זהות התהליך.
    set_taskbar_identity()
    app = QApplication(sys.argv)
    app.setLayoutDirection(Qt.RightToLeft)
    app.setStyle("Fusion")
    app.setFont(theme.default_font())
    app.setStyleSheet(theme.build_stylesheet())
    # ברמת האפליקציה האייקון חל על שורת המשימות ועל כל חלון חדש.
    app.setWindowIcon(app_icon())
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
