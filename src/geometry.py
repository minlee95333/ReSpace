# -*- coding: utf-8 -*-
"""복셀-카메라 기하 (CLAUDE.md §5.2).

각 (복셀, 카메라) 쌍에 대해 ρ · θ · o 를 낸다.

  ρ = f_px · H_head / d
  θ = degrees(asin((z_cam - z_voxel) / d))
  o = 복셀에 세운 높이 1.7m 수직 막대의 11개 샘플점 중 골조에 막히는 비율

전부 막히면 visible=False, P=0 이다.

**스펙이 비워둔 것 — 카메라 지향 방향.**
§5.2 는 HFOV 90° 를 f_px 산출에만 쓰고 카메라가 어디를 보는지 정하지 않았다.
방향을 안 정하면 전방위 카메라가 되어 커버리지가 과대 산출된다.

처음에는 전 카메라가 현장 중심을 본다고 두었는데, 그러면 **중심 근처의 코어 상부·
타워크레인 카메라가 서로를 쳐다보게 되어** 쓸모없어진다. 실제로 최적화가 경계 폴만
8대 고르는 결과가 나왔다. 설치자는 볼 곳을 향해 돌리므로 이는 모델의 결함이다.

지금은 **카메라마다 방위(yaw)를 따로 고른다** — 15° 간격 24방위 중 자기 위험가중
가시량을 최대로 만드는 쪽. 위치와 무관하게 결정되고 난수가 없으므로 §5.4 의 최적화
전에 한 번만 계산한다. 부각(pitch)은 스펙에 없어 작업면을 덮도록 조준했다고 보고
수직 화각은 검사하지 않는다. 둘 다 제안서에 한계로 적는다.
"""
from pathlib import Path
import math
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

HALF_HFOV_DEG = config.HFOV_DEG / 2.0
YAW_STEP_DEG = 15                      # 24방위. 난수 없이 전수 탐색한다


def _ray_hits_box(p0, p1, box) -> bool:
    """선분 p0→p1 이 상자를 지나는가. 슬랩 방식.

    회전 상자는 두 끝점을 상자의 로컬 좌표로 옮겨 같은 판정을 쓴다
    (occlusion_row 와 같은 방법이다).
    """
    if getattr(box, "rotated", False):
        ax, ay = box.to_local_xy(p0[0], p0[1])
        bx, by = box.to_local_xy(p1[0], p1[1])
        hx, hy = box.half_xy
        p0 = (ax, ay, p0[2])
        p1 = (bx, by, p1[2])
        spans = ((-hx, hx), (-hy, hy), (box.z1, box.z2))
    else:
        spans = ((box.x1, box.x2), (box.y1, box.y2), (box.z1, box.z2))
    t_min, t_max = 0.0, 1.0
    for i, (lo, hi) in enumerate(spans):
        o, d = p0[i], p1[i] - p0[i]
        if abs(d) < 1e-12:
            if o < lo or o > hi:
                return False
            continue
        t1, t2 = (lo - o) / d, (hi - o) / d
        if t1 > t2:
            t1, t2 = t2, t1
        t_min, t_max = max(t_min, t1), min(t_max, t2)
        if t_min > t_max:
            return False
    return True


def occlusion_ratio(vx: float, vy: float, cam, solids: list,
                    stand_z: float = 0.0) -> float:
    """복셀에 세운 사람 막대가 얼마나 가려지는가 (§5.2).

    `stand_z` 는 **딛는 면의 높이**이며 막대는 거기서 시작한다 (2026-08-27).
    종전에는 이 인자가 없어 막대를 항상 지면에 세웠고, 3층 슬래브 위 작업자를
    지상에 세워놓고 가림을 재어 **상부층이 통째로 틀렸다.** 복셀마다 `floor_z`
    를 저장해 두고도 여기서 읽지 않고 있었다.

    브라우저 구현(`mockup/engine.js`)과 대조해 드러났다 — 지면 복셀은 4,780건
    전수 일치했는데 상부층만 6.5~8.5% 어긋났다. `tools/test_engine.mjs` 가
    이 대조를 고정한다.
    """
    n = config.OCCLUSION_SAMPLE_POINTS
    top = config.OCCLUSION_BAR_HEIGHT_M
    cam_p = (cam.x, cam.y, cam.z)
    total = 0.0
    for i in range(n):
        z = stand_z + top * i / (n - 1)
        p0 = (vx, vy, z)
        # 여러 겹을 지나면 가장 많이 막는 것을 쓴다. 곱으로 누적하면 비계 두 겹만
        # 지나도 사실상 불투명이 되어 실제보다 어둡게 잡힌다.
        hit = [s.coverage for s in solids if _ray_hits_box(p0, cam_p, s)]
        total += max(hit) if hit else 0.0
    return total / n


def bearing_deg(cam, vx: float, vy: float) -> float:
    """카메라에서 복셀로 향하는 방위각(도). 0=+x, 반시계."""
    return math.degrees(math.atan2(vy - cam.y, vx - cam.x)) % 360.0


