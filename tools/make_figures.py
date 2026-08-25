"""발표자료용 그림 ― 편집 디자인 규칙에 맞춰 그린다.

  - 격자·축 프레임 없음. 기준선 헤어라인 하나만 남긴다
  - 범례 대신 직접 라벨
  - 강조색은 결론을 지는 계열에만. 나머지는 중립색
  - figsize 는 슬라이드에 놓일 실제 폭과 같게 ― 축소하면 글씨가 본문보다 작아진다
"""
import csv
import json
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib import font_manager

import fonts as F
import theme as T

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "figures"
OUT.mkdir(parents=True, exist_ok=True)

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
    "axes.labelsize": 13.5,
    "xtick.labelsize": 12.5,
    "ytick.labelsize": 12.5,
    "figure.facecolor": T.HEX["paper"],
    "axes.facecolor": T.HEX["paper"],
    "savefig.facecolor": T.HEX["paper"],
    "text.color": T.HEX["body"],
    "axes.labelcolor": T.HEX["muted"],
    "xtick.color": T.HEX["muted"],
    "ytick.color": T.HEX["muted"],
})

cp = json.loads((ROOT / "outputs" / "curve_params.json").read_text(encoding="utf-8"))
cm = json.loads((ROOT / "outputs" / "comparison.json").read_text(encoding="utf-8"))
rows = list(csv.DictReader((ROOT / "outputs" / "grid_results.csv").open(encoding="utf-8")))
for r in rows:
    for k in r:
        # detector 처럼 숫자가 아닌 열이 나중에 붙었다. 통째로 float 하면 깨진다
        try:
            r[k] = float(r[k]) if r[k] not in ("", "None") else None
        except ValueError:
            pass
# 곡선이 탐지 항목별로 갈리면서 파라미터가 per_target 아래로 내려갔다.
# 주 지표(미착용)의 것을 쓴다.
cp = cp["per_target"][cp["primary"]] if "per_target" in cp else cp
BASE = cp["baseline_P"]


def f_rho(x):
    p = cp["f_rho"]
    return p["L"] / (1 + np.exp(-p["k"] * (x - p["x0"])))


def g_theta(x):
    p = cp["g_theta"]["params"]
    return (1 + np.exp(-p["k"] * p["x0"])) / (1 + np.exp(p["k"] * (x - p["x0"])))


def h_occ(x):
    return np.exp(-cp["h_occ"]["lambda"] * x)


def section(fixed):
    return [r for r in rows if all(abs(r[k] - v) < 1e-6 for k, v in fixed.items())]


def bare(ax):
    """축 프레임을 걷어내고 기준선 헤어라인만 남긴다."""
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(T.HEX["rule"])
    ax.spines["bottom"].set_linewidth(0.9)
    ax.tick_params(length=3, width=0.8, pad=5)
    ax.grid(False)


# ══ 1. 3축 응답 곡선 ═══════════════════════════════════════════════════════
fig, axes = plt.subplots(1, 3, figsize=(11.4, 3.05))
specs = [
    ("rho_px", {"theta_deg": 0.0, "occ_pct_target": 0.0}, f_rho,
     "화면 속 머리 크기 (픽셀)", (3.0, 50), False),
    ("theta_deg", {"rho_px": 48.0, "occ_pct_target": 0.0}, g_theta,
     "내려다보는 각도 (도)", (-3, 79), False),
    ("occ_pct_target", {"rho_px": 48.0, "theta_deg": 0.0}, h_occ,
     "가려진 정도 (%)", (-4, 79), True),
]
# ρ 축의 관측점은 **합성 격자가 아니라 실사진 실측**이다 (2026-08-25).
# 곡선을 실측으로 갈아끼운 뒤에도 옛 격자 점을 찍으면 점과 선이 어긋난 그림이
# 나온다. 실제로 한 번 그렇게 나왔다.
_native = json.loads((ROOT / "outputs" / "native_curve.json").read_text(encoding="utf-8"))
_nb = _native["targets"]["helmet_nohat"]["bins"]
NATIVE_RHO = [(0.5 * (b["lo"] + (b["hi"] or 120)), b["recall"]) for b in _nb]

