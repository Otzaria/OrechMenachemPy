# -*- coding: utf-8 -*-
"""
converter.py — מנוע ההמרה של "עורך מנחם" מ‑Word (.docx) לטקסט עם תגיות עיצוב.

שכתוב בפייתון של הלוגיקה שבמודול EXPORT_TO_TEXT.bas בתבנית "עורך מנחם.dotm"
(TAGS_ADDING + SAVE_AS_TEXT), כסימולציה נאמנה של מעברי החיפוש/החלפה של המאקרו:

    • העיצוב נקרא כמו במאקרו: BoldBi/ItalicBi/SizeBi = מאפייני הכתב המורכב
      bCs / iCs / szCs בלבד (בעברית אלו המאפיינים הקובעים), קו תחתון, עילי/תחתי.
    • המעברים מבוצעים באותו הסדר: מודגש, קו תחתון, נטוי, עילי, תחתי,
      ואז גדלים — <big> מ‑normal+0.5 עד 20, <small> מ‑normal-0.5 עד 3.
    • כמו ב‑Word, תווי תגית שהוכנסו במעבר מוקדם יורשים את עיצוב הטקסט שנעטף,
      ולכן מעברי הגודל המאוחרים עוטפים אותם יחד עם הטקסט (וכך מתקבל למשל
      <small><b>x</b></small>).
    • בשונה מהמאקרו, התגיות צמודות לטקסט: רווחים בקצות טווח מעוצב נשארים
      מחוץ לתגיות (<b>מילה</b> ולא <b>מילה </b>), ורווח שעיצובו שונה משני
      צדדיו — למשל רווח קטן יותר בין שני קטעי טקסט רגילים — אינו מקבל
      תגיות כלל. רווח בין שתי מילים בעלות אותו עיצוב נשאר בתוך התגיות.
    • אחרי כל מעבר מבוצעים המיזוגים "</b> <b>" -> " " ו‑"<b> </b>" -> " ".
    • סימני הערות שוליים מנוטרלים (עיצוב רגיל) ומוחלפים ב‑<sup>מספר</sup>.
    • ההערות נשמרות לקובץ נפרד "הערות על <שם>.txt" (מעברי פסקה בפנים -> <br>).

הפלט: UTF‑8 עם BOM ושורות CRLF, שורה אחת לכל פסקה (שורות ריקות מושמטות).
"""

import os
import zipfile
from lxml import etree

# --- מרחב שמות של WordprocessingML ---
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def w(tag):
    return "{%s}%s" % (W, tag)


def _local(el):
    t = el.tag
    return t.rsplit("}", 1)[-1] if isinstance(t, str) else ""


# תו מציין‑מקום לסימן הערת שוליים (מוחלף בסוף ב‑<sup>מספר</sup>)
_FNREF = "\x02"


class ConversionError(Exception):
    pass


# ============================================================ סימולציית המעברים
# כל תו מיוצג כ‑[char, props] כאשר props = (bold, underline, italic, sup, sub, size_hp)
# size_hp — גודל בחצאי נקודות (int) או None.

# תווי רווח שנשארים מחוץ לתגיות בקצות טווח מעוצב
_WS = " \t\n"


# מרחב השמות של תאימות סימון (mc:Choice / mc:Fallback)
MC = "http://schemas.openxmlformats.org/markup-compatibility/2006"

# רכיבי תוכן של ריצה (w:r) — רק הם מייצגים תווים בפסקה. אותם שמות מקומיים
# מופיעים גם במאפייני הפסקה, ובראשם w:pPr/w:tabs/w:tab — שהוא הגדרת
# *עצירת טאב* של הפסקה ולא תו טאב. לכן רכיב שהוא במרחב השמות של Word נחשב
# תוכן רק אם הוא ילד ישיר של w:r. רכיבים ממרחבי שמות אחרים (DrawingML a:t,
# נוסחאות m:t) נבדקים לפי המכולה בלבד, כדי לא לאבד טקסט: ההורה שלהם עשוי
# להיות a:fld או a:p ולא ריצה.
_RUN_CONTENT = ("t", "tab", "br", "cr", "noBreakHyphen",
                "footnoteRef", "footnoteReference")

