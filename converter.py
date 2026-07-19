# -*- coding: utf-8 -*-
"""
converter.py — מנוע ההמרה של "עורך מנחם" מ‑Word (.docx) לטקסט עם תגיות עיצוב.

זהו שכתוב בפייתון של הלוגיקה שבמודול EXPORT_TO_TEXT.bas בתבנית "עורך מנחם.dotm":
    TAGS_ADDING  +  SAVE_AS_TEXT

מה שנשמר (בדיוק כמו המאקרו):
    • סגנונות כותרת 1‑9  ->  <h1>..</h1> ... <h9>..</h9>
    • בתוך טקסט רגיל: מודגש<b>, נטוי<i>, קו‑תחתון<u>, עילי<sup>, תחתי<sub>
    • גודל יחסי לגודל ברירת המחדל: גדול יותר -> <big>, קטן יותר -> <small>
    • סימני הפניה להערות שוליים בגוף  ->  <sup>מספר</sup>
    • ההערות עצמן נשמרות לקובץ נפרד:  "הערות על <שם>.txt"

הערכים "מודגש/נטוי/גודל" נבדקים לפי מאפייני הכתב המורכב (bCs/iCs/szCs) —
בדיוק כמו BoldBi/ItalicBi/SizeBi שבמאקרו — כי בעברית אלו המאפיינים הקובעים.

הפלט: UTF‑8 עם BOM ושורות CRLF, שורה אחת לכל פסקה (כמו פלט המאקרו).
"""

import os
import re
import zipfile
from lxml import etree

# --- מרחב שמות של WordprocessingML ---
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def w(tag):
    return "{%s}%s" % (W, tag)


def _local(el):
    t = el.tag
    return t.rsplit("}", 1)[-1] if isinstance(t, str) else ""


# שמות התגיות לצורך מיזוג תגיות סמוכות (כמו במאקרו: "</b> <b>" -> " ").
_MERGE_TAGS = ["b", "u", "i", "sup", "sub", "big", "small"]


