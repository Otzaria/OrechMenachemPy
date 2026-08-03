import zipfile

import pytest
from lxml import etree

from converter import (
    ConversionError,
    DocxConverter,
    _FNREF,
    _local,
    _macro_passes,
    _replace_literal,
    _sanitize_filename,
    _strip_line_end_spaces,
    _wrap_pass,
    convert_file,
    w,
)


W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
P = (False, False, False, False, False, 22)


def text(chars):
    return "".join(char for char, _ in chars)


def chars(value, props=P):
    return [[char, props] for char in value]


def run(value, rpr=""):
    return "<w:r>%s<w:t>%s</w:t></w:r>" % (rpr, value)


def para(contents, ppr=""):
    return "<w:p>%s%s</w:p>" % (ppr, contents)


def test_namespace_helpers():
    element = etree.Element(w("p"))
    assert _local(element) == "p"
    assert _local(etree.Comment("note")) == ""
    assert w("t") == "{%s}t" % W


def test_wrap_pass_wraps_contiguous_range_and_preserves_props():
    bold = (True, False, False, False, False, 22)
    wrapped = _wrap_pass(chars("ab", bold) + chars("c"), lambda p: p[0], "<b>", "</b>")
    assert text(wrapped) == "<b>ab</b>c"
    assert wrapped[0][1] == bold


def test_replace_literal_uses_properties_of_replaced_text():
    bold = (True, False, False, False, False, 22)
    replaced = _replace_literal(chars("xx", bold), "xx", "!")
    assert text(replaced) == "!"
    assert replaced[0][1] == bold


def test_strip_line_end_spaces_and_final_spaces():
    result = _strip_line_end_spaces(chars("a  \nb  "))
    assert text(result) == "a\nb"


def test_macro_passes_formats_and_merges_bold_ranges_separated_by_space():
    bold = (True, False, False, False, False, 22)
    source = chars("a", bold) + chars(" ") + chars("b", bold)
    assert text(_macro_passes(source, 22)) == "<b>a b</b>"


def test_macro_passes_nests_size_tag_around_existing_formatting():
    bold_big = (True, False, False, False, False, 24)
    assert text(_macro_passes(chars("x", bold_big), 22)) == "<big><b>x</b></big>"


def test_macro_passes_handles_underline_italic_super_and_subscript():
    source = (
        chars("u", (False, True, False, False, False, 22))
        + chars("i", (False, False, True, False, False, 22))
        + chars("s", (False, False, False, True, False, 22))
        + chars("d", (False, False, False, False, True, 22))
    )
    assert text(_macro_passes(source, 22)) == "<u>u</u><i>i</i><sup>s</sup><sub>d</sub>"


def test_macro_passes_returns_none_for_empty_paragraph():
    assert _macro_passes(chars("text "), 22) is not None
    assert _macro_passes(chars("   "), 22) is None
    assert _macro_passes([], 22) is None


@pytest.mark.parametrize(
    ("raw", "clean"),
    [("a:b/c", "abc"), ('  a*?"<>|  ', "a"), ("normal", "normal")],
)
def test_sanitize_filename(raw, clean):
    assert _sanitize_filename(raw) == clean


def test_invalid_docx_raises_conversion_error(tmp_path):
    invalid = tmp_path / "invalid.docx"
    invalid.write_text("not a zip", encoding="utf-8")
    with pytest.raises(ConversionError):
        DocxConverter(invalid)


def test_missing_document_xml_raises_conversion_error(tmp_path):
    path = tmp_path / "missing.docx"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("word/styles.xml", "<styles/>")
    with pytest.raises(ConversionError, match="document.xml"):
        DocxConverter(path)


def test_convert_handles_heading_and_rich_text(write_docx):
    styles = (
        '<w:styles xmlns:w="%s">'
        '<w:style w:type="paragraph" w:styleId="Heading1">'
        '<w:pPr><w:outlineLvl w:val="0"/></w:pPr></w:style></w:styles>' % W
    )
    body = (
        para(run(" כותרת"), '<w:pPr><w:pStyle w:val="Heading1"/></w:pPr>')
        + para(
            run("B", "<w:rPr><w:bCs/></w:rPr>")
            + run("I", "<w:rPr><w:iCs/></w:rPr>")
            + run("U", '<w:rPr><w:u w:val="single"/></w:rPr>')
        )
    )
    conv = DocxConverter(write_docx(body=body, styles=styles))
    assert conv.convert(11, 10) == ("<h1>כותרת</h1>\r\n<b>B</b><i>I</i><u>U</u>", None)


def test_convert_replaces_footnotes_and_writes_notes(write_docx):
    body = para(run("גוף") + '<w:r><w:footnoteReference w:id="2"/></w:r>')
    footnotes = (
        '<w:footnotes xmlns:w="%s"><w:footnote w:id="2">'
        '<w:p><w:r><w:footnoteRef/><w:t> הערה</w:t></w:r></w:p>'
        '</w:footnote></w:footnotes>' % W
    )
    conv = DocxConverter(write_docx(body=body, footnotes=footnotes))
    assert conv.convert(11, 10) == ("גוף<sup>1</sup>", "<sup>1</sup> הערה\r\n")


def test_suggested_sizes_are_taken_from_body_and_footnote_style(write_docx):
    styles = (
        '<w:styles xmlns:w="%s">'
        '<w:style w:type="paragraph" w:styleId="FootnoteText">'
        '<w:name w:val="Footnote Text"/><w:rPr><w:szCs w:val="20"/></w:rPr>'
        '</w:style></w:styles>' % W
    )
    body = para(run("רוב", '<w:rPr><w:szCs w:val="24"/></w:rPr>'))
    conv = DocxConverter(write_docx(body=body, styles=styles))
    assert conv.suggest_body_size() == 12.0
    assert conv.suggest_notes_size() == 10.0


def test_convert_file_writes_bom_and_can_skip_notes(write_docx, tmp_path):
    source = write_docx("bad:name.docx", para(run("תוכן")))
    result = convert_file(source, 11, 10, out_dir=tmp_path / "out", make_notes=False)
    body = (tmp_path / "out" / "badname.txt")
    assert result["body_path"] == str(body)
    assert result["notes_path"] is None
    assert body.read_bytes().startswith(b"\xef\xbb\xbf")
    assert body.read_text(encoding="utf-8-sig") == "תוכן"


def test_finalize_replaces_missing_reference_with_empty_superscript():
    value = DocxConverter._finalize(chars("a") + [[_FNREF, P]], [])
    assert value == "a<sup></sup>"
