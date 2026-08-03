# -*- coding: utf-8 -*-
"""בדיקות ברמת המסמך: קריאת עיצוב, סגנונות, כותרות, הערות שוליים והצעות גודל."""

import zipfile

import pytest

from converter import ConversionError, DocxConverter, w

from conftest import (
    W,
    doc_defaults,
    footnote,
    footnotes_xml,
    para,
    rpr,
    run,
    style,
    styles_xml,
)


def convert_body(write_docx, body, styles=None, footnotes=None,
                 normal_pt=11, notes_pt=10):
    conv = DocxConverter(write_docx(body=body, styles=styles,
                                    footnotes=footnotes))
    return conv.convert(normal_pt, notes_pt)


# ------------------------------------------------------- קריאת מאפייני עיצוב
@pytest.mark.parametrize(
    ("attribute", "expected"),
    [("", "<b>x</b>"), (' w:val="1"', "<b>x</b>"), (' w:val="true"', "<b>x</b>"),
     (' w:val="0"', "x"), (' w:val="false"', "x"), (' w:val="off"', "x")],
)
def test_toggle_attribute_decides_whether_bold_applies(write_docx, attribute, expected):
    body = para(run("x", rpr("<w:bCs%s/>" % attribute)))
    assert convert_body(write_docx, body)[0] == expected


@pytest.mark.parametrize(
    ("underline", "expected"),
    [('<w:u w:val="single"/>', "<u>x</u>"), ('<w:u w:val="double"/>', "<u>x</u>"),
     ('<w:u w:val="none"/>', "x"), ("<w:u/>", "x")],
)
def test_underline_value_none_or_missing_means_no_underline(write_docx, underline, expected):
    assert convert_body(write_docx, para(run("x", rpr(underline))))[0] == expected


@pytest.mark.parametrize(
    ("vert_align", "expected"),
    [('<w:vertAlign w:val="superscript"/>', "<sup>x</sup>"),
     ('<w:vertAlign w:val="subscript"/>', "<sub>x</sub>"),
     ('<w:vertAlign w:val="baseline"/>', "x")],
)
def test_vertical_alignment_maps_to_sup_and_sub(write_docx, vert_align, expected):
    assert convert_body(write_docx, para(run("x", rpr(vert_align))))[0] == expected


def test_fractional_size_value_is_read_as_half_points(write_docx):
    body = para(run("x", rpr('<w:szCs w:val="24.0"/>')))
    assert convert_body(write_docx, body)[0] == "<big>x</big>"


def test_unreadable_size_value_is_ignored(write_docx):
    body = para(run("x", rpr('<w:szCs w:val="huge"/>')))
    assert convert_body(write_docx, body)[0] == "x"


def test_run_without_properties_uses_plain_formatting(write_docx):
    assert convert_body(write_docx, para(run("x")))[0] == "x"


# --------------------------------------------------------------- סגנונות
def test_document_defaults_apply_to_every_run(write_docx):
    styles = styles_xml(doc_defaults(rpr("<w:bCs/>")))
    assert convert_body(write_docx, para(run("x")), styles)[0] == "<b>x</b>"


def test_character_style_applies_its_formatting(write_docx):
    styles = styles_xml(style("Strong", kind="character", run_props=rpr("<w:bCs/>")))
    body = para(run("x", rpr('<w:rStyle w:val="Strong"/>')))
    assert convert_body(write_docx, body, styles)[0] == "<b>x</b>"


def test_paragraph_style_applies_its_formatting(write_docx):
    styles = styles_xml(style("Quote", run_props=rpr("<w:iCs/>")))
    body = para(run("x"), '<w:pPr><w:pStyle w:val="Quote"/></w:pPr>')
    assert convert_body(write_docx, body, styles)[0] == "<i>x</i>"


def test_default_paragraph_style_applies_without_an_explicit_pstyle(write_docx):
    styles = styles_xml(style("Normal", default=True, run_props=rpr("<w:bCs/>")))
    assert convert_body(write_docx, para(run("x")), styles)[0] == "<b>x</b>"


def test_run_properties_override_the_paragraph_style(write_docx):
    styles = styles_xml(style("Quote", run_props=rpr("<w:bCs/>")))
    body = para(run("x", rpr('<w:bCs w:val="0"/>')),
                '<w:pPr><w:pStyle w:val="Quote"/></w:pPr>')
    assert convert_body(write_docx, body, styles)[0] == "x"