def in_fov(bearing: float, yaw: float) -> bool:
    """방위각이 yaw 를 중심으로 한 수평 화각 안에 드는가."""
    diff = abs((bearing - yaw + 180.0) % 360.0 - 180.0)
    return diff <= HALF_HFOV_DEG


def occlusion_row(cam, voxels: list, solids: list) -> list:
    """카메라 하나에서 전 복셀까지의 가림률. **한 번만 계산해 돌려쓴다.**

    종전에는 choose_yaw 와 pair 가 각각 계산해 같은 광선을 두 번 쐈다.
    후보를 24개에서 100개 이상으로 늘리면 그 낭비가 그대로 두 배가 된다.

    복셀이 8만 개를 넘어 파이썬 반복으로는 카메라 하나에 8초가 걸린다.
    **전 복셀 × 전 샘플점을 numpy 로 한 번에 민다.** 슬랩 방식은 그대로다.
    """
    import numpy as np
    n = config.OCCLUSION_SAMPLE_POINTS
    top = config.OCCLUSION_BAR_HEIGHT_M

    vx = np.fromiter((v["x"] for v in voxels), float, len(voxels))
    vy = np.fromiter((v["y"] for v in voxels), float, len(voxels))
    # **막대는 딛는 면에서 시작한다** (2026-08-27). 종전에는 zs 를 0 에서 띄워
    # 복셀이 몇 층에 있든 지면에 세웠다. occlusion_ratio 의 주석 참조.
    fz = np.fromiter((v.get("floor_z", 0.0) for v in voxels), float, len(voxels))
    zs = np.linspace(0.0, top, n)

    # (복셀, 샘플점) 격자로 편다
    ox = vx[:, None]                      # 광선 시점
    oy = vy[:, None]
    oz = fz[:, None] + zs[None, :]
    dx = cam.x - ox
    dy = cam.y - oy
    dz = cam.z - oz

    worst = np.zeros((len(voxels), n))
    for s in solids:
        # **회전 상자는 광선을 상자의 로컬 좌표로 돌려서 푼다.** 슬랩 방식은
        # 축정렬을 전제하므로, 상자를 돌리는 대신 광선을 반대로 돌리면 같은
        # 코드를 그대로 쓸 수 있다. 연직축 회전이라 z 는 건드리지 않는다.
        # yaw_deg 가 0 이면 아래 세 줄이 항등이라 기존과 완전히 같다.
        if s.rotated:
            lox, loy = s.to_local_xy(ox, oy)
            ldx, ldy = s.to_local_xy(cam.x, cam.y)
            ldx, ldy = ldx - lox, ldy - loy
            shx, shy = s.half_xy
            axes = ((lox, ldx, -shx, shx), (loy, ldy, -shy, shy),
                    (oz, dz, s.z1, s.z2))
        else:
            axes = ((ox, dx, s.x1, s.x2), (oy, dy, s.y1, s.y2),
                    (oz, dz, s.z1, s.z2))
        t_min = np.zeros_like(worst)
        t_max = np.ones_like(worst)
        ok = np.ones_like(worst, dtype=bool)
        for o, d, lo, hi in axes:
            par = np.abs(d) < 1e-12
            with np.errstate(divide="ignore", invalid="ignore"):
                t1 = (lo - o) / d
                t2 = (hi - o) / d
            lo_t = np.minimum(t1, t2)
            hi_t = np.maximum(t1, t2)
            # 축에 평행한 광선은 그 축 구간 안에 있어야 통과한다
            inside = (o >= lo) & (o <= hi)
            lo_t = np.where(par, np.where(inside, t_min, 1.0), lo_t)
            hi_t = np.where(par, np.where(inside, t_max, 0.0), hi_t)
            t_min = np.maximum(t_min, np.broadcast_to(lo_t, worst.shape))
            t_max = np.minimum(t_max, np.broadcast_to(hi_t, worst.shape))
            ok &= (t_min <= t_max)
        # 여러 겹을 지나면 가장 많이 막는 것을 쓴다 (곱으로 누적하지 않는다)
        worst = np.where(ok, np.maximum(worst, s.coverage), worst)

    return worst.mean(axis=1).tolist()


def choose_yaw(cam, voxels: list, solids: list, occ_row: list = None) -> float:
    """이 카메라가 볼 수 있는 위험가중량을 최대로 만드는 방위를 고른다.

    가림·거리는 방위와 무관하므로 화각 판정만 방위별로 다시 한다.
    동점이면 작은 각도로 끊어 재현성을 지킨다.
    """
    if occ_row is None:
        occ_row = occlusion_row(cam, voxels, solids)
    seen = []
    for v, occ in zip(voxels, occ_row):
        if occ >= 1.0:
            continue
        seen.append((bearing_deg(cam, v["x"], v["y"]), v["w"]))

    best_yaw, best_score = 0.0, -1.0
    for i in range(int(360 / YAW_STEP_DEG)):
        yaw = i * YAW_STEP_DEG
        score = sum(w for b, w in seen if in_fov(b, yaw))
        if score > best_score:
            best_yaw, best_score = float(yaw), score
    return best_yaw