# מכולות שכל תוכנן אינו נפלט: מאפייני פסקה, טקסט שנמחק או הועבר במעקב
# שינויים, והענף שוורד אינו מציג ב‑mc:AlternateContent (כפילות של mc:Choice).
_SKIPPED_CONTAINERS = frozenset((
    "{%s}pPr" % W, "{%s}del" % W, "{%s}moveFrom" % W, "{%s}Fallback" % MC))


def _in_skipped_container(el):
    """True אם el נמצא בתוך מכולה שאינה נפלטת (ראה _SKIPPED_CONTAINERS)."""
    node = el.getparent()
    while node is not None:
        if node.tag in _SKIPPED_CONTAINERS:
            return True
        node = node.getparent()
    return False


def _is_para_content(el, p):
    """True אם el הוא תוכן שנפלט לשורה של הפסקה p.
    עוצר בפסקה מקוננת (w:p שבתוך תיבת טקסט) — היא נפלטת כשורה נפרדת,
    ואינה מוטמעת באמצע השורה של הפסקה המכילה."""
    node = el.getparent()
    while node is not None and node is not p:
        if node.tag in _SKIPPED_CONTAINERS or node.tag == "{%s}p" % W:
            return False
        node = node.getparent()
    return True


# רכיבי mc:AlternateContent אינם חלק ממודל התוכן של Word: לפי MCE הם הורים
# חוקיים בכל מקום, ותופסים את מקום התוכן שהיה חוקי שם. לכן הם עשויים לחצוץ
# בין ריצה לתוכן שלה — ‎<w:r><mc:AlternateContent><mc:Choice><w:t>…‎ — ויש
# לדלג מעליהם בחיפוש הריצה, אחרת הטקסט נזרק.
_MCE_TRANSPARENT = frozenset((
    "{%s}AlternateContent" % MC, "{%s}Choice" % MC, "{%s}Fallback" % MC))


def _builtin_heading_level(style_id, style_name):
    """1..9 אם הסגנון הוא אחד מסגנונות הכותרת המובנים, אחרת None.

    ב‑OOXML השם הראשי של סגנון מובנה הוא באנגלית ואינו תלוי בשפת הממשק:
    גם וורד עברי כותב ‎<w:name w:val="heading 1"/>‎. ה‑styleId לעומת זאת
    נקבע ע"י המפיק (וורד לפעמים כותב פשוט "1"), ולכן בודקים גם אותו."""
    for value in (style_name, style_id):
        if not value:
            continue
        text = value.strip().lower()
        for prefix in ("heading", "כותרת"):
            if text.startswith(prefix):
                rest = text[len(prefix):].strip()
                if rest.isdigit() and 1 <= int(rest) <= 9:
                    return int(rest)
    return None


def _enclosing_run(el, p=None):
    """הריצה (w:r) שהרכיב el הוא תוכן שלה, או None אם אינו תוכן של ריצה.
    זו הבדיקה שמונעת את הבאג המקורי: w:tab שבתוך w:pPr/w:tabs הוא הגדרת
    עצירת טאב, ההורה שלו הוא w:tabs, ולכן אין לו ריצה עוטפת."""
    node = el.getparent()
    while node is not None and node is not p:
        if node.tag == "{%s}r" % W:
            return node
        if node.tag not in _MCE_TRANSPARENT:
            return None
        node = node.getparent()
    return None


def _wrap_pass(chars, pred, otag, ctag):
    """עוטף טווחים רציפים מקסימליים שבהם pred(props) אמת.
    רווחים בקצוות הטווח נשארים מחוץ לתגיות (התגיות צמודות לטקסט), וטווח
    שכולו רווחים אינו נעטף כלל. תווי התגית מקבלים את המאפיינים של התו
    הראשון שנעטף (כמו ב‑Word)."""
    out = []
    i = 0
    n = len(chars)
    while i < n:
        if pred(chars[i][1]):
            j = i
            while j < n and pred(chars[j][1]):
                j += 1
            a, b = i, j
            while a < b and chars[a][0] in _WS:
                a += 1
            while b > a and chars[b - 1][0] in _WS:
                b -= 1
            out.extend(chars[i:a])
            if a < b:
                p0 = chars[a][1]
                for c in otag:
                    out.append([c, p0])
                out.extend(chars[a:b])
                for c in ctag:
                    out.append([c, p0])
            out.extend(chars[b:j])
            i = j
        else:
            out.append(chars[i])
            i += 1
    return out


