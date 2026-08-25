# -*- coding: utf-8 -*-
"""스마트 안전보고서 자동 생성 (2026-08-19 교수 지시).

**CCTV 계획서를 넣으면 보고서가 나온다.** 이것이 이 도구의 사용 형태다.

  입력   data/plans/<이름>.json   — 카메라 위치·방위·사양
  출력   outputs/safety_report.json
         outputs/safety_report.html  — 인쇄 가능한 단일 파일

보고서에 담기는 것:

  1. 판정        LH 기준 대비 통과/미달
  2. 커버리지    층별 · 위험구역별. 분모를 밝힌다
  3. 사각지대    어디가 왜 안 보이는가
  4. 처방        재배치 / 증설 대수 / 설치 위치 / 예상 커버리지
  5. 근거        곡선 출처, 검출기, 측정 범위, 한계

수치는 전부 계산 결과이며 이 파일에서 만들지 않는다(§0.1-1).
"""
from pathlib import Path
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

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config
import site_model
import geometry
import detect_model
import prescribe
import schedule
import plan_io

REPORT_JSON = config.OUTPUTS / "safety_report.json"
REPORT_HTML = config.OUTPUTS / "safety_report.html"


def _shown_path(plan_path: Path) -> str:
    """보고서에 찍을 계획서 경로. 표시용이므로 여기서 죽어선 안 된다.

    리포 안이면 상대경로가 읽기 좋고, 밖이면 절대경로 말고 쓸 것이 없다.
    `relative_to` 를 그냥 부르면 상대경로 인자(`data/plans/...`)와 리포 밖
    경로 둘 다에서 ValueError 가 나 보고서 전체가 못 나온다.
    """
    p = Path(plan_path).resolve()
    try:
        return str(p.relative_to(config.ROOT))
    except ValueError:
        return str(p)


