# -*- coding: utf-8 -*-
"""현장 내보내기 — **배치 전 상태** (2026-08-27).

목업이 결과 뷰어에서 **배치 도구**로 바뀐다. 사용자가 CCTV 를 직접 놓으므로
미리 정한 배치가 없고, 따라서 복셀별 `P_total` 도 없다. 브라우저가 배치를 받아
그 자리에서 계산한다(`mockup/engine.js`).

그래서 `report.py` 의 출력 계약(배치별 P 를 복셀마다 싣는다)을 쓸 수 없다.
여기서 내보내는 것은 계산에 필요한 **재료**뿐이다.

  · 건설 목적물과 가설물 — 가림 계산과 도면 표시에 쓴다. **회전(yaw) 포함**
  · 복셀 격자와 occupiable · 가중치 · 딛는 면 — 지표의 분모와 막대 밑동
  · 위험구역 — 가중치의 출처. 화면에서 어디가 왜 중요한지 보여준다
  · 검출확률 곡선 계수 전체 — 브라우저가 P 를 직접 계산한다
  · 설치 가능 위치 규칙 — 사용자가 높이를 정하면 자리를 보여준다

**크기를 줄인다.** 복셀 좌표는 격자 인덱스에서 계산되므로 싣지 않고,
occupiable·가중치·층·딛는면은 런렝스로 접는다.

── 이식 경위 (2026-08-27) ──────────────────────────────────────────────────
`feat/mockup-and-eval` 브랜치(팀원 작성)의 같은 이름 모듈을 이 갈래에 맞춰
다시 썼다. 두 갈래에서 `site_model.py` 가 566줄 갈라져 그대로 쓸 수 없었다.
바뀐 곳은 넷이다.

  ① `site_model.build()` 인자가 다르다. 이 갈래는 위험구역을 코드가 골조에서
     도출하므로(`zone_derive.py`) 입력 인자를 받지 않는다
  ② 복셀의 딛는 면 키가 `stand_z` 가 아니라 `floor_z` 다
  ③ 솔리드에 `yaw_deg` 가 있다 — 404·405동이 사선 배치다. **반드시 실어야
     한다.** 빠지면 브라우저가 축정렬로 펴서 가림을 반대편으로 계산한다
  ④ 위험구역이 사각형 하나가 아니라 `areas` 목록이다

`rules`(브라우저가 입력을 받아 다시 계산하는 규칙)와 `presets` 는 **싣지
않는다.** 그쪽 갈래의 `site_rules.js` 가 팀원 쪽 `site_model.py` 를 옮긴 것이라
이 갈래의 규칙과 어긋난다. 위험구역·가설물은 Python 에서 확정해 내보내고,
브라우저는 **카메라 배치만** 실시간으로 계산한다.
"""
from pathlib import Path
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
# 콘솔이 cp949 인 환경에서 출력을 파일로 리디렉션하면 한글·기호에서 죽는다.
# 계산을 다 끝내고 마지막 print 에서 죽으므로 출력단에서 막는다.
try:
    sys.stdout.reconfigure(errors="replace")
    sys.stderr.reconfigure(errors="replace")
except (AttributeError, ValueError):
    pass
import config
import site_model
import detect_model

OUT_JSON = config.MOCKUP / "site.json"
OUT_JS = config.MOCKUP / "site.js"

# 코드가 골조에서 유도하는 설치 방식. 여기 없는 것은 **가설물에서 온 것**이며
# `mounts.equipment` 로 나간다 — 타워크레인·비계 난간이 그것이다.
CODE_MOUNTS = ("boundary_pole", "core_top")


def _rle(values: list) -> list:
    """[값, 반복] 쌍의 목록. 같은 값이 길게 이어지는 배열에 효과가 크다."""
    out = []
    for v in values:
        if out and out[-1][0] == v:
            out[-1][1] += 1
        else:
            out.append([v, 1])
    return out


def _solids(site) -> list:
    """가림원. **`yaw_deg` 를 반드시 싣는다.**

    404·405동이 사선으로 앉아 있다. 이 값이 빠지면 브라우저가 상자를 축정렬로
    보고 가림을 엉뚱한 방향으로 계산한다 — 눈으로는 안 보이는 오류라
    `tools/test_obb.mjs` 가 두 구현의 광선 판정을 대조한다.
    """
    return [{"x1": b.x1, "y1": b.y1, "z1": b.z1,
             "x2": b.x2, "y2": b.y2, "z2": b.z2,
             "yaw_deg": b.yaw_deg, "kind": b.kind, "coverage": b.coverage}
            for b in site.solids]