def test_character_style_overrides_the_paragraph_style(write_docx):
    styles = styles_xml(
        style("Quote", run_props=rpr("<w:bCs/>")),
        style("Plain", kind="character", run_props=rpr('<w:bCs w:val="0"/>')),
    )
    body = para(run("x", rpr('<w:rStyle w:val="Plain"/>')),
                '<w:pPr><w:pStyle w:val="Quote"/></w:pPr>')
    assert convert_body(write_docx, body, styles)[0] == "x"


def test_formatting_is_inherited_along_the_basedon_chain(write_docx):
    styles = styles_xml(
        style("Base", run_props=rpr("<w:bCs/>")),
        style("Child", based_on="Base"),
    )
    body = para(run("x"), '<w:pPr><w:pStyle w:val="Child"/></w:pPr>')
    assert convert_body(write_docx, body, styles)[0] == "<b>x</b>"


def test_a_basedon_cycle_does_not_hang_the_converter(write_docx):
    styles = styles_xml(
        style("A", based_on="B"),
        style("B", based_on="A"),
    )
    body = para(run("x"), '<w:pPr><w:pStyle w:val="A"/></w:pPr>')
    assert convert_body(write_docx, body, styles)[0] == "x"


def test_unknown_style_id_is_ignored(write_docx):
    styles = styles_xml(style("Known", run_props=rpr("<w:bCs/>")))
    body = para(run("x"), '<w:pPr><w:pStyle w:val="Missing"/></w:pPr>')
    assert convert_body(write_docx, body, styles)[0] == "x"


def test_style_without_an_id_is_skipped(write_docx):
    styles = '<w:styles xmlns:w="%s"><w:style w:type="paragraph"/></w:styles>' % W
    conv = DocxConverter(write_docx(body=para(run("x")), styles=styles))
    assert conv.styles == {}


def test_document_without_styles_part_still_converts(write_docx):
    conv = DocxConverter(write_docx(body=para(run("x"))))
    assert conv.styles == {}
    assert conv.default_rpr == {}
    assert conv.convert(11, 10)[0] == "x"


# ------------------------------------------------------------------ כותרות
@pytest.mark.parametrize("level", [0, 1, 4, 8])
def test_outline_level_in_the_paragraph_becomes_a_heading_tag(write_docx, level):
    body = para(run("כותרת"), '<w:pPr><w:outlineLvl w:val="%d"/></w:pPr>' % level)
    expected = "<h%d>כותרת</h%d>" % (level + 1, level + 1)
    assert convert_body(write_docx, body)[0] == expected


@pytest.mark.parametrize("level", ["9", "-1", "abc"])
def test_outline_level_outside_the_heading_range_stays_body_text(write_docx, level):
    body = para(run("x"), '<w:pPr><w:outlineLvl w:val="%s"/></w:pPr>' % level)
    assert convert_body(write_docx, body)[0] == "x"


def test_heading_level_is_taken_from_the_style_chain(write_docx):
    styles = styles_xml(
        style("Heading2", outline=1),
        style("MyHeading", based_on="Heading2"),
    )
    body = para(run("x"), '<w:pPr><w:pStyle w:val="MyHeading"/></w:pPr>')
    assert convert_body(write_docx, body, styles)[0] == "<h2>x</h2>"


def test_paragraph_outline_level_wins_over_the_style(write_docx):
    styles = styles_xml(style("Heading1", outline=0))
    body = para(
        run("x"),
        '<w:pPr><w:pStyle w:val="Heading1"/><w:outlineLvl w:val="2"/></w:pPr>',
    )
    assert convert_body(write_docx, body, styles)[0] == "<h3>x</h3>"


def test_headings_drop_character_tags_and_manual_breaks(write_docx):
    body = para(
        run("a", rpr("<w:bCs/>")) + "<w:r><w:br/></w:r>" + run("b", rpr("<w:iCs/>")),
        '<w:pPr><w:outlineLvl w:val="0"/></w:pPr>',
    )
    assert convert_body(write_docx, body)[0] == "<h1>a b</h1>"


def test_empty_heading_paragraph_is_dropped(write_docx):
    body = (
        para(run("   "), '<w:pPr><w:outlineLvl w:val="0"/></w:pPr>')
        + para(run("body"))
    )
    assert convert_body(write_docx, body)[0] == "body"


def test_heading_keeps_footnote_markers(write_docx):
    body = para(
        run("כותרת") + '<w:r><w:footnoteReference w:id="1"/></w:r>',
        '<w:pPr><w:outlineLvl w:val="0"/></w:pPr>',
    )
    footnotes = footnotes_xml(footnote("1", para(run("הערה"))))
    text, notes = convert_body(write_docx, body, footnotes=footnotes)
    assert text == "<h1>כותרת<sup>1</sup></h1>"
    assert notes == "<sup>1</sup> הערה\r\n"


