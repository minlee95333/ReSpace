# -*- coding: utf-8 -*-
"""제안서 6장(연구 상세 내용) 초안을 워드(.docx) 로 뽑는다.

**왜 있는가.** 초안은 `docs/제안서_6장_연구상세내용.md` 에 마크다운으로 쓴다 —
수치가 바뀌면 고치기 쉽고 git 이 차이를 보여주기 때문이다. 그런데 그 형식은
표가 `|` 기호 그대로 보여서 사람이 읽기 나쁘고, 한글에 붙여넣을 수도 없다.
여기서 표를 진짜 표로, 그림 자리를 진짜 그림으로 바꿔 워드 문서를 만든다.

**제출물이 아니다.** 최종 제출은 .hwp 이며, 이 파일은 검토용이자 한글로
복사해 갈 원본이다.

**맑은 고딕에 U+2212(−) 가 없다.** 그대로 넣으면 네모로 뜨므로 ASCII 하이픈으로
바꾼다. 수식은 이 때문에 그림(`outputs/figures/eq_*.png`)으로 넣는다.

    python tools/make_section6_docx.py

산출: outputs/제안서_6장_0825.docx
"""
from pathlib import Path
import re
import sys

from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

ROOT = Path(__file__).resolve().parents[1]

# 압축 모드 — 제출 분량(5쪽)에 맞춘 판면. 원본 마크다운이 다르다.
COMPACT = "--compact" in sys.argv
# 원본을 인자로 받는다 (2026-08-27). 종전에는 파일명이 박혀 있어 새 판을 쓸
# 때마다 이 파일을 고쳐야 했다.
#
#   python tools/make_section6_docx.py                     # 최신본
#   python tools/make_section6_docx.py --compact           # 압축본
#   python tools/make_section6_docx.py docs/다른초안.md
_ARG = next((a for a in sys.argv[1:] if not a.startswith("--")), None)
if _ARG:
    SRC = Path(_ARG) if Path(_ARG).is_absolute() else ROOT / _ARG
elif COMPACT:
    SRC = ROOT / "docs" / "제안서_6장_압축본.md"
else:
    SRC = ROOT / "docs" / "제안서_6장_0827.md"
OUT = ROOT / "outputs" / (SRC.stem + ".docx")

FONT = "맑은 고딕"
BODY = 8.6 if COMPACT else 10.0
LEAD = 1.16 if COMPACT else 1.35          # 줄간격
GAP = 3 if COMPACT else 7                 # 문단 뒤 여백(pt)
MARGIN_CM = 1.7 if COMPACT else 2.5
INK = RGBColor(0x1E, 0x22, 0x28)
MUTED = RGBColor(0x5C, 0x65, 0x70)
ACCENT = RGBColor(0x14, 0x4E, 0x8C)
RULE = "D8DCE0"
HEAD_BG = "EEF1F4"

BODY_W_CM = 21.0 - 2 * MARGIN_CM   # A4 210mm - 좌우 여백

# 맑은 고딕에 없는 글자 → 있는 글자로
FIXUP = {
    "−": "-",        # 마이너스 기호
    "‑": "-",        # non-breaking hyphen
    " ": " ",
}


def fix(s: str) -> str:
    for a, b in FIXUP.items():
        s = s.replace(a, b)
    return s


# ── 서식 도구 ──────────────────────────────────────────────────────────────

def set_base(doc):
    st = doc.styles["Normal"]
    st.font.name = FONT
    st.font.size = Pt(BODY)
    st.element.rPr.rFonts.set(qn("w:eastAsia"), FONT)
    for s in doc.sections:
        s.top_margin = s.bottom_margin = Cm(MARGIN_CM)
        s.left_margin = s.right_margin = Cm(MARGIN_CM)


def _run(p, text, size=BODY, bold=False, color=INK, italic=False, mono=False):
    name = "Consolas" if mono else FONT
    r = p.add_run(fix(text))
    r.font.size = Pt(size - 0.5 if mono else size)
    r.bold = bold
    r.italic = italic
    r.font.color.rgb = color
    r.font.name = name
    r._element.rPr.rFonts.set(qn("w:eastAsia"), name)
    return r


