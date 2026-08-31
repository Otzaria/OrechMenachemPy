# -*- coding: utf-8 -*-
"""בדיקות סריקת ה‑XML: מה נחשב תוכן של פסקה ומה לא.

הבאג המקורי היה שסריקת הפסקה (``p.iter()``) זיהתה רכיבים לפי השם המקומי
בלבד, ולכן ``w:pPr/w:tabs/w:tab`` — *הגדרת עצירת טאב*, כלומר עיצוב פסקה —
נפלט כתו טאב אמיתי בטקסט. הקבצים כאן מקבעים את הגבולות של הסריקה:
מאפייני פסקה, מעקב שינויים, ענף mc:Fallback ופסקאות מקוננות (תיבות טקסט)
אינם תוכן; DrawingML ונוסחאות כן.
"""

import pytest

from converter import DocxConverter

from conftest import W, footnote, footnotes_xml, para, rpr, run

A = "http://schemas.openxmlformats.org/drawingml/2006/main"
MC = "http://schemas.openxmlformats.org/markup-compatibility/2006"
V = "urn:schemas-microsoft-com:vml"
M = "http://schemas.openxmlformats.org/officeDocument/2006/math"
WPS = "http://schemas.microsoft.com/office/word/2010/wordprocessingShape"

TAB_STOPS = '<w:pPr><w:tabs><w:tab w:val="left" w:pos="4394"/></w:tabs></w:pPr>'


def document(body):
    """מסמך עם כל מרחבי השמות שהבדיקות כאן צריכות."""
    return (
        '<w:document xmlns:w="%s" xmlns:a="%s" xmlns:mc="%s" xmlns:v="%s" '
        'xmlns:m="%s" xmlns:wps="%s"><w:body>%s</w:body></w:document>'
        % (W, A, MC, V, M, WPS, body)
    )


def convert(write_docx, body, styles=None, footnotes=None,
            normal_pt=11, notes_pt=10):
    conv = DocxConverter(write_docx(document=document(body), styles=styles,
                                    footnotes=footnotes))
    return conv.convert(normal_pt, notes_pt)


def text_box(inner):
    """תיבת טקסט בסימון VML — פסקה מקוננת בתוך ריצה."""
    return ("<w:r><w:pict><v:shape><v:textbox><w:txbxContent>%s"
            "</w:txbxContent></v:textbox></v:shape></w:pict></w:r>" % inner)


# ------------------------------------------------ הגדרות טאב אינן תווי טאב
@pytest.mark.parametrize("stops", [1, 2, 5])
def test_no_matter_how_many_tab_stops_a_paragraph_declares_none_become_text(
        write_docx, stops):
    ppr = ("<w:pPr><w:tabs>%s</w:tabs></w:pPr>"
           % ('<w:tab w:val="left" w:pos="4394"/>' * stops))
    assert convert(write_docx, para(run("שורה"), ppr))[0] == "שורה"


def test_tab_stops_do_not_survive_the_formatting_passes(write_docx):
    """התגית חייבת לעטוף את הטקסט בלבד, בלי טאב מדומה לפניה."""
    body = para(run("מודגש", rpr("<w:bCs/>")), TAB_STOPS)
    assert convert(write_docx, body)[0] == "<b>מודגש</b>"


def test_an_otherwise_empty_paragraph_with_tab_stops_counts_as_empty(write_docx):
    """המקרה שהשפיע על מבנה השורות: פסקת רווח שיש לה עצירות טאב.

    לפני התיקון היא הכילה תו טאב, ולכן לא נחשבה ריקה ולא נמחקה — ונשארה
    שורה שכל תוכנה טאב.
    """
    body = para(run("א")) + para("", TAB_STOPS) + para(run("ב"))
    assert convert(write_docx, body)[0] == "א\r\nב"


def test_a_document_of_nothing_but_tab_stops_converts_to_nothing(write_docx):
    assert convert(write_docx, para("", TAB_STOPS))[0] == ""


# --------------------------------------------- טאב בסוף שורה — שגיאת הקלדה
def test_a_tab_at_the_end_of_a_line_is_removed(write_docx):
    body = para(run("שורה") + "<w:r><w:tab/></w:r>")
    assert convert(write_docx, body)[0] == "שורה"


