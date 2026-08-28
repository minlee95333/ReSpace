# -*- coding: utf-8 -*-
"""Phase 3 산출 — site_eval.json · comparison.json · mockup/data.json.

출력 계약은 CLAUDE.md §5.5 다. 계산되지 않은 값은 `null` 로 두고 `status` 로
알린다(§0.1-1). 두 배치 모두 **B 의 자(P_detect)로 재측정**한 값을 싣는다.

`ENABLE_OPTIMIZATION` 이 False 면 폴백 경로다(§7 D+7). optimize 를 돌리지 않고
단일 배치 진단만 낸다.
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
import pair_cache
import geometry
import detect_model
import baseline_curve
import aggregate
import optimize
import plan_io
import score


def _dori_sweep(site, pairs, curve, prob_result: dict) -> list:
    """기하 기준선을 DORI 등급별로 다시 세우고 확률 배치와 비교한다.

    §5.4 A 의 기하 커버리지를 임계 없이 세면 116m 떨어진 복셀도 커버로 잡혀
    기존 방식을 실무보다 못하게 모델링하게 된다. 어느 등급으로 세워도 결론이
    유지되는지 보이는 것이 이 표의 목적이다. 확률 배치는 등급과 무관하므로
    한 번 구한 것을 그대로 쓴다.
    """
    rows = []
    levels = [("none", 0.0)] + [(lv, config.dori_rho_px(lv))
                                for lv in ("detection", "observation", "recognition")]
    for lv, thr in levels:
        cams = optimize.greedy(site, pairs, curve, "geometric",
                               config.CAMERA_BUDGET, thr)
        res = aggregate.evaluate(site, cams, pairs, curve)
        rows.append({
            "dori_level": lv,
            "ppm": config.DORI_PPM.get(lv),
            "min_rho_px": round(thr, 2),
            "camera_ids": cams,
            "WDR": res["WDR"],
            "fail_voxel_count": res["fail_voxel_count"],
            "delta_WDR": round(prob_result["WDR"] - res["WDR"], 4),
            "is_default": lv == config.GEOMETRIC_DORI_LEVEL,
        })
    return rows


def build_payload() -> dict:
    site = site_model.build()
    curve = detect_model.load()

    if config.ENABLE_OPTIMIZATION:
        # 탐욕이 후보 전체를 훑으므로 모든 쌍이 필요하다. 광선투사는 곡선과
        # 무관하니 기하가 그대로면 캐시를 쓴다(src/pair_cache.py).
        pairs, yaws = pair_cache.load_or_build(site)
        assumed = baseline_curve.load()
        placements = optimize.run(site, pairs, curve, assumed_curve=assumed)
        mode = "optimization"
        baseline_sweep = _dori_sweep(site, pairs, curve, placements["empirical"])
    else:
        # 단일 배치 진단 (§7 D+7 의 폴백 경로. 2026-08-27 부터 이것이 기본이다)
        #
        # **종전에는 카메라 id 를 정렬해 앞 16개를 잘랐다.** 배치라고 부를 수
        # 없는 임의 슬라이스였고, 그 위에서 나온 수치는 무엇을 잰 것인지
        # 설명할 수 없다. 지금은 계획서를 읽는다 — 화면에서 내보낸 것이거나
        # tools/make_as_planned.py 가 만든 실무 관행 배치다.
        plan_path = config.ROOT / "data" / "plans" / "as_planned.json"
        if not plan_path.exists():
            raise SystemExit(
                f"계획서가 없다: {plan_path}\n"
                "  python tools/make_as_planned.py   (실무 관행 배치를 만든다)\n"
                "  또는 mockup 화면에서 '계획서로 내보내기' 한 파일을 여기 둘 것")
        plan_cams, plan_yaws, plan_doc = plan_io.load(plan_path)
        base = [c.cid for c in plan_cams]
        # 계획서의 카메라가 현장 후보에 없으면 광선투사 결과가 없다. 조용히
        # 빠지면 대수가 줄어든 채로 지표가 나오므로 여기서 멈춘다.
        known = {c.cid for c in site.cameras}
        missing = [cid for cid in base if cid not in known]
        if missing:
            raise SystemExit(
                f"계획서의 카메라 {len(missing)}대가 현장 후보에 없다: "
                f"{missing[:5]}\n"
                "  화면에서 내보낸 계획서라면 후보 밖 좌표일 수 있다. "
                "pair_cache 가 그 카메라의 쌍을 갖고 있지 않으므로 계산할 수 없다.")
        # **계획서의 카메라에만 광선을 쏜다** (2026-08-27).
        #
        # 자동 배치를 뺀 뒤로 후보 308대의 쌍은 아무도 읽지 않는다. 그런데도
        # 전부 만들고 있었고, 쌍 3,800만 개가 메모리 10GB 를 먹어 스래싱으로
        # 한 번 도는 데 두 시간이 넘어갔다. 16대만 쏘면 5% 다.
        #
        # 캐시도 쓰지 않는다 — 캐시는 후보 전체를 담는 물건이라 여기서는
        # 만들 이유가 없다.
        use = [c for c in site.cameras if c.cid in set(base)]
        pairs, _ = geometry.all_pairs(site, cameras=use, fixed_yaws=plan_yaws)
        yaws = dict(plan_yaws)              # 계획서의 방위를 그대로 쓴다
        placements = {"baseline": aggregate.evaluate(site, base, pairs, curve)}
        mode = "single_placement"
        baseline_sweep = None

    voxels = []
    for v in site.voxels:
        row = {"id": v["id"], "x": v["x"], "y": v["y"], "z": v["z"],
               "level": v["level"], "floor_z": v["floor_z"],
               "occupiable": v["occupiable"],
               "w": v["w"], "zones": v["zones"]}
        for key, res in placements.items():
            pv = res["per_voxel"][v["id"]]
            # 사람이 못 서는 자리에는 검출확률이 없다(None). 0 으로 바꾸면
            # 지도가 온통 미달로 읽히고, round() 는 None 에서 죽는다.
            row[f"P_total_{key}"] = None if pv is None else round(pv, 4)
        primary = "empirical" if "empirical" in placements else list(placements)[0]
        pp = row[f"P_total_{primary}"]
        row["pass"] = None if pp is None else bool(pp >= config.P_DETECT_THRESHOLD)
        voxels.append(row)

    payload = {
        "site": {"width_m": site.width, "depth_m": site.depth,
                 "voxel_m": config.VOXEL_M},
        "camera_budget": config.CAMERA_BUDGET,
        "threshold": config.P_DETECT_THRESHOLD,
        "mode": mode,
        # **평가한 카메라만 싣는다.** 최적화 모드에서는 후보 전체(탐욕이 그
        # 안에서 고르므로 화면이 후보를 그려야 한다), 단일 배치 모드에서는
        # 계획서의 카메라만. 방위가 없는 카메라를 실으면 KeyError 로 죽는다.
        "cameras": [{"id": c.cid, "x": c.x, "y": c.y, "z": c.z, "mount": c.mount,
                     "yaw_deg": yaws[c.cid]}
                    for c in site.cameras if c.cid in yaws],
        # 3D/2.5D 뷰가 골조를 그리는 데 쓴다. 계산에는 관여하지 않는다.
        "solids": [{"x1": b.x1, "y1": b.y1, "z1": b.z1,
                    "x2": b.x2, "y2": b.y2, "z2": b.z2,
                    "yaw_deg": b.yaw_deg,
                    "kind": b.kind, "coverage": b.coverage} for b in site.solids],
        "levels": sorted({v["level"] for v in site.voxels}),
        "slab_levels_m": config.SLAB_LEVELS_M,
        "aim": {"hfov_deg": config.HFOV_DEG,
                "yaw_step_deg": geometry.YAW_STEP_DEG,
                "note": "§5.2 가 지향을 정하지 않아, 카메라마다 자기 위험가중 가시량을 "
                        "최대로 만드는 방위를 15° 간격 전수 탐색으로 골랐다"},
        # 목업이 배치별로 히트맵·미달목록을 토글하므로 fail_zones 를 배치마다 싣는다.
        # §5.5 의 최상위 fail_zones 는 계약이라 그대로 두고 확률 배치 것을 넣는다.
        "placements": {
            k: {"camera_ids": v["camera_ids"], "WDR": v["WDR"],
                "fail_voxel_count": v["fail_voxel_count"],
                # 대표 지표 — 가중치 없는 인식 가능 공간 비율과 그 구역별 분해.
                # WDR 은 보조로 내린다 (aggregate._headline 참조).
                "recognized_ratio": v.get("recognized_ratio"),
                "recognized_voxels": v.get("recognized_voxels"),
                "denominator_voxels": v.get("denominator_voxels"),
                "mean_p": v.get("mean_p"),
                "risk_miss_total": v.get("risk_miss_total"),
                "by_zone": v.get("by_zone"),
                # **같은 배치를 기존 방식의 자로 잰 값.** 배치 둘을 비교하는
                # 대신 자 둘로 재는 것이 지금의 논증이다.
                "geometric_measure": aggregate.geometric_cover(
                    site, v["camera_ids"], pairs),
                # 100점 만점 채점 (src/score.py). 화면 머리의 대표 숫자가 이것이다.
                # 배점은 **가중치에 비례하고 면적과 무관하다** - 넓은 저위험
                # 구역을 잘 덮어 갱폼을 통째로 놓치고도 높은 점수가 나오는 것을
                # 막는다. 치명 구역이 요구에 미달하면 등급에 상한이 걸린다.
                "score": score.evaluate(site, _pt_array(site, v["per_voxel"])),
                "fail_zones": v["fail_zones"]}
            for k, v in placements.items()
        },
        "voxels": voxels,
        "fail_zones": (placements.get("empirical") or
                       list(placements.values())[0])["fail_zones"],
        "curve": {
            "source": str(config.CURVE_PARAMS_JSON.relative_to(config.ROOT)),
            "rho_measured_px": curve.p["f_rho"]["measured_range_px"],
            # ρ 축을 실사진 실측으로 바꾼 뒤 r2_full_grid 는 null 이다.
            # 합성 격자를 맞히는 것이 더 이상 목적이 아니기 때문이다
            # (src/apply_native_rho.py 의 설명 참조).
            "r2_full_grid": curve.p.get("r2_full_grid"),
            "r2_rho_native": curve.p.get("r2_rho_native"),
            "f_rho_source": curve.p.get("f_rho_source"),
            "g_theta_h_occ_source": curve.p.get("g_theta_h_occ_source"),
        },
        "geometric_baseline": {
            "standard": "IEC 62676-4 (DORI)",
            "level": config.GEOMETRIC_DORI_LEVEL,
            "min_rho_px": round(config.GEOMETRIC_MIN_RHO_PX, 2),
            "note": "기하 기준선은 임계 없는 가시성이 아니라 DORI 최소 픽셀밀도를 "
                    "지키도록 세웠다. 등급별 결과는 baseline_sweep 에 있다. "
                    "DORI 는 인간 관찰자 기준이며 AI 검출기에 검증된 바 없다",
            "sweep": baseline_sweep,
        },
        "assumed_curve": (assumed.describe()
                          if config.ENABLE_OPTIMIZATION else None),
        "dori_pair_stats": _pair_stats(pairs),
        "out_of_measured_range": _range_stats(pairs, curve),
        "status": "ok",
    }
    return payload, placements


def _pt_array(site, per_voxel: dict):
    """score.evaluate 가 받는 복셀별 P_total 배열.

    사람이 못 서는 자리는 값이 없다(None). 채점은 구역 인덱스로 잘라 쓰므로
    그 자리에 0 을 두어도 집계에 들어가지 않는다 - zone_index 가 occupiable
    만 담는다.
    """
    import numpy as np
    return np.array([(per_voxel[v["id"]] or 0.0) for v in site.voxels], dtype=float)


def _range_stats(pairs: dict, curve) -> dict:
    """실측 범위를 벗어나 P=0 으로 처리된 쌍이 얼마나 되는가.

    §9 는 "측정 범위 밖으로 외삽하지 않는다"를 원칙으로 세웠다. 그 원칙이
    실제로 몇 개를 잘라내는지 숫자로 남겨야 영향의 크기를 말할 수 있다.
    """
    vis = [p for p in pairs.values() if p["visible"]]
    n = len(vis) or 1
    below_rho = sum(1 for p in vis if p["rho_px"] < curve.rho_min)
    over_theta = sum(1 for p in vis if p["theta_deg"] > curve.theta_max)
    over_occ = sum(1 for p in vis if p["occ_ratio"] > curve.occ_max)
    any_out = sum(1 for p in vis
                  if p["rho_px"] < curve.rho_min or p["theta_deg"] > curve.theta_max
                  or p["occ_ratio"] > curve.occ_max)
    return {
        "n_visible": len(vis),
        "rho_below_min": {"limit_px": curve.rho_min, "n": below_rho,
                          "ratio": round(below_rho / n, 4)},
        "theta_over_max": {"limit_deg": curve.theta_max, "n": over_theta,
                           "ratio": round(over_theta / n, 4)},
        "occ_over_max": {"limit": curve.occ_max, "n": over_occ,
                         "ratio": round(over_occ / n, 4)},
        "any": {"n": any_out, "ratio": round(any_out / n, 4)},
    }


def _pair_stats(pairs: dict) -> dict:
    """가시 쌍이 DORI 각 등급을 얼마나 만족하는가.

    "보이기는 하지만 판별할 픽셀이 없는" 비율을 수치로 남긴다.
    """
    vis = [p for p in pairs.values() if p["visible"]]
    if not vis:
        return {"n_pairs": len(pairs), "n_visible": 0}
    rs = sorted(p["rho_px"] for p in vis)
    out = {
        "n_pairs": len(pairs),
        "n_visible": len(vis),
        "rho_px_median": round(rs[len(rs) // 2], 2),
        "rho_px_min": round(rs[0], 2),
        "rho_px_max": round(rs[-1], 2),
        "levels": {},
    }
    for lv in config.DORI_PPM:
        thr = config.dori_rho_px(lv)
        n = sum(1 for r in rs if r >= thr)
        out["levels"][lv] = {"ppm": config.DORI_PPM[lv], "min_rho_px": round(thr, 2),
                             "n_pass": n, "ratio": round(n / len(vis), 4)}
    return out


MOCKUP_FAIL_ROWS = 2000     # 미달구역 탭은 400행만 그린다. 여유를 두고 자른다.


def _slim_for_mockup(payload: dict) -> dict:
    """브라우저가 받을 것만 남긴다.

    **왜.** 단지 전체로 넓히자 site_eval.json 이 171MB 가 됐다. 그대로 목업에
    넘기면 fetch 와 JSON.parse 만으로 수십 초가 걸리고 메모리도 위험하다.
    실제로 화면이 안 열린다는 신고를 받았다.

    무엇을 빼는가 - 둘 다 **뷰어가 애초에 쓰지 않는 것**이다.

      (1) 비활동 복셀. viewer._ensurePrep 이 occupiable === false 를 건너뛴다.
          372,567 중 247,935 개(67%)가 여기 해당한다. 화면에 없던 데이터다.
      (2) 미달구역 전량. 표는 상위 400행만 그린다. 개수는 fail_voxel_count 로
          따로 싣고 있으므로 목록을 잘라도 화면이 같다.

    **개수와 지표는 건드리지 않는다.** WDR·미달 수는 payload 에 이미 계산돼
    들어 있고 여기서 다시 세지 않는다. 목록만 자른다.
    """
    out = dict(payload)
    out["voxels"] = [
        {k: v for k, v in row.items() if k != "occupiable"}
        for row in payload["voxels"] if row.get("occupiable", True)
    ]
    out["_slim"] = {
        "note": ("목업 표시용이다. 비활동 복셀과 미달구역 목록 꼬리를 뺐다. "
                 "정본은 outputs/site_eval.json 이다."),
        "voxels_full": len(payload["voxels"]),
        "voxels_here": len(out["voxels"]),
        "fail_rows_kept": MOCKUP_FAIL_ROWS,
    }

    def cut(zones):
        return list(zones or [])[:MOCKUP_FAIL_ROWS]

    out["fail_zones"] = cut(payload.get("fail_zones"))
    if "placements" in payload:
        out["placements"] = {
            k: {**v, "fail_zones": cut(v.get("fail_zones"))}
            for k, v in payload["placements"].items()
        }
    return out


def main() -> None:
    payload, placements = build_payload()
    config.OUTPUTS.mkdir(parents=True, exist_ok=True)
    config.SITE_EVAL_JSON.write_text(
        json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")

    if {"geometric", "assumed", "empirical"} <= set(placements):
        g = placements["geometric"]
        a = placements["assumed"]
        e = placements["empirical"]
        comparison = {
            "measured_with": "empirical_curve",
            "note": "세 배치를 모두 실측 곡선의 자로 쟀다. 가정 곡선은 설계에만 "
                    "쓰고 채점에는 쓰지 않는다 (ADDENDUM-01 §5.4)",
            "geometric_baseline": payload["geometric_baseline"]["level"],
            "geometric_baseline_min_rho_px": payload["geometric_baseline"]["min_rho_px"],
            "baseline_sweep": payload["geometric_baseline"]["sweep"],
            "placements": {
                "geometric": {"camera_ids": g["camera_ids"], "WDR": g["WDR"],
                              "fail_voxel_count": g["fail_voxel_count"]},
                "assumed": {"camera_ids": a["camera_ids"], "WDR": a["WDR"],
                            "fail_voxel_count": a["fail_voxel_count"],
                            "curve_source": payload["assumed_curve"]["curve_source"]},
                "empirical": {"camera_ids": e["camera_ids"], "WDR": e["WDR"],
                              "fail_voxel_count": e["fail_voxel_count"]},
            },
            "delta_WDR": {
                "empirical_minus_geometric": round(e["WDR"] - g["WDR"], 4),
                "empirical_minus_assumed": round(e["WDR"] - a["WDR"], 4),
                "assumed_minus_geometric": round(a["WDR"] - g["WDR"], 4),
            },
            "overlap_camera_count": {
                "empirical_vs_geometric": len(set(e["camera_ids"]) & set(g["camera_ids"])),
                "empirical_vs_assumed": len(set(e["camera_ids"]) & set(a["camera_ids"])),
            },
            "per_target_WDR": {
                "_note": "ADDENDUM-01 §5.3 의 4항목 분해(person/helmet/pose-fallen/"
                         "pose-gesture)는 현재 CLAUDE.md 스펙에 없어 미구현이다. "
                         "지금 곡선은 안전모 미착용(recall_nohat) 단일 항목이다.",
                "target": "helmet_nohat",
                "geometric": {"helmet_nohat": g["WDR"]},
                "assumed": {"helmet_nohat": a["WDR"]},
                "empirical": {"helmet_nohat": e["WDR"]},
            },
            "status": "ok",
        }
        config.COMPARISON_JSON.write_text(
            json.dumps(comparison, ensure_ascii=False, indent=1), encoding="utf-8")
    else:
        # **낡은 파일이 최신인 척하지 못하게 막는다** (2026-08-27).
        #
        # 단일 배치 모드에서는 비교할 배치가 없어 이 파일을 만들지 않는다.
        # 그런데 종전 판이 그대로 남아 있으면 사람도 도구도 그것을 현재
        # 수치로 읽는다 — 실제로 요약 출력이 8/25 의 ΔWDR 을 찍고 있었다.
        # 지우지 않고 **못 쓰게 표시한다** — 지우면 무엇이 있었는지도 사라진다.
        config.COMPARISON_JSON.write_text(json.dumps({
            "status": "not_produced",
            "note": "배치를 두 개 만들어 비교하던 산출물이다. 자동 배치를 연구 "
                    "범위에서 빼면서(CLAUDE.md §1.5) 비교할 대상이 없어졌다. "
                    "**이 파일의 수치를 쓰지 말 것.** 지금 지표는 "
                    "outputs/site_eval.json 의 placements.baseline 에 있고, "
                    "제안서용 요약은 python tools/section6_numbers.py 로 뽑는다.",
            "mode": payload.get("mode"),
            "superseded_by": "outputs/site_eval.json",
        }, ensure_ascii=False, indent=1), encoding="utf-8")

    # 목업은 data.json 을 fetch 로 읽는다 (§7 Phase 4).
    # data.js 는 같은 내용의 사본이다. file:// 로 직접 열면 브라우저가 fetch 를
    # 막아 §7 Phase 4 Acceptance("파일 열었을 때 에러 없이 렌더링")를 통과하지
    # 못하므로 폴백을 함께 낸다. 데이터는 여전히 여기서 만들며 HTML 에 박지 않는다.
    config.MOCKUP.mkdir(parents=True, exist_ok=True)
    blob = json.dumps(_slim_for_mockup(payload), ensure_ascii=False,
                      separators=(",", ":"))
    (config.MOCKUP / "data.json").write_text(blob, encoding="utf-8")
    (config.MOCKUP / "data.js").write_text(
        "// report.py 가 만든 사본이다. 직접 고치지 말 것.\n"
        "window.SITE_DATA = " + blob + ";\n", encoding="utf-8")

    st = payload.get("dori_pair_stats") or {}
    if st.get("n_visible"):
        print(f"가시 쌍 {st['n_visible']}/{st['n_pairs']} · ρ 중앙값 {st['rho_px_median']}px "
              f"(최소 {st['rho_px_min']} / 최대 {st['rho_px_max']})")
        for lv, v in st["levels"].items():
            print(f"  DORI {lv:<15}{v['ppm']:>6.1f} PPM = ρ {v['min_rho_px']:>5.2f}px"
                  f" → {v['n_pass']:>6} 쌍 ({v['ratio']*100:5.1f}%)")

    rg = payload.get("out_of_measured_range") or {}
    if rg:
        print(f"측정 범위 밖 (P=0 처리) - 가시 쌍 {rg['n_visible']} 중")
        print(f"  ρ < {rg['rho_below_min']['limit_px']}px      {rg['rho_below_min']['n']:>6} "
              f"({rg['rho_below_min']['ratio']*100:5.2f}%)")
        print(f"  θ > {rg['theta_over_max']['limit_deg']}°       {rg['theta_over_max']['n']:>6} "
              f"({rg['theta_over_max']['ratio']*100:5.2f}%)")
        print(f"  o > {rg['occ_over_max']['limit']}       {rg['occ_over_max']['n']:>6} "
              f"({rg['occ_over_max']['ratio']*100:5.2f}%)")
        print(f"  합계(중복 제거) {rg['any']['n']:>6} ({rg['any']['ratio']*100:5.2f}%)\n")

    sweep = (payload.get("geometric_baseline") or {}).get("sweep")
    if sweep:
        print(f"\n기하 기준선 등급별 (기본값 = {payload['geometric_baseline']['level']})")
        for r in sweep:
            mark = " ←기본" if r["is_default"] else ""
            print(f"  {r['dori_level']:<12} ρ≥{r['min_rho_px']:>5.2f}px  "
                  f"WDR {r['WDR']:.4f} · 미달 {r['fail_voxel_count']:>4}  "
                  f"ΔWDR {r['delta_WDR']:+.4f}{mark}")
        print()

    print(f"복셀 {len(payload['voxels'])} · 카메라 예산 {payload['camera_budget']}")
    for k, v in payload["placements"].items():
        print(f"  {k:<15} WDR {v['WDR']:.4f} · 미달 {v['fail_voxel_count']}개 "
              f"· {','.join(v['camera_ids'])}")
    if config.COMPARISON_JSON.exists():
        c = json.loads(config.COMPARISON_JSON.read_text(encoding="utf-8"))
        d = c.get("delta_WDR")
    else:
        c = d = None
    if d:
        print(f"  ΔWDR  실측-기하 {d['empirical_minus_geometric']:+.4f}"
              f" · 실측-가정 {d['empirical_minus_assumed']:+.4f}"
              f" · 가정-기하 {d['assumed_minus_geometric']:+.4f}")
        o = c["overlap_camera_count"]
        print(f"  공통 카메라  실측∩기하 {o['empirical_vs_geometric']}대"
              f" · 실측∩가정 {o['empirical_vs_assumed']}대")
    print(f"→ {config.SITE_EVAL_JSON}")
    print(f"→ {config.COMPARISON_JSON}")
    print(f"→ {config.MOCKUP / 'data.json'}")
    print(f"→ {config.MOCKUP / 'data.js'}  (file:// 폴백)")


if __name__ == "__main__":
    main()