INLINE = re.compile(r"(\*\*.+?\*\*|`[^`]+`|\*[^*]+?\*)")


def inline(p, text, size=BODY, color=INK, base_bold=False):
    """**굵게** · `코드` · *기울임* 을 살려서 한 문단에 이어 붙인다."""
    for tok in INLINE.split(text):
        if not tok:
            continue
        if tok.startswith("**") and tok.endswith("**"):
            _run(p, tok[2:-2], size, True, color)
        elif tok.startswith("`") and tok.endswith("`"):
            _run(p, tok[1:-1], size, base_bold, MUTED, mono=True)
        elif tok.startswith("*") and tok.endswith("*"):
            _run(p, tok[1:-1], size, base_bold, color, italic=True)
        else:
            _run(p, tok, size, base_bold, color)


def para(doc, text="", size=BODY, color=INK, after=GAP, before=0,
         indent=0.0, align=None, bold=False):
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.space_after, pf.space_before = Pt(after), Pt(before)
    pf.line_spacing = LEAD
    if indent:
        pf.left_indent = Cm(indent)
    if align is not None:
        p.alignment = align
    if text:
        inline(p, text, size, color, base_bold=bold)
    return p


def shade(cell, hexcolor):
    el = OxmlElement("w:shd")
    el.set(qn("w:val"), "clear")
    el.set(qn("w:fill"), hexcolor)
    cell._tc.get_or_add_tcPr().append(el)


def bar(doc, color=RULE, size=6):
    """문단 아래 가는 선 — 절 구분에 쓴다."""
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(size)
    pbdr = OxmlElement("w:pBdr")
    b = OxmlElement("w:bottom")
    b.set(qn("w:val"), "single")
    b.set(qn("w:sz"), "6")
    b.set(qn("w:color"), color)
    pbdr.append(b)
    p._p.get_or_add_pPr().append(pbdr)
    return p


# ── 마크다운 조각별 렌더 ───────────────────────────────────────────────────

def render_table(doc, rows):
    """rows[0] 는 머리글, rows[1] 은 정렬 지정줄."""
    header, align_row, body = rows[0], rows[1], rows[2:]
    aligns = []
    for a in align_row:
        a = a.strip()
        aligns.append(WD_ALIGN_PARAGRAPH.RIGHT if a.endswith(":") and not a.startswith(":")
                      else WD_ALIGN_PARAGRAPH.LEFT)
    n = len(header)
    t = doc.add_table(rows=0, cols=n)
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER

    def fill(cells, values, is_head):
        for i, (c, v) in enumerate(zip(cells, values)):
            c.paragraphs[0].clear() if False else None
            p = c.paragraphs[0]
            p.paragraph_format.space_before = Pt(0.5 if COMPACT else 2)
            p.paragraph_format.space_after = Pt(0.5 if COMPACT else 2)
            p.paragraph_format.line_spacing = 1.06 if COMPACT else 1.2
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER if is_head else aligns[i]
            inline(p, v.strip(), size=BODY - 0.5, base_bold=is_head)
            if is_head:
                shade(c, HEAD_BG)

    fill(t.add_row().cells, header, True)
    for row in body:
        row = (row + [""] * n)[:n]
        fill(t.add_row().cells, row, False)
    para(doc, "", after=6)
    return t


FIGRE = re.compile(
    r"<그림 (?:자리|2단)>\s*\*\*(.+?)\*\*\s*(?:\(`(.+?)`(?:,\s*`(.+?)`)?\))?")


