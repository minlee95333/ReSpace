# -*- coding: utf-8 -*-
"""제안서용 추가 그림 ― make_figures.py 가 안 그리는 것들.

기존 편집 규칙을 그대로 따른다.
  - 격자·축 프레임 없음. 기준선 헤어라인 하나만
  - 범례 대신 직접 라벨
  - 강조색은 결론을 지는 계열에만
  - **색만으로 구분하지 않는다.** 심사위원이 흑백으로 출력할 수 있다

수치는 전부 outputs/ 에서 읽는다. 손으로 적은 값이 없어야 한다.

    python tools/make_figures_extra.py
"""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mp
import numpy as np
from matplotlib import font_manager

import fonts as F
import theme as T

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "figures"
OUT.mkdir(parents=True, exist_ok=True)
DPI = 300          # 인쇄용. 종전 220 에서 올렸다

for _p in F.all_files():
    font_manager.fontManager.addfont(str(_p))
# ── 배경을 순백으로 덮어쓴다 ────────────────────────────────────────────
# theme.py 는 따뜻한 미색(FBFAF6)을 쓰고 순백을 금한다. 화면과 슬라이드에서는
# 그게 맞다. 그런데 **이 그림들은 한글 문서에 들어간다.** 한글 지면은 순백이라
# 미색 배경이면 그림마다 옅은 회색 사각형이 생긴다. 그래서 여기서만 뒤집는다.
# 잉크·강조색은 그대로 두므로 편집 톤은 유지된다.
T.HEX["paper"] = "#FFFFFF"

plt.rcParams.update({
    "font.family": T.TEXT,
    "axes.unicode_minus": True,
    "font.size": 13,
    "figure.facecolor": T.HEX["paper"],
    "axes.facecolor": T.HEX["paper"],
    "savefig.facecolor": T.HEX["paper"],
    "text.color": T.HEX["body"],
})

sr = json.loads((ROOT / "outputs" / "safety_report.json").read_text(encoding="utf-8"))
sd = sr["coverage"]["overall"]["score_detail"]
ov = sr["coverage"]["overall"]
realloc = (sr.get("options") or {}).get("reallocate") or {}
pres = sr["prescription"]

PAPER, INK, MUTED = T.HEX["paper"], T.HEX["ink"], T.HEX["muted"]
RULE, ACCENT, NEUTRAL = T.HEX["rule"], T.HEX["accent"], T.HEX["neutral"]


def bare(ax, keep=("bottom",)):
    for s in ("top", "right", "left", "bottom"):
        ax.spines[s].set_visible(s in keep)
    if "bottom" in keep:
        ax.spines["bottom"].set_color(RULE)
        ax.spines["bottom"].set_linewidth(0.9)
    ax.tick_params(length=3, width=0.8, pad=5, colors=MUTED)
    ax.grid(False)


# ══ A. 채점 분해 ― 배점 중 얼마를 얻었나 ═══════════════════════════════════
# 빗금으로 '잃은 점수'를 표시한다. 색을 못 쓰는 흑백 출력에서도 읽힌다.
rows = [r for r in sd["rows"] if r["zone"] != "_background"]
rows = sorted(rows, key=lambda r: (-r["weight"], r["zone"]))
labels = [r["label"].replace(" (", "\n(") for r in rows]
alloc = np.array([r["allocated"] for r in rows])
earn = np.array([r["earned"] for r in rows])
y = np.arange(len(rows))[::-1]

fig, ax = plt.subplots(figsize=(11.4, 3.9))
ax.barh(y, alloc, height=0.62, color=PAPER, edgecolor=RULE, linewidth=1.0, zorder=2)
ax.barh(y, alloc, height=0.62, facecolor="none", edgecolor=NEUTRAL,
        hatch="///", linewidth=0.0, zorder=2)
for i, r in enumerate(rows):
    hot = r["critical_fail"]
    ax.barh(y[i], r["earned"], height=0.62,
            color=ACCENT if hot else NEUTRAL, zorder=3)
    ax.text(r["allocated"] + 0.35, y[i], f"{r['earned']:.1f} / {r['allocated']:.1f}",
            va="center", fontsize=11.5, color=INK if hot else MUTED,
            fontweight="bold" if hot else "normal")
