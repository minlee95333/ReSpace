# -*- coding: utf-8 -*-
"""민감도 스윕 - 결론이 근거 없는 자유 파라미터에 얼마나 매달려 있는가.

실험에서 가림축이 세 축 중 압도적으로 세다. 그런데 그 축을 만드는 값 둘이
근거 없는 자유 파라미터다.

  1) 스트라이프 주기      transforms.DEFAULT_STRIPE_DIVISOR (= 화면 가로 / 24)
  2) 비계 시야 점유율     config.SCAFFOLD_COVERAGE (= 0.35)
  3) 판정 임계            config.P_DETECT_THRESHOLD (= 0.5, §5.3 이 잠정값이라 명시)

**무엇을 지키는 표인가가 2026-08-27 에 바뀌었다.** 종전에는 배치를 두 개
만들어(기하 / 확률) ΔWDR 의 부호가 유지되는지를 보였다. 자동 배치를 쓰지
않기로 하면서(`config.ENABLE_OPTIMIZATION = False`) 그 비교가 사라졌다.

지금 지키는 주장은 이것이다 - **어느 값을 넣어도 고위험 작업구역의 인식률이
낮게 유지된다.** 절대 인식률은 파라미터를 따라 크게 흔들리지만, 슬래브 단부
같은 특정 구역이 계속 바닥이라면 그것은 파라미터가 만든 결과가 아니다.

ΔWDR 대신 보는 것:
  - `recognized_ratio`      전체 인식 가능 공간 비율
  - `worst_zones`           가장 낮은 구역들의 인식률
  - 임계 스윕은 배치가 하나뿐이라 미달 개수의 절대값만 본다

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
import plan_io

SC_LEVELS = [0.20, 0.35, 0.50]
THRESHOLDS = [0.4, 0.5, 0.6]
# 표에 세워 둘 구역. 추락사고가 실제로 일어나는 자리들이며, 여기가 계속
# 바닥이라는 것이 이 스윕이 지키려는 주장이다.
WATCH = ("slab_edge", "concrete_pour", "gangform_workface", "opening_perimeter")
PLAN = config.ROOT / "data" / "plans" / "as_planned.json"


def plan_camera(site) -> tuple:
    """계획서의 카메라와 **방위**. 배치는 스윕 내내 고정이다 - 파라미터만 흔든다.

    방위를 함께 받아야 한다. 종전에는 id 만 받고 방위는 `all_pairs` 가 다시
    골랐는데, 그러면 report.py 와 기준값이 갈린다(실측 49,126 대 51,116).
    같은 배치를 잰다고 말하면서 다른 배치를 재고 있었다.
    """
    cams, yaws, _ = plan_io.load(PLAN)
    ids = [c.cid for c in cams]
    known = {c.cid for c in site.cameras}
    missing = [i for i in ids if i not in known]
    if missing:
        raise SystemExit(f"계획서 카메라가 현장 후보에 없다: {missing[:5]}")
    return ids, yaws


def diagnose(site, pairs, curve, cam_ids) -> dict:
    """배치 하나를 진단한다. 대표 지표와 주시 구역의 인식률을 함께 낸다."""
    r = aggregate.evaluate(site, cam_ids, pairs, curve)
    by = {e["zone"]: e for e in (r.get("by_zone") or [])}
    return {
        "recognized_ratio": r["recognized_ratio"],
        "WDR": r["WDR"],
        "fail": r["fail_voxel_count"],
        "zones": {z: (by[z]["recognized_ratio"] if z in by else None)
                  for z in WATCH},
        "per_voxel": r["per_voxel"],
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


def sweep_lambda(site, pairs, curve, cam_ids) -> list:
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
        r = diagnose(site, pairs, with_lambda(curve, lam), cam_ids)
        out.append({"case": name, "lambda": round(lam, 4),
                    "section_normalized": ys,
                    "recognized_ratio": r["recognized_ratio"],
                    "WDR": r["WDR"], "fail": r["fail"], "zones": r["zones"]})
    return out


# ── 2) 비계 점유율 ────────────────────────────────────────────────────────

def sweep_scaffold(curve, cam_ids, cam_yaws) -> list:
    out = []
    for sc in SC_LEVELS:
        # 점유율이 바뀌면 가림이 바뀌므로 광선을 다시 쏜다. 캐시는 형상 하나만
        # 들고 있어 여기서는 못 쓴다.
        #
        # **계획서의 카메라에만 쏜다** (2026-08-27). 후보 308대 전부에 쏘면 한
        # 수준에 수십 분이 들고 세 수준이면 하루가 간다. 배치는 스윕 내내
        # 고정이므로 나머지 292대의 쌍은 쓰이지 않는다 - 계산할 이유가 없다.
        site = site_model.build(scaffold_coverage=sc)
        use = [c for c in site.cameras if c.cid in set(cam_ids)]
        pairs, _ = geometry.all_pairs(site, cameras=use, fixed_yaws=cam_yaws)
        r = diagnose(site, pairs, curve, cam_ids)
        out.append({"scaffold_coverage": sc,
                    "recognized_ratio": r["recognized_ratio"],
                    "WDR": r["WDR"], "fail": r["fail"], "zones": r["zones"]})
        print(f"  비계 점유율 {sc:.2f} -> 인식률 {r['recognized_ratio']:.4f}")
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
        # 비활동 복셀의 P 는 None 이다(값이 없다는 뜻). 집계에서 뺀다.
        ok = sum(1 for v in vox
                 if res["per_voxel"][v["id"]] is not None
                 and res["per_voxel"][v["id"]] >= thr)
        out.append({"threshold": thr,
                    "recognized": ok, "fail": len(vox) - ok,
                    "recognized_ratio": round(ok / len(vox), 4) if vox else None,
                    "n_occupiable": len(vox)})
    return out


def main() -> None:
    print("현장·기하 계산 중…")
    site = site_model.build()
    curve = detect_model.load()
    cam_ids, cam_yaws = plan_camera(site)
    # **계획서의 카메라에만 쏜다.** 배치가 스윕 내내 고정이므로 나머지 후보의
    # 쌍은 쓰이지 않는다. 후보 전체(308대)를 쏘면 쌍이 3,800만 개가 되어
    # 메모리 10GB 를 먹고 한 번 도는 데 두 시간이 넘는다(2026-08-27 실측).
    use = [c for c in site.cameras if c.cid in set(cam_ids)]
    pairs, _ = geometry.all_pairs(site, cameras=use, fixed_yaws=cam_yaws)
    base = diagnose(site, pairs, curve, cam_ids)
    print(f"기준: 인식률 {base['recognized_ratio']:.4f} · WDR {base['WDR']:.4f} "
          f"· 카메라 {len(cam_ids)}대 (계획서 고정)")

    print("\n[1] 스트라이프 주기 -> λ")
    lam = sweep_lambda(site, pairs, curve, cam_ids)
    for r in lam:
        print(f"  {r['case']:<14} λ={r['lambda']:>7.4f}  "
              f"인식률 {r['recognized_ratio']:.4f}  WDR {r['WDR']:.4f}")
    if len(lam) == 1:
        print("  (단면 CSV 가 없다. run_grid.py --occ-only --occ-divisor N 로 만들 것)")

    print("\n[2] 비계 시야 점유율")
    sc = sweep_scaffold(curve, cam_ids, cam_yaws)

    print("\n[3] 판정 임계")
    th = sweep_threshold(site, base)
    for r in th:
        print(f"  임계 {r['threshold']}  인식 {r['recognized']:>7,} / "
              f"미달 {r['fail']:>7,}  ({r['recognized_ratio']:.4f})")

    rows = lam + sc
    ratios = [r["recognized_ratio"] for r in rows]
    # 주시 구역이 전 구간에서 낮게 유지되는가 - 이것이 이 표가 지키는 주장이다.
    worst = {}
    for z in WATCH:
        vals = [r["zones"].get(z) for r in rows if r["zones"].get(z) is not None]
        if vals:
            worst[z] = {"min": min(vals), "max": max(vals)}

    payload = {
        "note": "가림축을 만드는 자유 파라미터 셋에 대한 민감도. **배치는 "
                "계획서로 고정**하고 파라미터만 흔든다. 절대 인식률은 크게 "
                "흔들리지만 고위험 작업구역이 계속 바닥이라면 그것은 "
                "파라미터가 만든 결과가 아니다",
        "placement": {"source": str(PLAN.relative_to(config.ROOT)),
                      "camera_ids": cam_ids, "n": len(cam_ids)},
        "baseline": {"recognized_ratio": base["recognized_ratio"],
                     "WDR": base["WDR"], "fail": base["fail"],
                     "zones": base["zones"]},
        "stripe_period_lambda": lam,
        "scaffold_coverage": sc,
        "threshold": th,
        "recognized_ratio_range": [min(ratios), max(ratios)],
        "watch_zone_range": worst,
        "status": "ok",
    }
    path = config.OUTPUTS / "sensitivity.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n인식률 범위 {min(ratios):.4f} ~ {max(ratios):.4f}")
    for z, v in worst.items():
        print(f"  {z:<20} {v['min']:.4f} ~ {v['max']:.4f}")
    print(f"→ {path}")


if __name__ == "__main__":
    main()
