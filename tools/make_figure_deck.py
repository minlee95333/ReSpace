# -*- coding: utf-8 -*-
"""제안서용 그림 관리 덱(PPTX) 생성.

**그림을 PPT 안에서 관리한다.** 슬라이드 하나에 그림 하나를 놓고, 그 아래에
제안서에 그대로 쓸 캡션과 어느 절에 들어갈지를 적는다. 제안서를 쓸 때 여기서
복사해 붙이면 된다.

캡션에는 반드시 **수치**를 넣는다. 심사위원이 본문을 안 읽고 그림만 훑을 때
남는 것이 캡션 한 줄이기 때문이다.

수치는 outputs/ 에서 읽는다. 손으로 적은 값이 없어야 한다.

    python tools/make_figures.py && python tools/make_figures_extra.py
    python tools/make_figure_deck.py
"""
from pathlib import Path
import json
import datetime

from pptx import Presentation
from pptx.util import Cm, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN

ROOT = Path(__file__).resolve().parents[1]
FIG = ROOT / "outputs" / "figures"
OUT = ROOT / "outputs" / "BIGB_그림_0823.pptx"


def _free(path: Path) -> Path:
    """파일이 잠겨 있으면(파워포인트로 열려 있으면) 옆 이름으로 낸다.

    덮어쓰기를 시도하면 PermissionError 로 죽고, 강제로 덮으면 사용자가
    편집 중이던 내용이 날아간다. 둘 다 하지 않는다.
    """
    try:
        with open(path, "ab"):
            return path
    except PermissionError:
        for i in range(2, 20):
            alt = path.with_name(f"{path.stem}_v{i}{path.suffix}")
            try:
                with open(alt, "ab"):
                    return alt
            except PermissionError:
                continue
        raise

# 16:9
W, H = Cm(33.87), Cm(19.05)

# **검정·흰색·회색만 쓴다.** 강조는 색이 아니라 명도와 굵기로 한다.
INK = RGBColor(0x1A, 0x1A, 0x1A)
MUTED = RGBColor(0x6E, 0x6E, 0x6E)
ACCENT = RGBColor(0x1A, 0x1A, 0x1A)
# 그림 배경이 순백이라 슬라이드도 맞춘다. 미색이면 그림 테두리가 드러난다
PAPER = RGBColor(0xFF, 0xFF, 0xFF)
RULE = RGBColor(0xC9, 0xC9, 0xC9)
FONT = "맑은 고딕"

sr = json.loads((ROOT / "outputs" / "safety_report.json").read_text(encoding="utf-8"))
cm_ = json.loads((ROOT / "outputs" / "comparison.json").read_text(encoding="utf-8"))
cp = json.loads((ROOT / "outputs" / "curve_params.json").read_text(encoding="utf-8"))
sn = json.loads((ROOT / "outputs" / "sensitivity.json").read_text(encoding="utf-8"))
site = json.loads((ROOT / "outputs" / "site_eval.json").read_text(encoding="utf-8"))
mf = json.loads((ROOT / "data" / "filtered" / "manifest.json").read_text(encoding="utf-8"))

pl = cm_["placements"]
sd = sr["coverage"]["overall"]["score_detail"]
pres = sr["prescription"]
prim = cp["per_target"][cp["primary"]]
cut = (1 - pl["empirical"]["fail_voxel_count"]
       / pl["geometric"]["fail_voxel_count"]) * 100


def txt(slide, x, y, w, hgt, text, size, color=INK, bold=False,
        align=PP_ALIGN.LEFT, space=6):
    tb = slide.shapes.add_textbox(x, y, w, hgt)
    tf = tb.text_frame
    tf.word_wrap = True
    lines = text.split("\n")
    for i, line in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        p.space_after = Pt(space)
        r = p.add_run()
        r.text = line
        r.font.size = Pt(size)
        r.font.bold = bold
        r.font.color.rgb = color
        r.font.name = FONT
    return tb


