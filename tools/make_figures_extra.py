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
from PIL import Image
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
# ── 무채색 팔레트 ───────────────────────────────────────────────────────
# **검정·흰색·회색만 쓴다.** theme.py 의 미색 바탕과 붉은 강조색을 여기서
# 덮어쓴다. 강조는 색이 아니라 명도와 굵기로 한다 — 짙은 회색 대 옅은 회색,
# 굵게 대 보통. 흑백 출력에서 잃을 정보가 애초에 없어진다.
T.HEX["paper"] = "#FFFFFF"
T.HEX["ink"] = "#1A1A1A"
T.HEX["body"] = "#2B2B2B"
T.HEX["muted"] = "#6E6E6E"
T.HEX["faint"] = "#9A9A9A"
T.HEX["rule"] = "#C9C9C9"
T.HEX["accent"] = "#1A1A1A"     # 강조 = 검정
T.HEX["neutral"] = "#B4B4B4"    # 대조군 = 옅은 회색

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
# 빗금으로 '잃은 점수'를, 명도로 치명 여부를 나눈다. 색을 쓰지 않는다.
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
        "빗금 = 배점,  채움 = 획득,  검정 = 치명 구역 미달",
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
# 목표선은 **막대 뒤**에 둔다(zorder 1). 앞에 두면 막대를 가로지른다.
# 왼쪽 라벨 자리까지 선을 끌지 않는다 ― 글씨에 닿는다.
tgt = sr["standard"]["target"] * 100
ax.set_xlim(-0.62, len(opts) - 0.38)
ax.plot([-0.28, len(opts) - 0.45], [tgt, tgt], color=RULE, lw=1.0,
        ls=(0, (5, 4)), zorder=1)
ax.text(-0.58, tgt + 2.0, f"목표 {tgt:.0f}점", ha="left", va="bottom",
        fontsize=11, color=MUTED)

for i, (lab, val, crit, ok) in enumerate(opts):
    ax.bar(i, val, width=0.5, color=ACCENT if ok else NEUTRAL, zorder=3)
    # 글씨를 막대 안에 넣지 않는다. 전부 막대 위 빈자리로 올리고, va 를
    # bottom 으로 고정해 글자 아랫변이 막대 윗변에 닿지 않게 한다.
    tag = "치명 구역 0곳" if crit == 0 else f"치명 구역 {crit}곳 남음"
    ax.text(i, val + 9.5, f"{val:.1f}점", ha="center", va="bottom",
            fontsize=14, color=INK, fontweight="bold")
    ax.text(i, val + 3.2, tag, ha="center", va="bottom",
            fontsize=10.5, color=MUTED)
ax.set_xticks(x)
ax.set_xticklabels([o[0] for o in opts], fontsize=12.5, color=INK)
ax.set_ylim(0, 134)
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
ax.set_xlim(-1, 101); ax.set_ylim(8.9, 39.0); ax.axis("off")


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
# 라벨을 오른쪽 끝에 둔다. 왼쪽에 두면 아래로 내려가는 화살표가 글씨를 가른다.
ax.text(x0 + 4 * IW + 3 * IGAP, 26.4, "입력 ― 네 개의 계약 파일",
        fontsize=10, color=MUTED, ha="right")

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

# 상자 안에 기호만 적어두면 처음 보는 사람이 못 읽는다. 한 줄로 풀어 준다.
ax.text(cx0, 11.6,
        "ρ 화면 속 머리 크기(픽셀)   ·   θ 내려다보는 각도   ·   "
        "o 가려진 정도   ·   P 검출확률", fontsize=9.5, color=INK)
ax.text(cx0, 9.9,
        "실제 도면·계획서를 계약 형식으로 넣으면 그대로 돈다. "
        "굵은 테두리 상자가 이 연구의 몫이다.", fontsize=9.5, color=MUTED)
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
        # 사진은 원본 컬러 그대로 둔다. 무채색 규칙은 우리가 그리는 도해에
        # 적용하는 것이고, 사진은 검출기가 실제로 본 것이라 손대지 않는다.
        ax.imshow(plt.imread(p))
        ax.set_xticks([]); ax.set_yticks([])
        for s in ax.spines.values():
            s.set_color(RULE); s.set_linewidth(0.9)
        ax.set_title(t1, fontsize=12, color=INK, pad=7)
        ax.set_xlabel(t2, fontsize=10.5, color=MUTED, labelpad=6)
    fig.tight_layout(w_pad=2.0)
    fig.savefig(OUT / "fig_samples.png", dpi=DPI)
    plt.close(fig)