for ax, (xkey, fixed, fn, xlabel, xlim, hot) in zip(axes, specs):
    if xkey == "rho_px":
        xs = np.array([x for x, _ in NATIVE_RHO])
        ys = np.array([y for _, y in NATIVE_RHO]) / BASE
    else:
        pts = section(fixed)
        xs = np.array([p[xkey] for p in pts])
        ys = np.array([p["recall_nohat"] for p in pts]) / BASE
    o = np.argsort(xs); xs, ys = xs[o], ys[o]
    grid = np.linspace(max(xs.min(), 0.1), 48.0 if xkey == "rho_px" else xs.max(), 300)
    fit = fn(grid / 100.0 if xkey == "occ_pct_target" else grid)
    if xkey == "rho_px":
        fit = fit / BASE
    ax.plot(grid, fit, color=T.HEX["accent"] if hot else T.HEX["neutral"],
            lw=2.4, zorder=2, solid_capstyle="round")
    ax.scatter(xs, ys, s=24, color=T.HEX["ink"] if hot else T.HEX["muted"], zorder=3)
    ax.set_xlabel(xlabel)
    ax.set_ylim(-0.06, 1.16)
    ax.set_xlim(*xlim)
    ax.set_yticks([0, 1.0])
    bare(ax)

axes[0].set_ylabel("검출률", labelpad=2)
axes[0].set_yticklabels(["0", "1"])
for ax in axes[1:]:
    ax.set_yticks([])

o15 = [p for p in section({"rho_px": 48.0, "theta_deg": 0.0})
       if abs(p["occ_pct_target"] - 15) < 1e-6][0]
# 지시선을 쓰지 않는다 ― 선이 곡선을 가로지른다. 빈자리에 글씨만 둔다.
_pct = o15["recall_nohat"] / BASE * 100
axes[2].text(40, 0.90, "가림 15%에서", fontsize=12.5, color=T.HEX["ink"],
             fontweight="bold", ha="left", va="top")
axes[2].text(40, 0.74, f"{_pct:.0f}%로 떨어진다", fontsize=12.5,
             color=T.HEX["ink"], fontweight="bold", ha="left", va="top")

fig.tight_layout(w_pad=2.8)
fig.savefig(OUT / "fig_curves.png", dpi=300)
plt.close(fig)

# ══ 2. 3단 비교 ― 평균은 붙고 꼬리는 벌어진다 (ADDENDUM-01 §5.4) ══════════
P = cm["placements"]
ARMS = [("시야만 따짐", "geometric"), ("가정한 값", "assumed"), ("직접 잰 값", "empirical")]

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11.4, 2.35))
ys = [2, 1, 0]

for ax, key, xlabel, fmt in (
        (ax1, "WDR", "위험가중 검출률 (%)", lambda v: f"{v*100:.1f}%"),
        (ax2, "fail_voxel_count", "사각지대 (칸)", lambda v: f"{v:,}")):
    vals = [P[k][key] for _, k in ARMS]
    show = [v * 100 if key == "WDR" else v for v in vals]
    lo, hi = min(show), max(show)
    pad = (hi - lo) * 0.42 or 1
    ax.set_xlim(lo - pad, hi + pad * 1.35)
    for y, v, (label, k) in zip(ys, show, ARMS):
        hot = k == "empirical"
        ax.plot([lo - pad, v], [y, y], color=T.HEX["rule"], lw=0.9, zorder=1)
        ax.scatter([v], [y], s=118 if hot else 82,
                   color=T.HEX["accent"] if hot else T.HEX["neutral"], zorder=3)
        ax.text(v + pad * 0.16, y, fmt(P[k][key]), va="center", ha="left",
                fontsize=14.5 if hot else 13,
                color=T.HEX["ink"] if hot else T.HEX["muted"],
                fontweight="bold" if hot else "normal")
    ax.set_yticks(ys)
    ax.set_yticklabels([l for l, _ in ARMS], fontsize=12.5, color=T.HEX["body"])
    ax.set_xticks([])
    ax.set_ylim(-0.6, 2.6)
    for sp in ("top", "right", "bottom"):
        ax.spines[sp].set_visible(False)
    ax.spines["left"].set_color(T.HEX["rule"]); ax.spines["left"].set_linewidth(0.9)
    ax.tick_params(length=0, pad=9)
    ax.set_xlabel(xlabel, color=T.HEX["muted"], fontsize=12, labelpad=8)

fig.tight_layout(w_pad=5.0)
fig.savefig(OUT / "fig_three.png", dpi=300)
plt.close(fig)

print("saved:", sorted(p.name for p in OUT.glob("*.png")))