def test_heading_style_without_outline_level_is_body_text(write_docx):
    styles = styles_xml(style("Fancy", run_props=rpr("<w:bCs/>")))
    body = para(run("x"), '<w:pPr><w:pStyle w:val="Fancy"/></w:pPr>')
    assert convert_body(write_docx, body, styles)[0] == "<b>x</b>"


# ------------------------------------------------------- תווים מיוחדים בפסקה
def test_tab_is_kept_as_a_tab_character(write_docx):
    body = para(run("a") + "<w:r><w:tab/></w:r>" + run("b"))
    assert convert_body(write_docx, body)[0] == "a\tb"


def test_manual_break_becomes_a_crlf_inside_the_same_paragraph(write_docx):
    body = para(run("a") + "<w:r><w:br/></w:r>" + run("b"))
    assert convert_body(write_docx, body)[0] == "a\r\nb"


def test_carriage_return_element_behaves_like_a_manual_break(write_docx):
    body = para(run("a") + "<w:r><w:cr/></w:r>" + run("b"))
    assert convert_body(write_docx, body)[0] == "a\r\nb"


def test_non_breaking_hyphen_becomes_a_plain_hyphen(write_docx):
    body = para(run("a") + "<w:r><w:noBreakHyphen/></w:r>" + run("b"))
    assert convert_body(write_docx, body)[0] == "a-b"


def test_empty_text_element_is_skipped(write_docx):
    body = para(run("") + run("x"))
    assert convert_body(write_docx, body)[0] == "x"


def test_spaces_before_a_manual_break_are_removed(write_docx):
    body = para(run("a  ") + "<w:r><w:br/></w:r>" + run("b  "))
    assert convert_body(write_docx, body)[0] == "a\r\nb"


# -------------------------------------------------------------- פסקאות ריקות
def test_empty_paragraphs_in_the_middle_are_dropped(write_docx):
    body = para(run("a")) + para("") + para(run("   ")) + para(run("b"))
    assert convert_body(write_docx, body)[0] == "a\r\nb"


def test_empty_paragraphs_at_the_end_survive_as_blank_lines(write_docx):
    body = para(run("a")) + para("") + para("")
    assert convert_body(write_docx, body)[0] == "a\r\n\r\n"


def test_a_document_of_only_empty_paragraphs_yields_blank_lines(write_docx):
    assert convert_body(write_docx, para("") + para(""))[0] == "\r\n"


def test_an_empty_body_converts_to_an_empty_string(write_docx):
    assert convert_body(write_docx, "") == ("", None)


# ------------------------------------------------------------ הערות שוליים
def test_footnote_numbers_follow_the_order_of_appearance_in_the_body(write_docx):
    body = (
        para(run("a") + '<w:r><w:footnoteReference w:id="7"/></w:r>')
        + para(run("b") + '<w:r><w:footnoteReference w:id="3"/></w:r>')
    )
    footnotes = footnotes_xml(
        footnote("3", para(run("שלוש"))),
        footnote("7", para(run("שבע"))),
    )
    text, notes = convert_body(write_docx, body, footnotes=footnotes)
    assert text == "a<sup>1</sup>\r\nb<sup>2</sup>"
    assert notes == "<sup>1</sup> שבע\r\n<sup>2</sup> שלוש\r\n"


def test_reference_to_a_missing_footnote_is_dropped(write_docx):
    body = para(run("a") + '<w:r><w:footnoteReference w:id="99"/></w:r>')
    footnotes = footnotes_xml(footnote("1", para(run("הערה"))))
    assert convert_body(write_docx, body, footnotes=footnotes) == ("a", None)


def test_separator_footnotes_are_not_treated_as_real_notes(write_docx):
    footnotes = footnotes_xml(
        footnote("-1", para(run("sep")), kind="separator"),
        footnote("0", para(run("cont")), kind="continuationSeparator"),
        footnote("1", para(run("הערה"))),
    )
    conv = DocxConverter(write_docx(body=para(run("a")), footnotes=footnotes))
    assert list(conv.footnotes) == ["1"]


def test_footnote_paragraphs_are_joined_with_line_break_tags(write_docx):
    body = para(run("a") + '<w:r><w:footnoteReference w:id="1"/></w:r>')
    footnotes = footnotes_xml(
        footnote("1", para(run("ראשונה")) + para(run("שנייה"))),
    )
    assert convert_body(write_docx, body, footnotes=footnotes)[1] == \
        "<sup>1</sup> ראשונה<br>שנייה\r\n"


