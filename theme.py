# -*- coding: utf-8 -*-
"""
theme.py — עיצוב Material 3 בסגנון "אוצריא" ל"עורך מנחם".

מקור הצבעים: Otzaria (Flutter) בונה את ה-ColorScheme שלה עם
ColorScheme.fromSeed(seedColor: 0xFF2C1B02, variant: tonalSpot) — ראו
otzaria/lib/theme/app_seed_colors.dart (AppSeedColors.darkBrown) ו-
app_theme_data.dart (createColorScheme). הצבעים כאן חושבו בפועל מאותו
seed לפי אלגוריתם ה-HCT/CAM16 הרשמי של Material Color Utilities
(חבילת materialyoucolor, spec 2021, tonalSpot, light, contrast 0.0),
ולכן זהים לצבעים שרואים בפועל באוצריא.

רקע החלון (F6EDE5) הוא בדיוק AppSurfaces.panelBackground של אוצריא:
alphaBlend(surfaceContainerHighest @ 47.5%, surface) — הרקע המשמש שם
למסכי לוח/הגדרות/כלים, שזה בדיוק סוג המסך שהחלון הזה הוא.

רדיוס פינות אחיד לכפתורים/כרטיסים = 8px (AppTokens.radius), ושדות קלט
מעוגלים כמעט לגמרי (pill), בהתאם ל-AppInputTokens (compact: גובה 36,
רדיוס 20). הדגשת ריחוף (hover) על כפתורים היא overlay של primary/
onPrimary ב-8%/12% אלפא — בדיוק כמו ב-AppThemeData, ולא אפור גנרי.
"""

from PyQt5.QtGui import QFont

# ── Material 3 color roles (light, seed = AppSeedColors.darkBrown) ─────────
PRIMARY = "#805610"
ON_PRIMARY = "#FFFFFF"
PRIMARY_CONTAINER = "#FFDDB3"
ON_PRIMARY_CONTAINER = "#633F00"

SECONDARY_CONTAINER = "#FBDEBC"
ON_SECONDARY_CONTAINER = "#56442A"

SURFACE = "#FFF8F4"                 # AppSurfaces.card() — כרטיסים/רשימות/שדות
ON_SURFACE = "#201B13"
ON_SURFACE_VARIANT = "#4F4539"
SURFACE_CONTAINER = "#F9ECDF"
SURFACE_CONTAINER_HIGH = "#F3E6DA"
SURFACE_CONTAINER_HIGHEST = "#EDE0D4"
OUTLINE = "#817567"
OUTLINE_VARIANT = "#D3C4B4"

WINDOW_BACKGROUND = "#F6EDE5"       # AppSurfaces.panelBackground — רקע החלון

ERROR = "#BA1A1A"

# ── Overlay/blend states (primary|onPrimary at 8%/12% alpha, precomposited) ─
# על משטח SURFACE (#FFF8F4) — כפתורי outline/text ותפריטים
HOVER_ON_SURFACE = "#F5EBE2"        # primary @ 8% מעל surface
PRESSED_ON_SURFACE = "#F0E5D9"      # primary @ 12% מעל surface (גם focus)
SELECTED_ROW = "#FFF0E1"            # primaryContainer @ 30% מעל surface

# על כפתור מלא (primary) — overlay onPrimary (לבן) בהיר יותר בריחוף
HOVER_ON_PRIMARY = "#8A6423"        # onPrimary @ 8% מעל primary
PRESSED_ON_PRIMARY = "#8F6A2D"      # onPrimary @ 12% מעל primary

# מנוטרל (disabled) — onSurface @ 12%/38% מעל surface
DISABLED_CONTAINER = "#E4DDD9"
DISABLED_TEXT = "#AAA49F"

SCROLLBAR_THUMB = "#B9B0A9"         # onSurfaceVariant @ 40% מעל surface
SCROLLBAR_THUMB_ACTIVE = PRIMARY

