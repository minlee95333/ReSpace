# -*- coding: utf-8 -*-
"""다중 카메라 결합과 위험가중 집계 (CLAUDE.md §5.3).

    P_total(v) = 1 − Π_c (1 − P(v, c))
    WDR        = Σ_v w(v) · P_total(v) / Σ_v w(v)

다중 카메라 결합은 WSN target coverage 문헌의 표준 형태다.
**중첩은 페널티가 아니다.** 각 0.6 인 두 대가 합쳐 0.84 가 된다.
참고: RESPIRE(2020)도 coverage-only 접근이 단일 센서 의존을 낳는다고 보고했다.

**중첩을 페널티로 다루는 코드를 절대 넣지 않는다** (§5.3).

> ADDENDUM-01 §5.1 로 문구를 고쳤다. 종전에는 *"기존 연구는 중첩 최소화를 목표로
> 삼는데 우리는 반대"* 라고 적었으나 **사실이 아니다** — 센서 네트워크 분야에서는
> 이미 알려진 결과다. 코드 동작은 바뀌지 않았다.
"""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config


def p_total(voxel_id: str, cam_ids, pairs: dict, curve) -> float:
    """복셀 하나가 선택된 카메라들에게 잡힐 확률."""
    miss = 1.0
    for cid in cam_ids:
        geo = pairs.get((cid, voxel_id))
        if geo is None:
            continue
        miss *= (1.0 - curve.p_detect(geo))
    return 1.0 - miss


def evaluate(site, cam_ids, pairs: dict, curve) -> dict:
    """배치 하나를 평가한다. WDR 과 미달구역을 낸다.

    **분모는 사람이 있을 수 있는 복셀(occupiable)뿐이다.** CCTV 는 공중도
    보지만 검출 대상은 사람이라, 아무도 못 가는 허공을 분모에 넣으면
    커버리지가 의미 없이 희석된다. 시각화는 전 복셀을 그린다.
    """
    num = den = 0.0
    per_voxel = {}
    fails = []
    for v in site.voxels:
        if not v.get("occupiable", True):
            # 사람이 못 서는 자리에는 검출확률이 없다. 0 으로 두면 "미달"로
            # 읽히고 지도가 온통 붉어진다. 값이 없다는 뜻의 None 이 맞다.
            per_voxel[v["id"]] = None
            continue
        pt = p_total(v["id"], cam_ids, pairs, curve)
        per_voxel[v["id"]] = pt
        num += v["w"] * pt
        den += v["w"]
        if pt < config.P_DETECT_THRESHOLD:
            # 가장 좋은 카메라의 사유를 대표로 붙인다
            best, best_p = None, -1.0
            for cid in cam_ids:
                geo = pairs.get((cid, v["id"]))
                if geo is None:
                    continue
                p = curve.p_detect(geo)
                if p > best_p:
                    best, best_p = geo, p
            fails.append({
                "voxel_id": v["id"], "x": v["x"], "y": v["y"], "w": v["w"],
                "zones": v["zones"], "P_total": round(pt, 4),
                "reason": curve.reason(best) if best else "가시 카메라 없음",
            })
    return {
        "camera_ids": list(cam_ids),
        "WDR": round(num / den, 4) if den else None,
        "fail_voxel_count": len(fails),
        "per_voxel": per_voxel,
        "fail_zones": fails,
        **_headline(site, per_voxel),
    }


