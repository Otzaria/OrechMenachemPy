# -*- coding: utf-8 -*-
"""בדיקות יחידה למעברי החיפוש/החלפה שמדמים את המאקרו (ללא קבצי docx)."""

import pytest

from converter import (
    _macro_passes,
    _replace_literal,
    _strip_line_end_spaces,
    _wrap_pass,
)


PLAIN = (False, False, False, False, False, 22)
BOLD = (True, False, False, False, False, 22)
UNDERLINE = (False, True, False, False, False, 22)
ITALIC = (False, False, True, False, False, 22)
SUPER = (False, False, False, True, False, 22)
SUB = (False, False, False, False, True, 22)


def text(chars):
    return "".join(char for char, _ in chars)


def chars(value, props=PLAIN):
    return [[char, props] for char in value]


def sized(value, half_points, bold=False, underline=False):
    return chars(value, (bold, underline, False, False, False, half_points))


# ------------------------------------------------------------------ _wrap_pass
def test_wrap_pass_leaves_text_untouched_when_nothing_matches():
    source = chars("abc")
    assert text(_wrap_pass(source, lambda p: p[0], "<b>", "</b>")) == "abc"


def test_wrap_pass_wraps_the_whole_paragraph_when_everything_matches():
    source = chars("abc", BOLD)
    assert text(_wrap_pass(source, lambda p: p[0], "<b>", "</b>")) == "<b>abc</b>"


def test_wrap_pass_wraps_each_separate_range_on_its_own():
    source = chars("a", BOLD) + chars("-") + chars("b", BOLD)
    assert text(_wrap_pass(source, lambda p: p[0], "<b>", "</b>")) == "<b>a</b>-<b>b</b>"


def test_wrap_pass_gives_both_tags_the_properties_of_the_range_start():
    source = chars("a", BOLD) + chars("b", (True, True, False, False, False, 22))
    wrapped = _wrap_pass(source, lambda p: p[0], "<b>", "</b>")
    assert [props for _, props in wrapped] == [BOLD] * 3 + [BOLD, source[1][1]] + [BOLD] * 4


def test_wrap_pass_handles_an_empty_paragraph():
    assert _wrap_pass([], lambda p: p[0], "<b>", "</b>") == []


# ------------------------------------------------------------- _replace_literal
def test_replace_literal_leaves_text_without_the_pattern_untouched():
    assert text(_replace_literal(chars("abc"), "xy", "!")) == "abc"


def test_replace_literal_replaces_every_occurrence():
    assert text(_replace_literal(chars("axxbxxc"), "xx", "-")) == "a-b-c"


def test_replace_literal_keeps_a_partial_match_at_the_end_of_the_paragraph():
    assert text(_replace_literal(chars("ab"), "abc", "!")) == "ab"


def test_replace_literal_advances_one_char_when_only_the_first_char_matches():
    assert text(_replace_literal(chars("aab"), "ab", "!")) == "a!"


def test_replace_literal_can_delete_text_with_an_empty_replacement():
    assert text(_replace_literal(chars("a-b"), "-", "")) == "ab"


# -------------------------------------------------------- _strip_line_end_spaces
def test_strip_line_end_spaces_keeps_leading_spaces():
    assert text(_strip_line_end_spaces(chars("  a"))) == "  a"


def test_strip_line_end_spaces_clears_a_paragraph_of_only_spaces():
    assert _strip_line_end_spaces(chars("   ")) == []


def test_strip_line_end_spaces_cleans_every_manual_line_break():
    assert text(_strip_line_end_spaces(chars("a \nb  \nc "))) == "a\nb\nc"


def test_strip_line_end_spaces_keeps_tabs():
    assert text(_strip_line_end_spaces(chars("a\t"))) == "a\t"


# ------------------------------------------------------------- _macro_passes
def test_macro_passes_merges_a_bold_space_between_plain_words():
    source = chars("a") + chars(" ", BOLD) + chars("b")
    assert text(_macro_passes(source, 22)) == "a b"


def test_macro_passes_moves_a_trailing_bold_space_out_of_the_tag():
    source = chars("word ", BOLD) + chars("x")
    assert text(_macro_passes(source, 22)) == "<b>word</b> x"


def test_macro_passes_moves_edge_bold_spaces_out_of_the_tag():
    source = chars("a") + chars(" word ", BOLD) + chars("b")
    assert text(_macro_passes(source, 22)) == "a <b>word</b> b"