ax.set_yticks(y)
ax.set_yticklabels(labels, fontsize=11.5, color=INK)
ax.set_xlim(0, max(alloc) * 1.42)
ax.set_xticks([])
bare(ax, keep=())
ax.text(0, len(rows) - 0.05, f"총점 {sd['total']:.1f} / 100   등급 {sd['grade']}",
        fontsize=15, color=ACCENT, fontweight="bold", va="bottom")
ax.text(max(alloc) * 0.62, len(rows) - 0.05,
        "빗금 = 배점,  채움 = 획득,  붉은색 = 치명 구역 미달",
        fontsize=11, color=MUTED, va="bottom")
fig.tight_layout()
fig.savefig(OUT / "fig_score.png", dpi=DPI)
plt.close(fig)

# ══ B. 처방 ― 옮기면 되는가, 더 달아야 하는가 ══════════════════════════════
opts = [("현 계획서\n8대", ov["score_100"], len(ov["critical_failures"]), False)]
if realloc:
    opts.append(("같은 8대\n재배치", realloc["score_100"],
                 len(realloc["critical_failures"]), False))
if pres.get("resulting") is not None:
    opts.append((f"{pres['add_cameras']}대 증설\n({8 + pres['add_cameras']}대)",
                 pres["resulting"] * 100, 0, True))

fig, ax = plt.subplots(figsize=(7.6, 3.6))
x = np.arange(len(opts))
for i, (lab, val, crit, ok) in enumerate(opts):
    ax.bar(i, val, width=0.5, color=ACCENT if ok else NEUTRAL, zorder=3)
    ax.text(i, val + 2.0, f"{val:.1f}점", ha="center", fontsize=14,
            color=ACCENT if ok else INK, fontweight="bold")
    tag = "치명 구역 0곳" if crit == 0 else f"치명 구역 {crit}곳 남음"
    ax.text(i, 4, tag, ha="center", fontsize=11,
            color=PAPER if val > 20 else MUTED)
tgt = sr["standard"]["target"] * 100
ax.axhline(tgt, color=INK, lw=1.0, ls=(0, (5, 4)), zorder=4)
ax.text(len(opts) - 0.42, tgt + 1.6, f"목표 {tgt:.0f}점", ha="right",
        fontsize=11.5, color=INK)
ax.set_xticks(x)
ax.set_xticklabels([o[0] for o in opts], fontsize=12.5, color=INK)
ax.set_ylim(0, 118)
ax.set_yticks([])
bare(ax)
fig.tight_layout()
fig.savefig(OUT / "fig_prescribe.png", dpi=DPI)
plt.close(fig)

# ══ C. 파이프라인 흐름도 ═══════════════════════════════════════════════════
# 입력 넷을 상단에 가로로 묶고, 복셀화부터 처방까지는 한 줄로 흐른다.
# 갈래가 없으니 굽은 화살표도 없어야 한다 ― 읽는 눈이 한 방향으로만 간다.
fig, ax = plt.subplots(figsize=(11.4, 3.05))
# 내용이 y 9~38 에만 있다. 0~40 으로 두면 아래가 통째로 빈다
ax.set_xlim(-1, 101); ax.set_ylim(8.6, 39.0); ax.axis("off")


def box(x, y, w, hgt, title, sub, hot=False, fs=11.5, fss=9.0):
    ax.add_patch(mp.FancyBboxPatch(
        (x, y), w, hgt, boxstyle="round,pad=0.3,rounding_size=0.7",
        linewidth=1.1, edgecolor=ACCENT if hot else RULE,
        facecolor=PAPER, zorder=3))
    ax.text(x + w / 2, y + hgt * (0.63 if sub else 0.5), title,
            ha="center", va="center", fontsize=fs,
            color=ACCENT if hot else INK, fontweight="bold", zorder=4)
    if sub:
        ax.text(x + w / 2, y + hgt * 0.25, sub, ha="center", va="center",
                fontsize=fss, color=MUTED, zorder=4)


def arrow(x1, y1, x2, y2, color=None):
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1), zorder=2,
                arrowprops=dict(arrowstyle="-|>", color=color or MUTED,
                                lw=1.2, shrinkA=0, shrinkB=0))


