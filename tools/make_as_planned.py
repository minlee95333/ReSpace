# -*- coding: utf-8 -*-
"""기준 CCTV 계획서 만들기 — 실무 관행 모사 (2026-08-27).

**왜 필요한가.** 자동 배치(`optimize.py`)를 쓰지 않기로 하면서
(`config.ENABLE_OPTIMIZATION = False`) 제안서가 근거로 삼을 **배치 하나**가
있어야 한다. 그 배치가 무엇인지 설명할 수 없으면 뒤따르는 수치가 전부 공중에
뜬다.

**규칙은 하나다 — 현장 경계를 따라 등간격.** 실무에서 가장 흔한 설치 방식이고,
종전 `data/plans/as_planned.json` 도 같은 규칙이었다(*"경계 폴에 균등 배치한
8대"*). 현장이 100×60m·8대에서 210×125m·16대로 커지면서 좌표만 다시 잡는다.

**이것은 최적화가 아니다.** 위치는 위 규칙이 정하며 검출확률을 보지 않는다.
방위(yaw)만 `geometry.choose_yaw` 로 고르는데, 이는 설치자가 현장에서 카메라를
작업면 쪽으로 돌리는 것을 모사한 것이다. §5.2 에 방위 규정이 없어 이 저장소가
줄곧 쓰던 방식이며(`site_eval.json` 의 `aim` 참조), 배치 세 종 모두에 같은
방식이 적용돼 왔다.

**화면에서 놓은 배치를 쓰고 싶다면** 이 파일을 돌리지 말고, `mockup/index.html`
에서 카메라를 놓고 "계획서로 내보내기" 를 눌러 나온 파일을 `data/plans/` 에
두면 된다. 계약이 같으므로 `src/report.py` 가 그대로 읽는다.

    python tools/make_as_planned.py
"""
from pathlib import Path
import math
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(errors="replace")
except (AttributeError, ValueError):
    pass
import config
import site_model
import geometry
import plan_io

OUT = ROOT / "data" / "plans" / "as_planned.json"
MOUNT = "boundary_pole"


def _perimeter_key(cam, w: float, d: float) -> float:
    """경계를 한 바퀴 도는 거리. 등간격으로 고르기 위한 1차원 좌표다.

    남 -> 동 -> 북 -> 서 순으로 편다. 어느 변에 붙었는지는 가장 가까운 변으로
    본다 — 폴은 경계에서 1~2m 안쪽에 서므로 정확히 변 위에 있지 않다.
    """
    dist = {"S": cam.y, "E": w - cam.x, "N": d - cam.y, "W": cam.x}
    side = min(dist, key=dist.get)
    if side == "S":
        return cam.x
    if side == "E":
        return w + cam.y
    if side == "N":
        return w + d + (w - cam.x)
    return 2 * w + d + (d - cam.y)


def main() -> None:
    site = site_model.build()
    pool = [c for c in site.cameras if c.mount == MOUNT]
    if len(pool) < config.CAMERA_BUDGET:
        raise SystemExit(f"경계 폴 후보가 {len(pool)}개뿐이라 "
                         f"{config.CAMERA_BUDGET}대를 놓을 수 없다")

    per = 2 * (site.width + site.depth)
    pool.sort(key=lambda c: _perimeter_key(c, site.width, site.depth))
    keys = [_perimeter_key(c, site.width, site.depth) for c in pool]

    # 둘레를 예산으로 나눈 지점마다 가장 가까운 후보를 집는다. 같은 후보가 두 번
    # 걸리면 그 다음으로 가까운 것을 쓴다 — 후보 간격이 고르지 않아 생긴다.
    picked, used = [], set()
    for i in range(config.CAMERA_BUDGET):
        target = per * i / config.CAMERA_BUDGET
        order = sorted(range(len(pool)),
                       key=lambda j: min(abs(keys[j] - target),
                                         per - abs(keys[j] - target)))
        for j in order:
            if j not in used:
                used.add(j)
                picked.append(pool[j])
                break

    picked.sort(key=lambda c: _perimeter_key(c, site.width, site.depth))

    # 방위는 현장 조준을 모사한다. 가림·거리는 방위와 무관하므로 한 번만 쏜다.
    yaws = {}
    for c in picked:
        occ = geometry.occlusion_row(c, site.voxels, site.solids)
        yaws[c.cid] = geometry.choose_yaw(c, site.voxels, site.solids, occ)

    note = (f"실무 관행 모사 — 현장 경계를 따라 등간격 {config.CAMERA_BUDGET}대. "
            f"위치는 이 규칙만으로 정했고 검출확률을 보지 않았다. 방위는 "
            f"설치자의 현장 조준을 모사해 15도 격자에서 골랐다. "
            f"생성: tools/make_as_planned.py")
    plan_io.save_sample(OUT, site, yaws, [c.cid for c in picked], note)

    print(f"경계 폴 후보 {len(pool)} 중 {len(picked)}대 선정 -> {OUT.name}")
    for c in picked:
        print(f"  {c.cid}  ({c.x:6.1f}, {c.y:6.1f}, z{c.z:4.1f})  방위 {yaws[c.cid]:5.1f}도")


if __name__ == "__main__":
    main()