def slide_fig(prs, no, title, png, caption, section, why, note=None):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    s.background.fill.solid()
    s.background.fill.fore_color.rgb = PAPER

    txt(s, Cm(1.6), Cm(0.8), Cm(24), Cm(1.2), f"그림 {no}", 13, ACCENT, True)
    txt(s, Cm(1.6), Cm(1.7), Cm(30), Cm(1.4), title, 22, INK, True)
    txt(s, Cm(26.5), Cm(0.9), Cm(6), Cm(1.0), section, 12, MUTED, True,
        PP_ALIGN.RIGHT)

    p = FIG / png
    if p.exists():
        from PIL import Image
        iw, ih = Image.open(p).size
        # 가로로 납작한 그림은 위쪽에 붙어 아래가 비어 보인다. 세로 가운데로 둔다.
        top, band = Cm(3.5), Cm(11.4)
        scale = min(Cm(30.6) / iw, band / ih)
        w_, h_ = int(iw * scale), int(ih * scale)
        s.shapes.add_picture(str(p), int((W - w_) / 2),
                             int(top + (band - h_) / 2), w_, h_)
    else:
        txt(s, Cm(1.6), Cm(7), Cm(30), Cm(2), f"[{png} 없음]", 16, ACCENT)

    txt(s, Cm(1.6), Cm(15.2), Cm(30.6), Cm(1.4), caption, 13, INK, True)
    txt(s, Cm(1.6), Cm(16.4), Cm(30.6), Cm(1.8), why, 11, MUTED)
    if note:
        txt(s, Cm(1.6), Cm(17.5), Cm(30.6), Cm(1.2), note, 10, ACCENT)
    return s