# ── 상단: 입력 네 개를 가로로 ──────────────────────────────────────────
INPUTS = [("CCTV 계획서", "위치·높이·방위·화각"), ("골조 형상", "도면·BIM·실측"),
          ("위험구역", "안전관리계획서"), ("공정표", "시간대별 작업")]
IW, IGAP = 22.6, 3.2
x0 = (100 - (len(INPUTS) * IW + (len(INPUTS) - 1) * IGAP)) / 2
for i, (t1, t2) in enumerate(INPUTS):
    box(x0 + i * (IW + IGAP), 30.5, IW, 7.4, t1, t2)

# 묶음 표시 ― 네 개가 한 덩어리임을 가로선 하나로 보인다
ax.plot([x0, x0 + 4 * IW + 3 * IGAP], [28.4, 28.4], color=RULE, lw=1.0, zorder=1)
for xx in (x0, x0 + 4 * IW + 3 * IGAP):
    ax.plot([xx, xx], [28.4, 29.6], color=RULE, lw=1.0, zorder=1)
ax.text(x0 - 0.4, 26.4, "입력 ― 네 개의 계약 파일", fontsize=10, color=MUTED)

# 묶음에서 **첫 단계로** 내려간다. 가운데로 떨어뜨리면 세 번째 상자를 가리켜
# 입력이 중간에 끼어드는 것처럼 읽힌다.
CW, CGAP = 17.4, 3.2
cx0 = (100 - (5 * CW + 4 * CGAP)) / 2
arrow(cx0 + CW / 2, 28.2, cx0 + CW / 2, 21.4)

# ── 하단: 복셀화부터 처방까지 한 줄 ────────────────────────────────────
CHAIN = [("복셀화 + 광선투사", "ρ · θ · o", False),
         ("검출확률 곡선", "f(ρ)·g(θ)·h(o)", True),
         ("다중 카메라 결합", "1 - Π(1-P)", False),
         ("100점 채점", "배점 × 달성률", True),
         ("처방", "재배치 → 증설", False)]
for i, (t1, t2, hot) in enumerate(CHAIN):
    x = cx0 + i * (CW + CGAP)
    box(x, 13.6, CW, 7.4, t1, t2, hot=hot, fs=10.8, fss=8.6)
    if i:
        arrow(x - CGAP + 0.2, 17.3, x - 0.2, 17.3)

ax.text(cx0 - 0.4, 10.4,
        "실제 도면·계획서를 계약 형식으로 넣으면 그대로 돈다. "
        "붉은 상자가 이 연구의 몫이다.", fontsize=9.5, color=MUTED)
fig.tight_layout()
fig.savefig(OUT / "fig_pipeline.png", dpi=DPI)
plt.close(fig)

# ══ D. 변형 샘플 3장 ═══════════════════════════════════════════════════════
SM = ROOT / "outputs" / "smoke_samples"
picks = [("sample_rho48_theta0_occ0.jpg", "ρ 48px · θ 0° · 가림 0%", "가장 좋은 조건"),
         ("sample_rho24_theta30_occ30.jpg", "ρ 24px · θ 30° · 가림 30%", "중간 거리"),
         ("sample_rho12_theta60_occ60.jpg", "ρ 12px · θ 60° · 가림 60%", "현장에 흔한 조건")]
have = [(SM / f, t1, t2) for f, t1, t2 in picks if (SM / f).exists()]
if have:
    fig, axes = plt.subplots(1, len(have), figsize=(11.4, 4.4))
    axes = np.atleast_1d(axes)
    for ax, (p, t1, t2) in zip(axes, have):
        ax.imshow(plt.imread(p))
        ax.set_xticks([]); ax.set_yticks([])
        for s in ax.spines.values():
            s.set_color(RULE); s.set_linewidth(0.9)
        ax.set_title(t1, fontsize=12, color=INK, pad=7)
        ax.set_xlabel(t2, fontsize=10.5, color=MUTED, labelpad=6)
    fig.tight_layout(w_pad=2.0)
    fig.savefig(OUT / "fig_samples.png", dpi=DPI)
    plt.close(fig)

print("saved:", sorted(p.name for p in OUT.glob("*.png")))
