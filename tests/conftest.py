import os
import zipfile

import pytest


# מאפשר להריץ בדיקות PyQt גם במכונת CI ללא מסך.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


@pytest.fixture(scope="session")
def qapp():
    from PyQt5.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


@pytest.fixture
def write_docx(tmp_path):
    """יוצר docx מינימלי ישירות מ-WordprocessingML לצורכי בדיקה."""
    def _write(name="sample.docx", body="", styles=None, footnotes=None):
        path = tmp_path / name
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
        return path

    return _write
