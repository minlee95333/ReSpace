# -*- coding: utf-8 -*-
"""검출확률 대조표 생성 (2026-08-27).

`mockup/engine.js` 는 `src/geometry.py` + `src/detect_model.py` 를 브라우저로
옮긴 것이다. **값이 갈리면 화면과 보고서가 다른 말을 하게 된다.** 눈으로는
드러나지 않는 종류의 오류라 표본으로 못 박는다.

실제로 이 대조가 결함을 하나 잡았다 — Python 이 사람 막대를 항상 지면에
세우고 있었고(복셀의 `floor_z` 를 읽지 않았다), 지면 복셀은 전수 일치하는데
상부층만 6.5~8.5% 어긋나는 모양으로 나타났다.

  python tools/make_engine_fixture.py   # 대조표 생성 (약 10초)
  node   tools/test_engine.mjs          # 브라우저 구현이 같은 답을 내는지

전 복셀을 재면 Python 이 카메라 하나에 수십 초라 표본을 쓴다. 씨앗을 박아
몇 번을 돌려도 같은 표본이 나온다.
"""
from pathlib import Path
import json
import random
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(errors="replace")
except (AttributeError, ValueError):
    pass
import site_model
import geometry
import detect_model

SEED = 3
N_SAMPLE = 2000
# 경계 폴 높이에서 단지 안쪽을 보는 네 대. 층·거리·가림이 골고루 섞이도록
# 네 귀퉁이에 둔다. 배치의 좋고 나쁨은 여기서 따지지 않는다 — 대조용이다.
CAMS = [(5, 5, 6, 40), (205, 5, 6, 140), (205, 120, 6, 220), (5, 120, 6, 320)]


def main() -> None:
    site = site_model.build()
    curve = detect_model.load()
    occ_vox = [v for v in site.voxels if v["occupiable"]]
    random.seed(SEED)
    sample = random.sample(occ_vox, min(N_SAMPLE, len(occ_vox)))

    recs = []
    for v in sample:
        ps = []
        for i, (x, y, z, yaw) in enumerate(CAMS):
            cam = site_model.Camera(f"bench{i}", float(x), float(y), float(z),
                                    "boundary_pole")
            g = geometry.pair(v, cam, site.solids, float(yaw))
            ps.append(round(curve.p_detect(g) if g["visible"] else 0.0, 10))
        recs.append({"id": v["id"], "x": v["x"], "y": v["y"], "z": v["z"],
                     "floor_z": v["floor_z"], "p": ps})

    out = ROOT / "tools" / "fixture_engine.json"
    out.write_text(json.dumps({
        "_about": "engine.js 대조표. src/geometry.py + src/detect_model.py 의 값이다",
        "cams": [{"x": c[0], "y": c[1], "z": c[2], "yaw": c[3]} for c in CAMS],
        "sample": recs,
    }, ensure_ascii=False), encoding="utf-8")

    nz = sum(1 for r in recs if any(p > 0 for p in r["p"]))
    print(f"{out.name}: 표본 {len(recs):,} × 카메라 {len(CAMS)} "
          f"(검출확률 0 초과 {nz:,}건)")


if __name__ == "__main__":
    main()