def test_a_tab_before_a_manual_line_break_is_removed(write_docx):
    body = para(run("א") + "<w:r><w:tab/></w:r>" + "<w:r><w:br/></w:r>"
                + run("ב") + "<w:r><w:tab/></w:r>")
    assert convert(write_docx, body)[0] == "א\r\nב"


def test_a_tab_with_text_after_it_is_kept(write_docx):
    body = para(run("א") + "<w:r><w:tab/></w:r>" + run("ב"))
    assert convert(write_docx, body)[0] == "א\tב"


def test_a_trailing_tab_is_removed_from_a_heading_too(write_docx):
    ppr = '<w:pPr><w:outlineLvl w:val="0"/></w:pPr>'
    body = para(run("כותרת") + "<w:r><w:tab/></w:r>", ppr)
    assert convert(write_docx, body)[0] == "<h1>כותרת</h1>"


def test_a_paragraph_of_only_tabs_is_dropped(write_docx):
    body = para(run("א")) + para("<w:r><w:tab/><w:tab/></w:r>") + para(run("ב"))
    assert convert(write_docx, body)[0] == "א\r\nב"


# ------------------------------------------------------ מעקב שינויים (w:del)
def test_deleted_text_leaves_no_tab_behind(write_docx):
    """w:delText לא נפלט — וגם הטאב שבתוך אותה ריצה מחוקה לא."""
    body = para(
        run("א")
        + '<w:del w:id="1" w:author="x"><w:r>'
          '<w:delText>מחוק</w:delText><w:tab/></w:r></w:del>'
        + run("ב")
    )
    assert convert(write_docx, body)[0] == "אב"


def test_a_deleted_manual_break_does_not_split_the_line(write_docx):
    body = para(run("א") + '<w:del w:id="1" w:author="x"><w:r><w:br/></w:r>'
                           '</w:del>' + run("ב"))
    assert convert(write_docx, body)[0] == "אב"


def test_a_deleted_footnote_reference_is_neither_numbered_nor_exported(write_docx):
    footnotes = footnotes_xml(footnote(
        "1", '<w:p><w:r><w:footnoteRef/><w:t xml:space="preserve"> '
             'הערה</w:t></w:r></w:p>'))
    body = para(run("א")
                + '<w:del w:id="1" w:author="x"><w:r>'
                  '<w:footnoteReference w:id="1"/></w:r></w:del>'
                + run("ב"))
    text, notes = convert(write_docx, body, footnotes=footnotes)
    assert text == "אב"
    assert notes is None


def test_a_live_footnote_after_a_deleted_one_keeps_number_one(write_docx):
    """אם ההפניה המחוקה הייתה נספרת, ההערה החיה הייתה מקבלת 2 במקום 1."""
    footnotes = footnotes_xml(
        footnote("1", '<w:p><w:r><w:footnoteRef/><w:t xml:space="preserve"> '
                      'ראשונה</w:t></w:r></w:p>'),
        footnote("2", '<w:p><w:r><w:footnoteRef/><w:t xml:space="preserve"> '
                      'שניה</w:t></w:r></w:p>'),
    )
    body = para('<w:del w:id="1" w:author="x"><w:r>'
                '<w:footnoteReference w:id="1"/></w:r></w:del>'
                + run("א") + '<w:r><w:footnoteReference w:id="2"/></w:r>')
    text, notes = convert(write_docx, body, footnotes=footnotes)
    assert text == "א<sup>1</sup>"
    assert notes == "<sup>1</sup> שניה\r\n"


def test_a_deleted_paragraph_is_not_exported(write_docx):
    body = (para(run("א"))
            + '<w:del w:id="1" w:author="x">' + para(run("מחוק")) + '</w:del>'
            + para(run("ב")))
    assert convert(write_docx, body)[0] == "א\r\nב"


# ------------------------------------------ פסקה מקוננת (תיבת טקסט)
def test_text_box_content_is_its_own_line_and_is_not_glued_into_the_host(
        write_docx):
    """לפני התיקון תוכן התיבה נדחס לאמצע השורה המכילה — וגם נפלט שוב."""
    body = para(run("לפני") + text_box(para(run("תיבה"))) + run("אחרי"))
    assert convert(write_docx, body)[0] == "לפניאחרי\r\nתיבה"


