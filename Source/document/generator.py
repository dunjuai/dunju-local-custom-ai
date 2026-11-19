"""
Dunju AI — Document Generator
Turn a chat reply (markdown) into a downloadable .docx / .pdf / .pptx / .xlsx.
Fully local/offline. Uses python-docx, reportlab, python-pptx, openpyxl.
"""

import io
import re


# ── Markdown → typed blocks ──────────────────────────────────────────
def parse_blocks(md: str) -> list:
    lines = (md or "").replace("\r\n", "\n").split("\n")
    n = len(lines)
    blocks, i = [], 0

    def is_sep(s):
        return "-" in s and bool(re.match(r'^\s*\|?[\s:|-]*-[\s:|-]*\|?\s*$', s))

    while i < n:
        line = lines[i]
        st = line.strip()
        if st.startswith("```"):
            code, i = [], i + 1
            while i < n and not lines[i].strip().startswith("```"):
                code.append(lines[i]); i += 1
            i += 1
            blocks.append(("code", "\n".join(code)))
            continue
        if "|" in line and i + 1 < n and is_sep(lines[i + 1]):
            header = [c.strip() for c in st.strip("|").split("|")]
            rows, i = [], i + 2
            while i < n and "|" in lines[i] and lines[i].strip():
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                i += 1
            blocks.append(("table", (header, rows)))
            continue
        m = re.match(r'^(#{1,4})\s+(.*)', line)
        if m:
            blocks.append(("h" + str(len(m.group(1))), m.group(2).strip())); i += 1; continue
        m = re.match(r'^\s*[-*•]\s+(.*)', line)
        if m:
            blocks.append(("bullet", m.group(1).strip())); i += 1; continue
        m = re.match(r'^\s*\d+[.)]\s+(.*)', line)
        if m:
            blocks.append(("number", m.group(1).strip())); i += 1; continue
        if st == "":
            i += 1; continue
        blocks.append(("para", st)); i += 1
    return blocks


def _plain(t: str) -> str:
    t = t or ""
    t = re.sub(r'\*\*(.+?)\*\*', r'\1', t)
    t = re.sub(r'\*(.+?)\*', r'\1', t)
    t = re.sub(r'`(.+?)`', r'\1', t)
    return t


# ── DOCX ─────────────────────────────────────────────────────────────
def generate_docx(content: str, title: str = "Dunju AI Export") -> bytes:
    from docx import Document
    from docx.shared import Pt
    doc = Document()
    if title:
        doc.add_heading(title, 0)

    def runs(p, text):
        for part in re.split(r'(\*\*.+?\*\*)', text):
            if part.startswith("**") and part.endswith("**"):
                p.add_run(part[2:-2]).bold = True
            elif part:
                p.add_run(re.sub(r'`(.+?)`', r'\1', re.sub(r'\*(.+?)\*', r'\1', part)))

    for kind, val in parse_blocks(content):
        if kind in ("h1", "h2", "h3", "h4"):
            doc.add_heading(_plain(val), int(kind[1]))
        elif kind == "bullet":
            runs(doc.add_paragraph(style="List Bullet"), val)
        elif kind == "number":
            runs(doc.add_paragraph(style="List Number"), val)
        elif kind == "code":
            r = doc.add_paragraph().add_run(val)
            r.font.name = "Consolas"; r.font.size = Pt(9)
        elif kind == "table":
            header, rows = val
            t = doc.add_table(rows=1, cols=len(header))
            try: t.style = "Light Grid Accent 1"
            except Exception: pass
            for j, h in enumerate(header):
                t.rows[0].cells[j].text = _plain(h)
            for row in rows:
                cells = t.add_row().cells
                for j in range(len(header)):
                    cells[j].text = _plain(row[j]) if j < len(row) else ""
        else:
            runs(doc.add_paragraph(), val)
    buf = io.BytesIO(); doc.save(buf); return buf.getvalue()