def build(plan_path: Path) -> dict:
    site = site_model.build()
    cams_plan, yaws_plan, doc = plan_io.load(plan_path)

    # 후보 전체 + 계획서 카메라. 계획서 카메라는 방위가 이미 정해져 있다.
    known = {c.cid for c in site.cameras}
    extra = [c for c in cams_plan if c.cid not in known]
    all_cams = list(site.cameras) + extra
    pairs, yaws = geometry.all_pairs(site, all_cams, fixed_yaws=yaws_plan)

    curve = detect_model.load()
    cam_ids = [c.cid for c in all_cams]
    cams, P, w = prescribe.build_matrix(site, pairs, curve, cam_ids)
    plan_idx = [cams.index(c.cid) for c in cams_plan]

    d = prescribe.diagnose(site, pairs, curve, plan_idx, cams, P, w)
    m = d["target_metric"]

    # 층별 분해 — 3D 화의 실질 내용이다
    pt = prescribe.p_total(P, plan_idx)
    levels = {}
    for lvl in sorted({v["level"] for v in site.voxels}):
        sel = [i for i, v in enumerate(site.voxels) if v["level"] == lvl]
        ok = [i for i in sel if pt[i] >= d["threshold"]]
        wsum = sum(site.voxels[i]["w"] for i in sel)
        levels[str(lvl)] = {
            "floor_z_m": site.voxels[sel[0]]["floor_z"],
            "voxels": len(sel),
            "spatial_coverage": round(len(ok) / len(sel), 4),
            "risk_coverage": round(
                sum(site.voxels[i]["w"] for i in ok) / wsum, 4) if wsum else None,
        }

    # 위험구역별 분해. **출처를 함께 싣는다** — 어느 사각형이 어디서 왔는지
    # 보고서만 보고 추적할 수 있어야 한다. 근거 없는 구역은 애초에 들어오지
    # 못하지만(site_model._zones 가 raise), 들어온 것의 출처는 보여야 한다.
    meta = {}
    for z in site.zones:
        e = meta.setdefault(z.name, {"label": z.label, "hazard": z.hazard,
                                     "tier": z.tier, "source": z.source,
                                     "rule": z.rule, "parts": 0})
        e["parts"] += 1
    zones = {}
    for zname in sorted({z for v in site.voxels for z in v["zones"]}):
        sel = [i for i, v in enumerate(site.voxels) if zname in v["zones"]]
        ok = [i for i in sel if pt[i] >= d["threshold"]]
        zones[zname] = {"voxels": len(sel),
                        "coverage": round(len(ok) / len(sel), 4),
                        "weight": site.voxels[sel[0]]["w"],
                        **meta.get(zname, {})}

    blind = sorted(
        [{"voxel_id": site.voxels[i]["id"], "x": site.voxels[i]["x"],
          "y": site.voxels[i]["y"], "level": site.voxels[i]["level"],
          "w": site.voxels[i]["w"], "zones": site.voxels[i]["zones"],
          "P_total": round(float(pt[i]), 4),
          "reason": _worst_reason(cams, plan_idx, site.voxels[i]["id"], pairs, curve)}
         for i in range(len(site.voxels)) if pt[i] < d["threshold"]],
        key=lambda r: (-r["w"], r["P_total"]))

    # 시간대별 위험구역 진단 (2026-08-20). 위험구역은 하루 내내 같지 않다.
    try:
        timed = schedule.evaluate_all(site, P, plan_idx)
    except FileNotFoundError:
        timed = None

    return {
        "plan": {"path": _shown_path(plan_path),
                 "note": doc.get("_note", ""), "cameras": len(cams_plan)},
        "site": {"width_m": site.width, "depth_m": site.depth,
                 "voxel_m": config.VOXEL_M, "levels": len(levels),
                 "voxels": len(site.voxels)},
        "standard": {"target": d["target"], "metric": m,
                     "source": config.LH_COVERAGE_TARGET_SOURCE,
                     "threshold": d["threshold"],
                     "note": "커버리지 비율 기준은 어느 법령·고시·지침에도 없다"
                             "(2026-08-21 조사 종결). 이 값은 우리가 제안하는 "
                             "값이며 고시값이 아니다. 네 임계 전부의 결과를 "
                             "target_sweep 에 함께 싣는다. "
                             "docs/reference/커버리지_기준_조사.md",
                     "sweep": d.get("target_sweep")},
        "verdict": {"passes": d["passes"],
                    "value": d["current"][m],
                    "gap": round(d["target"] - d["current"][m], 4)},
        "coverage": {"overall": d["current"], "by_level": levels, "by_zone": zones},
        "blind_spots": blind,
        "prescription": d["prescription"],
        "time_phased": timed,
        "options": {"reallocate": d["reallocated_same_count"],
                    "ceiling": d["ceiling"], "add_curve": d["add_curve"],
                    "full_curve": d["full_curve"]},
        "basis": {
            "detector": curve.p.get("detector"),
            "detector_weights": curve.p.get("detector_weights"),
            "curve": str(config.CURVE_PARAMS_JSON.relative_to(config.ROOT)),
            # r2_full_grid 는 **항목별 최솟값**이다(fit_curve.py). 보수적 대표값이라
            # 그것만 실으면 주 지표의 설명력을 실제보다 낮게 보고하게 된다.
            # 판정에 쓰이는 곡선은 미착용(주 지표) 쪽이므로 둘을 같이 싣는다.
            "r2_full_grid": curve.p.get("r2_full_grid"),
            "r2_primary": curve.p.get("r2_primary"),
            "r2_rho_native": curve.p.get("r2_rho_native"),
            "f_rho_source": curve.p.get("f_rho_source"),
            "g_theta_h_occ_source": curve.p.get("g_theta_h_occ_source"),
            "rho_measured_px": curve.p["f_rho"]["measured_range_px"],
            "camera_spec": {"img_w": config.IMG_WIDTH_PX,
                            "img_h": config.IMG_HEIGHT_PX,
                            "hfov_deg": config.HFOV_DEG},
            "limits": [
                "ρ(픽셀밀도) 축은 GDUT-HWD 실사진의 실제 머리 크기로 쟀다. "
                "θ·o 축은 SHWD 정지영상의 합성 변형에서 얻었고, 합성 가림(수직 "
                "스트라이프)과 실제 비계 가림의 등가성은 검증되지 않았다",
                "θ·o 는 ρ=48px 단면에서 쟀다. 작은 머리에서의 추가 열화가 "
                "빠져 있어 낙관 방향이다",
                "ρ 곡선은 검출기가 해당 영역을 원 해상도로 본다고 가정한다 "
                "(타일링·크롭 추론). 4K 프레임을 통째로 축소해 넣는 파이프라인은 "
                "이보다 나쁘다",
                "카메라 부각(pitch)은 검사하지 않는다 — 작업면을 덮도록 "
                "조준했다고 본다",
                "비계 점유율은 잠정값이다. 건설현장 실측 가림률 통계가 없다",
                "위험 가중치 1~10 은 고용노동부 사망사고 통계에서 유도했다. 전국 합계라 구역별 노출면적을 보정하지 못한다 — 붕괴가 낮게 나온다. 두 프로파일로 민감도를 확인했고 판정은 같았다 (docs/reference/위험가중치_근거.md)",
            ],
        },
        "status": "ok",
    }


def _worst_reason(cams, idx, vid, pairs, curve) -> str:
    best, best_p = None, -1.0
    for i in idx:
        geo = pairs.get((cams[i], vid))
        if geo is None:
            continue
        p = curve.p_detect(geo)
        if p > best_p:
            best, best_p = geo, p
    return curve.reason(best) if best else "가시 카메라 없음"


def main(plan_path: Path = None) -> Path:
    plan_path = Path(plan_path or config.ROOT / "data/plans/as_planned.json")
    rep = build(plan_path)
    REPORT_JSON.parent.mkdir(parents=True, exist_ok=True)
    REPORT_JSON.write_text(json.dumps(rep, ensure_ascii=False, indent=1),
                           encoding="utf-8")
    import render_report
    render_report.write(rep, REPORT_HTML)

    m = rep["standard"]["metric"]
    print(f"계획서 {rep['plan']['cameras']}대 · 복셀 {rep['site']['voxels']} "
          f"({rep['site']['levels']}개 층)")
    print(f"판정: {rep['coverage']['overall'][m]:.1%} / 목표 "
          f"{rep['standard']['target']:.0%} → "
          f"{'통과' if rep['verdict']['passes'] else '미달'}")
    print(f"처방[{rep['prescription']['verdict']}] {rep['prescription']['text']}")
    print(f"→ {REPORT_JSON}")
    print(f"→ {REPORT_HTML}")
    return REPORT_HTML


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
