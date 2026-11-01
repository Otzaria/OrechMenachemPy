# -*- coding: utf-8 -*-
"""בדיקות לטקסט נסתר (w:vanish) ולמספור האוטומטי של וורד (w:numPr / numbering.xml)."""

import pytest

from converter import DocxConverter, _format_number, _hebrew1

from conftest import (
    W,
    footnote,
    footnotes_xml,
    para,
    rpr,
    run,
    style,
    styles_xml,
)


def convert(write_docx, body, styles=None, footnotes=None, numbering=None):
    parts = {"word/numbering.xml": numbering} if numbering is not None else None
    conv = DocxConverter(write_docx(body=body, styles=styles,
                                    footnotes=footnotes, parts=parts))
    return conv.convert(11, 10)


def numbering_xml(levels, nums=(("1", "", ),), abstract_id="0"):
    """levels: רשימת (ilvl, numFmt, lvlText[, start[, suff]]); nums: (numId, תוכן נוסף)."""
    lvls = ""
    for spec in levels:
        ilvl, fmt, text = spec[:3]
        start = spec[3] if len(spec) > 3 else 1
        suff = '<w:suff w:val="%s"/>' % spec[4] if len(spec) > 4 else ""
        lvls += ('<w:lvl w:ilvl="%d"><w:start w:val="%d"/><w:numFmt w:val="%s"/>'
                 '%s<w:lvlText w:val="%s"/></w:lvl>' % (ilvl, start, fmt, suff, text))
    nums_xml = "".join(
        '<w:num w:numId="%s"><w:abstractNumId w:val="%s"/>%s</w:num>'
        % (num_id, abstract_id, extra) for num_id, extra in nums)
    return ('<w:numbering xmlns:w="%s"><w:abstractNum w:abstractNumId="%s">%s'
            '</w:abstractNum>%s</w:numbering>' % (W, abstract_id, lvls, nums_xml))


def numpr(num_id="1", ilvl=0, extra=""):
    return ('<w:pPr>%s<w:numPr><w:ilvl w:val="%d"/><w:numId w:val="%s"/></w:numPr></w:pPr>'
            % (extra, ilvl, num_id))


# ------------------------------------------------------------------ טקסט נסתר
def test_hidden_run_is_dropped(write_docx):
    body = para(run("גלוי ") + run("נסתר", rpr("<w:vanish/>")) + run("סוף"))
    assert convert(write_docx, body)[0] == "גלוי סוף"


def test_vanish_turned_off_is_visible(write_docx):
    body = para(run("x", rpr('<w:vanish w:val="0"/>')))
    assert convert(write_docx, body)[0] == "x"


def test_hidden_via_character_style(write_docx):
    styles = styles_xml(style("Hid", kind="character", run_props=rpr("<w:vanish/>")))
    body = para(run("a") + run("b", rpr('<w:rStyle w:val="Hid"/>')))
    assert convert(write_docx, body, styles)[0] == "a"


def test_fully_hidden_paragraph_produces_no_line(write_docx):
    body = para(run("a")) + para(run("נסתר", rpr("<w:vanish/>"))) + para(run("b"))
    assert convert(write_docx, body)[0] == "a\r\nb"


def test_hidden_text_in_footnote_is_dropped(write_docx):
    body = para(run("x") + '<w:r><w:footnoteReference w:id="1"/></w:r>')
    notes = footnotes_xml(footnote("1", para(
        run("הערה") + run(" נסתרת", rpr("<w:vanish/>")))))
    assert convert(write_docx, body, footnotes=notes)[1] == "<sup>1</sup> הערה\r\n"


# ---------------------------------------------------------- פורמטי מספרים
@pytest.mark.parametrize(("n", "expected"), [
    (1, "א"), (10, "י"), (14, "יד"), (15, "טו"), (16, "טז"), (115, "קטו"),
    (400, "ת"), (500, "תק"), (0, "")])
def test_hebrew1(n, expected):
    assert _hebrew1(n) == expected


@pytest.mark.parametrize(("n", "fmt", "expected"), [
    (3, "decimal", "3"), (3, "decimalZero", "03"), (2, "lowerLetter", "b"),
    (27, "lowerLetter", "aa"), (4, "upperRoman", "IV"), (23, "hebrew2", "אא")])
def test_format_number(n, fmt, expected):
    assert _format_number(n, fmt) == expected


# ------------------------------------------------------------- מספור אוטומטי
def test_paragraph_gets_its_list_label(write_docx):
    numbering = numbering_xml([(0, "hebrew1", "%1)")])
    body = "".join(para(run(t), numpr()) for t in ("ראשון", "שני"))
    assert convert(write_docx, body, numbering=numbering)[0] == "א) ראשון\r\nב) שני"


def test_list_start_value(write_docx):
    numbering = numbering_xml([(0, "decimal", "%1.", 5)])
    assert convert(write_docx, para(run("x"), numpr()), numbering=numbering)[0] == "5. x"


