# -*- coding: utf-8 -*-
"""재계산이 필요한가. start.bat 이 물어보는 자리다.

**왜 필요한가.** start.bat 은 화면을 열기 전에 늘 `report.py` 를 돌렸다.
"옛 수치를 최신인 양 보여주는 것이 가장 나쁘다" 는 이유였고 그 판단은 옳다.
그런데 현장이 단지 전체로 넓어지면서 그 계산이 55분이 됐다. 버튼을 누른
사람 눈에는 멈춘 것으로 보인다 — 실제로 그 신고를 받았다.

**고치는 방향은 "늘 계산" 도 "안 계산" 도 아니다.** 입력이 바뀌었을 때만
계산한다. 입력(형상·구역·설정·소스)이 산출물보다 새로우면 재계산이고,
아니면 그대로 연다. 옛 수치를 보여줄 위험은 그대로 막힌다.

종료 코드
    0   재계산이 필요하다
    1   최신이다 (그냥 열면 된다)

    python src/needs_eval.py          판정만
    python src/needs_eval.py --why    이유를 사람이 읽게 출력
"""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent

# 이것들이 바뀌면 결과가 바뀐다
INPUTS = [
    ROOT / "config.py",
    ROOT / "data" / "building.json",
    ROOT / "data" / "zones.json",
    ROOT / "outputs" / "curve_params.json",
]
# **숫자를 바꾸는 모듈만 센다.**
#
# 종전에는 src/*.py 를 통째로 넣었다. 그러자 출력 서식만 고쳐도(실제로 목업
# 슬림화를 넣었을 때) 55분짜리 재계산이 걸렸다. 사용자가 버튼을 눌렀는데
# 화면이 안 열린다는 신고를 그 때문에 두 번 받았다.
#
# report.py 는 계산을 조율하고 파일을 쓸 뿐 값을 만들지 않는다. 값을 만드는
# 것은 아래 여덟이다. 여기 없는 파일을 고쳤는데 숫자가 달라졌다면 그건 이
# 목록이 틀린 것이므로 목록을 고쳐야 한다.
COMPUTE_SRC = [
    "site_model.py",    # 현장 형상·복셀·카메라 후보
    "geometry.py",      # 광선투사 → rho·theta·occ
    "detect_model.py",  # 곡선 적용
    "aggregate.py",     # P_total·WDR
    "optimize.py",      # 탐욕 배치
    "zone_derive.py",   # 골조에서 위험구역 도출
    "prescribe.py",     # 처방 행렬
    "occ_box.py",       # 가림률 정의
]
INPUTS += [ROOT / "src" / n for n in COMPUTE_SRC]

OUTPUT = ROOT / "outputs" / "site_eval.json"
MOCKUP = ROOT / "mockup" / "data.json"


def stale() -> tuple[bool, str]:
    if not OUTPUT.exists():
        return True, f"{OUTPUT.name} 이 없다"
    if not MOCKUP.exists():
        return True, f"{MOCKUP.name} 이 없다"
    out = min(OUTPUT.stat().st_mtime, MOCKUP.stat().st_mtime)
    newer = [p for p in INPUTS if p.exists() and p.stat().st_mtime > out]
    if newer:
        names = ", ".join(p.name for p in newer[:4])
        more = f" 외 {len(newer) - 4}개" if len(newer) > 4 else ""
        return True, f"입력이 더 새롭다: {names}{more}"
    return False, "산출물이 입력보다 새롭다"


def main() -> int:
    need, why = stale()
    if "--why" in sys.argv:
        try:
            sys.stdout.reconfigure(errors="replace")
        except (AttributeError, ValueError):
            pass
        print(why)
    return 0 if need else 1


if __name__ == "__main__":
    sys.exit(main())