def test_text_box_formatting_belongs_to_the_text_box_line(write_docx):
    body = para(run("רגיל") + text_box(para(run("מודגש", rpr("<w:bCs/>")))))
    assert convert(write_docx, body)[0] == "רגיל\r\n<b>מודגש</b>"


def test_tab_stops_inside_a_text_box_add_no_characters(write_docx):
    body = para(run("א") + text_box(para(run("תיבה"), TAB_STOPS)))
    assert convert(write_docx, body)[0] == "א\r\nתיבה"


# ---------------------------------------------- mc:AlternateContent
def test_only_one_branch_of_alternate_content_is_exported(write_docx):
    """וורד מציג ענף אחד; שני הענפים נושאים את אותו הכיתוב."""
    choice = ('<mc:Choice Requires="wps"><w:drawing><wps:txbx>'
              '<w:txbxContent>%s</w:txbxContent></wps:txbx></w:drawing>'
              '</mc:Choice>' % para(run("כיתוב")))
    fallback = ('<mc:Fallback><w:pict><v:shape><v:textbox><w:txbxContent>%s'
                '</w:txbxContent></v:textbox></v:shape></w:pict></mc:Fallback>'
                % para(run("כיתוב")))
    body = para("<w:r><mc:AlternateContent>%s%s</mc:AlternateContent></w:r>"
                % (choice, fallback))
    assert convert(write_docx, body)[0] == "כיתוב"


def test_a_footnote_reference_in_the_fallback_branch_is_not_counted(write_docx):
    footnotes = footnotes_xml(footnote(
        "1", '<w:p><w:r><w:footnoteRef/><w:t xml:space="preserve"> '
             'הערה</w:t></w:r></w:p>'))
    ref = '<w:r><w:footnoteReference w:id="1"/></w:r>'
    body = para("<w:r><mc:AlternateContent>"
                '<mc:Choice Requires="wps">' + ref + '</mc:Choice>'
                '<mc:Fallback>' + ref + '</mc:Fallback>'
                "</mc:AlternateContent></w:r>")
    text, notes = convert(write_docx, body, footnotes=footnotes)
    assert text == "<sup>1</sup>"
    assert notes == "<sup>1</sup> הערה\r\n"


# ------------------------------- טקסט שאינו במרחב השמות של Word אינו נזרק
def test_drawingml_shape_text_is_still_exported(write_docx):
    body = para('<w:r><w:drawing><a:txBody><a:p><a:r><a:t>צורה</a:t></a:r>'
                '</a:p></a:txBody></w:drawing></w:r>')
    assert convert(write_docx, body)[0] == "צורה"


def test_drawingml_field_text_is_not_dropped(write_docx):
    """a:fld הוא הורה חוקי של a:t — לא ריצה. אין להסיק ממנו שזה עיצוב."""
    body = para('<w:r><w:drawing><a:txBody><a:p>'
                '<a:r><a:t>עמוד </a:t></a:r>'
                '<a:fld id="{1}" type="slidenum"><a:t>12</a:t></a:fld>'
                '</a:p></a:txBody></w:drawing></w:r>')
    assert convert(write_docx, body)[0] == "עמוד 12"


def test_drawingml_line_break_is_kept(write_docx):
    """a:br הוא ילד ישיר של a:p, ואף פעם לא של ריצה."""
    body = para('<w:r><w:drawing><a:txBody><a:p>'
                '<a:r><a:t>א</a:t></a:r><a:br/><a:r><a:t>ב</a:t></a:r>'
                '</a:p></a:txBody></w:drawing></w:r>')
    assert convert(write_docx, body)[0] == "א\r\nב"


def test_equation_text_is_still_exported(write_docx):
    body = para('<m:oMath><m:r><m:t>x=1</m:t></m:r></m:oMath>' + run("א"))
    assert convert(write_docx, body)[0] == "x=1א"


# --------------------------------------------------- הצעת גודל הטקסט הרגיל
def test_suggest_body_size_counts_text_box_text_only_once(write_docx):
    """כיתוב תיבת טקסט נספר פעם אחת — לא גם דרך הפסקה המכילה.

    10 תווים ב‑12 נק' מול 6 תווים ב‑20 נק': בספירה אחת מנצח 12, ובספירה
    כפולה (12 תווים) היה מנצח 20.
    """
    body = para(run("עשרה תווים", rpr('<w:szCs w:val="24"/>'))
                + text_box(para(run("ענקענק", rpr('<w:szCs w:val="40"/>')))))
    conv = DocxConverter(write_docx(document=document(body)))
    assert conv.suggest_body_size() == 12.0