def _replace_literal(chars, pat, rep):
    """החלפה טקסטואלית (כמו Find ללא עיצוב): תווי התחליף מקבלים את
    מאפייני התו הראשון שהוחלף. סריקה קדימה כמו ReplaceAll."""
    n = len(chars)
    m = len(pat)
    out = []
    i = 0
    while i < n:
        if chars[i][0] == pat[0] and i + m <= n and \
                all(chars[i + k][0] == pat[k] for k in range(1, m)):
            p0 = chars[i][1]
            for c in rep:
                out.append([c, p0])
            i += m
        else:
            out.append(chars[i])
            i += 1
    return out


# תווי רווח שנמחקים בסוף שורה (רווח וטאב) — כמו '[ ^9]@^13' -> '^13' במאקרו.
# טאב בסוף שורה הוא כמעט תמיד שגיאת הקלדה, ואין לו משמעות בטקסט הסופי.
_TRAILING_WS = (" ", "\t")


def _strip_line_end_spaces(chars):
    """מסיר רווחים וטאבים בסוף הפסקה ולפני מעברי שורה ידניים
    (כמו '[ ^9]@^13' -> '^13' ו‑'[ ^9]@^11' -> '^11' במאקרו)."""
    out = []
    for item in chars:
        if item[0] == "\n":
            while out and out[-1][0] in _TRAILING_WS:
                out.pop()
        out.append(item)
    while out and out[-1][0] in _TRAILING_WS:
        out.pop()
    return out


def _macro_passes(chars, normal_hp):
    """מריץ על פסקה אחת את כל מעברי העיצוב בסדר של המאקרו. מחזיר None לפסקה ריקה."""
    chars = _strip_line_end_spaces(chars)
    if not chars:
        return None

    # מודגש
    chars = _wrap_pass(chars, lambda p: p[0], "<b>", "</b>")
    chars = _replace_literal(chars, "</b> <b>", " ")
    chars = _replace_literal(chars, "<b> </b>", " ")
    # קו תחתון
    chars = _wrap_pass(chars, lambda p: p[1], "<u>", "</u>")
    chars = _replace_literal(chars, "</u> <u>", " ")
    chars = _replace_literal(chars, "<u> </u>", " ")
    # נטוי
    chars = _wrap_pass(chars, lambda p: p[2], "<i>", "</i>")
    chars = _replace_literal(chars, "</i> <i>", " ")
    chars = _replace_literal(chars, "<i> </i>", " ")
    # עילי
    chars = _wrap_pass(chars, lambda p: p[3], "<sup>", "</sup>")
    chars = _replace_literal(chars, "</sup> <sup>", " ")
    chars = _replace_literal(chars, "<sup> </sup>", " ")
    # תחתי
    chars = _wrap_pass(chars, lambda p: p[4], "<sub>", "</sub>")
    chars = _replace_literal(chars, "</sub> <sub>", " ")
    chars = _replace_literal(chars, "<sub> </sub>", " ")

    # גדלים — ביחס לגודל ברירת המחדל, בחצאי נקודות (כמו לולאות המאקרו)
    if normal_hp and normal_hp > 0:
        present = set()
        for _, p in chars:
            if p[5] is not None:
                present.add(p[5])
        # <big>: normal+0.5 .. 20  (עולה)
        for hp in range(normal_hp + 1, 41):
            if hp in present:
                chars = _wrap_pass(chars, lambda p, hp=hp: p[5] == hp,
                                   "<big>", "</big>")
        chars = _replace_literal(chars, "</big> <big>", " ")
        chars = _replace_literal(chars, "<big> </big>", " ")
        # <small>: normal-0.5 .. 3  (יורד)
        for hp in range(normal_hp - 1, 5, -1):
            if hp in present:
                chars = _wrap_pass(chars, lambda p, hp=hp: p[5] == hp,
                                   "<small>", "</small>")
        chars = _replace_literal(chars, "</small> <small>", " ")
        chars = _replace_literal(chars, "<small> </small>", " ")

    return chars


