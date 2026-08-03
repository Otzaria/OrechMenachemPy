import os
import zipfile

import pytest


# מאפשר להריץ בדיקות PyQt גם במכונת CI ללא מסך.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


# ---------------------------------------------------------------- בוני XML
def run(value, rpr=""):
    """ריצת טקסט (<w:r>) עם מאפייני עיצוב אופציונליים."""
    return "<w:r>%s<w:t>%s</w:t></w:r>" % (rpr, value)


def para(contents, ppr=""):
    return "<w:p>%s%s</w:p>" % (ppr, contents)


def rpr(*children):
    return "<w:rPr>%s</w:rPr>" % "".join(children)


def styles_xml(*styles):
    return '<w:styles xmlns:w="%s">%s</w:styles>' % (W, "".join(styles))


def style(style_id, kind="paragraph", based_on=None, name=None,
          outline=None, run_props="", default=False):
    attrs = 'w:type="%s" w:styleId="%s"' % (kind, style_id)
    if default:
        attrs += ' w:default="1"'
    inner = ""
    if name is not None:
        inner += '<w:name w:val="%s"/>' % name
    if based_on is not None:
        inner += '<w:basedOn w:val="%s"/>' % based_on
    if outline is not None:
        inner += '<w:pPr><w:outlineLvl w:val="%d"/></w:pPr>' % outline
    inner += run_props
    return "<w:style %s>%s</w:style>" % (attrs, inner)


def doc_defaults(run_props):
    return ("<w:docDefaults><w:rPrDefault>%s</w:rPrDefault></w:docDefaults>"
            % run_props)


def footnotes_xml(*footnotes):
    return '<w:footnotes xmlns:w="%s">%s</w:footnotes>' % (W, "".join(footnotes))


def footnote(fid, paragraphs, kind=None):
    attrs = 'w:id="%s"' % fid
    if kind is not None:
        attrs += ' w:type="%s"' % kind
    return "<w:footnote %s>%s</w:footnote>" % (attrs, paragraphs)


@pytest.fixture(scope="session")
def qapp():
    from PyQt5.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


@pytest.fixture
def write_docx(tmp_path):
    """יוצר docx מינימלי ישירות מ-WordprocessingML לצורכי בדיקה."""
    def _write(name="sample.docx", body="", styles=None, footnotes=None,
               document=None, parts=None):
        path = tmp_path / name
        if document is None:
            document = (
                '<w:document xmlns:w="%s"><w:body>%s</w:body></w:document>'
                % (W, body)
            )
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("word/document.xml", document)
            if styles is not None:
                archive.writestr("word/styles.xml", styles)
            if footnotes is not None:
                archive.writestr("word/footnotes.xml", footnotes)
            for part_name, content in (parts or {}).items():
                archive.writestr(part_name, content)
        return path

    return _write