class ConversionError(Exception):
    pass


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

        self.styles = {}       # styleId -> dict(type, basedOn, outline, rpr, name)
        self.default_rpr = {}  # מאפייני ברירת מחדל (docDefaults)
        self._load_styles()

        self.footnotes = {}    # id(str) -> footnote element
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

    def _load_footnotes(self):
        try:
            froot = etree.fromstring(self.zip.read("word/footnotes.xml"))
        except KeyError:
            return
        for fn in froot.findall(w("footnote")):
            ftype = fn.get(w("type"))
            if ftype in ("separator", "continuationSeparator"):
                continue  # מפרידים – לא הערות אמיתיות
            fid = fn.get(w("id"))
            if fid is not None:
                self.footnotes[fid] = fn

    # ----------------------------------------------------- קריאת מאפייני עיצוב
    @staticmethod
    def _toggle(el):
        """ערך של תכונת דגל (bold/italic): קיים ללא val => True ; val=0/false => False."""
        v = el.get(w("val"))
        if v is None:
            return True
        return v not in ("0", "false", "off")

    def _extract_rpr(self, rpr):
        d = {}
        for name in ("b", "bCs", "i", "iCs"):
            el = rpr.find(w(name))
            if el is not None:
                d[name] = self._toggle(el)
        u = rpr.find(w("u"))
        if u is not None:
            d["u"] = (u.get(w("val")) not in (None, "none"))
        va = rpr.find(w("vertAlign"))
        if va is not None:
            d["vertAlign"] = va.get(w("val"))
        for name in ("sz", "szCs"):
            el = rpr.find(w(name))
            if el is not None:
                try:
                    d[name] = int(el.get(w("val")))
                except (TypeError, ValueError):
                    pass
        return d

    def _style_prop(self, sid, prop, seen=None):
        """מחזיר ערך מאפיין מתוך שרשרת הסגנונות (basedOn), או None."""
        seen = seen or set()
        while sid and sid in self.styles and sid not in seen:
            seen.add(sid)
            info = self.styles[sid]
            if prop in info["rpr"]:
                return info["rpr"][prop]
            sid = info["basedOn"]
        return None

    def _resolve(self, prop, run_rpr, rstyle, pstyle):
        """ערך אפקטיבי של מאפיין: ריצה ישירה -> סגנון תו -> סגנון פסקה -> ברירת מחדל."""
        if prop in run_rpr:
            return run_rpr[prop]
        v = self._style_prop(rstyle, prop)
        if v is not None:
            return v
        v = self._style_prop(pstyle, prop)
        if v is not None:
            return v
        return self.default_rpr.get(prop)

    def _resolve_pref(self, primary, fallback, run_rpr, rstyle, pstyle):
        """קדימות לכתב מורכב (bCs/iCs/szCs); אם אינו מוגדר כלל – נופל לכתב לטיני."""
        v = self._resolve(primary, run_rpr, rstyle, pstyle)
        if v is not None:
            return v
        return self._resolve(fallback, run_rpr, rstyle, pstyle)

    # --------------------------------------------------- רמת כותרת של פסקה
    def _style_outline(self, sid, seen=None):
        seen = seen or set()
        while sid and sid in self.styles and sid not in seen:
            seen.add(sid)
            info = self.styles[sid]
            if info["outline"] is not None:
                return info["outline"]
            sid = info["basedOn"]
        return None

    def _para_heading_level(self, p):
        """מחזיר 1..9 עבור פסקת כותרת, או None עבור טקסט רגיל."""
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

    # ----------------------------------------------------- חתימת עיצוב של ריצה
    def _run_signature(self, r, pstyle, normal_pt):
        """מחזיר tuple של תכונות התגיות עבור ריצה נתונה."""
        rpr = r.find(w("rPr"))
        run_rpr = self._extract_rpr(rpr) if rpr is not None else {}
        rstyle = None
        if rpr is not None:
            rs = rpr.find(w("rStyle"))
            if rs is not None:
                rstyle = rs.get(w("val"))

        bold = bool(self._resolve_pref("bCs", "b", run_rpr, rstyle, pstyle))
        italic = bool(self._resolve_pref("iCs", "i", run_rpr, rstyle, pstyle))
        underline = bool(self._resolve("u", run_rpr, rstyle, pstyle))
        va = self._resolve("vertAlign", run_rpr, rstyle, pstyle)
        sup = (va == "superscript")
        sub = (va == "subscript")

        size_cls = None
        if normal_pt and normal_pt > 0:
            szcs = self._resolve_pref("szCs", "sz", run_rpr, rstyle, pstyle)
            if szcs is not None:
                pt = szcs / 2.0
                eps = 1e-6
                if pt > normal_pt + eps and pt <= 20 + eps:
                    size_cls = "big"
                elif pt < normal_pt - eps and pt >= 3 - eps:
                    size_cls = "small"

        return (bold, underline, italic, sup, sub, size_cls)

    @staticmethod
    def _sig_tags(sig):
        """מחזיר את רשימת התגיות הפעילות לפי סדר הקינון (חיצוני -> פנימי)."""
        bold, underline, italic, sup, sub, size_cls = sig
        tags = []
        if size_cls:
            tags.append("big" if size_cls == "big" else "small")
        if sub:
            tags.append("sub")
        if sup:
            tags.append("sup")
        if italic:
            tags.append("i")
        if underline:
            tags.append("u")
        if bold:
            tags.append("b")
        return tags

    # ------------------------------------------------- איסוף אסימונים מפסקה
    def _paragraph_tokens(self, p, fn_map, pstyle, normal_pt):
        """
        עובר על תוכן הפסקה לפי הסדר ומחזיר רשימת אסימונים:
            ('run', sig, text)  או  ('fnref', 'מספר')
        """
        tokens = []
        sig_cache = {}
        for el in p.iter():
            name = _local(el)
            if name == "footnoteReference":
                fid = el.get(w("id"))
                num = fn_map.get(fid)
                if num is not None:
                    tokens.append(("fnref", str(num)))
                continue
            if name == "t":
                run = el.getparent()
                key = id(run)
                if key not in sig_cache:
                    sig_cache[key] = self._run_signature(run, pstyle, normal_pt)
                tokens.append(("run", sig_cache[key], el.text or ""))
            elif name == "tab":
                run = el.getparent()
                key = id(run)
                if key not in sig_cache:
                    sig_cache[key] = self._run_signature(run, pstyle, normal_pt)
                tokens.append(("run", sig_cache[key], "\t"))
            elif name in ("br", "cr"):
                tokens.append(("run", None, "\n"))
            elif name == "noBreakHyphen":
                run = el.getparent()
                key = id(run)
                if key not in sig_cache:
                    sig_cache[key] = self._run_signature(run, pstyle, normal_pt)
                tokens.append(("run", sig_cache[key], "-"))
        return tokens

    @staticmethod
    def _tokens_to_line(tokens):
        """
        בונה מחרוזת עם תגיות באמצעות מחסנית: כל מאפיין עוטף אזור רציף מקסימלי
        (בדיוק כמו מעברי החיפוש/החלפה במאקרו), והתגיות תמיד מקוננות כהלכה.
        """
        out = []
        stack = []  # תגיות פתוחות, מהחיצונית לפנימית

        def close_to(k):
            while len(stack) > k:
                out.append("</%s>" % stack.pop())

        for tok in tokens:
            if tok[0] == "fnref":
                close_to(0)
                out.append("<sup>%s</sup>" % tok[1])
                continue
            sig, text = tok[1], tok[2]
            if text == "":
                continue
            desired = [] if sig is None else DocxConverter._sig_tags(sig)
            common = 0
            while (common < len(stack) and common < len(desired)
                   and stack[common] == desired[common]):
                common += 1
            close_to(common)
            for t in desired[common:]:
                out.append("<%s>" % t)
                stack.append(t)
            out.append(text)
        close_to(0)
        return "".join(out)

    @staticmethod
    def _merge_adjacent_tags(line):
        """מיזוג תגיות סמוכות מופרדות ברווח, כמו במאקרו ('</b> <b>' -> ' ')."""
        for t in _MERGE_TAGS:
            line = line.replace("</%s> <%s>" % (t, t), " ")
            line = line.replace("<%s> </%s>" % (t, t), " ")
        return line

    @staticmethod
    def _clean_body_line(line):
        line = DocxConverter._merge_adjacent_tags(line)
        # הסרת רווחים בסוף שורה (כמו '[ ]@^13' -> '^13' במאקרו)
        line = re.sub(r"[ ]+(?=\n)", "", line)
        line = line.rstrip(" ")
        return line

    # ------------------------------------------------------------ הערות שוליים
    def _footnote_number_map(self):
        """ממפה id של הערה -> מספר סידורי, לפי סדר ההופעה בגוף המסמך."""
        fn_map = {}
        order = []
        num = 0
        for ref in self.doc.iter(w("footnoteReference")):
            fid = ref.get(w("id"))
            if fid is None or fid not in self.footnotes:
                continue
            if fid in fn_map:
                continue
            num += 1
            fn_map[fid] = num
            order.append(fid)
        return fn_map, order

    def _footnote_line(self, fn_el, notes_pt):
        """בונה את שורת ההערה (ללא הקידומת <sup>מספר</sup>), עם תגיות עיצוב."""
        para_lines = []
        for p in fn_el.findall(w("p")):
            pstyle = None
            pPr = p.find(w("pPr"))
            if pPr is not None:
                ps = pPr.find(w("pStyle"))
                if ps is not None:
                    pstyle = ps.get(w("val"))
            tokens = []
            sig_cache = {}
            for el in p.iter():
                name = _local(el)
                if name == "footnoteRef":
                    continue  # סימן ההערה של עצמה – מדולג
                if name == "footnoteReference":
                    continue  # הפניה מקוננת – מדולגת
                if name == "t":
                    run = el.getparent()
                    key = id(run)
                    if key not in sig_cache:
                        sig_cache[key] = self._run_signature(run, pstyle, notes_pt)
                    tokens.append(("run", sig_cache[key], el.text or ""))
                elif name == "tab":
                    run = el.getparent()
                    key = id(run)
                    if key not in sig_cache:
                        sig_cache[key] = self._run_signature(run, pstyle, notes_pt)
                    tokens.append(("run", sig_cache[key], "\t"))
                elif name in ("br", "cr"):
                    tokens.append(("run", None, "\n"))
                elif name == "noBreakHyphen":
                    run = el.getparent()
                    key = id(run)
                    if key not in sig_cache:
                        sig_cache[key] = self._run_signature(run, pstyle, notes_pt)
                    tokens.append(("run", sig_cache[key], "-"))
            line = self._tokens_to_line(tokens)
            line = self._merge_adjacent_tags(line)
            para_lines.append(line)
        # מעברי פסקה בתוך הערה -> <br> (כמו NOTE_LINE_TO_HTML), עם ניקוי קצוות
        text = "<br>".join(para_lines)
        text = text.replace("\n", "<br>")
        text = text.strip()
        while text.startswith("<br>"):
            text = text[4:].strip()
        while text.endswith("<br>"):
            text = text[:-4].strip()
        return text

    # ------------------------------------------------------------------ המרה
    def convert(self, normal_pt, notes_pt):
        """
        מבצע את ההמרה ומחזיר tuple:  (body_text, notes_text_or_None)
        normal_pt  – גודל הטקסט הרגיל (בנקודות)
        notes_pt   – גודל ההערות הרגיל (בנקודות)
        """
        fn_map, order = self._footnote_number_map()

        body = self.doc.find(w("body"))
        if body is None:
            raise ConversionError("מבנה מסמך לא תקין (חסר body)")

        lines = []
        # נעבור על פסקאות ברמה העליונה וגם בתוך טבלאות
        for p in body.iter(w("p")):
            level = self._para_heading_level(p)
            if level is not None:
                # כותרת: ללא תגיות עיצוב פנימיות, רק טקסט + סימני הערה
                tokens = self._paragraph_tokens(p, fn_map, None, 0)
                inner = []
                for tok in tokens:
                    if tok[0] == "fnref":
                        inner.append("<sup>%s</sup>" % tok[1])
                    else:
                        inner.append(tok[2])
                text = "".join(inner).replace("\n", " ").strip()
                if text:
                    lines.append("<h%d>%s</h%d>" % (level, text, level))
            else:
                pstyle = None
                pPr = p.find(w("pPr"))
                if pPr is not None:
                    ps = pPr.find(w("pStyle"))
                    if ps is not None:
                        pstyle = ps.get(w("val"))
                tokens = self._paragraph_tokens(p, fn_map, pstyle, normal_pt)
                line = self._tokens_to_line(tokens)
                line = self._clean_body_line(line)
                # פיצול מעברי שורה ידניים לשורות נפרדות
                for sub in line.split("\n"):
                    sub = sub.rstrip(" ")
                    if sub.strip() != "":
                        lines.append(sub)

        body_text = "\r\n".join(lines)

        notes_text = None
        if order:
            note_lines = []
            for fid in order:
                num = fn_map[fid]
                content = self._footnote_line(self.footnotes[fid], notes_pt)
                note_lines.append("<sup>%d</sup> %s" % (num, content))
            notes_text = "\r\n".join(note_lines)

        return body_text, notes_text

    # ----------------------------------------------- הצעת גודל טקסט רגיל
    def suggest_body_size(self):
        """מחזיר את גודל הטקסט הנפוץ ביותר בפסקאות הרגילות (בנקודות), או None."""
        from collections import Counter
        body = self.doc.find(w("body"))
        if body is None:
            return None
        counts = Counter()
        for p in body.iter(w("p")):
            if self._para_heading_level(p) is not None:
                continue
            pstyle = None
            pPr = p.find(w("pPr"))
            if pPr is not None:
                ps = pPr.find(w("pStyle"))
                if ps is not None:
                    pstyle = ps.get(w("val"))
            for t in p.iter(w("t")):
                run = t.getparent()
                rpr = run.find(w("rPr"))
                run_rpr = self._extract_rpr(rpr) if rpr is not None else {}
                rstyle = None
                if rpr is not None:
                    rs = rpr.find(w("rStyle"))
                    if rs is not None:
                        rstyle = rs.get(w("val"))
                szcs = self._resolve_pref("szCs", "sz", run_rpr, rstyle, pstyle)
                if szcs:
                    counts[szcs] += len(t.text or "")
        if not counts:
            return None
        return counts.most_common(1)[0][0] / 2.0

    # ----------------------------------------------- הצעת גודל הערות ברירת מחדל
    def suggest_notes_size(self):
        """מחזיר גודל מוצע להערות (מתוך סגנון 'footnote text' או ריצה בהערה), או None."""
        for sid, info in self.styles.items():
            nm = (info.get("name") or "").lower()
            if nm in ("footnote text", "annotation text") or "הערת שוליים" in nm:
                sz = info["rpr"].get("szCs") or info["rpr"].get("sz")
                if sz:
                    return sz / 2.0
        # נסיון שני: הגודל של הריצה הראשונה בהערה הראשונה
        for fn in self.footnotes.values():
            rpr = fn.find(".//%s/%s" % (w("r"), w("rPr")))
            if rpr is not None:
                el = rpr.find(w("szCs")) or rpr.find(w("sz"))
                if el is not None:
                    try:
                        return int(el.get(w("val"))) / 2.0
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
if __name__ == "__main__":
    import argparse
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
