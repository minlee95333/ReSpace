# -*- coding: utf-8 -*-
"""회전 상자 광선판정 대조표 생성 (2026-08-27).

`mockup/engine.js` 의 rayHitsBox 는 `src/geometry.py` 의 `_ray_hits_box` 를
옮긴 것이다. **회전 부호가 갈리면 사선 동(404·405)의 가림이 반대편으로
계산되고, 화면과 보고서가 다른 말을 하게 된다.** 눈으로는 안 보이는 오류라
난수 케이스로 못 박는다.

  python tools/make_obb_fixture.py     # 대조표 생성
  node   tools/test_obb.mjs            # JS 가 같은 답을 내는지 확인
"""
from pathlib import Path
import json
import math
import random
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))
import site_model
import geometry

SEED = 7            # 난수를 쓰되 씨앗을 박아 몇 번을 돌려도 같은 표가 나온다
N = 4000
YAWS = [0, 15, -23.5, 37, 90, 180, -62.3]   # 0 을 넣어 축정렬 경로도 함께 덮는다


def main() -> None:
    random.seed(SEED)
    cases = []
    for _ in range(N):
        cx, cy = random.uniform(0, 100), random.uniform(0, 100)
        hw, hd = random.uniform(2, 20), random.uniform(2, 20)
        box = site_model.Box(cx - hw, cy - hd, random.uniform(0, 3),
                             cx + hw, cy + hd, random.uniform(5, 30),
                             "solid", 1.0, random.choice(YAWS))
        p0 = (random.uniform(-20, 120), random.uniform(-20, 120), random.uniform(0, 20))
        p1 = (random.uniform(-20, 120), random.uniform(-20, 120), random.uniform(0, 20))
        cases.append({
            "b": {"x1": box.x1, "y1": box.y1, "z1": box.z1,
                  "x2": box.x2, "y2": box.y2, "z2": box.z2,
                  "yaw_deg": box.yaw_deg},
            "p0": list(p0), "p1": list(p1),
            "hit": bool(geometry._ray_hits_box(p0, p1, box)),
        })
    out = ROOT / "tools" / "fixture_obb.json"
    out.write_text(json.dumps(cases), encoding="utf-8")
    hits = sum(c["hit"] for c in cases)
    print(f"{out.name}: {len(cases)}건 (적중 {hits}건, 회전 {sum(1 for c in cases if c['b']['yaw_deg'])}건)")


if __name__ == "__main__":
    main()