def two_up(doc, paths, caption):
    """그림 둘을 나란히. 테두리 없는 1x2 표를 자로 쓴다."""
    t = doc.add_table(rows=1, cols=2)
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    w = (BODY_W_CM - 0.5) / 2
    for cell, rel in zip(t.rows[0].cells, paths):
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_before = Pt(2)
        p.paragraph_format.space_after = Pt(0)
        f = ROOT / rel
        if f.exists():
            p.add_run().add_picture(str(f), width=Cm(w))
        else:
            inline(p, f"[그림 없음: {rel}]")
    para(doc, caption, size=BODY - 0.4, color=MUTED,
         align=WD_ALIGN_PARAGRAPH.CENTER, after=GAP + 2, before=2)


def render_figure(doc, line, tail):
    m = FIGRE.match(line.strip())
    if not m:
        para(doc, line)
        return
    caption, *paths = m.groups()
    paths = [p for p in paths if p]
    if line.strip().startswith("<그림 2단>") and len(paths) == 2:
        two_up(doc, paths, caption)
        return
    for rel in paths:
        f = ROOT / rel
        if not f.exists():
            para(doc, f"[그림 파일 없음: {rel}]", color=MUTED, size=BODY - 1)
            continue
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_before = Pt(6)
        p.paragraph_format.space_after = Pt(3)
        # 압축 모드에서는 그림을 판면보다 좁게 — 세로가 줄어 쪽수가 준다
        full = BODY_W_CM * (0.80 if COMPACT else 1.0)
        w = full if not f.name.startswith("eq_") else min(full, 11.0)
        p.add_run().add_picture(str(f), width=Cm(w))
    cap = para(doc, caption, size=BODY - 0.5, color=MUTED,
               align=WD_ALIGN_PARAGRAPH.CENTER, after=4)
    if tail:
        para(doc, tail, size=BODY - 1, color=MUTED,
             align=WD_ALIGN_PARAGRAPH.CENTER, after=8)