def _zones(site) -> list:
    """위험구역. 가중치가 어디서 왔는지 화면이 보여줄 수 있게 출처까지 싣는다.

    이 갈래의 위험구역은 사각형 하나가 아니라 `areas` 목록이다 — 한 구역이
    여러 동에 흩어져 있다(슬래브 단부가 5개 동에 각각 있는 식).
    """
    out = []
    for z in site.zones:
        out.append({
            "name": z.name,
            "label": z.label,
            "areas": [list(a) for a in z.areas],
            "z_min": z.z_min,
            "z_max": None if z.z_max == float("inf") else z.z_max,
            "weight": z.weight,
            "tier": z.tier,
            "source": z.source,
        })
    return out


def _mounts(site) -> dict:
    """설치 가능 위치 규칙. 브라우저가 이걸로 자리를 그린다(`mockup/mounts.js`).

    높이를 주면 자리가 정해진다 — 가설 장비 위거나, 구조물 상부거나, 구조체
    측면이거나, 폴이거나. 가설 장비는 도면에서 오지 않으므로 가설물 입력이
    있어야 자리가 생긴다.

    **회전 상자의 자리는 아직 정확하지 않다.** 여기서 `yaw_deg` 를 함께 내보내되
    `mounts.js` 는 아직 축정렬 사각형으로 판정한다. 사선 동(404·405)의 상단·측면
    자리가 실제보다 조금 어긋나며, 이는 배치 후보의 문제이지 평가값의 문제는
    아니다(평가는 engine.js 가 회전을 반영해 계산한다). 다음 단계에서 고친다.
    """
    tops, sides = [], []
    for b in site.solids:
        # 가설 펜스도 카메라를 다는 구조체다. 다만 **상단은 아니다** —
        # 펜스 위에 올라서지 않으므로 측면(선)만 자리로 준다.
        rect = {"kind": b.kind, "yaw_deg": b.yaw_deg,
                "x1": b.x1, "y1": b.y1, "x2": b.x2, "y2": b.y2}
        if b.kind == "fence":
            sides.append(dict(rect, z1=round(b.z1, 2), z2=round(b.z2, 2)))
            continue
        if b.kind not in ("core", "slab"):
            continue
        tops.append(dict(rect, z=round(b.z2, 2)))
        sides.append(dict(rect, z1=round(b.z1, 2), z2=round(b.z2, 2)))

    out = {
        "structure_top": {
            "snap_m": config.CAMERA_MOUNT_SNAP_M,
            "surfaces": tops,
            "note": "구조물 상부에 붙인다. 그 구조물 상단 높이에서만 가능하다",
        },
        # 구조체 측면 — 벽면·단부에 브래킷으로 붙인다. 자리는 **면이 아니라
        # 테두리 선**이며, 높이는 그 구조체의 z 범위 안이면 된다.
        "structure_side": {
            "band_m": config.CAMERA_SIDE_BAND_M,
            "snap_m": config.CAMERA_MOUNT_SNAP_M,
            "faces": sides,
            "note": "구조체 측면에 브래킷으로 붙인다. 테두리 선 위이며 "
                    "그 구조체의 높이 범위 안이면 된다. 가설 펜스도 여기 온다. "
                    "브래킷 폭은 잠정값이다",
        },
        # 가설 장비 위의 자리 — 가설물에서 온다. 타워크레인·비계 난간이 여기다.
        "equipment": {
            "points": [{"id": c.cid, "x": c.x, "y": c.y, "z": c.z, "mount": c.mount}
                       for c in site.cameras if c.mount not in CODE_MOUNTS],
            "snap_m": config.CAMERA_MOUNT_SNAP_M,
            "note": "가설 장비 위에 달 수 있는 자리. 타워크레인·비계 난간이 "
                    "여기 온다. 도면에서 오지 않으므로 가설계획 입력이 있어야 생긴다",
        },
        "_note": "구조물 상부·구조체 측면은 건설 목적물에서 유도된다. "
                 "가설 장비는 가설계획에서 온다",
        "_obb": "회전 상자의 자리 판정은 아직 축정렬 근사다. yaw_deg 를 함께 "
                "실어 두었으므로 mounts.js 가 받으면 바로 정확해진다",
    }
    lo, hi = config.CAMERA_POLE_H_RANGE_M
    if config.ENABLE_POLE_MOUNT:
        out["pole"] = {"h_min_m": lo, "h_max_m": hi,
                       "clearance_m": config.CAMERA_POLE_CLEARANCE_M,
                       "note": "지면에 폴을 세운다. 골조 밖이면 어디든. "
                               "높이 범위는 잠정값이다"}
    else:
        out["_pole_off"] = ("가설 폴은 지금 쓰지 않는다. 폴을 쓴다는 근거를 "
                            "확보하지 못했고, 구조체 측면 설치로 배치가 성립한다")
    return out


