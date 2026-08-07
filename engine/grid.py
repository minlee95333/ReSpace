"""② gridify — 600mm 격자화.

셀 점유는 보수적으로 처리한다. 기둥·코어·샤프트가 셀에 조금이라도 걸치면 그 셀
전체를 해당 상태로 본다. 반대로 하면 실제로는 놓을 수 없는 자리에 유닛이 놓여
세대수가 과대 산정된다.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum

from .contracts import FloorPlan, Point, Rect, Rules


class CellState(IntEnum):
    OUTSIDE = 0
    FREE = 1
    COLUMN = 2
    SHAFT = 3
    CORE = 4
    CORRIDOR = 5


#: 장애물 스탬프 우선순위. 값이 큰 쪽이 이긴다.
_STAMP_PRECEDENCE = (CellState.COLUMN, CellState.SHAFT, CellState.CORE)

BLOCKED = (CellState.OUTSIDE, CellState.COLUMN, CellState.SHAFT, CellState.CORE)


def _point_in_polygon(x: float, y: float, poly: tuple[Point, ...]) -> bool:
    """Ray casting. 셀 중심점으로 판정하므로 경계 위 점은 발생하지 않는다."""
    inside = False
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        if (y1 > y) != (y2 > y):
            xin = (x2 - x1) * (y - y1) / (y2 - y1) + x1
            if x < xin:
                inside = not inside
    return inside


@dataclass
class Grid:
    cols: int
    rows: int
    origin_mm: Point
    grid_mm: int
    cells: list[list[CellState]]  # cells[row][col]

    def __getitem__(self, rc: tuple[int, int]) -> CellState:
        r, c = rc
        return self.cells[r][c]

    def __setitem__(self, rc: tuple[int, int], v: CellState) -> None:
        r, c = rc
        self.cells[r][c] = v

    def in_bounds(self, r: int, c: int) -> bool:
        return 0 <= r < self.rows and 0 <= c < self.cols

    def is_free(self, r: int, c: int) -> bool:
        return self.in_bounds(r, c) and self.cells[r][c] == CellState.FREE

    def count(self, state: CellState) -> int:
        return sum(row.count(state) for row in self.cells)

    def cell_rect_mm(self, r: int, c: int) -> Rect:
        ox, oy = self.origin_mm
        g = self.grid_mm
        return (ox + c * g, oy + r * g, g, g)

    def to_mm(self, r: int, c: int) -> Point:
        """셀 좌하단 좌표."""
        ox, oy = self.origin_mm
        return ox + c * self.grid_mm, oy + r * self.grid_mm

    def stamp_rect(self, rect: Rect, state: CellState) -> int:
        """rect 에 조금이라도 걸치는 셀을 state 로 칠한다. 칠한 셀 수를 반환."""
        x, y, w, h = rect
        ox, oy = self.origin_mm
        g = self.grid_mm
        c0 = max(0, (x - ox) // g)
        c1 = min(self.cols - 1, (x + w - 1 - ox) // g)
        r0 = max(0, (y - oy) // g)
        r1 = min(self.rows - 1, (y + h - 1 - oy) // g)
        n = 0
        for r in range(r0, r1 + 1):
            for c in range(c0, c1 + 1):
                cur = self.cells[r][c]
                if cur == CellState.OUTSIDE:
                    continue
                if _STAMP_PRECEDENCE.index(state) >= (
                    _STAMP_PRECEDENCE.index(cur) if cur in _STAMP_PRECEDENCE else -1
                ):
                    self.cells[r][c] = state
                    n += 1
        return n


def gridify(fp: FloorPlan, rules: Rules) -> Grid:
    g = rules.grid_mm
    min_x, min_y, max_x, max_y = fp.bbox_mm
    cols = (max_x - min_x) // g
    rows = (max_y - min_y) // g

    grid = Grid(
        cols=cols,
        rows=rows,
        origin_mm=(min_x, min_y),
        grid_mm=g,
        cells=[[CellState.OUTSIDE] * cols for _ in range(rows)],
    )

    half = g / 2
    for r in range(rows):
        cy = min_y + r * g + half
        for c in range(cols):
            cx = min_x + c * g + half
            if _point_in_polygon(cx, cy, fp.boundary):
                grid.cells[r][c] = CellState.FREE

    for rect in fp.columns:
        grid.stamp_rect(rect, CellState.COLUMN)
    for rect in fp.shafts:
        grid.stamp_rect(rect, CellState.SHAFT)
    for core in fp.cores:
        grid.stamp_rect(core.rect, CellState.CORE)

    return grid


def shaft_cells(fp: FloorPlan, grid: Grid) -> list[tuple[int, int]]:
    """설비 재사용률 계산의 기준점. 저개입형 배치에서 쓴다."""
    out = []
    for r in range(grid.rows):
        for c in range(grid.cols):
            if grid.cells[r][c] == CellState.SHAFT:
                out.append((r, c))
    return out