def test_footnote_manual_breaks_become_line_break_tags(write_docx):
    body = para(run("a") + '<w:r><w:footnoteReference w:id="1"/></w:r>')
    footnotes = footnotes_xml(
        footnote("1", para(run("א") + "<w:r><w:br/></w:r>" + run("ב"))),
    )
    assert convert_body(write_docx, body, footnotes=footnotes)[1] == \
        "<sup>1</sup> א<br>ב\r\n"


def test_empty_paragraphs_around_a_footnote_are_trimmed(write_docx):
    body = para(run("a") + '<w:r><w:footnoteReference w:id="1"/></w:r>')
    footnotes = footnotes_xml(
        footnote("1", para("") + para(run("תוכן")) + para("")),
    )
    assert convert_body(write_docx, body, footnotes=footnotes)[1] == \
        "<sup>1</sup> תוכן\r\n"


def test_footnote_reference_mark_and_the_space_after_it_are_removed(write_docx):
    body = para(run("a") + '<w:r><w:footnoteReference w:id="1"/></w:r>')
    footnotes = footnotes_xml(
        footnote("1", '<w:p><w:r><w:footnoteRef/><w:t>  שתי רווחים</w:t></w:r></w:p>'),
    )
    assert convert_body(write_docx, body, footnotes=footnotes)[1] == \
        "<sup>1</sup>  שתי רווחים\r\n"


def test_nested_footnote_reference_inside_a_footnote_is_skipped(write_docx):
    body = para(run("a") + '<w:r><w:footnoteReference w:id="1"/></w:r>')
    footnotes = footnotes_xml(
        footnote("1", para(run("תוכן") + '<w:r><w:footnoteReference w:id="2"/></w:r>')),
        footnote("2", para(run("שנייה"))),
    )
    text, notes = convert_body(write_docx, body, footnotes=footnotes)
    assert text == "a<sup>1</sup>"
    assert notes == "<sup>1</sup> תוכן\r\n"


def test_footnote_formatting_uses_the_notes_reference_size(write_docx):
    body = para(run("a") + '<w:r><w:footnoteReference w:id="1"/></w:r>')
    footnotes = footnotes_xml(
        footnote("1", para(run("קטן", rpr('<w:szCs w:val="18"/>')))),
    )
    conv = DocxConverter(write_docx(body=body, footnotes=footnotes))
    assert conv.convert(11, 10)[1] == "<sup>1</sup> <small>קטן</small>\r\n"
    assert conv.convert(11, 9)[1] == "<sup>1</sup> קטן\r\n"


def test_the_same_footnote_referenced_twice_keeps_one_number(write_docx):
    body = para(
        run("a") + '<w:r><w:footnoteReference w:id="1"/></w:r>'
        + run("b") + '<w:r><w:footnoteReference w:id="1"/></w:r>'
    )
    footnotes = footnotes_xml(footnote("1", para(run("הערה"))))
    text, notes = convert_body(write_docx, body, footnotes=footnotes)
    assert text == "a<sup>1</sup>b<sup>1</sup>"
    assert notes == "<sup>1</sup> הערה\r\n"


def test_footnotes_part_without_references_produces_no_notes_file(write_docx):
    footnotes = footnotes_xml(footnote("1", para(run("לא בשימוש"))))
    assert convert_body(write_docx, para(run("a")), footnotes=footnotes)[1] is None


def test_document_without_a_footnotes_part_has_no_footnotes(write_docx):
    conv = DocxConverter(write_docx(body=para(run("a"))))
    assert conv.footnotes == {}


# ------------------------------------------------------------------ שגיאות
def test_missing_body_element_raises_conversion_error(write_docx):
    path = write_docx(document='<w:document xmlns:w="%s"/>' % W)
    with pytest.raises(ConversionError, match="body"):
        DocxConverter(path).convert(11, 10)


def test_malformed_document_xml_raises_conversion_error(tmp_path):
    path = tmp_path / "broken.docx"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("word/document.xml", "<w:document")
    with pytest.raises(Exception):
        DocxConverter(path)


def test_missing_file_raises_conversion_error(tmp_path):
    with pytest.raises(ConversionError, match="docx"):
        DocxConverter(tmp_path / "nope.docx")


# ------------------------------------------------------------- הצעות גודל
def test_suggested_body_size_is_none_without_any_size_information(write_docx):
    conv = DocxConverter(write_docx(body=para(run("x"))))
    assert conv.suggest_body_size() is None


def test_suggested_body_size_is_weighted_by_the_amount_of_text(write_docx):
    body = para(
        run("עשרה תווים", rpr('<w:szCs w:val="20"/>'))
        + run("קצר", rpr('<w:szCs w:val="24"/>'))
    )
    conv = DocxConverter(write_docx(body=body))
    assert conv.suggest_body_size() == 10.0


