"""⑦ common — 잔여 영역의 공용시설 전환.

창에서 먼 공간을 억지로 주거세대로 만들지 않는다. 배치되지 않았거나 채광·피난에서
탈락한 영역을 사유별로 묶어 공용시설 후보로 넘긴다. 공유주방·세탁실·라운지·창고·
자전거보관소·설비실·택배보관실 등이 여기 들어간다.

사유를 남기는 것이 핵심이다. "왜 여기는 세대가 안 되는가"가 심의 근거가 된다.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass

from .contracts import Rect
from .daylight import RejectedUnit
from .egress import EgressMap
from .grid import CellState, Grid
from .place import PlacedUnit

_NEIGHBORS = ((1, 0), (-1, 0), (0, 1), (0, -1))

#: 사유 우선순위. 여러 사유가 겹치면 위쪽이 이긴다.
REASONS = ("egress_over_limit", "no_window", "daylight_short", "geometry")

REASON_LABEL = {
    "egress_over_limit": "피난 보행거리 초과",
    "no_window": "외벽 창 미접",
    "daylight_short": "채광 창면적 부족",
    "geometry": "유닛 깊이·폭 미달",
}


@dataclass(frozen=True)
class CommonArea:
    bbox_cells: tuple[int, int, int, int]  # (r0, c0, rows, cols)
    bbox_mm: Rect
    cell_count: int
    area_m2: float
    reason: str
    detail: str

    @property
    def label(self) -> str:
        return REASON_LABEL[self.reason]


def _components(
    grid: Grid, cells: set[tuple[int, int]]
) -> list[list[tuple[int, int]]]:
    """4-연결 성분. 스캔 순서가 고정이라 결과가 결정론적이다."""
    seen: set[tuple[int, int]] = set()
    out: list[list[tuple[int, int]]] = []
    for r in range(grid.rows):
        for c in range(grid.cols):
            if (r, c) not in cells or (r, c) in seen:
                continue
            comp = []
            q = deque([(r, c)])
            seen.add((r, c))
            while q:
                cr, cc = q.popleft()
                comp.append((cr, cc))
                for dr, dc in _NEIGHBORS:
                    n = (cr + dr, cc + dc)
                    if n in cells and n not in seen:
                        seen.add(n)
                        q.append(n)
            out.append(comp)
    return out


def _rect_cells(cells: tuple[int, int, int, int]) -> set[tuple[int, int]]:
    r0, c0, rows, cols = cells
    return {(r, c) for r in range(r0, r0 + rows) for c in range(c0, c0 + cols)}


def collect(
    grid: Grid,
    egress: EgressMap,
    units: tuple[PlacedUnit, ...],
    rejected: tuple[RejectedUnit, ...],
) -> tuple[CommonArea, ...]:
    occupied: set[tuple[int, int]] = set()
    for u in units:
        occupied |= _rect_cells(u.cells)

    cell_m2 = (grid.grid_mm / 1000) ** 2
    areas: list[CommonArea] = []

    # 탈락 유닛은 사각형 그대로 내보낸다. 잔여 영역에 흡수시키면 "왜 여기가
    # 세대가 아닌가"라는 사유가 큰 덩어리에 뭉개진다.
    rejected_cells: set[tuple[int, int]] = set()
    for rj in sorted(rejected, key=lambda x: (x.cells[0], x.cells[1])):
        cells = _rect_cells(rj.cells)
        rejected_cells |= cells
        areas.append(
            CommonArea(
                bbox_cells=rj.cells,
                bbox_mm=rj.rect_mm,
                cell_count=len(cells),
                area_m2=round(len(cells) * cell_m2, 2),
                reason=rj.reason,
                detail=rj.detail,
            )
        )

    leftover = {
        (r, c)
        for r in range(grid.rows)
        for c in range(grid.cols)
        if grid.cells[r][c] == CellState.FREE
        and (r, c) not in occupied
        and (r, c) not in rejected_cells
    }

    # 피난 초과 셀은 따로 성분을 만든다. 섞어서 묶으면 통과 셀 하나 때문에
    # 초과 구역 전체가 'geometry' 로 뭉개져 화면에서 사라진다.
    over = {rc for rc in leftover if not egress.ok(*rc)}
    groups = (
        (over, "egress_over_limit", f"한계 {egress.limit_m}m 초과 구역"),
        (leftover - over, "geometry", "유닛이 들어갈 깊이·폭이 나오지 않는다"),
    )

    for cells, reason, detail in groups:
        for comp in _components(grid, cells):
            rows = [r for r, _ in comp]
            cols = [c for _, c in comp]
            r0, c0 = min(rows), min(cols)
            bbox = (r0, c0, max(rows) - r0 + 1, max(cols) - c0 + 1)
            x, y = grid.to_mm(r0, c0)
            areas.append(
                CommonArea(
                    bbox_cells=bbox,
                    bbox_mm=(x, y, bbox[3] * grid.grid_mm, bbox[2] * grid.grid_mm),
                    cell_count=len(comp),
                    area_m2=round(len(comp) * cell_m2, 2),
                    reason=reason,
                    detail=detail,
                )
            )

    areas.sort(key=lambda a: (REASONS.index(a.reason), -a.cell_count, a.bbox_cells))
    return tuple(areas)


def summarize(areas: tuple[CommonArea, ...]) -> dict[str, float]:
    out: dict[str, float] = {}
    for a in areas:
        out[a.reason] = round(out.get(a.reason, 0.0) + a.area_m2, 2)
    return out