def test_suffix_nothing_glues_label_to_text(write_docx):
    numbering = numbering_xml([(0, "hebrew1", "%1]", 1, "nothing")])
    assert convert(write_docx, para(run("x"), numpr()), numbering=numbering)[0] == "א]x"


def test_bullet_from_symbol_font_is_mapped(write_docx):
    numbering = numbering_xml([(0, "bullet", "")])
    assert convert(write_docx, para(run("x"), numpr()), numbering=numbering)[0] == "• x"


def test_empty_numbered_paragraph_still_advances_the_counter(write_docx):
    numbering = numbering_xml([(0, "decimal", "%1.")])
    body = para(run("a"), numpr()) + para("", numpr()) + para(run("c"), numpr())
    assert convert(write_docx, body, numbering=numbering)[0] == "1. a\r\n3. c"


def test_deeper_level_restarts_after_upper_level(write_docx):
    numbering = numbering_xml([(0, "decimal", "%1."), (1, "hebrew1", "%2)")])
    body = (para(run("a"), numpr()) + para(run("b"), numpr(ilvl=1))
            + para(run("c"), numpr(ilvl=1)) + para(run("d"), numpr())
            + para(run("e"), numpr(ilvl=1)))
    assert convert(write_docx, body, numbering=numbering)[0] == (
        "1. a\r\nא) b\r\nב) c\r\n2. d\r\nא) e")


def test_multi_level_text(write_docx):
    numbering = numbering_xml([(0, "decimal", "%1."), (1, "decimal", "%1.%2")])
    body = para(run("a"), numpr()) + para(run("b"), numpr(ilvl=1))
    assert convert(write_docx, body, numbering=numbering)[0] == "1. a\r\n1.1 b"


def test_num_id_zero_cancels_numbering(write_docx):
    numbering = numbering_xml([(0, "decimal", "%1.")])
    assert convert(write_docx, para(run("x"), numpr("0")), numbering=numbering)[0] == "x"


def test_start_override_applies_to_its_num(write_docx):
    numbering = numbering_xml(
        [(0, "decimal", "%1.")],
        nums=(("1", ""), ("2", '<w:lvlOverride w:ilvl="0"><w:startOverride w:val="1"/>'
                               '</w:lvlOverride>')))
    body = (para(run("a"), numpr("1")) + para(run("b"), numpr("1"))
            + para(run("c"), numpr("2")))
    assert convert(write_docx, body, numbering=numbering)[0] == "1. a\r\n2. b\r\n1. c"


def test_numbering_from_paragraph_style(write_docx):
    numbering = numbering_xml([(0, "hebrew1", "%1]")])
    styles = styles_xml(
        '<w:style w:type="paragraph" w:styleId="Lst"><w:pPr><w:numPr>'
        '<w:numId w:val="1"/></w:numPr></w:pPr></w:style>')
    body = para(run("x"), '<w:pPr><w:pStyle w:val="Lst"/></w:pPr>')
    assert convert(write_docx, body, styles, numbering=numbering)[0] == "א] x"


def test_heading_carries_its_label(write_docx):
    numbering = numbering_xml([(0, "hebrew1", "%1]")])
    body = para(run("כותרת"), numpr(extra='<w:outlineLvl w:val="3"/>'))
    assert convert(write_docx, body, numbering=numbering)[0] == "<h4>א] כותרת</h4>"


def test_label_is_not_wrapped_in_run_formatting(write_docx):
    numbering = numbering_xml([(0, "decimal", "%1.")])
    body = para(run("x", rpr("<w:bCs/>")), numpr())
    assert convert(write_docx, body, numbering=numbering)[0] == "1. <b>x</b>"


def test_fully_hidden_paragraph_is_not_counted(write_docx):
    numbering = numbering_xml([(0, "decimal", "%1.")])
    body = (para(run("a"), numpr()) + para(run("h", rpr("<w:vanish/>")), numpr())
            + para(run("b"), numpr()))
    assert convert(write_docx, body, numbering=numbering)[0] == "1. a\r\n2. b"


def test_footnotes_have_their_own_counters(write_docx):
    numbering = numbering_xml([(0, "decimal", "%1.")])
    body = (para(run("a"), numpr()) + para(run("b"), numpr())
            + para(run("x") + '<w:r><w:footnoteReference w:id="1"/></w:r>'))
    notes = footnotes_xml(footnote("1", para(run("הערה"), numpr())))
    text, notes_text = convert(write_docx, body, footnotes=notes, numbering=numbering)
    assert text == "1. a\r\n2. b\r\nx<sup>1</sup>"
    assert notes_text == "<sup>1</sup> 1. הערה\r\n"


def test_document_without_numbering_part(write_docx):
    assert convert(write_docx, para(run("x"), numpr()))[0] == "x"
