# -*- coding: utf-8 -*-
"""제안서 본문에 붙일 수식 그림(PNG·SVG).

**왜 필요한가.** 제출 원본이 .hwp 라 수식 개체가 다른 편집기(Word·PDF 변환)를
거치면 글자 하나("P")로 뭉개져 나온다. 실제로 6.7.3 의 종합 검출확률 식이
그렇게 깨졌다. 그림으로 넣으면 어디서 열어도 같은 모양이 나온다.

**어떻게.** matplotlib mathtext(STIX) 로 렌더한다. LaTeX 설치가 필요 없고
Cambria Math 와 모양이 가깝다. 배경은 투명이라 본문 어디에 놓아도 뜨지 않는다.

기호 설명이 붙은 판(`eq_ptotal_legend`)은 **논문 그림 조판**을 따른다 —
"여기서," 같은 안내 문구도 구분선도 넣지 않고, 식과 기호표를 각각 중앙에 두어 한
덩어리로 보이게 한다. 열 너비는 글자를 실제로 재서 잡는다(고정 들여쓰기로는
한쪽이 치우친다).

    python tools/make_equation_png.py

산출: outputs/figures/eq_*.png (600dpi), eq_*.svg
"""
import os
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "figures"
OUT.mkdir(parents=True, exist_ok=True)

INK = "#1C1A17"          # 순흑 금지 (tools/theme.py 와 같은 먹색)
KR = "Malgun Gothic"     # 맑은 고딕. U+2212(−)이 없으므로 설명문은 ASCII 하이픈
DPI = 600

matplotlib.rcParams.update({
    "mathtext.fontset": "stix",
    "font.family": "STIXGeneral",
})

# (파일명, 수식, 글자크기)
EQS = [
    # 6.7.3 다중 카메라 결합 — 이번에 깨진 식
    ("eq_ptotal",
     r"$P_{\mathrm{total}}(v)\;=\;1-\prod_{c\,\in\,C}\left(1-P(v,c)\right)$", 26),
    # 같은 절의 위험가중 검출률
    ("eq_wdr",
     r"$\mathrm{WDR}\;=\;\frac{\sum_{v} w(v)\cdot P_{\mathrm{total}}(v)}"
     r"{\sum_{v} w(v)}$", 26),
    # 6.7.2 분리형 곱셈 곡선
    ("eq_curve",
     r"$P(\rho,\theta,o)\;=\;f(\rho)\cdot g(\theta)\cdot h(o)$", 26),
]


def render(name: str, tex: str, size: int) -> None:
    fig = plt.figure(figsize=(0.01, 0.01))
    fig.text(0, 0, tex, fontsize=size, color=INK, ha="left", va="bottom")
    for ext in ("png", "svg"):
        fig.savefig(OUT / f"{name}.{ext}", dpi=DPI, transparent=True,
                    bbox_inches="tight", pad_inches=0.06)
    plt.close(fig)
    print(f"  {name}.png / .svg")


# ── 기호 설명이 붙은 판 ────────────────────────────────────────────────────
LEGEND_EQ = r"$P_{\mathrm{total}}(v)\;=\;1-\prod_{c\,\in\,C}\left(1-P(v,c)\right)$"

LEGEND_ROWS = [
    (r"$v$", ["평가 대상 공간. 현장을 1 m 격자로 나눈 복셀 하나"]),
    (r"$c$", ["현장에 배치된 CCTV 한 대"]),
    (r"$C$", ["해당 배치에서 선택된 CCTV 집합 (본 평가는 8대)"]),
    (r"$P(v,c)$", ["CCTV c 가 공간 v 의 객체를 검출할 확률.",
                   "6.7.2 의 곡선 P = f(ρ)·g(θ)·h(o) 로 산정하며,",
                   "v 가 c 의 화각을 벗어나거나 완전히 가려지면 0 이다"]),
    (r"$1-P(v,c)$", ["CCTV c 가 공간 v 의 객체를 놓칠 확률"]),
    (r"$\prod_{c\,\in\,C}$", ["배치된 모든 CCTV 가 동시에 놓칠 확률.",
                              "카메라별 검출이 독립이라는 1차 가정에서 곱이 된다"]),
    (r"$P_{\mathrm{total}}(v)$", ["적어도 한 대가 검출할 확률 (0 ~ 1).",
                                  "0.5 미만인 공간을 미달구역으로 판정한다"]),
]

# 기호표는 식의 딸림이라 활자를 절반으로 줄인다. 행간·열간도 같은 비율로 줄여야
# 표가 성기게 벌어지지 않는다.
# 짧은 판 — 식을 읽는 데 꼭 필요한 다섯 기호만. 1-P 와 곱셈기호는 P(v,c) 를
# 정의하고 나면 저절로 읽히므로 뺀다.
LEGEND_ROWS_MIN = [
    (r"$v$", ["평가 대상 공간 (1 m 복셀)"]),
    (r"$c$", ["배치된 CCTV 한 대"]),
    (r"$C$", ["배치된 CCTV 집합"]),
    (r"$P(v,c)$", ["CCTV c 가 공간 v 를 검출할 확률"]),
    (r"$P_{\mathrm{total}}(v)$", ["공간 v 의 종합 검출확률"]),
]

EQ_SIZE, SYM_SIZE, DESC_SIZE = 20, 6.25, 5.25
LINE_H = 0.098           # inch. 설명문 한 줄 높이
ROW_GAP = 0.035          # 기호 사이 여백
COL_GAP = 0.09           # 기호열과 설명열 사이
PAD = 0.10               # bbox_inches="tight" 가 더 잘라내므로 최소만