def test_macro_passes_keeps_an_inner_bold_space_inside_the_tag():
    source = chars("a ") + chars("w1 w2", BOLD) + chars(" b")
    assert text(_macro_passes(source, 22)) == "a <b>w1 w2</b> b"


def test_macro_passes_leaves_a_lone_smaller_space_untagged():
    source = chars("a") + sized(" ", 21) + chars("b")
    assert text(_macro_passes(source, 22)) == "a b"


def test_macro_passes_moves_edge_small_spaces_out_of_the_tag():
    source = chars("a") + sized(" (x) ", 20) + chars("b")
    assert text(_macro_passes(source, 22)) == "a <small>(x)</small> b"


def test_macro_passes_bold_word_with_smaller_spaces_around_it():
    # כמו במסמך אמיתי: רווחים מודגשים־וקטנים סביב מילה מודגשת בגודל רגיל,
    # ואחריהם סוגריים בגודל קטן — התגיות צמודות לטקסט והרווחים נקיים.
    source = (chars("a.") + sized(" ", 20, bold=True) + chars("word", BOLD)
              + sized(" ", 20, bold=True) + sized("(x)", 20) + chars(" b"))
    assert text(_macro_passes(source, 22)) == "a. <b>word</b> <small>(x)</small> b"


def test_macro_passes_merges_underline_ranges_separated_by_a_space():
    source = chars("a", UNDERLINE) + chars(" ") + chars("b", UNDERLINE)
    assert text(_macro_passes(source, 22)) == "<u>a b</u>"


def test_macro_passes_merges_italic_ranges_separated_by_a_space():
    source = chars("a", ITALIC) + chars(" ") + chars("b", ITALIC)
    assert text(_macro_passes(source, 22)) == "<i>a b</i>"


def test_macro_passes_merges_superscript_ranges_separated_by_a_space():
    source = chars("a", SUPER) + chars(" ") + chars("b", SUPER)
    assert text(_macro_passes(source, 22)) == "<sup>a b</sup>"


def test_macro_passes_merges_subscript_ranges_separated_by_a_space():
    source = chars("a", SUB) + chars(" ") + chars("b", SUB)
    assert text(_macro_passes(source, 22)) == "<sub>a b</sub>"


def test_macro_passes_nests_tags_of_a_run_that_is_bold_and_underlined():
    both = (True, True, False, False, False, 22)
    assert text(_macro_passes(chars("x", both), 22)) == "<u><b>x</b></u>"


def test_macro_passes_keeps_manual_line_breaks_as_paragraph_content():
    assert text(_macro_passes(chars("\n"), 22)) == "\n"
    assert text(_macro_passes(chars("a\nb"), 22)) == "a\nb"


def test_macro_passes_marks_smaller_text_with_the_small_tag():
    assert text(_macro_passes(sized("x", 20), 22)) == "<small>x</small>"


def test_macro_passes_leaves_text_at_the_reference_size_untagged():
    assert text(_macro_passes(sized("x", 22), 22)) == "x"


def test_macro_passes_wraps_small_text_around_existing_formatting():
    assert text(_macro_passes(sized("x", 20, underline=True), 22)) == \
        "<small><u>x</u></small>"


def test_macro_passes_ignores_sizes_above_the_macro_range():
    assert text(_macro_passes(sized("x", 42), 22)) == "x"
    assert text(_macro_passes(sized("x", 40), 22)) == "<big>x</big>"


def test_macro_passes_ignores_sizes_below_the_macro_range():
    assert text(_macro_passes(sized("x", 4), 22)) == "x"
    assert text(_macro_passes(sized("x", 6), 22)) == "<small>x</small>"


def test_macro_passes_skips_all_size_passes_without_a_reference_size():
    assert text(_macro_passes(sized("x", 30), 0)) == "x"


def test_macro_passes_ignores_runs_without_a_size():
    assert text(_macro_passes(chars("x", (False,) * 5 + (None,)), 22)) == "x"


def test_macro_passes_merges_size_ranges_separated_by_a_space():
    source = sized("a", 24) + sized(" ", 22) + sized("b", 24)
    assert text(_macro_passes(source, 22)) == "<big>a b</big>"


@pytest.mark.parametrize("value", ["", "   ", " "])
def test_macro_passes_returns_none_for_paragraphs_left_empty(value):
    assert _macro_passes(chars(value), 22) is None


@pytest.mark.parametrize("value", [" \n ", "\t ", " a "])
def test_macro_passes_keeps_paragraphs_with_content_after_stripping(value):
    assert _macro_passes(chars(value), 22) is not None