# ── Shape / metrics ──────────────────────────────────────────────────────────
RADIUS = 8                  # AppTokens.radius — כפתורים, כרטיסים, פרוגרס
INPUT_RADIUS = 18           # קרוב ל-AppInputTokens.compactRadius (20) על גובה 36
INPUT_HEIGHT = 36           # AppInputTokens.compactHeight

FONT_FAMILY = "Segoe UI"    # Roboto אינו מותקן; Segoe UI היא החלופה הקרובה בווינדוס
BASE_POINT_SIZE = 10
PRIMARY_BUTTON_POINT_SIZE = 12


def default_font():
    return QFont(FONT_FAMILY, BASE_POINT_SIZE)


def build_stylesheet():
    return """
    /* ── בסיס ─────────────────────────────────────────────────────────── */
    QWidget {{
        background-color: {window_bg};
        color: {on_surface};
        font-family: '{font}';
        font-size: {base_pt}pt;
    }}

    QToolTip {{
        background-color: {surface_container_high};
        color: {on_surface};
        border: 1px solid {outline_variant};
        border-radius: {radius}px;
        padding: 4px 8px;
    }}

    /* ── כרטיסים (GroupBox) ───────────────────────────────────────────── */
    QGroupBox {{
        background-color: {surface};
        border: 1px solid {outline_variant};
        border-radius: {radius}px;
        margin-top: 22px;
        padding: 14px 10px 10px 10px;
        font-weight: 600;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        subcontrol-position: top left;
        padding: 0px 6px;
        color: {primary};
        background-color: {window_bg};
    }}

    /* ── מפריד בין קבוצות שורות בתוך כרטיס ────────────────────────────── */
    QFrame#divider {{
        background-color: {outline_variant};
        border: none;
        max-height: 1px;
        min-height: 1px;
    }}

    /* ── כפתורים — ברירת מחדל = Outlined/Tonal (רוב הכפתורים במסך) ──────── */
    QPushButton {{
        background-color: transparent;
        color: {primary};
        border: 1px solid {outline};
        border-radius: {radius}px;
        padding: 6px 16px;
        min-height: 24px;
        font-weight: 500;
    }}
    QPushButton:hover {{
        background-color: {hover_on_surface};
    }}
    QPushButton:pressed {{
        background-color: {pressed_on_surface};
    }}
    QPushButton:focus {{
        border: 2px solid {primary};
    }}
    QPushButton:disabled {{
        color: {disabled_text};
        border-color: {disabled_container};
    }}

    /* ── כפתור ראשי (Filled) — הפעולה המודגשת של המסך ────────────────── */
    QPushButton#btnPrimary {{
        background-color: {primary};
        color: {on_primary};
        border: none;
        padding: 8px 20px;
        min-height: 30px;
        font-size: {primary_pt}pt;
        font-weight: 700;
    }}
    QPushButton#btnPrimary:hover {{
        background-color: {hover_on_primary};
    }}
    QPushButton#btnPrimary:pressed {{
        background-color: {pressed_on_primary};
    }}
    QPushButton#btnPrimary:focus {{
        border: 2px solid {on_primary_container};
    }}
    QPushButton#btnPrimary:disabled {{
        background-color: {disabled_container};
        color: {disabled_text};
    }}

    /* ── שדות טקסט — מעוגלים כמעט לגמרי (pill), כמו ב-AppInputTokens ────── */
    QLineEdit {{
        background-color: {hover_on_surface};
        color: {on_surface};
        border: 1px solid transparent;
        border-radius: {input_radius}px;
        padding: 4px 14px;
        min-height: {input_height}px;
    }}
    QLineEdit:focus {{
        background-color: {pressed_on_surface};
        border: 1.5px solid {primary};
    }}
    QLineEdit:disabled {{
        background-color: {disabled_container};
        color: {disabled_text};
    }}

    /* ── שדות מספר ───────────────────────────────────────────────────── */
    QDoubleSpinBox, QSpinBox {{
        background-color: {hover_on_surface};
        color: {on_surface};
        border: 1px solid transparent;
        border-radius: {radius}px;
        padding: 4px 8px;
        min-height: {input_height}px;
    }}
    QDoubleSpinBox:focus, QSpinBox:focus {{
        background-color: {pressed_on_surface};
        border: 1.5px solid {primary};
    }}
    QDoubleSpinBox:disabled, QSpinBox:disabled {{
        background-color: {disabled_container};
        color: {disabled_text};
    }}
    /* ── תיבות סימון ──────────────────────────────────────────────────── */
    QCheckBox {{
        background-color: transparent;
        spacing: 8px;
        padding: 2px 0;
    }}
    QCheckBox::indicator {{
        width: 18px;
        height: 18px;
        border-radius: 4px;
        border: 2px solid {outline};
        background-color: transparent;
    }}
    QCheckBox::indicator:hover {{
        border-color: {primary};
    }}
    QCheckBox::indicator:checked {{
        border: 2px solid {primary};
        background-color: {primary};
        image: none;
    }}

    /* ── טבלת/רשימת קבצים ─────────────────────────────────────────────── */
    QListWidget, QTreeWidget {{
        background-color: {surface};
        border: 1px solid {outline_variant};
        border-radius: {radius}px;
        padding: 4px;
        outline: none;
    }}
    QListWidget::item, QTreeWidget::item {{
        border-radius: {radius}px;
        /* מאפשר לבקר הגודל (40px) ולשם הקובץ להיות ממורכזים באותה שורה. */
        padding: 1px 8px;
        margin: 1px 0;
    }}
    QListWidget::item:hover, QTreeWidget::item:hover {{
        background-color: {hover_on_surface};
    }}
    QListWidget::item:selected, QTreeWidget::item:selected {{
        background-color: {selected_row};
        color: {on_surface};
    }}

    /* כותרת הטבלה — שקופה ועדינה, מופרדת בקו תחתון בלבד */
    QHeaderView {{
        background-color: transparent;
    }}
    QHeaderView::section {{
        background-color: transparent;
        color: {on_surface_variant};
        border: none;
        border-bottom: 1px solid {outline_variant};
        padding: 4px 8px;
        font-weight: 600;
    }}

    /* בקרי גודל בשורות הטבלה: שדה מספר ושני כפתורי +/- גדולים.
       לא משתמשים בתת-הרכיבים הילידיים של QDoubleSpinBox, כי QSS עליהם
       מעלים את חיצי Fusion. */
    QWidget#sizeControl {{
        background-color: transparent;
    }}
    QDoubleSpinBox#rowSpin {{
        background-color: {surface};
        border: 1px solid {outline_variant};
        border-radius: 6px;
        /* תיקון אופטי: גופני Qt מציגים ספרות מעט נמוך ממרכז הריבוע. */
        padding: 0px 2px 4px 2px;
        /* 30px תוכן + 4px תיקון אופטי + גבולות = גובה חיצוני של 36px. */
        min-height: 30px;
    }}
    QDoubleSpinBox#rowSpin:hover {{
        border-color: {primary};
    }}
    QDoubleSpinBox#rowSpin:focus {{
        background-color: {pressed_on_surface};
        border: 1.5px solid {primary};
    }}
    QPushButton#sizeStepButton {{
        background-color: {surface_container_high};
        color: {on_primary_container};
        border: 1px solid {outline_variant};
        border-radius: 8px;
        /* תיקון אופטי: סימני +/− ממורכזים ביחס לריבוע הכפתור. */
        padding: 0px 0px 4px 0px;
        min-width: 34px;
        /* 30px תוכן + 4px תיקון אופטי + גבולות = גובה חיצוני של 36px. */
        min-height: 30px;
        font-size: 16pt;
        font-weight: 600;
    }}
    QPushButton#sizeStepButton:hover {{
        background-color: {primary_container};
        border-color: {primary};
    }}
    QPushButton#sizeStepButton:pressed {{
        background-color: {pressed_on_surface};
    }}
    QPushButton#sizeStepButton:focus {{
        border: 2px solid {primary};
    }}
    QPushButton#sizeStepButton:disabled {{
        background-color: {disabled_container};
        color: {disabled_text};
        border-color: {disabled_container};
    }}

    /* ── יומן פעולות ──────────────────────────────────────────────────── */
    QPlainTextEdit {{
        background-color: {surface};
        color: {on_surface};
        border: 1px solid {outline_variant};
        border-radius: {radius}px;
        padding: 6px;
    }}

    /* ── פס התקדמות ───────────────────────────────────────────────────── */
    QProgressBar {{
        background-color: {surface_container_highest};
        border: none;
        border-radius: 7px;
        min-height: 14px;
        max-height: 14px;
        text-align: center;
        color: {on_surface};
    }}
    QProgressBar::chunk {{
        background-color: {primary};
        border-radius: 7px;
    }}

    /* ── תוויות ───────────────────────────────────────────────────────── */
    QLabel {{
        background-color: transparent;
        color: {on_surface_variant};
    }}
    /* כותרת-משנה בתוך כרטיס (למשל "ברירת מחדל לקבצים חדשים") */
    QLabel#sectionHint {{
        color: {primary};
        font-weight: 600;
        padding-top: 2px;
    }}

    /* ── תיבות הודעה ──────────────────────────────────────────────────── */
    QMessageBox {{
        background-color: {surface};
    }}

    /* ── פסי גלילה ────────────────────────────────────────────────────── */
    QScrollBar:vertical {{
        background: transparent;
        width: 12px;
        margin: 2px;
    }}
    QScrollBar::handle:vertical {{
        background: {scrollbar_thumb};
        border-radius: 5px;
        min-height: 24px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: {scrollbar_thumb_active};
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0;
    }}
    QScrollBar:horizontal {{
        background: transparent;
        height: 12px;
        margin: 2px;
    }}
    QScrollBar::handle:horizontal {{
        background: {scrollbar_thumb};
        border-radius: 5px;
        min-width: 24px;
    }}
    QScrollBar::handle:horizontal:hover {{
        background: {scrollbar_thumb_active};
    }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
        width: 0;
    }}
    """.format(
        window_bg=WINDOW_BACKGROUND,
        on_surface=ON_SURFACE,
        on_surface_variant=ON_SURFACE_VARIANT,
        surface=SURFACE,
        surface_container_high=SURFACE_CONTAINER_HIGH,
        surface_container_highest=SURFACE_CONTAINER_HIGHEST,
        outline=OUTLINE,
        outline_variant=OUTLINE_VARIANT,
        primary=PRIMARY,
        on_primary=ON_PRIMARY,
        primary_container=PRIMARY_CONTAINER,
        on_primary_container=ON_PRIMARY_CONTAINER,
        hover_on_surface=HOVER_ON_SURFACE,
        pressed_on_surface=PRESSED_ON_SURFACE,
        selected_row=SELECTED_ROW,
        hover_on_primary=HOVER_ON_PRIMARY,
        pressed_on_primary=PRESSED_ON_PRIMARY,
        disabled_container=DISABLED_CONTAINER,
        disabled_text=DISABLED_TEXT,
        scrollbar_thumb=SCROLLBAR_THUMB,
        scrollbar_thumb_active=SCROLLBAR_THUMB_ACTIVE,
        radius=RADIUS,
        input_radius=INPUT_RADIUS,
        input_height=INPUT_HEIGHT,
        font=FONT_FAMILY,
        base_pt=BASE_POINT_SIZE,
        primary_pt=PRIMARY_BUTTON_POINT_SIZE,
    )