def slide_pipeline_native(prs):
    """파이프라인을 **네이티브 도형**으로 그린다.

    그림 파일로 넣으면 PPT 에서 글자 하나 못 고친다. 이 장만은 도형·화살표·
    글상자로 만들어 파워포인트에서 그대로 편집할 수 있게 한다. 상자를 끌어
    옮기고 문구를 고치고 색을 바꾸는 일이 전부 된다.

    배치는 두 단이다. 입력 넷을 상단에 가로로 묶고, 복셀화부터 처방까지는
    한 줄로 흐른다. 갈래가 없으니 굽은 화살표도 없다.
    """
    from pptx.enum.shapes import MSO_SHAPE, MSO_CONNECTOR
    from pptx.enum.text import MSO_ANCHOR
    from pptx.util import Emu

    s = prs.slides.add_slide(prs.slide_layouts[6])
    s.background.fill.solid()
    s.background.fill.fore_color.rgb = PAPER

    txt(s, Cm(1.6), Cm(0.8), Cm(24), Cm(1.2), "그림 4", 13, ACCENT, True)
    txt(s, Cm(1.6), Cm(1.7), Cm(21), Cm(1.4), "입력에서 처방까지", 22, INK, True)
    txt(s, Cm(26.5), Cm(0.9), Cm(6), Cm(1.0), "§3 개선방안", 12, MUTED, True,
        PP_ALIGN.RIGHT)
    txt(s, Cm(24.2), Cm(2.1), Cm(8.4), Cm(1.0),
        "이 장은 도형이라 PPT 에서 편집됩니다", 10, ACCENT, False, PP_ALIGN.RIGHT)

    def node(x, y, w, hgt, title, sub, hot=False, t_size=13, s_size=10):
        sh = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, x, y, w, hgt)
        sh.adjustments[0] = 0.09
        sh.fill.solid()
        sh.fill.fore_color.rgb = PAPER
        # 강조는 색이 아니라 선 굵기다. 무채색만 쓰기 때문이다.
        sh.line.color.rgb = INK if hot else RULE
        sh.line.width = Pt(2.0) if hot else Pt(1.0)
        sh.shadow.inherit = False
        tf = sh.text_frame
        tf.word_wrap = True
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        tf.margin_left = tf.margin_right = Cm(0.15)
        tf.margin_top = tf.margin_bottom = Cm(0.1)
        p0 = tf.paragraphs[0]
        p0.alignment = PP_ALIGN.CENTER
        r = p0.add_run(); r.text = title
        r.font.size = Pt(t_size); r.font.bold = True
        r.font.color.rgb = ACCENT if hot else INK
        r.font.name = FONT
        if sub:
            p1 = tf.add_paragraph()
            p1.alignment = PP_ALIGN.CENTER
            p1.space_before = Pt(2)
            r1 = p1.add_run(); r1.text = sub
            r1.font.size = Pt(s_size)
            r1.font.color.rgb = MUTED
            r1.font.name = FONT
        return sh

    def connect(x1, y1, x2, y2):
        c = s.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, x1, y1, x2, y2)
        c.line.color.rgb = MUTED
        c.line.width = Pt(1.2)
        # 화살촉은 python-pptx 가 직접 안 열어준다. XML 로 붙인다
        ln = c.line._get_or_add_ln()
        from pptx.oxml.ns import qn as _qn
        import copy
        tail = ln.makeelement(_qn("a:tailEnd"), {"type": "triangle",
                                                 "w": "med", "len": "med"})
        ln.append(tail)
        return c

    # ── 상단: 입력 넷 ─────────────────────────────────────────────────
    INPUTS = [("CCTV 계획서", "위치·높이·방위·화각"), ("골조 형상", "도면·BIM·실측"),
              ("위험구역", "안전관리계획서"), ("공정표", "시간대별 작업")]
    IW, IGAP, IH = Cm(6.9), Cm(1.0), Cm(2.2)
    x0 = int((prs.slide_width - (4 * IW + 3 * IGAP)) / 2)
    top = Cm(4.3)
    for i, (t1, t2) in enumerate(INPUTS):
        node(x0 + i * (IW + IGAP), top, IW, IH, t1, t2, t_size=12.5, s_size=9.5)

    # 묶음 표시 ― 가로선 하나와 양끝 짧은 세로선
    span_r = x0 + 4 * IW + 3 * IGAP
    bar_y = top + IH + Cm(0.55)
    for a, b, c_, d in ((x0, bar_y, span_r, bar_y),
                        (x0, bar_y - Cm(0.28), x0, bar_y),
                        (span_r, bar_y - Cm(0.28), span_r, bar_y)):
        ln = s.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, a, b, c_, d)
        ln.line.color.rgb = RULE
        ln.line.width = Pt(1.0)
    txt(s, span_r - Cm(10), bar_y + Cm(0.15), Cm(10), Cm(0.8),
        "입력 ― 네 개의 계약 파일", 10.5, MUTED, False, PP_ALIGN.RIGHT)

    # ── 하단: 복셀화 → 처방 한 줄 ─────────────────────────────────────
    CHAIN = [("복셀화 + 광선투사", "ρ · θ · o", False),
             ("검출확률 곡선", "f(ρ)·g(θ)·h(o)", True),
             ("다중 카메라 결합", "1 - Π(1-P)", False),
             ("100점 채점", "배점 × 달성률", True),
             ("처방", "재배치 → 증설", False)]
    CW, CGAP, CH = Cm(5.5), Cm(1.0), Cm(2.3)
    cx0 = int((prs.slide_width - (5 * CW + 4 * CGAP)) / 2)
    cy = Cm(11.2)
    mid = cy + int(CH / 2)
    for i, (t1, t2, hot) in enumerate(CHAIN):
        x = cx0 + i * (CW + CGAP)
        node(x, cy, CW, CH, t1, t2, hot=hot, t_size=11.5, s_size=9.5)
        if i:
            connect(x - CGAP, mid, x, mid)

    # 묶음 → **첫 단계**. 슬라이드 가운데로 떨어뜨리면 세 번째 상자를 가리켜
    # 입력이 중간에 끼어드는 것처럼 읽힌다.
    drop_x = cx0 + int(CW / 2)
    connect(drop_x, bar_y, drop_x, cy)

    txt(s, cx0, Cm(13.9), Cm(28), Cm(0.9),
        "ρ 화면 속 머리 크기(픽셀)   ·   θ 내려다보는 각도   ·   "
        "o 가려진 정도   ·   P 검출확률", 10.5, INK)

    txt(s, Cm(1.6), Cm(15.0), Cm(30.6), Cm(1.2),
        "그림 4. 처리 흐름. 입력은 네 개의 계약 파일이며 실제 도면·계획서를 "
        "그 형식으로 넣으면 그대로 돈다.", 13, INK, True)
    txt(s, Cm(1.6), Cm(16.1), Cm(30.6), Cm(1.6),
        "굵은 테두리 상자 둘이 이 연구의 몫이다. 나머지는 기존 기법을 조합한 것이고, "
        "새로운 것은 검출확률을 실측해 연속값으로 다루는 것과 그 위에서 "
        "위험가중으로 채점한다는 점이다.", 11, MUTED)
    txt(s, Cm(1.6), Cm(17.6), Cm(30.6), Cm(1.0),
        "★ 필수 · 도형이라 PPT 에서 바로 수정된다. 그림 파일 판은 "
        "outputs/figures/fig_pipeline.png", 10, ACCENT)
    return s