def render(doc, lines):
    i, n = 0, len(lines)
    while i < n:
        ln = lines[i]
        s = ln.rstrip()

        # 코드 블록 (수식 등)
        if s.startswith("```"):
            i += 1
            buf = []
            while i < n and not lines[i].startswith("```"):
                buf.append(lines[i].rstrip())
                i += 1
            i += 1
            p = para(doc, "", after=8, before=4, indent=0.8)
            _run(p, "\n".join(buf), size=BODY + 0.5, color=ACCENT, mono=True)
            continue

        # 표
        if s.startswith("|"):
            rows = []
            while i < n and lines[i].lstrip().startswith("|"):
                cells = [c for c in lines[i].strip().strip("|").split("|")]
                rows.append(cells)
                i += 1
            if len(rows) >= 2:
                render_table(doc, rows)
            continue

        # 그림 자리
        if s.startswith("<그림 자리>") or s.startswith("<그림 2단>"):
            tail = ""
            j = i + 1
            if j < n and lines[j].strip().startswith("—"):
                while (j < n and lines[j].strip()
                       and not lines[j].lstrip().startswith("<그림")):
                    tail += (" " if tail else "") + lines[j].strip().lstrip("— ")
                    j += 1
            render_figure(doc, s, tail)
            i = j
            continue

        # 인용 블록
        if s.startswith(">"):
            buf = []
            while i < n and lines[i].lstrip().startswith(">"):
                buf.append(lines[i].lstrip()[1:].strip())
                i += 1
            text = " ".join(x for x in buf if x)
            if text:
                p = para(doc, text, size=BODY - 0.5, color=MUTED,
                         indent=0.6, after=9, before=3)
                pbdr = OxmlElement("w:pBdr")
                b = OxmlElement("w:left")
                b.set(qn("w:val"), "single")
                b.set(qn("w:sz"), "12")
                b.set(qn("w:space"), "10")
                b.set(qn("w:color"), "9AA6B2")
                pbdr.append(b)
                p._p.get_or_add_pPr().append(pbdr)
            continue

        # 구분선
        if s.strip() == "---":
            bar(doc)
            i += 1
            continue

        # 제목
        if s.startswith("### "):
            para(doc, s[4:], size=BODY + 0.5, color=ACCENT, bold=True,
                 before=7 if COMPACT else 10, after=3 if COMPACT else 4)
            i += 1
            continue
        if s.startswith("## "):
            para(doc, s[3:], size=BODY + (2.2 if COMPACT else 3.0), color=INK, bold=True,
                 before=11 if COMPACT else 16, after=4 if COMPACT else 6)
            i += 1
            continue
        if s.startswith("# "):
            para(doc, s[2:], size=BODY + 7.0, color=INK, bold=True, after=10)
            i += 1
            continue

        # 글머리표
        if s.lstrip().startswith("- "):
            depth = (len(s) - len(s.lstrip())) // 2
            body = s.lstrip()[2:]
            j = i + 1
            while j < n and lines[j].startswith("  " * (depth + 1)) \
                    and not lines[j].lstrip().startswith("- ") \
                    and lines[j].strip():
                body += " " + lines[j].strip()
                j += 1
            p = doc.add_paragraph()
            pf = p.paragraph_format
            pf.left_indent = Cm(0.55 + 0.5 * depth)
            pf.first_line_indent = Cm(-0.35)
            pf.space_after = Pt(4)
            pf.line_spacing = LEAD
            _run(p, "• ", color=MUTED)
            inline(p, body)
            i = j
            continue

        # 번호 목록
        m = re.match(r"^(\d+)\.\s+(.*)$", s)
        if m:
            body = m.group(2)
            j = i + 1
            while j < n and lines[j].startswith("   ") and lines[j].strip():
                body += " " + lines[j].strip()
                j += 1
            p = doc.add_paragraph()
            pf = p.paragraph_format
            pf.left_indent = Cm(0.7)
            pf.first_line_indent = Cm(-0.7)
            pf.space_after = Pt(4)
            pf.line_spacing = LEAD
            _run(p, f"{m.group(1)}. ", bold=True, color=ACCENT)
            inline(p, body)
            i = j
            continue

        # 빈 줄
        if not s.strip():
            i += 1
            continue

        # 보통 문단 — 다음 빈 줄까지 이어 붙인다
        buf = [s.strip()]
        j = i + 1
        while j < n and lines[j].strip() and not re.match(
                r"^(\||>|#|-\s|\d+\.\s|```|---|<그림 )", lines[j].lstrip()):
            buf.append(lines[j].strip())
            j += 1
        text = " ".join(buf)
        # **표 6-x. ...** 한 줄짜리는 표 제목으로 붙여 쓴다
        if re.match(r"^\*\*표 \d", text):
            para(doc, text, size=BODY - 0.5, color=INK, after=3, before=8)
        else:
            para(doc, text)
        i = j


def main():
    if not SRC.exists():
        sys.exit(f"원본이 없다: {SRC}")
    lines = SRC.read_text(encoding="utf-8").splitlines()

    # 맨 앞의 작업 메모 블록(> 로 시작하는 재작성 경위)은 문서에서 뺀다
    start = 0
    for k, ln in enumerate(lines):
        if ln.strip() == "---":
            start = k + 1
            break

    doc = Document()
    set_base(doc)
    para(doc, lines[0].lstrip("# "), size=BODY + (5.4 if COMPACT else 7.0),
         bold=True, after=2)
    para(doc, "제17회 LH 국토기술대전 공모 제안서 · 초안 2026-08-25"
         + (" · 제출 압축본" if COMPACT else ""),
         size=BODY - 0.5, color=MUTED, after=14)
    bar(doc)
    render(doc, lines[start:])

    # 표 뒤에 넣는 빈 문단이 끝에 남으면 워드가 쪽을 하나 더 센다
    body = doc.element.body
    for el in list(body)[::-1]:
        if el.tag.endswith("}p") and not "".join(el.itertext()).strip():
            body.remove(el)
        elif el.tag.endswith("}sectPr"):
            continue
        else:
            break

    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc.save(OUT)
    print(f"저장: {OUT}")
    print(f"  문단 {len(doc.paragraphs)} · 표 {len(doc.tables)} · "
          f"그림 {len(doc.inline_shapes)}")


if __name__ == "__main__":
    main()
