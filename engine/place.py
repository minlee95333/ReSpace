"""⑤ place — 규칙 기반 세대 배치.

"최적화"가 아니라 "규칙 기반 배치"다. 정직하고 방어가 쉬우며, 무엇보다
같은 입력이면 항상 같은 결과가 나온다. 심의 근거로 쓰이려면 이게 전제다.

배치는 복도에 면한 셀부터 채우며, 유닛 깊이는 복도 수직 방향으로 고정한다.
전략별 차이는 어느 후보를 먼저 고르느냐 뿐이다.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass

from .contracts import Rect, Rules, Units, UnitType
from .corridor import CorridorResult
from .egress import EgressMap
from .grid import CellState, Grid

Side = str  # "low" | "high"
_SIDE_RANK = {"high": 0, "low": 1}  # 좌상단 우선 → 복도 위쪽부터
_NEIGHBORS = ((1, 0), (-1, 0), (0, 1), (0, -1))


@dataclass(frozen=True)
class PlacedUnit:
    type_id: str
    cells: tuple[int, int, int, int]  # (r0, c0, rows, cols)
    rect_mm: Rect
    side: Side
    egress_dist_m: float
    shaft_dist_cells: int | None  # 샤프트가 없으면 None
    # ⑥ daylight 가 채운다. 배치 시점에는 None.
    window_len_mm: int | None = None
    daylight_ratio: float | None = None
    depth_from_window_m: float | None = None


@dataclass(frozen=True)
class PlacementResult:
    strategy: str
    units: tuple[PlacedUnit, ...]
    leftover_free_cells: int
    shaft_reuse_ratio: float

    @property
    def count(self) -> int:
        return len(self.units)

    def count_by_type(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for u in self.units:
            out[u.type_id] = out.get(u.type_id, 0) + 1
        return out


def is_shaft_reusable(unit: "PlacedUnit", rules: Rules) -> bool:
    """기존 배관 계통에 붙일 수 있는 세대인가. 샤프트가 없으면 False."""
    d = unit.shaft_dist_cells
    return d is not None and d <= rules.shaft_reuse_threshold_cells


def shaft_distance_field(grid: Grid) -> list[list[int | None]]:
    """샤프트에서의 셀 거리. 설비 재사용률과 저개입형 우선순위에 쓴다.

    배관 경로 근사이므로 코어·기둥을 통과해도 되는 것으로 본다 (외부만 막는다).
    """
    dist: list[list[int | None]] = [[None] * grid.cols for _ in range(grid.rows)]
    q: deque[tuple[int, int]] = deque()
    for r in range(grid.rows):
        for c in range(grid.cols):
            if grid.cells[r][c] == CellState.SHAFT:
                dist[r][c] = 0
                q.append((r, c))
    while q:
        r, c = q.popleft()
        d = dist[r][c]
        for dr, dc in _NEIGHBORS:
            nr, nc = r + dr, c + dc
            if not grid.in_bounds(nr, nc) or dist[nr][nc] is not None:
                continue
            if grid.cells[nr][nc] == CellState.OUTSIDE:
                continue
            dist[nr][nc] = d + 1
            q.append((nr, nc))
    return dist


def _at(grid: Grid, axis: str, lane: int, depth: int) -> CellState:
    return grid.cells[depth][lane] if axis == "h" else grid.cells[lane][depth]


def _outer_limit(
    grid: Grid, corridor: CorridorResult, side: Side, lane: int
) -> int | None:
    """복도 밴드에서 바깥으로 연속된 FREE 구간의 가장 바깥 인덱스.

    유닛을 외벽에 붙이기 위한 기준점이다. 즉시 막혀 있으면 None.
    """
    lo, hi = corridor.band
    extent = grid.rows if corridor.axis == "h" else grid.cols
    step = 1 if side == "high" else -1
    p = (hi + 1) if side == "high" else (lo - 1)
    last = None
    while 0 <= p < extent and _at(grid, corridor.axis, lane, p) == CellState.FREE:
        last = p
        p += step
    return last


def _unit_cells(
    grid: Grid,
    corridor: CorridorResult,
    side: Side,
    lane: int,
    w_cells: int,
    d_cells: int,
) -> tuple[int, int, int, int] | None:
    """(면, 레인) → 외벽에 붙인 유닛 셀 사각형. 깊이는 복도 수직 방향.

    복도가 아니라 **외벽**을 기준으로 붙인다. 그래야 유닛이 창에 면하고,
    복도 쪽에 남는 띠가 창에서 가장 먼 공간이 되어 공용시설 후보로 간다 (설계 4.6절).
    """
    lane_count = grid.cols if corridor.axis == "h" else grid.rows
    if lane + w_cells > lane_count:
        return None
    limits = [
        _outer_limit(grid, corridor, side, j) for j in range(lane, lane + w_cells)
    ]
    if any(v is None for v in limits):
        return None
    # 여러 레인에 걸치므로 가장 얕은 레인에 맞춘다 (보수적).
    anchor = min(limits) if side == "high" else max(limits)
    start = anchor - d_cells + 1 if side == "high" else anchor
    if corridor.axis == "h":
        return start, lane, d_cells, w_cells
    return lane, start, w_cells, d_cells


def _fits(
    grid: Grid,
    egress: EgressMap,
    occupied: set[tuple[int, int]],
    cells: tuple[int, int, int, int],
) -> bool:
    r0, c0, rows, cols = cells
    if r0 < 0 or c0 < 0 or r0 + rows > grid.rows or c0 + cols > grid.cols:
        return False
    for r in range(r0, r0 + rows):
        for c in range(c0, c0 + cols):
            if grid.cells[r][c] != CellState.FREE:
                return False
            if (r, c) in occupied:
                return False
            # 거실의 각 부분이 기준 이내여야 하므로 유닛 전체를 본다 (보수적).
            if not egress.ok(r, c):
                return False
    return True


def _max_egress(egress: EgressMap, cells: tuple[int, int, int, int]) -> float:
    r0, c0, rows, cols = cells
    return max(
        egress.at(r, c) or 0.0
        for r in range(r0, r0 + rows)
        for c in range(c0, c0 + cols)
    )


#: 샤프트가 없거나 도달 불가일 때의 정렬용 대체값. 결과 파일에는 None 으로 나간다.
_FAR = 10**6


def _min_shaft(
    field: list[list[int | None]], cells: tuple[int, int, int, int]
) -> int | None:
    r0, c0, rows, cols = cells
    vals = [
        field[r][c]
        for r in range(r0, r0 + rows)
        for c in range(c0, c0 + cols)
        if field[r][c] is not None
    ]
    return min(vals) if vals else None


def _shaft_key(v: int | None) -> int:
    return _FAR if v is None else v


def place(
    grid: Grid,
    corridor: CorridorResult,
    egress: EgressMap,
    rules: Rules,
    units: Units,
    strategy_id: str,
) -> PlacementResult:
    strategy = units.strategies[strategy_id]
    types = [units.by_id(uid) for uid in strategy.fill_order]
    by_shaft = strategy.priority == "shaft_proximity"
    field = shaft_distance_field(grid)

    # 저개입형은 재사용 범위 밖에는 아예 놓지 않는다. 순서만 바꾸고 놓을 수 있는
    # 자리를 다 채우면 결국 공급우선형과 같은 집합이 되어 '저개입'이 성립하지 않는다.
    reuse_only = strategy.constraint == "shaft_reuse_only"
    max_shaft = rules.shaft_reuse_threshold_cells if reuse_only else None

    lanes = grid.cols if corridor.axis == "h" else grid.rows
    occupied: set[tuple[int, int]] = set()
    placed: list[PlacedUnit] = []
    counts: dict[str, int] = {t.id: 0 for t in types}

    def candidates():
        for side in ("high", "low"):
            for lane in range(lanes):
                for ti, t in enumerate(types):
                    w, d = t.cells(rules.grid_mm)
                    cells = _unit_cells(grid, corridor, side, lane, w, d)
                    if cells is None or not _fits(grid, egress, occupied, cells):
                        continue
                    if max_shaft is not None and _shaft_key(
                        _min_shaft(field, cells)
                    ) > max_shaft:
                        continue
                    yield side, lane, ti, t, cells

    while True:
        best = None
        best_key = None
        for side, lane, ti, t, cells in candidates():
            if by_shaft:
                key = (
                    _shaft_key(_min_shaft(field, cells)),
                    _SIDE_RANK[side], lane, ti,
                )
            else:
                # 균형형은 적게 놓인 유형을 먼저 집어 교대 배치가 되게 한다.
                key = (_SIDE_RANK[side], lane, counts[t.id], ti)
            if best_key is None or key < best_key:
                best_key, best = key, (t, cells, side)
        if best is None:
            break
        t, cells, side = best
        r0, c0, rows, cols = cells
        for r in range(r0, r0 + rows):
            for c in range(c0, c0 + cols):
                occupied.add((r, c))
        x, y = grid.to_mm(r0, c0)
        placed.append(
            PlacedUnit(
                type_id=t.id,
                cells=cells,
                rect_mm=(x, y, cols * grid.grid_mm, rows * grid.grid_mm),
                side=side,
                egress_dist_m=round(_max_egress(egress, cells), 2),
                shaft_dist_cells=_min_shaft(field, cells),
            )
        )
        counts[t.id] += 1

    leftover = grid.count(CellState.FREE) - len(occupied)
    near = sum(1 for u in placed if is_shaft_reusable(u, rules))
    ratio = (near / len(placed)) if placed else 0.0

    return PlacementResult(
        strategy=strategy_id,
        units=tuple(placed),
        leftover_free_cells=leftover,
        shaft_reuse_ratio=round(ratio, 4),
    )


#: 기존 구조체. 이 면에는 이미 벽이 있으므로 신설 물량에서 뺀다.
_EXISTING = (CellState.OUTSIDE, CellState.CORE, CellState.SHAFT, CellState.COLUMN)


def new_wall_length_mm(grid: Grid, units: tuple[PlacedUnit, ...]) -> int:
    """신설해야 하는 세대 구획벽 연장(mm).

    유닛 경계면 중 기존 구조체에 접한 면은 제외한다. 유닛끼리 맞닿은 면은 한 번만 센다.
    단가는 곱하지 않는다 — 시스템은 물량까지만 낸다 (설계 [결정 필요] ④).
    """
    owner: dict[tuple[int, int], int] = {}
    for i, u in enumerate(units):
        r0, c0, rows, cols = u.cells
        for r in range(r0, r0 + rows):
            for c in range(c0, c0 + cols):
                owner[(r, c)] = i

    faces: set[frozenset[tuple[int, int]]] = set()
    for (r, c), i in owner.items():
        for dr, dc in _NEIGHBORS:
            n = (r + dr, c + dc)
            if owner.get(n) == i:
                continue  # 같은 유닛 내부
            if not grid.in_bounds(*n):
                continue  # 격자 밖 = 외벽
            if grid.cells[n[0]][n[1]] in _EXISTING:
                continue  # 기존 벽을 그대로 쓴다
            faces.add(frozenset(((r, c), n)))
    return len(faces) * grid.grid_mm