def _measure(items):
    """(문자열, 크기, 폰트) 목록의 실제 폭·높이를 인치로 잰다."""
    fig = plt.figure(figsize=(40, 40), dpi=100)
    r = fig.canvas.get_renderer()
    out = []
    for text, size, fam in items:
        kw = {"family": fam} if fam else {}
        t = fig.text(0, 0, text, fontsize=size, **kw)
        bb = t.get_window_extent(renderer=r)
        out.append((bb.width / 100.0, bb.height / 100.0))
    plt.close(fig)
    return out


def render_legend(rows=None, name="eq_ptotal_legend"):
    rows = rows or LEGEND_ROWS
    eq_w, eq_h = _measure([(LEGEND_EQ, EQ_SIZE, None)])[0]
    syms = _measure([(s, SYM_SIZE, None) for s, _ in rows])
    descs = _measure([(l, DESC_SIZE, KR)
                      for _, d in rows for l in d])

    sym_w = max(w for w, _ in syms)
    desc_w = max(w for w, _ in descs)
    table_w = sym_w + COL_GAP + desc_w
    block_w = max(table_w, eq_w)
    W = block_w + PAD * 2

    # 행 높이 — 기호는 첫 줄에 맞춰 세로 중앙을 두되, ∏ 처럼 큰 기호는 그만큼 벌린다
    row_h = []
    for (_, d), (_, sh) in zip(rows, syms):
        row_h.append(max(len(d) * LINE_H, LINE_H * 0.5 + sh * 0.5 + 0.04))

    GAP = 0.05               # 식과 기호표 사이 여백 (구분선 없이 여백만)
    H = PAD * 2 + eq_h + GAP * 2 + sum(row_h) + ROW_GAP * (len(rows) - 1)

    fig = plt.figure(figsize=(W, H))
    y = H - PAD

    fig.text(0.5, (y - eq_h * 0.5) / H, LEGEND_EQ, fontsize=EQ_SIZE, color=INK,
             ha="center", va="center")
    y -= eq_h + GAP

    x0 = (W - block_w) / 2                     # 식과 표를 같은 중심선에 둔다
    y -= GAP

    x_sym = (x0 + (block_w - table_w) / 2 + sym_w) / W      # 기호열 우측정렬
    x_desc = x_sym + (COL_GAP / W)                          # 설명열 좌측정렬
    for (sym, desc), h in zip(rows, row_h):
        y_first = y - LINE_H * 0.55
        fig.text(x_sym, y_first / H, sym, fontsize=SYM_SIZE, color=INK,
                 ha="right", va="center")
        for i, line in enumerate(desc):
            fig.text(x_desc, (y_first - i * LINE_H) / H, line,
                     fontsize=DESC_SIZE, color=INK, family=KR,
                     ha="left", va="center")
        y -= h + ROW_GAP

    for ext in ("png", "svg"):
        fig.savefig(OUT / f"{name}.{ext}", dpi=DPI, transparent=True,
                    bbox_inches="tight", pad_inches=0.04)
    plt.close(fig)
    print(f"  {name}.png / .svg")


# ── 한글 라벨 곡선식 ───────────────────────────────────────────────────────
# 기호 대신 한글 이름으로 읽히게 한 판. 본문 6.7.2 용이다.
# f·g·h 는 식의 기호이므로 이탤릭(STIX)으로 두고 한글만 KoPub 으로 찍는다.
KO_EQ = [
    ("검출확률  =  ", False), (r"$f$", True), ("(유효픽셀밀도)  ·  ", False),
    (r"$g$", True), ("(부감각)  ·  ", False), (r"$h$", True), ("(가림률)", False),
]


def _kopub(filename):
    """KoPub 은 굵기마다 파일이 다르고 패밀리 이름은 같다. 파일을 직접 지정한다."""
    for d in (Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "Windows" / "Fonts",
              Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"):
        f = d / filename
        if f.exists():
            return FontProperties(fname=str(f))
    raise SystemExit(f"폰트를 찾을 수 없다: {filename}. KoPub 은 kopus.org 에서 받는다.")


def render_ko_eq(font_file, name, size=20):
    """한글 서체를 지정해 한 줄 식을 그린다. 조각마다 폭을 재서 이어 붙인다."""
    fp = _kopub(font_file)
    probe = plt.figure(figsize=(40, 40), dpi=100)
    r = probe.canvas.get_renderer()
    widths, heights = [], []
    for text, is_math in KO_EQ:
        kw = {} if is_math else {"fontproperties": fp}
        bb = probe.text(0, 0, text, fontsize=size, **kw).get_window_extent(renderer=r)
        widths.append(bb.width / 100.0)
        heights.append(bb.height / 100.0)
    plt.close(probe)

    W = sum(widths) + 0.1
    H = max(heights) * 2.0
    fig = plt.figure(figsize=(W, H))
    x = 0.05
    for (text, is_math), w in zip(KO_EQ, widths):
        kw = {} if is_math else {"fontproperties": fp}
        fig.text(x / W, 0.5, text, fontsize=size, color=INK,
                 ha="left", va="center", **kw)
        x += w
    for ext in ("png", "svg"):
        fig.savefig(OUT / f"{name}.{ext}", dpi=DPI, transparent=True,
                    bbox_inches="tight", pad_inches=0.05)
    plt.close(fig)
    print(f"  {name}.png / .svg")


if __name__ == "__main__":
    print(f"저장 위치: {OUT}")
    for n, t, s in EQS:
        render(n, t, s)
    render_legend()
    render_legend(LEGEND_ROWS_MIN, "eq_ptotal_legend_min")
    render_ko_eq("KoPub Batang Medium.ttf", "eq_curve_ko_batang")
    render_ko_eq("KoPub Dotum Medium.ttf", "eq_curve_ko_dotum")