# ══ E. 안전보고서 지면 ― 두 단으로 쪼갠다 ═════════════════════════════════
# A4 보고서를 한 장으로 넣으면 1:2.9 로 길쭉해져 지면에서 글씨가 안 읽힌다.
# 세로로 반을 갈라 좌우로 놓으면 1:1.4 가 되고 같은 폭에서 글자가 두 배 커진다.
# 캡처는 tools/capture_report.py 가 만든다(긴 표는 앞부분만 남긴다).
SRC = OUT / "_report_full.png"
if SRC.exists():
    src = Image.open(SRC).convert("RGB")
    w, h = src.size
    half = h // 2
    # 자르는 자리에서 글자가 반토막 나지 않게 흰 가로줄을 찾아 붙인다
    px = src.load()
    best, span = half, 60
    for d in range(0, span):
        for cand in (half - d, half + d):
            if all(px[x, cand] == (255, 255, 255) for x in range(0, w, 7)):
                best = cand
                break
        else:
            continue
        break
    cols = [src.crop((0, 0, w, best)), src.crop((0, best, w, h))]
    ch = max(c.height for c in cols)
    GAP, PAD = 26, 2
    canvas = Image.new("RGB", (w * 2 + GAP, ch), "#FFFFFF")
    for k, c in enumerate(cols):
        canvas.paste(c, (k * (w + GAP), 0))
    # 브라우저 서브픽셀 렌더링이 글자 가장자리에 색을 남긴다. 회색조로 굳힌다.
    canvas = canvas.convert("L").convert("RGB")
    fig, ax = plt.subplots(figsize=(11.4, 11.4 * ch / (w * 2 + GAP)))
    ax.imshow(np.asarray(canvas))
    ax.set_xticks([]); ax.set_yticks([])
    for s in ax.spines.values():
        s.set_color(RULE); s.set_linewidth(0.9)
    # 가운데 이음선 ― 두 단이 이어진 한 장임을 보인다
    ax.axvline(w + GAP / 2, color=RULE, lw=0.9)
    fig.tight_layout(pad=0.4)
    fig.savefig(OUT / "fig_report.png", dpi=DPI)
    plt.close(fig)

# ══ F. 3D 검출확률 히트맵 ══════════════════════════════════════════════════
# tools/capture_mockup.py 가 무채색으로 찍어 여백까지 잘라 둔 것을 액자에만 넣는다.
M3D = OUT / "_mockup_3d.png"
if M3D.exists():
    src = Image.open(M3D).convert("RGB")
    fig, ax = plt.subplots(figsize=(11.4, 11.4 * src.height / src.width))
    ax.imshow(np.asarray(src))
    ax.set_xticks([]); ax.set_yticks([])
    for s in ax.spines.values():
        s.set_color(RULE); s.set_linewidth(0.9)
    fig.tight_layout(pad=0.3)
    fig.savefig(OUT / "fig_3d.png", dpi=DPI)
    plt.close(fig)

# ══ G. 시간대별 진단 ― 보고서 §7 만 잘라 쓴다 ══════════════════════════════
# 목업에는 시간대 화면이 없다. 그 내용은 보고서 7절에 있으므로 거기서 오린다.
# 위치는 캡처 전체 높이 대비 비율로 잡는다 ― 표 길이가 바뀌어도 따라간다.
RSRC = OUT / "_report_full.png"
if RSRC.exists():
    rep = Image.open(RSRC).convert("RGB")
    w, h = rep.size
    # 7절 제목 바로 위에서 자른다. 앞 절의 마지막 줄이 딸려오면 지저분하다.
    band = rep.crop((0, int(h * 0.752), w, h))
    # 아래쪽 꼬리말 여백을 잘라낸다
    g = band.convert("L")
    ins = int(w * 0.02)
    bb = g.crop((ins, 0, w - ins, band.height)).point(
        lambda v: 255 if v < 238 else 0).getbbox()
    if bb:
        band = band.crop((0, max(0, bb[1] - 12), w, min(band.height, bb[3] + 12)))
    fig, ax = plt.subplots(figsize=(11.4, 11.4 * band.height / band.width))
    ax.imshow(np.asarray(band))
    ax.set_xticks([]); ax.set_yticks([])
    for s in ax.spines.values():
        s.set_color(RULE); s.set_linewidth(0.9)
    fig.tight_layout(pad=0.3)
    fig.savefig(OUT / "fig_timephase.png", dpi=DPI)
    plt.close(fig)

print("saved:", sorted(p.name for p in OUT.glob("*.png")))
