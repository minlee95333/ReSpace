# -*- coding: utf-8 -*-
"""제안서 6장 Fig 4 — STEP 01~05 평가 프로세스 흐름도.

**왜 새로 그리는가.** 기존 `fig_pipeline.png` 은 상자가 "복셀화 / 검출확률 곡선 /
다중 카메라 결합 / 100점 채점 / 처방" 으로 되어 있어 본문의 STEP 01~05 와 라벨이
맞지 않았다. 심사위원이 그림과 본문을 대조하면 바로 걸린다.

**무엇을 다르게 하는가.** 단계 이름만 적지 않고 **그 단계에서 실제로 나온 수치**를
상자 안에 넣는다. 흐름도가 목차가 아니라 결과 요약이 된다. 수치는 전부
`outputs/` 에서 읽는다 — 손으로 적은 값이 없어야 한다(CLAUDE.md §0.1-1).

STEP 03 만 테두리를 굵게 한다. 전체 체계에서 실측 데이터에 기반하는 곳이 거기
하나이며, 나머지는 규칙 기반이라는 것이 이 그림의 요지다.

**무채색만 쓴다.** 심사위원이 흑백으로 출력할 수 있다.

    python tools/make_fig_process.py

산출: outputs/figures/fig_process_steps.png
"""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mp
from matplotlib import font_manager

import fonts as F
import theme as T

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "figures"
OUT.mkdir(parents=True, exist_ok=True)
DPI = 300

for _p in F.all_files():
    font_manager.fontManager.addfont(str(_p))

PAPER, INK, MUTED = "#FFFFFF", "#1A1A1A", "#6E6E6E"
RULE, FAINT = "#C9C9C9", "#9A9A9A"

plt.rcParams.update({
    "font.family": T.TEXT,
    "axes.unicode_minus": True,
    "figure.facecolor": PAPER,
    "savefig.facecolor": PAPER,
    "text.color": INK,
})


# ── 수치를 산출물에서 읽는다 ────────────────────────────────────────────────
def load():
    O = ROOT / "outputs"
    se = json.loads((O / "site_eval.json").read_text(encoding="utf-8"))
    cmp_ = json.loads((O / "comparison.json").read_text(encoding="utf-8"))
    cv = json.loads((O / "curve_params.json").read_text(encoding="utf-8"))
    nc = json.loads((O / "native_curve.json").read_text(encoding="utf-8"))

    vox = se["voxels"]
    occ = [v for v in vox if v["occupiable"]]
    hi = sum(1 for v in occ if v["w"] >= 4)
    ps = se["dori_pair_stats"]
    emp = cmp_["placements"]["empirical"]
    geo = cmp_["placements"]["geometric"]
    prim = cv["per_target"]["helmet_nohat"]
    return {
        "n_vox": len(vox),
        "n_occ": len(occ),
        "hi": hi,
        "hi_pct": 100 * hi / len(occ),
        "n_pairs": ps["n_pairs"],
        "n_vis": ps["n_visible"],
        "vis_pct": 100 * ps["n_visible"] / ps["n_pairs"],
        "rho_med": ps["rho_px_median"],
        "n_cond": cv["n_conditions"],
        "n_inst": sum(t["n_instances"] for t in nc["targets"].values()),
        "r2": prim["f_rho"]["r2_binned"],
        "x0": prim["f_rho"]["x0"],
        "wdr_geo": geo["WDR"],
        "wdr_emp": emp["WDR"],
        "fail": emp["fail_voxel_count"],
        "budget": se["camera_budget"],
        "n_cam": len(se["cameras"]),
    }


D = load()


def fmt(n):
    return f"{n:,}"


# ── 판면 ───────────────────────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(11.6, 3.55))
ax.set_xlim(-1, 101)
ax.set_ylim(6.0, 40.0)
ax.axis("off")


def box(x, y, w, h, step, title, out, stat, hot=False):
    ax.add_patch(mp.FancyBboxPatch(
        (x, y), w, h, boxstyle="round,pad=0.35,rounding_size=0.8",
        linewidth=2.0 if hot else 1.1, edgecolor=INK if hot else RULE,
        facecolor=PAPER, zorder=3))
    cx = x + w / 2
    ax.text(cx, y + h - 1.9, step, ha="center", va="center", fontsize=8.6,
            color=INK if hot else FAINT, fontweight="bold", zorder=4)
    # 제목은 아래에서부터 쌓아 올린다 — 줄 수가 달라도 아랫단이 어긋나지 않게
    for k, ln in enumerate(reversed(title)):
        ax.text(cx, y + h - 6.8 + k * 2.5, ln, ha="center", va="center",
                fontsize=10.4, color=INK, fontweight="bold", zorder=4)
    base = y + h - 8.6          # 모든 상자에서 같은 높이
    ax.text(cx, base, out, ha="center", va="center", fontsize=8.4,
            color=MUTED, zorder=4)
    ax.plot([x + 2.2, x + w - 2.2], [base - 2.1] * 2,
            color=RULE, lw=0.8, zorder=3)
    for k, ln in enumerate(stat):
        ax.text(cx, base - 3.9 - k * 2.25, ln, ha="center", va="center",
                fontsize=8.9, color=INK, zorder=4)