# ── PDF ──────────────────────────────────────────────────────────────
def generate_pdf(content: str, title: str = "Dunju AI Export") -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                    Table, TableStyle, Preformatted)
    from xml.sax.saxutils import escape
    ss = getSampleStyleSheet()
    body = ParagraphStyle("b", parent=ss["Normal"], fontSize=10.5, leading=15, spaceAfter=6)
    code = ParagraphStyle("c", parent=ss["Code"], fontSize=8.5, leading=11)

    def inline(t):
        t = escape(t or "")
        t = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', t)
        t = re.sub(r'\*(.+?)\*', r'<i>\1</i>', t)
        t = re.sub(r'`(.+?)`', r'<font face="Courier">\1</font>', t)
        return t

    story = []
    if title:
        story += [Paragraph(escape(title), ss["Title"]), Spacer(1, 8)]
    for kind, val in parse_blocks(content):
        if kind in ("h1", "h2", "h3", "h4"):
            story.append(Paragraph(inline(val), ss["Heading" + str(min(int(kind[1]), 4))]))
        elif kind == "bullet":
            story.append(Paragraph("&bull;&nbsp;" + inline(val), body))
        elif kind == "number":
            story.append(Paragraph(inline(val), body))
        elif kind == "code":
            story.append(Preformatted(val, code))
        elif kind == "table":
            header, rows = val
            data = [[Paragraph("<b>" + inline(_plain(h)) + "</b>", body) for h in header]]
            for row in rows:
                data.append([Paragraph(inline(_plain(row[j])) if j < len(row) else "", body)
                             for j in range(len(header))])
            t = Table(data, repeatRows=1)
            t.setStyle(TableStyle([
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cccccc")),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#ede9fe")),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]))
            story += [t, Spacer(1, 6)]
        else:
            story.append(Paragraph(inline(val), body))
    buf = io.BytesIO()
    SimpleDocTemplate(buf, pagesize=A4, topMargin=18 * mm, bottomMargin=18 * mm,
                      leftMargin=18 * mm, rightMargin=18 * mm).build(story)
    return buf.getvalue()


# ── PPTX ─────────────────────────────────────────────────────────────
def generate_pptx(content: str, title: str = "Dunju AI Export") -> bytes:
    from pptx import Presentation
    prs = Presentation()
    s0 = prs.slides.add_slide(prs.slide_layouts[0])
    s0.shapes.title.text = title or "Dunju AI Export"
    try: s0.placeholders[1].text = "Generated by Dunju AI"
    except Exception: pass

    state = {"tf": None}

    def new_slide(t):
        sl = prs.slides.add_slide(prs.slide_layouts[1])
        sl.shapes.title.text = t or "Overview"
        tf = sl.placeholders[1].text_frame
        tf.clear()
        state["tf"] = tf

    for kind, val in parse_blocks(content):
        if kind in ("h1", "h2"):
            new_slide(_plain(val))
            continue
        if state["tf"] is None:
            new_slide("Overview")
        if kind == "table":
            header, _ = val
            text = " | ".join(_plain(h) for h in header)
        elif kind == "code":
            text = val
        else:
            text = _plain(val)
        tf = state["tf"]
        if tf.text == "":
            tf.text = text
        else:
            tf.add_paragraph().text = text
    buf = io.BytesIO(); prs.save(buf); return buf.getvalue()


# ── XLSX ─────────────────────────────────────────────────────────────
def generate_xlsx(content: str, title: str = "Dunju AI Export") -> bytes:
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill
    wb = Workbook(); wb.remove(wb.active)
    blocks = parse_blocks(content)
    tables = [v for k, v in blocks if k == "table"]
    if tables:
        for idx, (header, rows) in enumerate(tables, 1):
            ws = wb.create_sheet(title=f"Table {idx}")
            ws.append([_plain(h) for h in header])
            for c in ws[1]:
                c.font = Font(bold=True)
                c.fill = PatternFill("solid", fgColor="EDE9FE")
            for row in rows:
                ws.append([_plain(x) for x in row])
    else:
        ws = wb.create_sheet(title="Content")
        for kind, val in blocks:
            if kind == "table":
                continue
            ws.append([_plain(val) if not isinstance(val, tuple) else ""])
    if not wb.sheetnames:
        wb.create_sheet(title="Content")
    buf = io.BytesIO(); wb.save(buf); return buf.getvalue()


MEDIA = {
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "pdf": "application/pdf",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


def generate(content: str, fmt: str, title: str = "Dunju AI Export"):
    fmt = (fmt or "docx").lower()
    fn = {"docx": generate_docx, "pdf": generate_pdf,
          "pptx": generate_pptx, "xlsx": generate_xlsx}.get(fmt)
    if not fn:
        raise ValueError(f"Unsupported format: {fmt}")
    return fn(content, title), MEDIA[fmt]
