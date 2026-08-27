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
