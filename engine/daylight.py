"""⑥ daylight — 창면적비 판정.

법정 기준은 거실 바닥면적의 1/10 이상 개구부다. 유닛이 놓여야 바닥면적이 정해지므로
사후 판정이며, 배치(⑤)가 유닛을 외벽에 붙여 놓은 뒤에 돈다.

거리 기반 판정(창에서 몇 m까지)은 법정 요건이 아니다. `depth_from_window_m` 으로
기록만 하고 판정에는 쓰지 않는다 — 법정 요건과 거주 품질을 분리해서 본다.

실제로 걸리는 것은 비율이 아니라 **창 접면이 0 인 유닛**이다. 청년형 18㎡ 는 창높이
1.5m 기준 1.2m, 신혼형 28.8㎡ 는 1.92m 의 창 길이면 통과하므로, 외벽에 면하기만 하면
대개 넘는다.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from .contracts import ContractError, FloorPlan, Rect, Rules, Units, Window
from .place import PlacedUnit, PlacementResult


@dataclass(frozen=True)
class RejectedUnit:
    cells: tuple[int, int, int, int]
    rect_mm: Rect
    reason: str  # "no_window" | "daylight_short"
    detail: str


@dataclass(frozen=True)
class DaylightResult:
    units: tuple[PlacedUnit, ...]
    rejected: tuple[RejectedUnit, ...]

    @property
    def kept(self) -> int:
        return len(self.units)


def _overlap(a0: int, a1: int, b0: int, b1: int) -> int:
    return max(0, min(a1, b1) - max(a0, b0))


def _segment_on_rect(win: Window, rect: Rect) -> int:
    """창 구간이 유닛 사각형의 변 위에 놓인 길이(mm).

    축 정렬 창만 지원한다. 대각선 창은 조용히 0 을 돌려주면 유닛이 부당하게
    탈락하므로 명시적으로 실패시킨다.
    """
    (x1, y1), (x2, y2) = win.start, win.end
    ux, uy, uw, uh = rect

    if x1 == x2:  # 수직 창
        if x1 not in (ux, ux + uw):
            return 0
        lo, hi = sorted((y1, y2))
        return _overlap(lo, hi, uy, uy + uh)

    if y1 == y2:  # 수평 창
        if y1 not in (uy, uy + uh):
            return 0
        lo, hi = sorted((x1, x2))
        return _overlap(lo, hi, ux, ux + uw)

    raise ContractError(
        f"windows: 대각선 창 구간은 지원하지 않는다 "
        f"({win.start} → {win.end}). 축 정렬 구간으로 나눠 입력할 것."
    )


def window_length_mm(fp: FloorPlan, rect: Rect) -> int:
    return sum(_segment_on_rect(w, rect) for w in fp.windows)


def _window_height_mm(fp: FloorPlan, rect: Rect) -> int:
    """유닛에 접한 창들 중 가장 낮은 창 높이. 여러 창이 걸치면 보수적으로 본다."""
    hs = [w.height for w in fp.windows if _segment_on_rect(w, rect) > 0]
    return min(hs) if hs else 0


def _depth_from_window_mm(fp: FloorPlan, rect: Rect) -> int:
    """창에 면한 변에서 유닛 최심부까지. 거주성 보조지표(법정 요건 아님)."""
    ux, uy, uw, uh = rect
    for w in fp.windows:
        if _segment_on_rect(w, rect) <= 0:
            continue
        (x1, y1), (x2, y2) = w.start, w.end
        if x1 == x2:
            return uw
        return uh
    return 0


def evaluate(
    fp: FloorPlan, rules: Rules, units: Units, placement: PlacementResult
) -> DaylightResult:
    kept: list[PlacedUnit] = []
    rejected: list[RejectedUnit] = []

    for u in placement.units:
        length = window_length_mm(fp, u.rect_mm)
        if length == 0:
            rejected.append(
                RejectedUnit(
                    u.cells, u.rect_mm, "no_window",
                    "외벽 창에 접하지 않는다",
                )
            )
            continue

        height = _window_height_mm(fp, u.rect_mm)
        window_area = length * height / 1_000_000
        area = units.by_id(u.type_id).area_m2
        required = area * rules.daylight_area_ratio
        ratio = window_area / area

        if window_area + 1e-9 < required:
            rejected.append(
                RejectedUnit(
                    u.cells, u.rect_mm, "daylight_short",
                    f"창면적 {window_area:.2f}㎡ < 필요 {required:.2f}㎡ "
                    f"(바닥 {area}㎡의 1/10)",
                )
            )
            continue

        kept.append(
            replace(
                u,
                window_len_mm=length,
                daylight_ratio=round(ratio, 4),
                depth_from_window_m=round(_depth_from_window_mm(fp, u.rect_mm) / 1000, 2),
            )
        )

    return DaylightResult(tuple(kept), tuple(rejected))
