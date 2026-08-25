# -*- coding: utf-8 -*-
"""민감도 스윕 - 결론이 근거 없는 자유 파라미터에 얼마나 매달려 있는가.

실험에서 가림축이 세 축 중 압도적으로 세다. 그런데 그 축을 만드는 값 둘이
근거 없는 자유 파라미터다.

  1) 스트라이프 주기      transforms.DEFAULT_STRIPE_DIVISOR (= 화면 가로 / 24)
  2) 비계 시야 점유율     config.SCAFFOLD_COVERAGE (= 0.35)
  3) 판정 임계            config.P_DETECT_THRESHOLD (= 0.5, §5.3 이 잠정값이라 명시)

셋 다 "그 값을 바꾸면 결론이 뒤집히지 않느냐"는 물음에 답이 있어야 한다.
**ΔWDR 의 부호가 유지되면 그 표 자체가 방어 근거가 된다.**

1)은 검출기를 다시 돌려야 하므로 h(o) 단면만 재측정한 CSV 를 읽어 λ 를 다시
맞춘다. 만드는 법:

    python src/run_grid.py --occ-only --occ-divisor 12
    python src/run_grid.py --occ-only --occ-divisor 48

2)·3)은 추론이 필요 없다.

사용:
    python src/sensitivity.py            -> outputs/sensitivity.json
"""
from pathlib import Path
import copy
import csv
import json
import sys
# 콘솔 인코딩이 cp949 인 환경에서 출력을 파일로 리디렉션하면, 문자열에 cp949 로
# 표현 못 하는 문자(U+2212 마이너스, U+2014 em dash 등)가 하나만 있어도
# UnicodeEncodeError 로 죽는다. **계산을 다 끝내고 마지막 print 에서 죽는다** —
# 실제로 두 번 겪었다. 문자를 하나씩 쫓는 대신 출력단에서 막는다.
# encoding 은 그대로 두어 한글 콘솔 표시를 유지하고 errors 만 바꾼다.
try:
    sys.stdout.reconfigure(errors="replace")
    sys.stderr.reconfigure(errors="replace")
except (AttributeError, ValueError):
    pass

import numpy as np
from scipy.optimize import curve_fit

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config
import site_model
import geometry
import detect_model
import aggregate
import optimize

SC_LEVELS = [0.20, 0.35, 0.50]
THRESHOLDS = [0.4, 0.5, 0.6]


def both_placements(site, pairs, curve) -> dict:
    """기하·확률 두 배치를 같은 자로 재고 요약을 낸다."""
    res = optimize.run(site, pairs, curve)
    # optimize.run 이 geometric / assumed / empirical 셋을 내도록 바뀌면서
    # "probabilistic" 키가 사라졌다. 이 파일이 그걸 못 따라가 KeyError 로 죽었고,
    # 그래서 outputs/sensitivity.json 이 2026-08-15 값에 멈춰 있었다.
    # 비교 대상은 실측 곡선 배치이므로 empirical 을 쓴다.
    # 아래로 나가는 JSON 키 이름(WDR_probabilistic)은 tools/build_*.py 가 그대로
    # 읽고 있어 유지한다.
    g, p = res["geometric"], res["empirical"]
    return {
        "geometric": {"WDR": g["WDR"], "fail": g["fail_voxel_count"],
                      "camera_ids": g["camera_ids"]},
        "probabilistic": {"WDR": p["WDR"], "fail": p["fail_voxel_count"],
                          "camera_ids": p["camera_ids"]},
        "delta_WDR": round(p["WDR"] - g["WDR"], 4),
        "per_voxel": p["per_voxel"],
        "per_voxel_geo": g["per_voxel"],
    }


# ── 1) 스트라이프 주기 -> λ ───────────────────────────────────────────────

def lambda_from_section(path: Path) -> tuple[float, list]:
    """h(o) 단면 CSV 에서 λ 를 다시 맞춘다. 기준점(o=0)에서 1 로 정규화한다."""
    with path.open(encoding="utf-8") as f:
        rows = sorted((r for r in csv.DictReader(f)),
                      key=lambda r: float(r["occ_pct_target"]))
    x = np.array([float(r["occ_pct_actual"]) / 100.0 for r in rows])
    y = np.array([float(r["recall_nohat"]) for r in rows])
    y = y / y[0]
    p, _ = curve_fit(lambda t, lam: np.exp(-lam * t), x, y, p0=[3.0], maxfev=200000)
    return float(p[0]), [round(v, 4) for v in y]


def with_lambda(curve, lam: float):
    """λ 만 바꾼 곡선 사본. 원본을 건드리지 않는다."""
    params = copy.deepcopy(curve.p)
    params["h_occ"]["lambda"] = lam
    return detect_model.Curve(params)


