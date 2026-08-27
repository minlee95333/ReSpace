# -*- coding: utf-8 -*-
"""사용자가 직접 CCTV 를 배치할 수 있도록 (셀 × 카메라) 검출확률을 내보낸다.

**왜 필요한가.** 제안서 §6 은 *"본 연구의 목적은 배치안을 자동으로 최적화하는
것이 아니라, 사용자가 계획하거나 실제 설치한 배치가 적정한지를 평가하는 것"*
이라고 적어 두었다. 그런데 목업은 미리 계산해 둔 세 배치만 보여주었다. 사용자가
카메라를 직접 놓아볼 수 없으면 그 문장이 화면에 없는 셈이다.

**어떻게.** 브라우저에서 `P_total(v) = 1 - Π(1-P(v,c))` 를 실시간으로 다시
계산하려면 카메라별 P 가 있어야 한다. 카메라 하나당 활동공간 전 셀의 P 를
uint8(0~255) 로 양자화해 이어 붙인 이진 파일을 만든다. JSON 으로 내면 파싱만
수십 초가 걸린다.

**후보를 추려 넣는다.** 전 후보를 다 실으면 300 x 124,632 = 37MB 다. 목업이
이미 data.json 37MB 를 읽으므로 두 배가 된다. 그래서 `MAX_PICKABLE` 개만
고른다 — 세 배치가 실제로 고른 카메라는 **무조건 포함**하고(그래야 화면에서
그 배치를 재현할 수 있다), 나머지는 후보 목록에서 고르게 편다.

    python src/export_picker.py

산출: mockup/pmatrix.bin (uint8) · mockup/pmatrix.json (메타)
"""
from pathlib import Path
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
try:
    sys.stdout.reconfigure(errors="replace")
except (AttributeError, ValueError):
    pass

import config
import site_model
import geometry
import detect_model

MAX_PICKABLE = 96          # 96 x 124,632 = 약 12MB
OUT_BIN = config.ROOT / "mockup" / "pmatrix.bin"
OUT_META = config.ROOT / "mockup" / "pmatrix.json"


def pick_candidates(site, must_have: list) -> list:
    """반드시 넣을 것 + 나머지를 고르게 편 것."""
    ids = [c.cid for c in site.cameras]
    keep = [c for c in ids if c in set(must_have)]
    rest = [c for c in ids if c not in set(keep)]
    room = max(0, MAX_PICKABLE - len(keep))
    if room and rest:
        step = max(1, len(rest) // room)
        keep += rest[::step][:room]
    # 원래 순서를 지킨다 — 화면 목록이 현장 둘레를 도는 순서가 된다
    order = {c: i for i, c in enumerate(ids)}
    return sorted(set(keep), key=lambda c: order[c])


def main():
    site = site_model.build()
    curve = detect_model.load()

    cmp_path = config.OUTPUTS / "comparison.json"
    must = []
    if cmp_path.exists():
        cmp_ = json.loads(cmp_path.read_text(encoding="utf-8"))
        for v in (cmp_.get("placements") or {}).values():
            must += v.get("camera_ids") or []

    cams = pick_candidates(site, must)
    by_id = {c.cid: c for c in site.cameras}
    chosen = [by_id[c] for c in cams]
    print(f"후보 {len(site.cameras)} 중 {len(chosen)} 개를 내보낸다 "
          f"(세 배치가 쓴 {len(set(must))} 개 포함)")

    vox = [v for v in site.voxels if v.get("occupiable", True)]
    print(f"활동공간 {len(vox):,} 셀 · 예상 {len(chosen) * len(vox) / 1e6:.1f}M 바이트")

    pairs, yaws = geometry.all_pairs(site, cameras=chosen)

    buf = bytearray(len(chosen) * len(vox))
    k = 0
    for cam in chosen:
        for v in vox:
            g = pairs.get((cam.cid, v["id"]))
            p = curve.p_detect(g) if g else 0.0
            buf[k] = int(round(max(0.0, min(1.0, p)) * 255))
            k += 1
    OUT_BIN.write_bytes(bytes(buf))

    meta = {
        "_about": "사용자 직접 배치용 (카메라 × 활동공간셀) 검출확률. uint8 0~255.",
        "_layout": "pmatrix.bin 은 cameras 순서로 이어 붙인 행이다. 행 길이 = n_voxels.",
        "_use": "P = byte/255. P_total(v) = 1 - Π(1-P) 를 선택된 카메라에 대해 계산한다.",
        "target": getattr(curve, "primary", "helmet_nohat"),
        "n_cameras": len(chosen),
        "n_voxels": len(vox),
        "cameras": [{"id": c.cid, "x": c.x, "y": c.y, "z": c.z,
                     "mount": c.mount, "yaw_deg": round(yaws.get(c.cid, 0.0), 1)}
                    for c in chosen],
        "voxel_ids": [v["id"] for v in vox],
        "weights": [v["w"] for v in vox],
        "threshold": config.P_DETECT_THRESHOLD,
        "camera_budget": config.CAMERA_BUDGET,
    }
    OUT_META.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    print(f"→ {OUT_BIN.name} {OUT_BIN.stat().st_size:,} bytes")
    print(f"→ {OUT_META.name} {OUT_META.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()
