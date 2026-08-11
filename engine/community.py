"""⑦-b community — 주민공동시설 의무면적 반영.

LH 공고는 **50세대 이상이면 세대당 1.0㎡ 이상**의 커뮤니티공간을 요구한다.
이 면적을 빼지 않으면 세대수가 과대 산출된다. 판정 시스템에서 과대평가는
과소평가보다 나쁘다 — "80세대 된다"고 했는데 실제로 안 되는 쪽이다.

**순환을 고정점으로 푼다.** 세대수가 필요면적을 정하고, 그 면적이 다시 세대수를
줄인다. 세대를 하나 빼면 확보면적은 늘고 필요면적은 줄어들어 격차가 단조 감소하므로
반복은 반드시 끝난다.

**어느 세대를 빼는가**는 규칙으로 고정한다(난수 금지). 공고가 커뮤니티시설을
'지상 1층 원칙'으로 두므로 **가장 낮은 주거층**에서, **배치 역순**으로 뺀다.
배치 순서가 결정론적이므로 같은 입력이면 같은 세대가 빠진다.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from .common import CommonArea
from .contracts import Inputs

_REASON = "community"


@dataclass(frozen=True)
class CommunityResult:
    households: int  # 반영 후 세대수
    households_before: int
    required_m2: float
    provided_m2: float
    removed_count: int
    floor: int | None  # 커뮤니티를 배치한 층
    offices: tuple[str, ...]  # 경비실 / 관리사무소 설치 의무
    satisfied: bool
    basis: str

    @property
    def applied(self) -> bool:
        return self.removed_count > 0


def _cell_m2(grid) -> float:
    return (grid.grid_mm / 1000) ** 2


def apply(inputs: Inputs, floors: tuple) -> tuple[tuple, CommunityResult]:
    """커뮤니티 의무면적을 반영한 층 분석과 그 내역을 돌려준다.

    반환된 층 목록은 세대가 빠진 상태이며, 빠진 자리는 사유 'community' 의
    공용면적으로 들어간다. 화면에서 "왜 여기가 세대가 아닌가"가 남는다.
    """
    rules = inputs.rules.community
    total_before = sum(len(f.units) for f in floors)
    offices = rules.offices_required(total_before)

    def result(
        households, required, provided, removed, floor, satisfied, basis
    ) -> CommunityResult:
        return CommunityResult(
            households=households,
            households_before=total_before,
            required_m2=round(required, 2),
            provided_m2=round(provided, 2),
            removed_count=removed,
            floor=floor,
            offices=offices,
            satisfied=satisfied,
            basis=basis,
        )

    if rules.required_area_m2(total_before) == 0:
        return floors, result(
            total_before, 0.0, 0.0, 0, None, True,
            f"{total_before}세대 — 의무 기준 {rules.required_from_households}세대 미만이라 "
            f"커뮤니티 의무면적이 없다",
        )

    # 가장 낮은 주거층에서 뺀다 (공고 '마. 지상 1층을 원칙으로 하되').
    target = min(range(len(floors)), key=lambda i: floors[i].floor)
    fa = floors[target]
    cell_m2 = _cell_m2(fa.grid)
    pool = list(fa.units)

    removed: list = []
    freed = 0.0
    while True:
        n = total_before - len(removed)
        required = rules.required_area_m2(n)
        if freed >= required:
            break
        if not pool:
            # 한 층을 통째로 비워도 모자란다. 숫자를 맞추려 다른 층을 건드리지 않고
            # 부족한 채로 보고한다 — 어디까지 확보되는지가 심의 정보다.
            return _rebuild(inputs, floors, target, removed, cell_m2), result(
                total_before - len(removed), required, freed, len(removed),
                fa.floor, False,
                f"{fa.floor}층 세대를 모두 전환해도 필요면적 {required:.1f}㎡ 에 "
                f"{freed:.1f}㎡ 로 미달한다",
            )
        u = pool.pop()  # 배치 역순
        removed.append(u)
        freed += u.cells[2] * u.cells[3] * cell_m2

    n = total_before - len(removed)
    required = rules.required_area_m2(n)
    return _rebuild(inputs, floors, target, removed, cell_m2), result(
        n, required, freed, len(removed), fa.floor, True,
        f"{total_before}세대 → 필요 {rules.area_per_household_m2}㎡/세대 기준으로 "
        f"{fa.floor}층 {len(removed)}세대를 커뮤니티로 전환, "
        f"확보 {freed:.1f}㎡ ≥ 필요 {required:.1f}㎡ (반영 후 {n}세대)",
    )


def _rebuild(inputs: Inputs, floors: tuple, target: int, removed: list, cell_m2: float):
    """전환된 세대를 빼고 같은 자리를 공용면적으로 넣은 층 목록."""
    if not removed:
        return floors

    fa = floors[target]
    gone = {u.cells for u in removed}
    kept = tuple(u for u in fa.units if u.cells not in gone)

    extra = tuple(
        CommonArea(
            bbox_cells=u.cells,
            bbox_mm=u.rect_mm,
            cell_count=u.cells[2] * u.cells[3],
            area_m2=round(u.cells[2] * u.cells[3] * cell_m2, 2),
            reason=_REASON,
            detail=(
                f"주민공동시설 의무면적 — 세대당 "
                f"{inputs.rules.community.area_per_household_m2}㎡ (공고 p5)"
            ),
        )
        for u in removed
    )

    new_fa = replace(
        fa,
        daylight=replace(fa.daylight, units=kept),
        commons=fa.commons + extra,
    )
    return floors[:target] + (new_fa,) + floors[target + 1 :]