def test_suggest_body_size_ignores_deleted_text(write_docx):
    body = (para(run("טקסט חי ארוך", rpr('<w:szCs w:val="24"/>')))
            + '<w:del w:id="1" w:author="x">'
            + para(run("מחוק ארוך מאוד מאוד", rpr('<w:szCs w:val="60"/>')))
            + '</w:del>')
    conv = DocxConverter(write_docx(document=document(body)))
    assert conv.suggest_body_size() == 12.0


# ------------------------------- mc:Choice כהורה ישיר של תוכן ריצה
# לפי MCE רכיבי mc:* הם הורים חוקיים בכל מקום, ולכן mc:Choice עשוי לחצוץ בין
# w:r לתוכן שלה. וורד פותח קבצים כאלה ופולט את הטקסט, וכך גם המאקרו.
CHOICE = '<mc:AlternateContent><mc:Choice Requires="w14">%s</mc:Choice></mc:AlternateContent>'


def test_text_held_directly_by_mc_choice_is_not_lost(write_docx):
    body = para(run("לפני ")
                + "<w:r>" + CHOICE % "<w:t>באמצע</w:t>" + "</w:r>"
                + run(" אחרי"))
    assert convert(write_docx, body)[0] == "לפני באמצע אחרי"


def test_a_tab_held_directly_by_mc_choice_is_not_lost(write_docx):
    body = para(run("א")
                + "<w:r>" + CHOICE % "<w:tab/>" + "</w:r>"
                + run("ב"))
    assert convert(write_docx, body)[0] == "א\tב"


def test_a_break_held_directly_by_mc_choice_is_not_lost(write_docx):
    body = para(run("א")
                + "<w:r>" + CHOICE % "<w:br/>" + "</w:r>"
                + run("ב"))
    assert convert(write_docx, body)[0] == "א\r\nב"


def test_a_hyphen_held_directly_by_mc_choice_is_not_lost(write_docx):
    body = para(run("א")
                + "<w:r>" + CHOICE % "<w:noBreakHyphen/>" + "</w:r>"
                + run("ב"))
    assert convert(write_docx, body)[0] == "א-ב"


def test_a_footnote_reference_held_by_mc_choice_still_produces_a_notes_file(write_docx):
    """המקרה החמור: אבדן ההפניה היה מבטל גם את כל קובץ ההערות."""
    footnotes = footnotes_xml(footnote(
        "1", '<w:p><w:r><w:footnoteRef/><w:t xml:space="preserve"> '
             'הערה</w:t></w:r></w:p>'))
    body = para(run("א")
                + "<w:r>" + CHOICE % '<w:footnoteReference w:id="1"/>' + "</w:r>")
    text, notes = convert(write_docx, body, footnotes=footnotes)
    assert text == "א<sup>1</sup>"
    assert notes == "<sup>1</sup> הערה\r\n"


def test_formatting_of_text_held_by_mc_choice_comes_from_the_enclosing_run(write_docx):
    """התגית נקבעת לפי w:rPr של הריצה, גם כשהתוכן יורד רמה תחת mc:Choice."""
    body = para("<w:r>" + rpr("<w:bCs/>") + CHOICE % "<w:t>מודגש</w:t>" + "</w:r>")
    assert convert(write_docx, body)[0] == "<b>מודגש</b>"


def test_tab_stops_are_still_ignored_when_mce_elements_are_present(write_docx):
    """התיקון ל‑mc:Choice לא החזיר את הבאג המקורי."""
    body = para("<w:r>" + CHOICE % "<w:t>שורה</w:t>" + "</w:r>", TAB_STOPS)
    assert convert(write_docx, body)[0] == "שורה"


# ------------------------------- רשומות שירות באזור ההערות אינן הערות
@pytest.mark.parametrize("kind", ["separator", "continuationSeparator",
                                  "continuationNotice"])