def _excluded(site, nx: int, ny: int, nz: int) -> dict:
    """골조 안이라 복셀을 만들지 않은 칸. 종류별로 센다.

    **분모 밖에 무엇이 얼마나 있는가.** 골조 안은 복셀을 아예 만들지 않으므로
    지금까지 화면에 아무 말 없이 조용히 빠져 있었다. 코어는 콘크리트 덩어리가
    아니라 승강로·계단실이고 공사 중에는 사람이 다니는데, CCTV 로는 볼 수 없어
    MVP 에서 감시 대상 밖으로 둔다. **빼는 것보다 빼놓고 말하지 않는 것이
    문제이므로** 수치로 드러낸다.

    한 칸이 여러 솔리드에 걸릴 수 있으므로 격자를 한 번 훑어 처음 걸린 종류로
    센다. 종류별 부피를 단순히 더하면 겹치는 만큼 부풀려진다.
    """
    step = config.VOXEL_M
    kinds = [b for b in site.solids if b.kind in ("core", "slab", "stack")]
    made = {(int(v["x"] / step), int(v["y"] / step), int(v["z"] / step))
            for v in site.voxels}
    by, total = {}, 0
    for k in range(nz):
        z = (k + 0.5) * step
        for j in range(ny):
            y = (j + 0.5) * step
            for i in range(nx):
                if (i, j, k) in made:
                    continue
                x = (i + 0.5) * step
                for b in kinds:
                    if b.z1 <= z <= b.z2 and b.contains_xy(x, y):
                        by[b.kind] = by.get(b.kind, 0) + 1
                        total += 1
                        break
    return {
        "count": total,
        "by_kind": by,
        "grid_cells": nx * ny * nz,
        "note": "골조 안이라 복셀을 만들지 않는다. 코어는 승강로·계단실이며 "
                "CCTV 로 볼 수 없어 MVP 에서 감시 대상 밖으로 둔다. "
                "실내 커버리지는 재지 않았다",
    }