class DocxConverter:
    """טוען קובץ .docx וממיר אותו לטקסט עם תגיות עיצוב."""

    def __init__(self, path):
        self.path = path
        try:
            self.zip = zipfile.ZipFile(path)
        except Exception as e:
            raise ConversionError("לא ניתן לפתוח את הקובץ כ‑docx: %s" % e)
        try:
            self.doc = etree.fromstring(self.zip.read("word/document.xml"))
        except KeyError:
            raise ConversionError("הקובץ אינו מסמך Word תקין (חסר document.xml)")

        self.styles = {}          # styleId -> dict(type, basedOn, outline, rpr, name)
        self.default_rpr = {}     # docDefaults
        self.default_pstyle = None  # סגנון הפסקה שמוגדר כברירת מחדל (Normal)
        self._load_styles()

        self.footnotes = {}       # id(str) -> footnote element
        self._load_footnotes()

    # ------------------------------------------------------------------ סגנונות
    def _load_styles(self):
        try:
            sroot = etree.fromstring(self.zip.read("word/styles.xml"))
        except KeyError:
            return

        dd = sroot.find(w("docDefaults"))
        if dd is not None:
            rpr = dd.find("%s/%s" % (w("rPrDefault"), w("rPr")))
            if rpr is not None:
                self.default_rpr = self._extract_rpr(rpr)

        for st in sroot.findall(w("style")):
            sid = st.get(w("styleId"))
            if sid is None:
                continue
            based = st.find(w("basedOn"))
            name = st.find(w("name"))
            info = {
                "type": st.get(w("type")),
                "basedOn": based.get(w("val")) if based is not None else None,
                "name": name.get(w("val")) if name is not None else "",
                "outline": None,
                "rpr": {},
            }
            ol = st.find("%s/%s" % (w("pPr"), w("outlineLvl")))
            if ol is not None:
                try:
                    info["outline"] = int(ol.get(w("val")))
                except (TypeError, ValueError):
                    pass
            rpr = st.find(w("rPr"))
            if rpr is not None:
                info["rpr"] = self._extract_rpr(rpr)
            self.styles[sid] = info
            if (st.get(w("default")) in ("1", "true")
                    and info["type"] == "paragraph"):
                self.default_pstyle = sid

    def _load_footnotes(self):
        try:
            froot = etree.fromstring(self.zip.read("word/footnotes.xml"))
        except KeyError:
            return
        for fn in froot.findall(w("footnote")):
            # רק הערה מסוג "normal" (או בלי סוג) היא הערה אמיתית. הסוגים
            # האחרים הם רשומות שירות של וורד: separator ו‑continuationSeparator
            # הם הקווים המפרידים, ו‑continuationNotice היא הודעת "ההערה נמשכת
            # בעמוד הבא". גם וורד עצמו אינו סופר אותן ב‑Footnotes.Count.
            if fn.get(w("type")) not in (None, "normal"):
                continue
            fid = fn.get(w("id"))
            if fid is not None:
                self.footnotes[fid] = fn

    # ----------------------------------------------------- קריאת מאפייני עיצוב
    @staticmethod
    def _toggle(el):
        """תכונת דגל: קיימת ללא val => True ; val=0/false => False."""
        v = el.get(w("val"))
        if v is None:
            return True
        return v not in ("0", "false", "off")

    def _extract_rpr(self, rpr):
        d = {}
        for name in ("bCs", "iCs"):
            el = rpr.find(w(name))
            if el is not None:
                d[name] = self._toggle(el)
        u = rpr.find(w("u"))
        if u is not None:
            d["u"] = (u.get(w("val")) not in (None, "none"))
        va = rpr.find(w("vertAlign"))
        if va is not None:
            d["vertAlign"] = va.get(w("val"))
        el = rpr.find(w("szCs"))
        if el is not None:
            try:
                d["szCs"] = int(float(el.get(w("val"))))
            except (TypeError, ValueError):
                pass
        return d

    def _style_prop(self, sid, prop, seen=None):
        """ערך מאפיין מתוך שרשרת הסגנונות (basedOn), או None."""
        seen = seen or set()
        while sid and sid in self.styles and sid not in seen:
            seen.add(sid)
            info = self.styles[sid]
            if prop in info["rpr"]:
                return info["rpr"][prop]
            sid = info["basedOn"]
        return None

    def _resolve(self, prop, run_rpr, rstyle, pstyle):
        """ערך אפקטיבי: ריצה -> סגנון תו -> סגנון פסקה -> ברירות מחדל של המסמך."""
        if prop in run_rpr:
            return run_rpr[prop]
        v = self._style_prop(rstyle, prop)
        if v is not None:
            return v
        v = self._style_prop(pstyle, prop)
        if v is not None:
            return v
        return self.default_rpr.get(prop)

    def _run_props(self, r, pstyle, normal_hp):
        """מחזיר את tuple המאפיינים של ריצה — מקביל ל‑BoldBi/ItalicBi/SizeBi וכו'."""
        rpr = r.find(w("rPr"))
        run_rpr = self._extract_rpr(rpr) if rpr is not None else {}
        rstyle = None
        if rpr is not None:
            rs = rpr.find(w("rStyle"))
            if rs is not None:
                rstyle = rs.get(w("val"))

        bold = bool(self._resolve("bCs", run_rpr, rstyle, pstyle))
        underline = bool(self._resolve("u", run_rpr, rstyle, pstyle))
        italic = bool(self._resolve("iCs", run_rpr, rstyle, pstyle))
        va = self._resolve("vertAlign", run_rpr, rstyle, pstyle)
        size = self._resolve("szCs", run_rpr, rstyle, pstyle)
        return (bold, underline, italic,
                va == "superscript", va == "subscript", size)

    # --------------------------------------------------- רמת כותרת של פסקה
    def _style_chain(self, sid):
        """שרשרת הסגנונות מ‑sid ומעלה דרך basedOn, בלי לולאות."""
        seen = set()
        out = []
        while sid and sid in self.styles and sid not in seen:
            seen.add(sid)
            out.append(sid)
            sid = self.styles[sid]["basedOn"]
        return out

    def _style_outline(self, sid, seen=None):
        """רמת הכותרת של הסגנון, או None.

        קודם מחפשים outlineLvl מפורש בשרשרת הסגנונות. אם אין — נסמכים על
        ברירת המחדל המובנית של סגנונות הכותרת, כמו שוורד עושה: בוורד
        para.OutlineLevel של פסקה בסגנון "heading 1" הוא 1 גם בלי שנכתב
        outlineLvl, והמאקרו קורא בדיוק את הערך הזה. וורד עצמו כן כותב את
        outlineLvl, אבל מפיקים אחרים (python‑docx, המרות מ‑HTML וכו') לא
        תמיד — ובלי הנפילה הזו הכותרת הייתה נפלטת כטקסט רגיל עם תגי גודל.
        """
        chain = self._style_chain(sid)
        for s in chain:
            if self.styles[s]["outline"] is not None:
                return self.styles[s]["outline"]
        for s in chain:
            lvl = _builtin_heading_level(s, self.styles[s].get("name"))
            if lvl is not None:
                return lvl - 1  # outlineLvl הוא מבוסס‑אפס
        return None

    def _para_style(self, p):
        pPr = p.find(w("pPr"))
        if pPr is not None:
            ps = pPr.find(w("pStyle"))
            if ps is not None:
                return ps.get(w("val"))
        return self.default_pstyle

    def _para_heading_level(self, p):
        """1..9 לפסקת כותרת, או None לטקסט רגיל."""
        pPr = p.find(w("pPr"))
        lvl = None
        if pPr is not None:
            ol = pPr.find(w("outlineLvl"))
            if ol is not None:
                try:
                    lvl = int(ol.get(w("val")))
                except (TypeError, ValueError):
                    lvl = None
            if lvl is None:
                ps = pPr.find(w("pStyle"))
                if ps is not None:
                    lvl = self._style_outline(ps.get(w("val")))
        if lvl is None or lvl < 0 or lvl > 8:
            return None  # wdOutlineLevelBodyText
        return lvl + 1

    # ------------------------------------------------- בניית רשימת תווים מפסקה
    def _par_chars(self, p, pstyle, normal_hp, fn_map, refs_out,
                   in_footnote=False):
        """
        ממיר פסקה לרשימת [char, props]. סימני הערות -> תו מציין‑מקום,
        והמספרים נאספים אל refs_out. בתוך הערה: מדלג על סימן ההערה של
        עצמה ועל תו רווח אחד שאחריו (כמו בטקסט שמפיק המאקרו).
        """
        neutral = (False, False, False, False, False, normal_hp)
        chars = []
        # בתוך הערה: כל הרווחים שבין סימן ההערה לתחילת הטקסט נבלעים, כך
        # שבקובץ ההערות יש תמיד רווח אחד בדיוק אחרי <sup>מספר</sup>.
        # כך גם במאקרו: Footnote.Range.text של וורד מתחיל בטקסט ההערה
        # עצמו, בלי הסימן ובלי הרווח שאחריו, והתחליף מוסיף רווח אחד.
        skip_leading_ws = False
        for el in p.iter():
            name = _local(el)
            if name not in _RUN_CONTENT:
                continue
            if el.getparent() is None:
                continue
            if el.tag == w(name):
                # תוכן במרחב השמות של Word חייב לשבת בתוך ריצה
                run = _enclosing_run(el, p)
                if run is None:
                    continue  # למשל w:tab שבתוך w:pPr/w:tabs
            else:
                # DrawingML / נוסחאות: ההורה עשוי להיות a:fld או a:p ולא ריצה,
                # והמאפיינים נלקחים ממנו כמו קודם.
                run = el.getparent()
            if not _is_para_content(el, p):
                continue  # מחוק במעקב שינויים / ענף mc:Fallback / פסקה מקוננת
            if name == "footnoteRef":
                skip_leading_ws = True
                continue
            if name == "footnoteReference":
                if in_footnote:
                    continue  # הפניה מקוננת בתוך הערה – מדולגת
                fid = el.get(w("id"))
                num = fn_map.get(fid)
                if num is not None:
                    chars.append([_FNREF, neutral])
                    refs_out.append(num)
                continue
            if name == "t":
                text = el.text or ""
                if skip_leading_ws:
                    text = text.lstrip(" \t")
                    if text:
                        skip_leading_ws = False
                if not text:
                    continue
                props = self._run_props(run, pstyle, normal_hp)
                for ch in text:
                    chars.append([ch, props])
            elif name == "tab":
                if skip_leading_ws:
                    continue
                props = self._run_props(run, pstyle, normal_hp)
                chars.append(["\t", props])
            elif name in ("br", "cr"):
                skip_leading_ws = False
                props = self._run_props(run, pstyle, normal_hp)
                chars.append(["\n", props])
            elif name == "noBreakHyphen":
                skip_leading_ws = False
                props = self._run_props(run, pstyle, normal_hp)
                chars.append(["-", props])
        return chars

    @staticmethod
    def _finalize(chars, refs):
        """chars -> מחרוזת, החלפת מצייני ההערות ב‑<sup>מספר</sup>."""
        s = "".join(c for c, _ in chars)
        if _FNREF in s:
            parts = s.split(_FNREF)
            out = [parts[0]]
            for k, part in enumerate(parts[1:]):
                num = refs[k] if k < len(refs) else ""
                out.append("<sup>%s</sup>" % num)
                out.append(part)
            s = "".join(out)
        return s

    # ------------------------------------------------------------ הערות שוליים
    def _footnote_number_map(self):
        """id של הערה -> מספר סידורי לפי סדר ההופעה בגוף."""
        fn_map = {}
        order = []
        num = 0
        for ref in self.doc.iter(w("footnoteReference")):
            fid = ref.get(w("id"))
            if fid is None or fid not in self.footnotes or fid in fn_map:
                continue
            if _enclosing_run(ref) is None or _in_skipped_container(ref):
                continue  # הפניה מחוקה או בענף mc:Fallback — אינה נספרת
            num += 1
            fn_map[fid] = num
            order.append(fid)
        return fn_map, order

    def _footnote_line(self, fn_el, notes_hp):
        """שורת ההערה (ללא קידומת המספר) עם תגיות; מעברי פסקה -> <br>."""
        para_lines = []
        for p in fn_el.findall(w("p")):
            pstyle = self._para_style(p)
            chars = self._par_chars(p, pstyle, notes_hp, {}, [],
                                    in_footnote=True)
            chars = _macro_passes(chars, notes_hp)
            if chars is None:
                para_lines.append("")
                continue
            para_lines.append("".join(c for c, _ in chars))
        # מעברי שורה ידניים -> <br> ; הסרת פסקאות ריקות בקצוות (כמו NOTE_LINE_TO_HTML)
        para_lines = [ln.replace("\n", "<br>") for ln in para_lines]
        while para_lines and para_lines[0] == "":
            para_lines.pop(0)
        while para_lines and para_lines[-1] == "":
            para_lines.pop()
        return "<br>".join(para_lines)

    # ------------------------------------------------------------------ המרה
    def convert(self, normal_pt, notes_pt):
        """מחזיר (body_text, notes_text_or_None). הגדלים בנקודות."""
        normal_hp = int(round(normal_pt * 2)) if normal_pt else 0
        notes_hp = int(round(notes_pt * 2)) if notes_pt else 0

        fn_map, order = self._footnote_number_map()

        body = self.doc.find(w("body"))
        if body is None:
            raise ConversionError("מבנה מסמך לא תקין (חסר body)")

        # None = פסקה ריקה. פסקאות ריקות באמצע המסמך נמחקות (כמו איחוד
        # '^13{2,}' במאקרו), אבל ריקות שבסוף המסמך שורדות (המאקרו אינו יכול
        # להחליף את סימן הפסקה האחרון) ונשמרות כשורות ריקות.
        paras = []
        for p in body.iter(w("p")):
            if _in_skipped_container(p):
                continue  # פסקה מחוקה או בענף mc:Fallback (כפילות)
            level = self._para_heading_level(p)
            pstyle = self._para_style(p)
            refs = []
            if level is not None:
                chars = self._par_chars(p, pstyle, normal_hp, fn_map, refs)
                chars = _strip_line_end_spaces(chars)
                text = self._finalize(chars, refs).replace("\n", " ")
                text = text.lstrip(" \t")
                if not text:
                    paras.append(None)
                    continue
                paras.append("<h%d>%s</h%d>" % (level, text, level))
            else:
                chars = self._par_chars(p, pstyle, normal_hp, fn_map, refs)
                chars = _macro_passes(chars, normal_hp)
                if chars is None:
                    paras.append(None)
                    continue
                line = self._finalize(chars, refs)
                paras.append(line.replace("\n", "\r\n"))

        # מציאת הפסקה האחרונה שאינה ריקה; ריקות אחריה נשמרות כשורות ריקות
        last_content = -1
        for i, t in enumerate(paras):
            if t is not None:
                last_content = i
        lines = [t for t in paras[:last_content + 1] if t is not None]
        lines += [""] * (len(paras) - 1 - last_content)

        body_text = "\r\n".join(lines)

        notes_text = None
        if order:
            note_lines = []
            for fid in order:
                content = self._footnote_line(self.footnotes[fid], notes_hp)
                note_lines.append("<sup>%d</sup> %s" % (fn_map[fid], content))
            # קובץ ההערות של המאקרו מסתיים במעבר שורה (סימן הפסקה האחרון של המסמך)
            notes_text = "\r\n".join(note_lines) + "\r\n"

        return body_text, notes_text

    # ----------------------------------------------- הצעת גודל טקסט רגיל
    def suggest_body_size(self):
        """הגודל (szCs) הנפוץ ביותר בפסקאות הרגילות, בנקודות; או None."""
        from collections import Counter
        body = self.doc.find(w("body"))
        if body is None:
            return None
        counts = Counter()
        for p in body.iter(w("p")):
            if self._para_heading_level(p) is not None:
                continue
            if _in_skipped_container(p):
                continue
            pstyle = self._para_style(p)
            for t in p.iter(w("t")):
                run = _enclosing_run(t, p)
                if run is None or not _is_para_content(t, p):
                    continue
                rpr = run.find(w("rPr"))
                run_rpr = self._extract_rpr(rpr) if rpr is not None else {}
                rstyle = None
                if rpr is not None:
                    rs = rpr.find(w("rStyle"))
                    if rs is not None:
                        rstyle = rs.get(w("val"))
                szcs = self._resolve("szCs", run_rpr, rstyle, pstyle)
                if szcs:
                    counts[szcs] += len(t.text or "")
        if not counts:
            return None
        return counts.most_common(1)[0][0] / 2.0

    # ----------------------------------------------- הצעת גודל הערות ברירת מחדל
    def suggest_notes_size(self):
        """גודל מוצע להערות: סגנון 'footnote text', או ריצה ראשונה בהערה."""
        for sid, info in self.styles.items():
            nm = (info.get("name") or "").lower()
            if nm in ("footnote text", "annotation text") or "הערת שוליים" in nm:
                if info["type"] == "paragraph" and "szCs" in info["rpr"]:
                    return info["rpr"]["szCs"] / 2.0
        for fn in self.footnotes.values():
            for rpr in fn.iter(w("rPr")):
                el = rpr.find(w("szCs"))
                if el is not None and rpr.find(w("rStyle")) is None:
                    try:
                        return int(float(el.get(w("val")))) / 2.0
                    except (TypeError, ValueError):
                        pass
        return None


