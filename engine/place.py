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
    shaft_dist_cells: int


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


def _unit_cells(
    corridor: CorridorResult, side: Side, lane: int, w_cells: int, d_cells: int
) -> tuple[int, int, int, int]:
    """(축, 면, 레인) → (r0, c0, rows, cols). 깊이는 복도 수직 방향."""
    lo, hi = corridor.band
    if corridor.axis == "h":
        r0 = hi + 1 if side == "high" else lo - d_cells
        return r0, lane, d_cells, w_cells
    c0 = hi + 1 if side == "high" else lo - d_cells
    return lane, c0, w_cells, d_cells


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


def _min_shaft(field: list[list[int | None]], cells: tuple[int, int, int, int]) -> int:
    r0, c0, rows, cols = cells
    vals = [
        field[r][c]
        for r in range(r0, r0 + rows)
        for c in range(c0, c0 + cols)
        if field[r][c] is not None
    ]
    return min(vals) if vals else 10**6


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
                    cells = _unit_cells(corridor, side, lane, w, d)
                    if not _fits(grid, egress, occupied, cells):
                        continue
                    if max_shaft is not None and _min_shaft(field, cells) > max_shaft:
                        continue
                    yield side, lane, ti, t, cells

    while True:
        best = None
        best_key = None
        for side, lane, ti, t, cells in candidates():
            if by_shaft:
                key = (_min_shaft(field, cells), _SIDE_RANK[side], lane, ti)
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
    near = sum(
        1 for u in placed if u.shaft_dist_cells <= rules.shaft_reuse_threshold_cells
    )
    ratio = (near / len(placed)) if placed else 0.0

    return PlacementResult(
        strategy=strategy_id,
        units=tuple(placed),
        leftover_free_cells=leftover,
        shaft_reuse_ratio=round(ratio, 4),
    )