def sweep_lambda(site, pairs, curve) -> list:
    out = []
    base_lam = curve.lam
    found = sorted(config.OUTPUTS.glob("occ_section_div*.csv"))
    entries = [("기본 (div 24)", base_lam, None)]
    for path in found:
        div = path.stem.replace("occ_section_div", "")
        try:
            lam, ys = lambda_from_section(path)
        except Exception as e:            # 파일이 비었거나 컬럼이 다를 때
            print(f"  {path.name} 를 읽지 못했다: {e}")
            continue
        entries.append((f"div {div}", lam, ys))

    for name, lam, ys in entries:
        r = both_placements(site, pairs, with_lambda(curve, lam))
        out.append({"case": name, "lambda": round(lam, 4),
                    "section_normalized": ys,
                    "WDR_geometric": r["geometric"]["WDR"],
                    "WDR_probabilistic": r["probabilistic"]["WDR"],
                    "fail_geometric": r["geometric"]["fail"],
                    "fail_probabilistic": r["probabilistic"]["fail"],
                    "delta_WDR": r["delta_WDR"]})
    return out


# ── 2) 비계 점유율 ────────────────────────────────────────────────────────

def sweep_scaffold(curve) -> list:
    out = []
    for sc in SC_LEVELS:
        site = site_model.build(scaffold_coverage=sc)
        pairs, _ = geometry.all_pairs(site)
        r = both_placements(site, pairs, curve)
        out.append({"scaffold_coverage": sc,
                    "WDR_geometric": r["geometric"]["WDR"],
                    "WDR_probabilistic": r["probabilistic"]["WDR"],
                    "fail_geometric": r["geometric"]["fail"],
                    "fail_probabilistic": r["probabilistic"]["fail"],
                    "delta_WDR": r["delta_WDR"]})
        print(f"  비계 점유율 {sc:.2f} -> ΔWDR {r['delta_WDR']:+.4f}")
    return out


# ── 3) 판정 임계 ──────────────────────────────────────────────────────────

def sweep_threshold(site, res: dict) -> list:
    """추론도 재최적화도 필요 없다. per_voxel 을 다시 세기만 한다.

    임계는 판정선일 뿐 목적함수가 아니라 배치가 바뀌지 않는다.
    """
    out = []
    # 분모는 aggregate.py 와 같아야 한다 — 사람이 있을 수 있는 복셀만 센다.
    # 전 복셀로 세면 site_eval.json 의 fail_voxel_count 와 어긋나 같은 표에
    # 두 종류 숫자가 섞인다 (2026-08-25 확인).
    vox = [v for v in site.voxels if v.get("occupiable", True)]
    for thr in THRESHOLDS:
        fg = sum(1 for v in vox if res["per_voxel_geo"][v["id"]] < thr)
        fp = sum(1 for v in vox if res["per_voxel"][v["id"]] < thr)
        out.append({"threshold": thr, "fail_geometric": fg,
                    "fail_probabilistic": fp, "reduction": fg - fp,
                    "n_occupiable": len(vox)})
    return out


def main() -> None:
    print("현장·기하 계산 중…")
    site = site_model.build()
    pairs, _ = geometry.all_pairs(site)
    curve = detect_model.load()
    base = both_placements(site, pairs, curve)
    print(f"기준: ΔWDR {base['delta_WDR']:+.4f} "
          f"(기하 {base['geometric']['WDR']} / 확률 {base['probabilistic']['WDR']})")

    print("\n[1] 스트라이프 주기 -> λ")
    lam = sweep_lambda(site, pairs, curve)
    for r in lam:
        print(f"  {r['case']:<14} λ={r['lambda']:>7.4f}  "
              f"WDR {r['WDR_geometric']:.4f} / {r['WDR_probabilistic']:.4f}  "
              f"ΔWDR {r['delta_WDR']:+.4f}")
    if len(lam) == 1:
        print("  (단면 CSV 가 없다. run_grid.py --occ-only --occ-divisor N 로 만들 것)")

    print("\n[2] 비계 시야 점유율")
    sc = sweep_scaffold(curve)

    print("\n[3] 판정 임계")
    th = sweep_threshold(site, base)
    for r in th:
        print(f"  임계 {r['threshold']}  미달 기하 {r['fail_geometric']:>4} / "
              f"확률 {r['fail_probabilistic']:>4}  (감소 {r['reduction']})")

    deltas = [r["delta_WDR"] for r in lam] + [r["delta_WDR"] for r in sc]
    payload = {
        "note": "가림축을 만드는 자유 파라미터 셋에 대한 민감도. "
                "ΔWDR 의 부호가 유지되는지가 판정 기준이다",
        "baseline": {"WDR_geometric": base["geometric"]["WDR"],
                     "WDR_probabilistic": base["probabilistic"]["WDR"],
                     "delta_WDR": base["delta_WDR"],
                     "geometric_dori_level": config.GEOMETRIC_DORI_LEVEL},
        "stripe_period_lambda": lam,
        "scaffold_coverage": sc,
        "threshold": th,
        "delta_WDR_range": [min(deltas), max(deltas)],
        "sign_preserved": bool(min(deltas) > 0),
        "status": "ok",
    }
    path = config.OUTPUTS / "sensitivity.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nΔWDR 범위 {min(deltas):+.4f} ~ {max(deltas):+.4f}  "
          f"부호 유지: {'예' if payload['sign_preserved'] else '아니오'}")
    print(f"→ {path}")


if __name__ == "__main__":
    main()