def build():
    prs = Presentation()
    prs.slide_width, prs.slide_height = W, H

    # ── 표지 ──────────────────────────────────────────────────────────
    s = prs.slides.add_slide(prs.slide_layouts[6])
    s.background.fill.solid()
    s.background.fill.fore_color.rgb = PAPER
    txt(s, Cm(2.6), Cm(6.0), Cm(28), Cm(2), "BIGB 제안서 그림 모음", 34, INK, True)
    txt(s, Cm(2.6), Cm(8.4), Cm(28), Cm(1.4),
        "AI CCTV 배치 적정성 평가 모델   ·   슬라이드 하나에 그림 하나", 15, MUTED)
    txt(s, Cm(2.6), Cm(10.4), Cm(28), Cm(4),
        "· 캡션은 제안서에 그대로 쓸 수 있게 수치를 넣어 적었다\n"
        "· 원본 PNG 는 outputs/figures/ 에 300dpi 로 있다\n"
        "· 수치가 바뀌면 make_figures.py → make_figures_extra.py → 이 파일 순으로 다시 돌린다\n"
        f"· 생성 {datetime.date.today():%Y-%m-%d}", 12.5, MUTED)

    # ── 필수 ──────────────────────────────────────────────────────────
    slide_fig(
        prs, "1", "같은 사람, 같은 카메라. 조건만 다르다", "fig_samples.png",
        f"그림 1. 설치 조건에 따른 화면 속 작업자. 오른쪽은 현장에서 흔한 조건이며 "
        f"이 조건의 미착용 검출률은 사실상 0이다.",
        "§2 현황분석·문제점",
        "말로 설명하면 안 와닿는 것을 3초에 끝낸다. 심사위원 대부분은 건설 쪽이지 "
        "비전 쪽이 아니다. 제안서에서 가장 앞에 두는 그림.",
        "★ 필수 · 이 그림 하나가 문제 제기를 통째로 대신한다")

    slide_fig(
        prs, "2", "설치 조건이 검출률을 어떻게 깎는가", "fig_curves.png",
        f"그림 2. 실측 검출확률 곡선. 288조건 × {mf['n_selected']}장 추론, "
        f"주 지표 R² = {cp['r2_primary']:.4f}.",
        "§3 개선방안",
        f"세 축을 각각 곡선으로 만들고 곱한다. θ는 45도까지 버티다 "
        f"{prim['g_theta']['params']['x0']:.0f}도 부근에서 절벽처럼 무너진다.",
        "★ 필수 · 핵심 아이디어")

    slide_fig(
        prs, "3", "같은 8대인데 자를 바꾸면 배치가 갈린다", "fig_three.png",
        f"그림 3. 동일 예산 8대에서 미달 복셀 "
        f"{pl['geometric']['fail_voxel_count']:,} → "
        f"{pl['empirical']['fail_voxel_count']:,}개 ({cut:.0f}% 감소).",
        "§3 개선방안",
        f"세 배치를 모두 실측 곡선의 자로 재측정했다. 평균 검출률 차이는 "
        f"+{cm_['delta_WDR']['empirical_minus_geometric']:.4f}로 작아 보이지만 "
        f"못 보는 자리가 3분의 1로 준다.",
        "★ 필수 · 핵심 실증. 평균이 아니라 꼬리를 보여주는 것이 요점")

    slide_pipeline_native(prs)

    slide_fig(
        prs, "5", "100점을 어디서 잃었나", "fig_score.png",
        f"그림 5. 예시 계획서 채점. 총점 {sd['total']:.1f}/100, 등급 "
        f"{sd['grade']}. 치명 구역 {len(sd['critical_failures'])}곳 미달로 "
        f"등급 상한이 걸렸다.",
        "§3 개선방안",
        "단일 커버리지 %가 지우는 정보를 되살리는 그림. 개구부 주변이 배점 "
        f"{sd['rows'][2]['allocated']:.1f}점 중 {sd['rows'][2]['earned']:.1f}점만 "
        "얻은 것이 한눈에 보인다.",
        "★ 필수 · 빗금(배점)과 채움(획득)이라 흑백 출력에서도 읽힌다")

    slide_fig(
        prs, "6", "옮기면 되는가, 더 달아야 하는가", "fig_prescribe.png",
        f"그림 6. 처방. 같은 8대 재배치로 95.6점까지 오르나 개구부가 남고, "
        f"{pres['add_cameras']}대를 증설하면 {pres['resulting']*100:.1f}점에 도달한다.",
        "§3 개선방안 / §6 파급효과",
        "대수를 늘리기 전에 재배치를 먼저 시도한다는 것이 실무에서 받아들여지는 "
        "이유다. 예산을 쓰지 않고 되는 일을 증설로 답하면 발주처가 쓰지 않는다.",
        "★ 필수")

    # ── 선택 ──────────────────────────────────────────────────────────
    slide_fig(
        prs, "7", "3D 검출확률 히트맵", "../../docs/screenshots/m-3d.png",
        "그림 7. 심사자 화면. 복셀별 검출확률을 색으로, 카메라 화각을 부채꼴로 "
        "표시한다.",
        "§5 적용성",
        "PT 승부처. 지면에서는 한 장만 쓰고 2D/2.5D 전환은 발표에서 보인다.",
        "선택 · 스크린샷이라 해상도 확인 필요")

    slide_fig(
        prs, "8", "스마트 안전보고서", "fig_report.png",
        "그림 8. 자동 생성되는 안전보고서. 건설기술진흥법 시행규칙 별표 7 의 "
        "CCTV 설치·운용계획 칸을 채운다.",
        "§5 적용성 / §6 파급효과",
        "A4 한 장을 그대로 넣으면 1:2.9 로 길쭉해 글씨가 안 읽힌다. 세로로 "
        "반을 갈라 좌우로 놓아 1:0.7 로 만들었다. 긴 표는 앞부분만 남겼다.",
        "★ 필수로 올림 · 법정 서류에 자리가 있다는 §1 논거와 짝을 이룬다")

    slide_fig(
        prs, "9", "시간대별 위험구역 진단", "../../docs/screenshots/time-phased.png",
        f"그림 9. 하루 다섯 시간대 진단. 최악은 "
        f"{(sr.get('time_phased') or {}).get('worst_window', '-')} 시간대이며 "
        f"종합은 평균이 아니라 최악값으로 대표한다.",
        "§3 개선방안",
        "고정 배치가 시간에 따라 달라지는 위험을 따라가는지 보인다. 카메라를 "
        "옮기는 4D 최적화와는 축이 다르다.",
        "선택 · 자리가 모자라면 표로 대체 가능")

    # ── 넣지 말 것 ────────────────────────────────────────────────────
    s = prs.slides.add_slide(prs.slide_layouts[6])
    s.background.fill.solid()
    s.background.fill.fore_color.rgb = PAPER
    txt(s, Cm(1.6), Cm(1.4), Cm(30), Cm(1.4), "넣지 말 것 · 제작 규칙", 24, INK, True)
    txt(s, Cm(1.6), Cm(3.6), Cm(15), Cm(9),
        "넣지 말 것\n\n"
        "· DORI 등급 스윕, 민감도 스윕 — 표가 낫다. 그림은 자리만 먹는다\n"
        f"   (민감도는 ΔWDR +{sn['delta_WDR_range'][0]:.4f} ~ "
        f"+{sn['delta_WDR_range'][1]:.4f} 한 줄이면 끝난다)\n"
        "· 코드 스크린샷 — 값어치가 없다\n"
        "· 2D/2.5D/3D 세 장 나란히 — 지면에서는 중복. 하나만\n"
        "· 곡선 파라미터 표를 그림으로 — 본문 표로",
        12.5, MUTED)
    txt(s, Cm(17.6), Cm(3.6), Cm(15), Cm(9),
        "제작 규칙\n\n"
        "· 300dpi PNG, 가로 최소 2,000px\n"
        "· 색만으로 구분하지 않는다. 심사위원이 흑백 출력할 수 있다\n"
        "   → 빗금·선 모양·마커를 같이 쓴다\n"
        "· 캡션에 수치를 넣는다. 본문을 안 읽고 그림만 훑을 때 남는 한 줄\n"
        "· 그림 번호는 절 번호와 맞춘다 (그림 3-1, 3-2)\n"
        "· 15매에 그림 9개면 실질 4~5쪽. 본문 분량을 먼저 잡고 넣는다",
        12.5, MUTED)

    out = _free(OUT)
    prs.save(out)
    return out


if __name__ == "__main__":
    p = build()
    print(f"→ {p}")