def test_service_footnote_records_are_not_counted_as_notes(write_docx, kind):
    """וורד שומר באזור ההערות גם קווים מפרידים והודעת "ההערה נמשכת".

    Footnotes.Count של וורד אינו סופר אותן, ולכן גם המונה שמוצג למשתמש
    ובחירת המספור לא צריכים לספור אותן.
    """
    service = ('<w:footnote w:id="9" w:type="%s"><w:p><w:r>'
               '<w:t>המשך בעמוד הבא</w:t></w:r></w:p></w:footnote>' % kind)
    real = ('<w:footnote w:id="1"><w:p><w:r><w:footnoteRef/>'
            '<w:t xml:space="preserve"> הערה</w:t></w:r></w:p></w:footnote>')
    footnotes = '<w:footnotes xmlns:w="%s">%s%s</w:footnotes>' % (W, service, real)
    conv = DocxConverter(write_docx(
        document=document(para(run("א")
                               + '<w:r><w:footnoteReference w:id="1"/></w:r>')),
        footnotes=footnotes))
    text, notes = conv.convert(11, 10)
    assert len(conv.footnotes) == 1
    assert text == "א<sup>1</sup>"
    assert notes == "<sup>1</sup> הערה\r\n"


# ------------------- רמת כותרת מברירת המחדל המובנית של סגנון "heading N"
def style(style_id, name=None, outline=None, based_on=None, run_props=""):
    inner = ""
    if name is not None:
        inner += '<w:name w:val="%s"/>' % name
    if based_on is not None:
        inner += '<w:basedOn w:val="%s"/>' % based_on
    if outline is not None:
        inner += '<w:pPr><w:outlineLvl w:val="%d"/></w:pPr>' % outline
    inner += run_props
    return ('<w:style w:type="paragraph" w:styleId="%s">%s</w:style>'
            % (style_id, inner))


def styles_of(*items):
    return '<w:styles xmlns:w="%s">%s</w:styles>' % (W, "".join(items))


def heading_para(style_id):
    return ('<w:p><w:pPr><w:pStyle w:val="%s"/></w:pPr>'
            '<w:r><w:rPr><w:szCs w:val="32"/></w:rPr>'
            '<w:t>פרק א</w:t></w:r></w:p>' % style_id)


@pytest.mark.parametrize("level", [1, 3, 9])
def test_a_builtin_heading_style_without_outline_level_is_still_a_heading(
        write_docx, level):
    """וורד כן כותב outlineLvl, אבל מפיקים אחרים לא תמיד.

    בוורד para.OutlineLevel של פסקה בסגנון "heading N" הוא N גם בלי
    outlineLvl מפורש, והמאקרו קורא בדיוק את הערך הזה — ולכן בלי הנפילה
    הזו הפייתון היה מפספס את הכותרת ופולט אותה כטקסט עם תגי גודל.
    """
    styles = styles_of(style("H", name="heading %d" % level))
    out = convert(write_docx, heading_para("H"), styles)[0]
    assert out == "<h%d>פרק א</h%d>" % (level, level)


def test_the_style_id_alone_is_enough_to_recognise_a_heading(write_docx):
    """מפיקים שאינם כותבים w:name בכלל."""
    styles = styles_of(style("Heading2"))
    assert convert(write_docx, heading_para("Heading2"), styles)[0] == \
        "<h2>פרק א</h2>"


def test_a_heading_level_inherited_through_based_on_is_found(write_docx):
    styles = styles_of(style("MyHead", name="My Head", based_on="H1base"),
                       style("H1base", name="heading 1"))
    assert convert(write_docx, heading_para("MyHead"), styles)[0] == \
        "<h1>פרק א</h1>"


def test_an_explicit_outline_level_still_wins_over_the_builtin_default(write_docx):
    """סגנון בשם "heading 1" שהוגדר במפורש כטקסט גוף (9) אינו כותרת."""
    styles = styles_of(style("H", name="heading 1", outline=9))
    assert convert(write_docx, heading_para("H"), styles)[0] != "<h1>פרק א</h1>"


def test_an_explicit_outline_level_overrides_the_name(write_docx):
    styles = styles_of(style("H", name="heading 1", outline=2))
    assert convert(write_docx, heading_para("H"), styles)[0] == "<h3>פרק א</h3>"


@pytest.mark.parametrize("name", ["heading", "heading 0", "heading 10",
                                  "headings 1", "Heading One", "subheading 1"])
def test_names_that_are_not_builtin_heading_styles_are_not_promoted(
        write_docx, name):
    styles = styles_of(style("H", name=name))
    assert not convert(write_docx, heading_para("H"), styles)[0].startswith("<h")