def pair(voxel: dict, cam, solids: list, yaw: float,
         occ: float = None) -> dict:
    """복셀-카메라 한 쌍의 기하량."""
    dx, dy, dz = voxel["x"] - cam.x, voxel["y"] - cam.y, voxel["z"] - cam.z
    d = math.sqrt(dx * dx + dy * dy + dz * dz)
    if d < 1e-6:
        return {"voxel_id": voxel["id"], "camera_id": cam.cid, "d_m": 0.0,
                "rho_px": 0.0, "theta_deg": 0.0, "occ_ratio": 1.0, "visible": False}

    if not in_fov(bearing_deg(cam, voxel["x"], voxel["y"]), yaw):
        return {"voxel_id": voxel["id"], "camera_id": cam.cid, "d_m": round(d, 2),
                "rho_px": 0.0, "theta_deg": 0.0, "occ_ratio": 1.0,
                "visible": False, "reason": "화각 밖"}

    if occ is None:
        occ = occlusion_ratio(voxel["x"], voxel["y"], cam, solids,
                              voxel.get("floor_z", 0.0))
    visible = occ < 1.0
    return {
        "voxel_id": voxel["id"],
        "camera_id": cam.cid,
        "d_m": round(d, 2),
        "rho_px": round(config.rho_px(d), 2),
        "theta_deg": round(config.theta_deg(cam.z, voxel["z"], d), 1),
        "occ_ratio": round(occ, 3),
        "visible": visible,
        **({} if visible else {"reason": "완전 차폐"}),
    }


def all_pairs(site, cameras=None, fixed_yaws: dict = None) -> tuple[dict, dict]:
    """(camera_id, voxel_id) → 기하량, 그리고 카메라별 방위.

    카메라 선택과 무관하므로 한 번만 계산한다.

    `cameras` 로 다른 카메라 집합을 줄 수 있다 — CCTV 계획서를 진단할 때 쓴다.
    `fixed_yaws` 가 있으면 그 방위를 그대로 쓴다. **계획서는 방위가 이미 정해져
    있으므로 우리가 고르지 않는다.** 없는 카메라만 자동으로 고른다.
    """
    cams = list(cameras if cameras is not None else site.cameras)
    fixed_yaws = fixed_yaws or {}
    # **사람이 있을 수 있는 복셀에만 광선을 쏜다** (2026-08-27).
    # 검출 대상은 사람이고, 지표(WDR)의 분모도 occupiable 뿐이며, 뷰어도
    # occupiable 이 아닌 복셀은 애초에 그리지 않는다(viewer._ensurePrep).
    # 그런데 여기서는 전 복셀에 쐈다 — 단지 전체로 넓히니 그 낭비가 3분의 2였다.
    # 372,567 복셀 중 활동공간은 124,632 개다.
    targets = [v for v in site.voxels if v.get("occupiable", True)]
    yaws, out = {}, {}
    for cam in cams:
        # 가림률은 방위와 무관하다. 카메라당 한 번만 쏘고 두 곳에서 쓴다.
        row = occlusion_row(cam, targets, site.solids)
        yaws[cam.cid] = (fixed_yaws[cam.cid] if cam.cid in fixed_yaws
                         else choose_yaw(cam, targets, site.solids, row))
        for v, occ in zip(targets, row):
            out[(cam.cid, v["id"])] = pair(v, cam, site.solids,
                                           yaws[cam.cid], occ)
    return out, yaws


if __name__ == "__main__":
    import site_model
    import collections
    s = site_model.build()
    pairs, yaws = all_pairs(s)
    vis = [p for p in pairs.values() if p["visible"]]
    print(f"쌍 {len(pairs)} (카메라 {len(s.cameras)} × 복셀 {len(s.voxels)})")
    print("  방위:", {k: int(v) for k, v in list(yaws.items())[:6]}, "...")
    print(f"  가시 {len(vis)} ({len(vis)/len(pairs)*100:.1f}%)")
    reasons = collections.Counter(p.get("reason", "-") for p in pairs.values() if not p["visible"])
    print("  비가시 사유:", dict(reasons))
    if vis:
        ds = sorted(p["d_m"] for p in vis)
        rs = sorted(p["rho_px"] for p in vis)
        n = len(ds)
        print(f"  거리   중앙값 {ds[n//2]:.1f}m · 최소 {ds[0]:.1f} · 최대 {ds[-1]:.1f}")
        print(f"  ρ      중앙값 {rs[n//2]:.1f}px · 최소 {rs[0]:.1f} · 최대 {rs[-1]:.1f}")
        below = sum(1 for r in rs if r < config.RHO_MEASURED_MIN_PX)
        print(f"  ρ < {config.RHO_MEASURED_MIN_PX}px (실측 범위 밖): {below} 쌍 ({below/len(vis)*100:.1f}%)")
