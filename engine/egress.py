"""④ reachability — 피난 보행거리 격자 BFS.

복도가 놓인 뒤에 돈다. 복도 없이 재면 격자 전체가 뚫린 것처럼 보여 거리가
비현실적으로 짧게 나온다.

출발점은 `stair` 코어만이다. EV 는 피난 수단이 아니다.

rules.egress.all_cores 스위치:
  True  — 셀 판정이 max(각 계단까지 거리) <= 한계.
          "직통계단 2개소 이상이면 모두 기준 충족"의 직역이며,
          이 해석에서는 계단 2개인 건물이 1개인 건물보다 불리해진다.
  False — min(...) <= 한계. 가장 가까운 계단 하나만 보면 된다.
두 값의 결과 차이가 층당 세대수를 좌우하므로 양쪽을 돌려 비교한다.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass

from .contracts import Building, Core, FloorPlan, Rules
from .grid import CellState, Grid

TRAVERSABLE = (CellState.FREE, CellState.CORRIDOR)
_NEIGHBORS = ((1, 0), (-1, 0), (0, 1), (0, -1))


@dataclass(frozen=True)
class EgressMap:
    dist_m: tuple[tuple[float | None, ...], ...]  # [row][col], None = 도달 불가
    limit_m: float
    all_cores: bool
    stair_count: int
    reachable_cells: int
    over_limit_cells: int

    def ok(self, r: int, c: int) -> bool:
        d = self.dist_m[r][c]
        return d is not None and d <= self.limit_m + 1e-9

    def at(self, r: int, c: int) -> float | None:
        return self.dist_m[r][c]


def _core_seed_cells(core: Core, grid: Grid) -> list[tuple[int, int]]:
    ox, oy = grid.origin_mm
    g = grid.grid_mm
    x, y, w, h = core.rect
    c0, c1 = (x - ox) // g, (x + w - 1 - ox) // g
    r0, r1 = (y - oy) // g, (y + h - 1 - oy) // g
    return [
        (r, c)
        for r in range(max(0, r0), min(grid.rows - 1, r1) + 1)
        for c in range(max(0, c0), min(grid.cols - 1, c1) + 1)
    ]


def _bfs(grid: Grid, seeds: list[tuple[int, int]]) -> list[list[int | None]]:
    """셀 단위 최단 보행 거리. 코어 셀은 0, 통행 가능 셀만 확장한다."""
    dist: list[list[int | None]] = [[None] * grid.cols for _ in range(grid.rows)]
    q: deque[tuple[int, int]] = deque()
    for r, c in seeds:
        if dist[r][c] is None:
            dist[r][c] = 0
            q.append((r, c))
    while q:
        r, c = q.popleft()
        d = dist[r][c]
        for dr, dc in _NEIGHBORS:
            nr, nc = r + dr, c + dc
            if not grid.in_bounds(nr, nc) or dist[nr][nc] is not None:
                continue
            if grid.cells[nr][nc] not in TRAVERSABLE:
                continue
            dist[nr][nc] = d + 1
            q.append((nr, nc))
    return dist


def compute(fp: FloorPlan, grid: Grid, rules: Rules, building: Building) -> EgressMap:
    stairs = fp.stair_cores()
    limit = rules.egress.limit_m(
        fire_resistant=building.fire_resistant,
        floor=fp.floor,
        floors_total=building.floors_total,
    )
    g_m = grid.grid_mm / 1000.0

    if not stairs:
        empty = tuple(tuple([None] * grid.cols) for _ in range(grid.rows))
        return EgressMap(empty, limit, rules.egress.all_cores, 0, 0, 0)

    maps = [_bfs(grid, _core_seed_cells(s, grid)) for s in stairs]

    combine = max if rules.egress.all_cores else min
    out: list[tuple[float | None, ...]] = []
    reachable = over = 0
    for r in range(grid.rows):
        row: list[float | None] = []
        for c in range(grid.cols):
            if grid.cells[r][c] not in TRAVERSABLE:
                row.append(None)
                continue
            vals = [m[r][c] for m in maps]
            if any(v is None for v in vals):
                # 한 계단이라도 도달 못 하면 all_cores 에서는 실격,
                # 아니면 도달 가능한 계단만으로 판정한다.
                if rules.egress.all_cores:
                    row.append(None)
                    continue
                vals = [v for v in vals if v is not None]
                if not vals:
                    row.append(None)
                    continue
            d = combine(vals) * g_m
            row.append(d)
            reachable += 1
            if d > limit + 1e-9:
                over += 1
        out.append(tuple(row))

    return EgressMap(
        dist_m=tuple(out),
        limit_m=limit,
        all_cores=rules.egress.all_cores,
        stair_count=len(stairs),
        reachable_cells=reachable,
        over_limit_cells=over,
    )
