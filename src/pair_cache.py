# -*- coding: utf-8 -*-
"""광선투사 결과(쌍)를 캐시한다. **곡선 교체를 몇 초로 만든다.**

**왜.** 이 도구의 계산은 두 층이다.

    ① 기하 — 복셀·카메라·골조에서 (거리, 픽셀밀도, 부감각, 가림률)을 낸다.
             현장 전체 기준 광선투사에만 40분이 걸린다. **곡선과 무관하다.**
    ② 곡선 — 그 네 값에 f(ρ)·g(θ)·h(o) 를 먹여 검출확률을 낸다. 초 단위다.

그런데 report.py 가 한 프로세스에서 둘을 다 하므로, 곡선만 바꿔도 40분을
다시 냈다. 제안서는 *"곡선은 교체 가능한 입력"* 이라고 주장하는데 실제로는
교체가 40분짜리였던 셈이다. 캐시가 그 주장을 시연 가능하게 만든다.

**무엇을 키로 삼는가.** 기하를 바꾸는 것만 본다 — 현장 형상(building.json),
위험구역(zones.json), 기하 상수(현장 크기·복셀·화각·초점거리·카메라 간격·
층 높이), 그리고 기하를 만드는 소스 세 개. 곡선 파일은 **일부러 뺀다**.
곡선이 바뀌어도 쌍은 그대로이기 때문이고, 그것이 이 캐시의 요점이다.

키가 다르면 조용히 옛 쌍을 쓰지 않고 다시 쏜다. 옛 기하를 새 것인 양
쓰는 것이 이 프로젝트에서 가장 나쁜 실패다.

    from pair_cache import load_or_build
    pairs, yaws = load_or_build(site)
"""
from pathlib import Path
import hashlib
import json
import pickle
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config

CACHE = config.ROOT / "outputs" / "_pairs_cache.pkl"

# 기하를 바꾸는 설정값만. 곡선·판정임계·예산은 여기 없다 — 쌍을 안 바꾼다.
GEOM_CONST = (
    "SITE_WIDTH_M", "SITE_DEPTH_M", "VOXEL_M", "VOXEL_MODE", "VOXEL_Z_MAX_M",
    "SLAB_LEVELS_M", "OCCUPIABLE_BAND_M", "OCCUPIABLE_NEAR_SCAFFOLD_M",
    "CAMERA_SPACING_M", "TOWER_CRANE_MAST_XY", "TOWER_CRANE_CAM_Z_M",
    "HFOV_DEG", "IMG_WIDTH_PX", "IMG_HEIGHT_PX", "H_HEAD_M",
    "OCCLUSION_BAR_HEIGHT_M", "OCCLUSION_SAMPLE_POINTS", "SCAFFOLD_COVERAGE",
    "WORK_PLANE_OFFSET_M", "RISK_WEIGHT_DEFAULT",
)
GEOM_SRC = ("site_model.py", "geometry.py", "zone_derive.py", "occ_box.py")


def _digest() -> str:
    h = hashlib.sha256()
    for name in GEOM_CONST:
        h.update(f"{name}={getattr(config, name, None)!r};".encode())
    for f in (config.ROOT / "data" / "building.json",
              config.ROOT / "data" / "zones.json"):
        h.update(f.read_bytes() if f.exists() else b"-")
    for n in GEOM_SRC:
        p = config.ROOT / "src" / n
        h.update(p.read_bytes() if p.exists() else b"-")
    return h.hexdigest()[:16]


def load_or_build(site, force: bool = False):
    """캐시가 이 기하의 것이면 읽고, 아니면 쏘고 저장한다."""
    import geometry
    key = _digest()
    if not force and CACHE.exists():
        try:
            blob = pickle.loads(CACHE.read_bytes())
            if blob.get("key") == key:
                print(f"쌍 캐시 적중 ({len(blob['pairs']):,} 쌍) — 광선투사를 건너뛴다")
                return blob["pairs"], blob["yaws"]
            print("쌍 캐시가 다른 기하의 것이다. 다시 쏜다.")
        except Exception as e:                      # 깨진 캐시는 무시하고 재계산
            print(f"쌍 캐시를 읽지 못했다({e}). 다시 쏜다.")

    pairs, yaws = geometry.all_pairs(site)
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_bytes(pickle.dumps({"key": key, "pairs": pairs, "yaws": yaws},
                                   protocol=pickle.HIGHEST_PROTOCOL))
    print(f"쌍 {len(pairs):,} 개를 캐시에 저장했다 ({CACHE.name})")
    return pairs, yaws


if __name__ == "__main__":
    print("기하 키:", _digest())
    print("캐시:", CACHE, "있음" if CACHE.exists() else "없음")