def test_suggested_body_size_ignores_heading_paragraphs(write_docx):
    body = (
        para(run("כותרת ארוכה מאוד", rpr('<w:szCs w:val="32"/>')),
             '<w:pPr><w:outlineLvl w:val="0"/></w:pPr>')
        + para(run("גוף", rpr('<w:szCs w:val="22"/>')))
    )
    conv = DocxConverter(write_docx(body=body))
    assert conv.suggest_body_size() == 11.0


def test_suggested_body_size_follows_the_paragraph_style(write_docx):
    styles = styles_xml(style("Body", run_props=rpr('<w:szCs w:val="26"/>')))
    body = para(run("x"), '<w:pPr><w:pStyle w:val="Body"/></w:pPr>')
    conv = DocxConverter(write_docx(body=body, styles=styles))
    assert conv.suggest_body_size() == 13.0


def test_suggested_notes_size_reads_the_hebrew_style_name(write_docx):
    styles = styles_xml(
        style("FN", name="הערת שוליים", run_props=rpr('<w:szCs w:val="18"/>')),
    )
    conv = DocxConverter(write_docx(body=para(run("x")), styles=styles))
    assert conv.suggest_notes_size() == 9.0


def test_suggested_notes_size_reads_the_annotation_text_style(write_docx):
    styles = styles_xml(
        style("AT", name="Annotation Text", run_props=rpr('<w:szCs w:val="16"/>')),
    )
    conv = DocxConverter(write_docx(body=para(run("x")), styles=styles))
    assert conv.suggest_notes_size() == 8.0


def test_suggested_notes_size_falls_back_to_the_first_footnote_run(write_docx):
    footnotes = footnotes_xml(
        footnote("1", para(run("הערה", rpr('<w:szCs w:val="18"/>')))),
    )
    conv = DocxConverter(write_docx(body=para(run("x")), footnotes=footnotes))
    assert conv.suggest_notes_size() == 9.0


def test_suggested_notes_size_skips_runs_that_use_a_character_style(write_docx):
    footnotes = footnotes_xml(
        footnote("1", para(run("סימן", rpr('<w:rStyle w:val="Ref"/>',
                                          '<w:szCs w:val="14"/>'))
                           + run("הערה", rpr('<w:szCs w:val="18"/>')))),
    )
    conv = DocxConverter(write_docx(body=para(run("x")), footnotes=footnotes))
    assert conv.suggest_notes_size() == 9.0


def test_suggested_notes_size_is_none_without_any_hint(write_docx):
    conv = DocxConverter(write_docx(body=para(run("x"))))
    assert conv.suggest_notes_size() is None


def test_footnote_style_must_be_a_paragraph_style(write_docx):
    styles = styles_xml(
        style("FN", kind="character", name="Footnote Text",
              run_props=rpr('<w:szCs w:val="18"/>')),
    )
    conv = DocxConverter(write_docx(body=para(run("x")), styles=styles))
    assert conv.suggest_notes_size() is None


# ------------------------------------------------------ שילובים מקצה לקצה
def test_a_full_document_converts_to_the_expected_text(write_docx):
    styles = styles_xml(
        doc_defaults(rpr('<w:szCs w:val="22"/>')),
        style("Heading1", outline=0),
    )
    body = (
        para(run("פרק א"), '<w:pPr><w:pStyle w:val="Heading1"/></w:pPr>')
        + para("")
        + para(
            run("רגיל ")
            + run("מודגש", rpr("<w:bCs/>"))
            + run(" ")
            + run("קטן", rpr('<w:szCs w:val="20"/>'))
            + '<w:r><w:footnoteReference w:id="1"/></w:r>'
        )
    )
    footnotes = footnotes_xml(
        footnote("1", '<w:p><w:r><w:footnoteRef/><w:t xml:space="preserve"> '
                      'הסבר</w:t></w:r></w:p>'),
    )
    conv = DocxConverter(write_docx(body=body, styles=styles,
                                    footnotes=footnotes))
    text, notes = conv.convert(11, 10)
    assert text == "<h1>פרק א</h1>\r\nרגיל <b>מודגש</b> <small>קטן</small><sup>1</sup>"
    # ברירת המחדל של המסמך (11 נק') חלה גם על ההערה, ולכן היא גדולה מגודל
    # ההערות שנקבע (10 נק') ומקבלת <big>.
    assert notes == "<sup>1</sup> <big>הסבר</big>\r\n"


def test_the_namespace_constant_matches_the_helper(write_docx):
    assert w("body") == "{%s}body" % W