def build() -> dict:
    site = site_model.build()
    curve = detect_model.load()
    step = config.VOXEL_M
    nx = int(round(site.width / step))
    ny = int(round(site.depth / step))
    nz = int(round(config.VOXEL_Z_MAX_M / step))

    idx, occ, w, lvl, stand = [], [], [], [], []
    for v in site.voxels:
        i = int(v["x"] / step)
        j = int(v["y"] / step)
        k = int(v["z"] / step)
        idx.append((k * ny + j) * nx + i)
        occ.append(1 if v["occupiable"] else 0)
        w.append(v["w"])
        lvl.append(v["level"])
        # 사람이 딛고 서는 면. 가림 계산의 막대 밑동이며 브라우저가 이 값을 쓴다.
        # 없으면 막대가 지면에 서고 상부층 가림이 통째로 틀린다.
        # 이 갈래의 키 이름은 `floor_z` 다 — 내보내는 이름은 계약대로 stand_z.
        stand.append(round(v["floor_z"], 3))

    return {
        "_about": "현장 내보내기 (배치 전). CCTV 는 사용자가 직접 놓는다",
        "site": {"width_m": site.width, "depth_m": site.depth, "voxel_m": step,
                 "nx": nx, "ny": ny, "nz": nz},
        "inputs": {
            "building": "data/building.json",
            "zones": "src/zone_derive.py (골조에서 도출)",
            "note": "이 갈래는 위험구역을 코드가 골조에서 도출한다. "
                    "위험도 지수 자체는 자체 산정하지 않고 표에서 받는다",
        },
        "solids": _solids(site),
        "zones": _zones(site),
        "excluded": _excluded(site, nx, ny, nz),
        "levels": sorted({v["level"] for v in site.voxels}),
        "slab_levels_m": config.SLAB_LEVELS_M,
        # 복셀 — 좌표는 싣지 않는다. index 에서 계산된다:
        #   i = index % nx, j = (index / nx) % ny, k = index / (nx*ny)
        #   x = (i+0.5)*voxel_m, y = (j+0.5)*voxel_m, z = (k+0.5)*voxel_m
        "voxels": {"count": len(idx), "index": idx,
                   "occupiable_rle": _rle(occ), "w_rle": _rle(w),
                   "level_rle": _rle(lvl), "stand_z_rle": _rle(stand)},
        # 곡선은 **실측본이다.** `MultiCurve.p` 가 primary(helmet_nohat)의
        # 계수를 그대로 들고 있다 — ρ 축은 GDUT-HWD 실사진에서 얻은 것이고
        # 합성 다운샘플이 아니다(CLAUDE.md §4.5).
        "curve": {
            "source": str(config.CURVE_PARAMS_JSON.relative_to(config.ROOT)),
            "detector": curve.p.get("detector"),
            "target": curve.primary,
            "r2_rho_native": curve.p.get("r2_rho_native"),
            "n_conditions": curve.p.get("n_conditions"),
            "f_rho": curve.p["f_rho"],
            "g_theta": curve.p["g_theta"],
            "h_occ": curve.p["h_occ"],
            "note": "측정 범위 밖은 P=0 이다. 외삽하지 않는다",
        },
        "camera": {"img_w": config.IMG_WIDTH_PX, "img_h": config.IMG_HEIGHT_PX,
                   "hfov_deg": config.HFOV_DEG, "h_head_m": config.H_HEAD_M,
                   "occ_samples": config.OCCLUSION_SAMPLE_POINTS,
                   "occ_bar_h_m": config.OCCLUSION_BAR_HEIGHT_M},
        "mounts": _mounts(site),
        # 화면이 쓰는 상수. **규칙 전체가 아니다** — 위험구역·가설물을 브라우저가
        # 다시 계산하지 않으므로(모듈 머리말 참조) 그리기에 필요한 것만 둔다.
        # 값을 화면에 박지 않아야 Python 과 한 곳에서만 정의된다.
        "rules": {
            "z_max_m": config.VOXEL_Z_MAX_M,
            "occupiable_band_m": list(config.OCCUPIABLE_BAND_M),
            "note": "위험구역·가설물은 Python 에서 확정한다. 브라우저는 "
                    "카메라 배치만 다시 계산한다",
        },
        "threshold": config.P_DETECT_THRESHOLD,
        "target": config.LH_COVERAGE_TARGET,
        "target_metric": config.LH_TARGET_METRIC,
        "target_source": config.LH_COVERAGE_TARGET_SOURCE,
        "status": "ok",
    }


def main() -> Path:
    d = build()
    config.MOCKUP.mkdir(parents=True, exist_ok=True)
    blob = json.dumps(d, ensure_ascii=False, separators=(",", ":"))
    OUT_JSON.write_text(blob, encoding="utf-8")
    # file:// 로 열면 fetch 가 막힌다. 같은 내용을 스크립트로도 둔다.
    OUT_JS.write_text("window.SITE_DATA = " + blob + ";\n", encoding="utf-8")
    v = d["voxels"]
    n_occ = sum(c for val, c in v["occupiable_rle"] if val)
    n_rot = sum(1 for b in d["solids"] if b["yaw_deg"])
    print(f"복셀 {v['count']:,} · occupiable {n_occ:,} "
          f"· 솔리드 {len(d['solids'])} (회전 {n_rot}) · 위험구역 {len(d['zones'])}")
    print(f"제외 {d['excluded']['count']:,} 칸 {d['excluded']['by_kind']}")
    print(f"곡선 f_rho.x0 = {d['curve']['f_rho']['x0']:.2f}px "
          f"({d['curve']['target']})")
    print(f"크기 {len(blob) / 1e6:.2f} MB")
    print(f"-> {OUT_JSON}")
    print(f"-> {OUT_JS}  (file:// 폴백)")
    return OUT_JSON


if __name__ == "__main__":
    main()
