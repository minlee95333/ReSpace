# -*- coding: utf-8 -*-
"""제안서 6장에 들어갈 수치를 산출물에서 뽑는다 (2026-08-27).

**왜 스크립트인가.** 6장의 수치를 사람이 JSON 에서 눈으로 읽어 옮기면 반드시
틀린다 — 이 프로젝트에서 이미 한 번 겪었다(§2 의 표가 다섯 번 움직였다).
초안을 쓸 때마다 여기서 뽑아 쓰고, 산출물이 바뀌면 다시 돌린다.

지어낸 값이 섞이지 않도록 **없는 값은 None 으로 남기고 표시한다**(§0.1-1).

    python tools/section6_numbers.py            # 사람이 읽는 표
    python tools/section6_numbers.py --json     # 기계가 읽는 JSON
"""
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(errors="replace")
except (AttributeError, ValueError):
    pass

OUT = ROOT / "outputs"
ZONE_KO = {
    "slab_edge": "슬래브 단부", "concrete_pour": "콘크리트 타설",
    "gangform_workface": "갱폼 작업면", "opening_perimeter": "개구부 주변",
    "lift_landing": "리프트 승강구", "material_yard": "자재 야적장",
    "tower_crane_radius": "타워크레인 인양반경", "_outside": "위험구역 밖",
}


def _load(name: str):
    p = OUT / name
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def collect() -> dict:
    ev = _load("site_eval.json")
    cv = _load("curve_params.json")
    sn = _load("sensitivity.json")
    out = {"_sources": {}, "status": "ok"}

    if ev is None:
        return {"status": "not_computed",
                "_note": "outputs/site_eval.json 이 없다. python src/report.py 를 먼저 돌릴 것"}

    out["_sources"]["site_eval"] = "outputs/site_eval.json"
    pl = ev.get("placements", {})
    key = "baseline" if "baseline" in pl else next(iter(pl), None)
    p = pl.get(key, {}) if key else {}

    out["site"] = {
        "width_m": ev["site"]["width_m"], "depth_m": ev["site"]["depth_m"],
        "voxel_m": ev["site"]["voxel_m"],
        "n_voxels": len(ev.get("voxels", [])),
        "n_occupiable": p.get("denominator_voxels"),
        "n_solids": len(ev.get("solids", [])),
        "levels": ev.get("slab_levels_m"),
        "n_camera_candidates": len(ev.get("cameras", [])),
        "camera_budget": ev.get("camera_budget"),
        "mode": ev.get("mode"),
    }
    out["headline"] = {
        "placement": key,
        "recognized_ratio": p.get("recognized_ratio"),
        "recognized_voxels": p.get("recognized_voxels"),
        "denominator_voxels": p.get("denominator_voxels"),
        "mean_p": p.get("mean_p"),
        "WDR": p.get("WDR"),
        "fail_voxel_count": p.get("fail_voxel_count"),
        "risk_miss_total": p.get("risk_miss_total"),
        "threshold": ev.get("threshold"),
    }
    gm = p.get("geometric_measure") or {}
    out["geometric_measure"] = {
        "level": gm.get("level"), "min_rho_px": gm.get("min_rho_px"),
        "covered_ratio": gm.get("covered_ratio"),
        "covered_voxels": gm.get("covered_voxels"),
        "weighted_covered_ratio": gm.get("weighted_covered_ratio"),
    }
    # 자 두 개의 차이 — 이 장의 핵심 문장이 여기서 나온다
    if gm.get("covered_ratio") is not None and p.get("recognized_ratio") is not None:
        out["gap"] = {
            "geometric_minus_recognized":
                round(gm["covered_ratio"] - p["recognized_ratio"], 4),
            "note": "같은 배치를 기존 자로 재면 covered_ratio, 실측 검출확률로 "
                    "재면 recognized_ratio 다",
        }

    zones = []
    for z in (p.get("by_zone") or []):
        zones.append({
            "zone": z["zone"], "label": ZONE_KO.get(z["zone"], z["zone"]),
            "n": z["n"], "w": z["w"],
            "recognized_ratio": z["recognized_ratio"],
            "risk_miss": z["risk_miss"],
            "share_of_total_miss": z["share_of_total_miss"],
        })
    out["by_zone"] = zones
    out["_zone_note"] = "위험구역은 겹친다 — 비율의 합이 전체와 다르다"

    oor = ev.get("out_of_measured_range") or {}
    out["out_of_measured_range"] = {
        k: (v.get("ratio") if isinstance(v, dict) else v)
        for k, v in oor.items() if k != "note"
    }
    ps = ev.get("dori_pair_stats") or {}
    out["pair_stats"] = {k: ps.get(k) for k in
                         ("n_pairs", "n_visible", "rho_px_median")}

    if cv:
        out["_sources"]["curve"] = "outputs/curve_params.json"
        t = (cv.get("per_target") or {}).get(cv.get("primary"), cv)
        out["curve"] = {
            "target": cv.get("primary"), "detector": cv.get("detector"),
            "f_rho_x0_px": (t.get("f_rho") or {}).get("x0"),
            "f_rho_L": (t.get("f_rho") or {}).get("L"),
            "f_rho_range_px": (t.get("f_rho") or {}).get("measured_range_px"),
            "g_theta_x0_deg": ((t.get("g_theta") or {}).get("params") or {}).get("x0"),
            "h_occ_lambda": (t.get("h_occ") or {}).get("lambda"),
            "r2_rho_native": cv.get("r2_rho_native"),
            "r2_full_grid": cv.get("r2_full_grid"),
            "n_instances": (t.get("f_rho") or {}).get("n_instances"),
        }
    else:
        out["curve"] = None
        out["status"] = "partial"

    if sn:
        out["_sources"]["sensitivity"] = "outputs/sensitivity.json"
        out["sensitivity"] = {
            "recognized_ratio_range": sn.get("recognized_ratio_range"),
            "watch_zone_range": sn.get("watch_zone_range"),
        }
    else:
        out["sensitivity"] = None
        if out["status"] == "ok":
            out["status"] = "partial"
    return out