# ------------------------------------------------------------------ שמירה
def _sanitize_filename(name):
    for ch in '\\/:*?"<>|':
        name = name.replace(ch, "")
    return name.strip()


def convert_file(src_path, normal_pt, notes_pt, out_dir=None,
                 add_bom=True, make_notes=True):
    """
    ממיר קובץ .docx יחיד ושומר את הפלט.
    מחזיר dict עם: body_path, notes_path (או None), n_footnotes.
    """
    conv = DocxConverter(src_path)
    body_text, notes_text = conv.convert(normal_pt, notes_pt)

    src_dir = os.path.dirname(os.path.abspath(src_path))
    stem = os.path.splitext(os.path.basename(src_path))[0]
    stem = _sanitize_filename(stem) or "output"
    target_dir = out_dir if out_dir else src_dir
    os.makedirs(target_dir, exist_ok=True)

    encoding = "utf-8-sig" if add_bom else "utf-8"

    body_path = os.path.join(target_dir, stem + ".txt")
    with open(body_path, "w", encoding=encoding, newline="") as fh:
        fh.write(body_text)

    notes_path = None
    if make_notes and notes_text is not None:
        notes_path = os.path.join(target_dir, "הערות על " + stem + ".txt")
        with open(notes_path, "w", encoding=encoding, newline="") as fh:
            fh.write(notes_text)

    return {
        "body_path": body_path,
        "notes_path": notes_path,
        "n_footnotes": len(conv.footnotes),
    }