def _headline(site, per_voxel: dict) -> dict:
    """대표 지표 — **AI 인식 가능 공간 비율**과 그 공간 분해 (2026-08-27).

    종전 대표 지표는 WDR 이었다. WDR 은 위험가중 기대값이라 "얼마나 잘 보고
    있는가"를 한 줄로 말하기에는 읽기 어렵다. 대표는 **가중치 없는 비율**로
    바꾼다 — *"작업자가 설 수 있는 공간의 몇 %를 AI 가 인식할 수 있는가"*.
    WDR 은 보조 지표로 남는다.

    `risk_miss` = w·(1−P) 는 **놓치고 있는 위험의 양**이다. 이 값의 합을 Σw 로
    나누면 정확히 1−WDR 이므로, 지도에 칠한 값을 다 더하면 헤드라인 숫자가
    된다. 어느 칸이 그 숫자에 얼마나 기여했는지가 그대로 보인다.

    구역별 집계는 **구역이 겹치므로 합이 전체를 넘는다.** 한 복셀이 타워크레인
    반경 안의 갱폼 작업면일 수 있다. 비율을 더하지 말 것.
    """
    thr = config.P_DETECT_THRESHOLD
    live = [v for v in site.voxels if v.get("occupiable", True)]
    n = len(live)
    if not n:
        return {"recognized_ratio": None, "mean_p": None,
                "risk_miss_total": None, "by_zone": []}

    # **구역의 제 가중치.** 복셀의 w 는 겹친 구역 중 최댓값이라(보수적 판정)
    # 그것으로 구역을 대표시키면 약한 구역이 강한 구역의 값을 빌려 온다 -
    # 콘크리트 타설(w2)이 슬래브 단부(w10)와 겹쳐 w10 으로 보고됐다.
    # 한 구역이 여러 층에 걸치면 층마다 Zone 이 있으므로 최댓값을 잇는다.
    zw = {}
    for z in getattr(site, "zones", []):
        if z.weight > zw.get(z.name, 0):
            zw[z.name] = z.weight

    ok = miss = psum = 0.0
    by = {}
    for v in live:
        p = per_voxel[v["id"]] or 0.0
        m = v["w"] * (1.0 - p)
        psum += p
        miss += m
        hit = 1 if p >= thr else 0
        ok += hit
        for z in (v["zones"] or ["_outside"]):
            e = by.setdefault(z, {"zone": z, "n": 0, "ok": 0, "miss": 0.0,
                                  "w": zw.get(z, config.RISK_WEIGHT_DEFAULT)})
            e["n"] += 1
            e["ok"] += hit
            e["miss"] += m

    rows = sorted(by.values(), key=lambda e: -e["miss"])
    for e in rows:
        e["recognized_ratio"] = round(e["ok"] / e["n"], 4)
        e["risk_miss"] = round(e["miss"], 1)
        e["share_of_total_miss"] = round(e["miss"] / miss, 4) if miss else None
        del e["miss"]

    return {
        "recognized_ratio": round(ok / n, 4),
        "recognized_voxels": int(ok),
        "denominator_voxels": n,
        "mean_p": round(psum / n, 4),
        "risk_miss_total": round(miss, 1),
        "by_zone": rows,
        "_note": "recognized_ratio 가 대표 지표다 (가중치 없는 비율). "
                 "by_zone 은 위험구역이 겹치므로 비율의 합이 전체와 다르다",
    }


def geometric_cover(site, cam_ids, pairs: dict, min_rho_px: float = None) -> dict:
    """**같은 배치를 기존 방식의 자로 잰다** (2026-08-27).

    §5.4 A 의 기하 커버리지를 목적함수가 아니라 **측정자**로 쓴다. 배치를 두 개
    만들어 비교하는 대신, 배치 하나를 자 두 개로 재는 것이 지금의 논증이다 —
    *"기존 기준으로는 커버라고 나오는데 실제 인식은 이만큼"*.

    임계는 DORI 최소 픽셀밀도이며 인간 관찰자 기준이다(§9). 여기서는 기존
    방식이 무엇을 커버로 세는지 재현하는 용도로만 쓴다.
    """
    if min_rho_px is None:
        min_rho_px = config.GEOMETRIC_MIN_RHO_PX
    live = [v for v in site.voxels if v.get("occupiable", True)]
    n = len(live)
    ok = wok = wsum = 0.0
    for v in live:
        wsum += v["w"]
        if any(_covers(pairs.get((cid, v["id"])), min_rho_px) for cid in cam_ids):
            ok += 1
            wok += v["w"]
    return {
        "standard": "IEC 62676-4 (DORI)",
        "level": config.GEOMETRIC_DORI_LEVEL,
        "min_rho_px": round(min_rho_px, 2),
        "covered_ratio": round(ok / n, 4) if n else None,
        "covered_voxels": int(ok),
        "weighted_covered_ratio": round(wok / wsum, 4) if wsum else None,
        "denominator_voxels": n,
        "note": "같은 배치를 기존 방식의 자로 잰 값이다. DORI 는 인간 관찰자 "
                "기준이며 AI 검출기에 대해 검증된 바 없다",
    }


def coverage_score(site, cam_ids, pairs: dict, min_rho_px: float = None) -> float:
    """기하 커버리지 Σ w(v)·1[가시] — 기존 방식의 목적함수 (§5.4 A).

    **가시 판정에 최소 픽셀밀도를 건다.** "화각 안 + 완전차폐 아님" 만으로 세면
    116m 떨어진 복셀도 커버로 잡혀, 기존 방식을 실무보다 못하게 모델링한 채
    이기게 된다. 실무 설계도구는 IEC 62676-4 의 DORI 최소 PPM 을 지키므로
    기준선도 그 수준이어야 비교가 성립한다 (config.GEOMETRIC_DORI_LEVEL).

    min_rho_px=0 을 주면 임계 없는 순수 가시성으로 돌아간다 — 등급별 비교용.
    """
    if min_rho_px is None:
        min_rho_px = config.GEOMETRIC_MIN_RHO_PX
    total = 0.0
    for v in site.voxels:
        if not v.get("occupiable", True):
            continue
        if any(_covers(pairs.get((cid, v["id"])), min_rho_px) for cid in cam_ids):
            total += v["w"]
    return total


def _covers(geo: dict | None, min_rho_px: float) -> bool:
    return bool(geo) and geo.get("visible") and geo.get("rho_px", 0.0) >= min_rho_px