def main() -> None:
    d = collect()
    if "--json" in sys.argv:
        print(json.dumps(d, ensure_ascii=False, indent=1))
        return
    if d.get("status") == "not_computed":
        print(d["_note"])
        return

    s, h, g = d["site"], d["headline"], d["geometric_measure"]
    pct = lambda v: "—" if v is None else f"{v * 100:.1f}%"
    print(f"[현장] {s['width_m']:.0f} x {s['depth_m']:.0f} m · 복셀 {s['voxel_m']}m · "
          f"솔리드 {s['n_solids']} · 층 {s['levels']}")
    print(f"       전체 {s['n_voxels']:,} 중 작업자 활동공간 "
          f"{(s['n_occupiable'] or 0):,} · 카메라 {s['camera_budget']}대 "
          f"(후보 {s['n_camera_candidates']}) · 모드 {s['mode']}")
    print()
    print(f"[대표] AI 인식 가능 공간 비율  {pct(h['recognized_ratio'])}  "
          f"({(h['recognized_voxels'] or 0):,} / {(h['denominator_voxels'] or 0):,})")
    print(f"       평균 검출확률 {pct(h['mean_p'])} · WDR {h['WDR']} · "
          f"임계 {h['threshold']} 미만 {(h['fail_voxel_count'] or 0):,}")
    print(f"[대조] 기존 자(DORI {g['level']}, ρ>={g['min_rho_px']}px) 로 재면 "
          f"{pct(g['covered_ratio'])}")
    if "gap" in d:
        print(f"       두 자의 차이 {d['gap']['geometric_minus_recognized'] * 100:+.1f}%p")
    print()
    print("[구역별]  (구역이 겹쳐 합이 전체와 다르다)")
    print(f"  {'구역':<16}{'셀':>9}{'w':>4}{'인식률':>9}{'미검출위험':>12}{'기여':>8}")
    for z in d["by_zone"]:
        print(f"  {z['label']:<16}{z['n']:>9,}{z['w']:>4}"
              f"{pct(z['recognized_ratio']):>9}{z['risk_miss']:>12,.0f}"
              f"{pct(z['share_of_total_miss']):>8}")
    if d.get("curve"):
        c = d["curve"]
        print()
        print(f"[곡선] {c['target']} · {c['detector']} · f(ρ) 반감점 "
              f"{c['f_rho_x0_px']:.2f}px · 실측범위 {c['f_rho_range_px']} · "
              f"R²(ρ 실측) {c['r2_rho_native']}")
    if d.get("sensitivity"):
        print()
        print(f"[민감도] 인식률 범위 {d['sensitivity']['recognized_ratio_range']}")
    else:
        print("\n[민감도] 아직 없다 — python src/sensitivity.py")


if __name__ == "__main__":
    main()
