"""③ corridor — 복도 자동 생성과 중복도/편복도 자체 판정.

복도를 먼저 놓는 이유: 피난 보행거리는 실제 통행 경로 위에서 재야 하는데, 복도가
없으면 격자 전체가 뚫린 것처럼 보여 거리가 비현실적으로 짧게 나온다.

사람이 복도를 그려 넣지 않고 규칙으로 생성하는 이유: 이 건물이 왜 중복도가 되는지가
입력자의 감각에 묻히지 않고 결과에 남는다.
"""

from __future__ import annotations

from dataclasses import dataclass

from .contracts import FloorPlan, Rules, Units
from .grid import CellState, Grid

Axis = str  # "h" | "v"
Band = tuple[int, int]  # (lo, hi) inclusive, 축에 수직인 방향의 셀 인덱스


@dataclass(frozen=True)
class CorridorResult:
    type: str  # "double" | "single" | "none"
    axis: Axis
    band: Band
    depth_low_cells: int  # 대표 깊이 (사용 가능 판정에 쓴 값)
    depth_high_cells: int
    need_cells: int
    coverage_low: float
    coverage_high: float

    @property
    def is_double(self) -> bool:
        return self.type == "double"


def _core_bbox_cells(fp: FloorPlan, grid: Grid) -> tuple[int, int, int, int]:
    """모든 코어(stair+ev)를 감싸는 셀 좌표 bbox → (r0, c0, r1, c1)."""
    ox, oy = grid.origin_mm
    g = grid.grid_mm
    rs, cs = [], []
    for core in fp.cores:
        x, y, w, h = core.rect
        cs += [(x - ox) // g, (x + w - 1 - ox) // g]
        rs += [(y - oy) // g, (y + h - 1 - oy) // g]
    return min(rs), min(cs), max(rs), max(cs)


def _pick_axis(fp: FloorPlan, grid: Grid) -> Axis:
    """코어 2개 이상이면 코어들이 벌어진 방향, 1개면 평면 장변 방향."""
    if len(fp.cores) >= 2:
        r0, c0, r1, c1 = _core_bbox_cells(fp, grid)
        return "h" if (c1 - c0) >= (r1 - r0) else "v"
    return "h" if grid.cols >= grid.rows else "v"


def _lane_count(grid: Grid, axis: Axis) -> int:
    return grid.cols if axis == "h" else grid.rows


def _cell(grid: Grid, axis: Axis, lane: int, depth: int) -> CellState:
    """axis='h' 이면 lane=col, depth=row. axis='v' 이면 lane=row, depth=col."""
    return grid.cells[depth][lane] if axis == "h" else grid.cells[lane][depth]

def _set_cell(grid: Grid, axis: Axis, lane: int, depth: int, v: CellState) -> None:
    if axis == "h":
        grid.cells[depth][lane] = v
    else:
        grid.cells[lane][depth] = v


def _depth_extent(grid: Grid, axis: Axis) -> int:
    return grid.rows if axis == "h" else grid.cols


def _side_depths(grid: Grid, axis: Axis, band: Band, side: str) -> list[int]:
    """레인마다 밴드 바깥으로 연속된 FREE 셀 수를 센다."""
    lo, hi = band
    step = -1 if side == "low" else 1
    start = lo - 1 if side == "low" else hi + 1
    extent = _depth_extent(grid, axis)
    out = []
    for lane in range(_lane_count(grid, axis)):
        d = 0
        p = start
        while 0 <= p < extent and _cell(grid, axis, lane, p) == CellState.FREE:
            d += 1
            p += step
        out.append(d)
    return out


def _active_lanes(grid: Grid, axis: Axis, band: Band) -> list[int]:
    """밴드가 평면 안에 걸치는 레인만 판정 대상으로 삼는다 (외부 영역 제외)."""
    lo, hi = band
    lanes = []
    for lane in range(_lane_count(grid, axis)):
        if any(
            _cell(grid, axis, lane, d) != CellState.OUTSIDE
            for d in range(lo, hi + 1)
        ):
            lanes.append(lane)
    return lanes


def _coverage(depths: list[int], lanes: list[int], need: int) -> tuple[float, int]:
    """유닛 깊이를 확보한 레인 비율과 대표 깊이(중앙값)를 돌려준다."""
    if not lanes:
        return 0.0, 0
    vals = [depths[l] for l in lanes]
    ok = sum(1 for v in vals if v >= need)
    vals.sort()
    median = vals[len(vals) // 2]
    return ok / len(vals), median


def _clamp_band(center: int, width: int, extent: int) -> Band:
    lo = center - (width - 1) // 2
    lo = max(0, min(lo, extent - width))
    return lo, lo + width - 1


def generate(fp: FloorPlan, grid: Grid, rules: Rules, units: Units) -> CorridorResult:
    """복도를 생성해 grid 에 CORRIDOR 를 칠하고 판정 결과를 돌려준다."""
    axis = _pick_axis(fp, grid)
    width = rules.corridor_width_cells
    extent = _depth_extent(grid, axis)
    need = units.min_depth_mm // rules.grid_mm
    coverage_min = rules.corridor_side_usable_coverage

    r0, c0, r1, c1 = _core_bbox_cells(fp, grid)
    center = (r0 + r1) // 2 if axis == "h" else (c0 + c1) // 2
    band = _clamp_band(center, width, extent)

    def measure(b: Band) -> tuple[float, int, float, int]:
        lanes = _active_lanes(grid, axis, b)
        cov_lo, d_lo = _coverage(_side_depths(grid, axis, b, "low"), lanes, need)
        cov_hi, d_hi = _coverage(_side_depths(grid, axis, b, "high"), lanes, need)
        return cov_lo, d_lo, cov_hi, d_hi

    cov_lo, d_lo, cov_hi, d_hi = measure(band)
    ok_lo = cov_lo >= coverage_min
    ok_hi = cov_hi >= coverage_min

    # 한쪽만 쓸 수 있으면 편복도. 복도를 못 쓰는 쪽 외벽에 붙여 사용 가능 깊이를 넓힌다.
    if ok_lo != ok_hi:
        band = (0, width - 1) if ok_hi else (extent - width, extent - 1)
        cov_lo, d_lo, cov_hi, d_hi = measure(band)
        ok_lo = cov_lo >= coverage_min
        ok_hi = cov_hi >= coverage_min

    if ok_lo and ok_hi:
        ctype = "double"
    elif ok_lo or ok_hi:
        ctype = "single"
    else:
        ctype = "none"

    lo, hi = band
    for lane in range(_lane_count(grid, axis)):
        for d in range(lo, hi + 1):
            if _cell(grid, axis, lane, d) == CellState.FREE:
                _set_cell(grid, axis, lane, d, CellState.CORRIDOR)

    return CorridorResult(
        type=ctype,
        axis=axis,
        band=band,
        depth_low_cells=d_lo,
        depth_high_cells=d_hi,
        need_cells=need,
        coverage_low=cov_lo,
        coverage_high=cov_hi,
    )