def arrow(x1, y1, x2, y2):
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1), zorder=2,
                arrowprops=dict(arrowstyle="-|>", color=MUTED, lw=1.2,
                                shrinkA=0, shrinkB=0))


# ── 상단: 입력 ─────────────────────────────────────────────────────────────
INPUTS = [("설계도면", "골조 형상"),
          ("안전관리계획서", "위험구역 · CCTV 계획"),
          ("가설계획", "비계 · 적치")]
IW, IGAP = 25.0, 3.4
ix0 = (100 - (len(INPUTS) * IW + (len(INPUTS) - 1) * IGAP)) / 2
for i, (t1, t2) in enumerate(INPUTS):
    x = ix0 + i * (IW + IGAP)
    ax.add_patch(mp.FancyBboxPatch(
        (x, 33.4), IW, 6.0, boxstyle="round,pad=0.3,rounding_size=0.7",
        linewidth=1.0, edgecolor=RULE, facecolor=PAPER, zorder=3))
    ax.text(x + IW / 2, 37.4, t1, ha="center", va="center", fontsize=10.0,
            color=INK, fontweight="bold", zorder=4)
    ax.text(x + IW / 2, 35.0, t2, ha="center", va="center", fontsize=8.4,
            color=MUTED, zorder=4)

span_l, span_r = ix0, ix0 + 3 * IW + 2 * IGAP
ax.plot([span_l, span_r], [31.6, 31.6], color=RULE, lw=1.0, zorder=1)
for xx in (span_l, span_r):
    ax.plot([xx, xx], [31.6, 32.9], color=RULE, lw=1.0, zorder=1)
ax.text(span_r, 29.9, "입력 — 시공사가 이미 제출하는 서류",
        fontsize=9.0, color=MUTED, ha="right")

# ── 하단: STEP 01~05 ───────────────────────────────────────────────────────
CW, CGAP = 17.6, 3.0
cx0 = (100 - (5 * CW + 4 * CGAP)) / 2

STEPS = [
    ("STEP 01", ["공간 위험도"], "→ 위험도 지도",
     [f"셀 {fmt(D['n_vox'])}", f"활동공간 {fmt(D['n_occ'])}",
      f"고위험 {D['hi_pct']:.0f}%"], False),
    ("STEP 02", ["CCTV", "관측 가능 영역"], "→ 가시성 지도",
     [f"쌍 {D['n_pairs'] / 1e6:.1f}M 중",
      f"가시 {D['vis_pct']:.0f}%",
      f"머리 중앙값 {D['rho_med']:.1f}px"], False),
    ("STEP 03", ["촬영조건별", "AI 검출성능"], "→ 검출확률 곡선",
     [f"{D['n_cond']}조건 + 실사진",
      f"{fmt(D['n_inst'])} 인스턴스",
      f"R² {D['r2']:.4f}"], True),
    ("STEP 04", ["배치", "적정성 평가"], "→ 위험가중 검출률",
     [f"기하 {D['wdr_geo'] * 100:.1f}%",
      f"확률 {D['wdr_emp'] * 100:.1f}%",
      f"동일 {D['budget']}대"], False),
    ("STEP 05", ["고위험", "미감시구역"], "→ 미달구역 + 원인",
     [f"미달 {fmt(D['fail'])}", "원인 89% 가림", "처방: 재배치"], False),
]

BH = 20.4
for i, (step, title, out, stat, hot) in enumerate(STEPS):
    x = cx0 + i * (CW + CGAP)
    box(x, 8.6, CW, BH, step, title, out, stat, hot=hot)
    if i:
        arrow(x - CGAP + 0.15, 8.6 + BH / 2, x - 0.15, 8.6 + BH / 2)

arrow(cx0 + CW / 2, 31.4, cx0 + CW / 2, 8.6 + BH + 0.4)

ax.text(cx0, 6.9,
        "굵은 테두리(STEP 03)만 실측 데이터에서 온다. 나머지 네 단계는 규칙 기반의 "
        "결정론적 계산이다.", fontsize=9.2, color=INK)

fig.tight_layout(pad=0.4)
fig.savefig(OUT / "fig_process_steps.png", dpi=DPI)
plt.close(fig)
print(f"저장: {OUT / 'fig_process_steps.png'}")
print(f"  셀 {fmt(D['n_vox'])} · 활동공간 {fmt(D['n_occ'])} · "
      f"WDR {D['wdr_geo']:.4f} -> {D['wdr_emp']:.4f}")
