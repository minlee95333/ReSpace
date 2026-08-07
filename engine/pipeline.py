"""①~⑧ 을 순서대로 돌려 한 건물의 분석 결과를 만든다.

기준층 1개만 입력해도 `building.floors_residential` 범위만큼 반복해 전 층을 낸다.
층마다 피난 한계가 달라질 수 있으므로(16층 이상 40m) 실제 층 번호로 각각 계산한다.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from .caps import Caps, compute as compute_caps, verdict as make_verdict
from .common import CommonArea, collect
from .contracts import ContractError, FloorPlan, Inputs
from .corridor import CorridorResult, generate
from .daylight import DaylightResult, evaluate
from .egress import EgressMap, compute as compute_egress
from .grid import CellState, Grid, gridify
from .place import (
    PlacedUnit,
    PlacementResult,
    is_shaft_reusable,
    new_wall_length_mm,
    place,
)


@dataclass(frozen=True)
class FloorAnalysis:
    floor: int
    grid: Grid
    corridor: CorridorResult
    egress: EgressMap
    placement: PlacementResult
    daylight: DaylightResult
    commons: tuple[CommonArea, ...]

    @property
    def units(self) -> tuple[PlacedUnit, ...]:
        return self.daylight.units

    @property
    def free_m2(self) -> float:
        return round(self.grid.count(CellState.FREE) * (self.grid.grid_mm / 1000) ** 2, 2)


@dataclass(frozen=True)
class Analysis:
    inputs: Inputs
    strategy: str
    floors: tuple[FloorAnalysis, ...]
    caps: Caps
    grade: str
    reasons: tuple[str, ...]
    quantities: dict[str, float | None]

    @property
    def units(self) -> tuple[PlacedUnit, ...]:
        return tuple(u for f in self.floors for u in f.units)


def residential_floors(inputs: Inputs) -> tuple[int, ...]:
    """분석 대상 층 번호. floors_residential 이 있으면 그 범위 전체를 돈다."""
    fr = inputs.building.floors_residential
    if fr is None:
        return tuple(f.floor for f in inputs.floors)
    lo, hi = fr
    if lo > hi:
        raise ContractError(f"building.json: floors_residential {fr} 의 범위가 뒤집혔다.")
    return tuple(range(lo, hi + 1))


def _plan_for(inputs: Inputs, floor: int) -> FloorPlan:
    """해당 층 도면. 없으면 기준층 1개를 층 번호만 바꿔 재사용한다."""
    exact = [f for f in inputs.floors if f.floor == floor]
    if exact:
        return exact[0]
    if len(inputs.floors) != 1:
        raise ContractError(
            f"{floor}층 도면이 없다. 층별 도면을 모두 주거나, "
            f"기준층 1개만 주고 floors_residential 로 반복시킬 것."
        )
    return replace(inputs.floors[0], floor=floor)


def analyze_floor(inputs: Inputs, floor: int, strategy: str) -> FloorAnalysis:
    fp = _plan_for(inputs, floor)
    grid = gridify(fp, inputs.rules)
    corridor = generate(fp, grid, inputs.rules, inputs.units)
    em = compute_egress(fp, grid, inputs.rules, inputs.building)
    pr = place(grid, corridor, em, inputs.rules, inputs.units, strategy)
    dl = evaluate(fp, inputs.rules, inputs.units, pr)
    commons = collect(grid, em, dl.units, dl.rejected)
    return FloorAnalysis(floor, grid, corridor, em, pr, dl, commons)


def _quantities(inputs: Inputs, floors: tuple[FloorAnalysis, ...], caps: Caps) -> dict:
    """물량만 낸다. 단가는 사용자 입력이다 (설계 [결정 필요] ④)."""
    units = tuple(u for f in floors for u in f.units)
    new_wall = sum(new_wall_length_mm(f.grid, f.units) for f in floors)
    near = sum(1 for u in units if is_shaft_reusable(u, inputs.rules))
    b = inputs.building

    # 부족분은 **평면 상한 전량을 실현할 때** 기준이다. 이 값이 곧 "병목을 풀려면
    # 무엇을 얼마나 보강해야 하는가"가 된다.
    parking_required = (
        round(sum(inputs.rules.parking_coef(inputs.units.by_id(u.type_id).area_m2)
                  for u in units), 1)
        if units else 0.0
    )
    parking = {
        "basis": "평면 상한 세대수 전량 실현 기준",
        "required": parking_required,
        "existing": b.parking_existing,
        "shortfall": (
            round(max(0.0, parking_required - b.parking_existing), 1)
            if b.parking_existing is not None else None
        ),
    }

    septic_required = None
    if caps.by_axis("septic").available and units:
        per_m3 = inputs.rules.septic_units_per_m3()
        septic_required = round(len(units) / per_m3, 2) if per_m3 else None
    septic = {
        "basis": "평면 상한 세대수 전량 실현 기준",
        "required_m3": septic_required,
        "existing_m3": b.septic_capacity_m3,
        "shortfall_m3": (
            round(max(0.0, septic_required - b.septic_capacity_m3), 2)
            if septic_required is not None and b.septic_capacity_m3 is not None
            else None
        ),
    }

    return {
        "units_total": len(units),
        "demo_wall_m": None,  # 기존 내부 벽이 입력 규격에 없어 산출 불가
        "new_wall_m": round(new_wall / 1000, 1),
        "shaft_reuse_ratio": round(near / len(units), 4) if units else 0.0,
        "common_area_m2": round(
            sum(a.area_m2 for f in floors for a in f.commons), 2
        ),
        "parking": parking,
        "septic": septic,
        "_note": "단가는 포함하지 않는다. 물량 × 사용자 입력 단가로 계산할 것.",
    }


def analyze(inputs: Inputs, strategy: str) -> Analysis:
    if strategy not in inputs.units.strategies:
        raise ContractError(
            f"알 수 없는 전략 '{strategy}'. "
            f"사용 가능: {', '.join(inputs.units.strategies)}"
        )
    floors = tuple(
        analyze_floor(inputs, f, strategy) for f in residential_floors(inputs)
    )
    units = tuple(u for f in floors for u in f.units)
    caps = compute_caps(inputs.rules, inputs.units, inputs.building, units)
    grade, reasons = make_verdict(caps, len(floors))
    return Analysis(
        inputs=inputs,
        strategy=strategy,
        floors=floors,
        caps=caps,
        grade=grade,
        reasons=reasons,
        quantities=_quantities(inputs, floors, caps),
    )