# ------------------------------------------------------------------ CLI
def _use_utf8_output():
    """
    מכריח את הפלט ל-UTF-8 כדי שנתיבים עבריים לא יפילו את ה-CLI.

    שמות הפלט כוללים "הערות על …", וקידוד ברירת המחדל של stdout הוא קידוד
    הקונסולה — שבמכונה באנגלית אינו מכיל עברית. בלי זה print יזרוק
    UnicodeEncodeError אחרי המרה שהצליחה.
    """
    import sys as _sys
    for stream in (_sys.stdout, _sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError):
            pass


if __name__ == "__main__":
    import argparse
    _use_utf8_output()
    ap = argparse.ArgumentParser(
        description="המרת קובץ Word (.docx) לטקסט עם תגיות עיצוב (עורך מנחם)")
    ap.add_argument("files", nargs="+", help="קבצי .docx להמרה")
    ap.add_argument("--normal", type=float, required=True, help="גודל טקסט רגיל")
    ap.add_argument("--notes", type=float, default=0, help="גודל הערות רגיל")
    ap.add_argument("--out", default=None, help="תיקיית פלט (ברירת מחדל: תיקיית המקור)")
    ap.add_argument("--no-bom", action="store_true", help="שמירה ללא BOM")
    args = ap.parse_args()

    for f in args.files:
        try:
            res = convert_file(f, args.normal, args.notes, args.out,
                               add_bom=not args.no_bom)
            print("OK:", res["body_path"])
            if res["notes_path"]:
                print("    +", res["notes_path"])
        except Exception as e:
            print("ERR:", f, "->", e)
