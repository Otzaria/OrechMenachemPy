# -*- coding: utf-8 -*-
"""בדיקות אסימוני העיצוב וגיליון הסגנון שנבנה מהם."""

import re

import pytest

import theme


COLOR_NAMES = [
    name for name in dir(theme)
    if name.isupper() and isinstance(getattr(theme, name), str)
    and getattr(theme, name).startswith("#")
]

SELECTORS = [
    "QWidget", "QToolTip", "QGroupBox", "QGroupBox::title", "QFrame#divider",
    "QPushButton", "QPushButton#btnPrimary", "QLineEdit", "QDoubleSpinBox",
    "QCheckBox::indicator", "QListWidget", "QTreeWidget", "QHeaderView::section",
    "QWidget#sizeControl", "QDoubleSpinBox#rowSpin", "QPushButton#sizeStepButton",
    "QPlainTextEdit", "QProgressBar", "QProgressBar::chunk", "QLabel",
    "QLabel#sectionHint", "QMessageBox", "QScrollBar:vertical",
    "QScrollBar::handle:horizontal",
]


@pytest.fixture(scope="module")
def stylesheet():
    return theme.build_stylesheet()


# ------------------------------------------------------------------ אסימונים
def test_the_module_defines_a_full_palette():
    assert len(COLOR_NAMES) >= 20


@pytest.mark.parametrize("name", COLOR_NAMES)
def test_every_color_token_is_a_six_digit_hex_value(name):
    assert re.fullmatch(r"#[0-9A-F]{6}", getattr(theme, name)), name


def test_scrollbar_active_thumb_reuses_the_primary_color():
    assert theme.SCROLLBAR_THUMB_ACTIVE == theme.PRIMARY


@pytest.mark.parametrize(
    "name", ["RADIUS", "INPUT_RADIUS", "INPUT_HEIGHT", "BASE_POINT_SIZE",
             "PRIMARY_BUTTON_POINT_SIZE"],
)
def test_metric_tokens_are_positive_integers(name):
    value = getattr(theme, name)
    assert isinstance(value, int) and value > 0


def test_the_primary_button_font_is_larger_than_the_base_font():
    assert theme.PRIMARY_BUTTON_POINT_SIZE > theme.BASE_POINT_SIZE


def test_input_fields_are_rounder_than_cards():
    assert theme.INPUT_RADIUS > theme.RADIUS


def test_default_font_matches_the_font_tokens(qapp):
    font = theme.default_font()
    assert font.family() == theme.FONT_FAMILY
    assert font.pointSize() == theme.BASE_POINT_SIZE


# --------------------------------------------------------------- גיליון סגנון
@pytest.mark.parametrize("selector", SELECTORS)
def test_the_stylesheet_styles_every_widget_the_ui_uses(stylesheet, selector):
    assert selector in stylesheet


def test_the_stylesheet_has_no_unfilled_placeholders(stylesheet):
    assert not re.search(r"\{[a-z_]+\}", stylesheet)


def test_the_stylesheet_uses_single_braces_after_formatting(stylesheet):
    assert "{{" not in stylesheet and "}}" not in stylesheet


@pytest.mark.parametrize(
    "name", ["PRIMARY", "ON_PRIMARY", "WINDOW_BACKGROUND", "SURFACE",
             "OUTLINE", "OUTLINE_VARIANT", "DISABLED_TEXT", "SELECTED_ROW",
             "HOVER_ON_PRIMARY", "SCROLLBAR_THUMB"],
)
def test_the_stylesheet_actually_uses_its_color_tokens(stylesheet, name):
    assert getattr(theme, name) in stylesheet


def test_the_stylesheet_carries_the_metric_tokens(stylesheet):
    assert "border-radius: %dpx" % theme.RADIUS in stylesheet
    assert "border-radius: %dpx" % theme.INPUT_RADIUS in stylesheet
    assert "min-height: %dpx" % theme.INPUT_HEIGHT in stylesheet
    assert "font-size: %dpt" % theme.BASE_POINT_SIZE in stylesheet
    assert "font-size: %dpt" % theme.PRIMARY_BUTTON_POINT_SIZE in stylesheet


def test_the_stylesheet_covers_the_interactive_states(stylesheet):
    for state in (":hover", ":pressed", ":focus", ":disabled", ":checked",
                  ":selected"):
        assert state in stylesheet


def test_the_stylesheet_is_stable_across_calls(stylesheet):
    assert theme.build_stylesheet() == stylesheet


def test_qt_accepts_the_stylesheet_without_dropping_it(qapp, stylesheet):
    from PyQt5.QtWidgets import QWidget

    widget = QWidget()
    widget.setStyleSheet(stylesheet)
    assert widget.styleSheet() == stylesheet
