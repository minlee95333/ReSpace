"""⑨ emit — result.json 과 도면 SVG.

엔진이 SVG 까지 그리는 이유: 계산 결과와 그림이 어긋날 수 없고, 사람이 숫자를
화면으로 옮겨 적는 단계가 사라진다. 대시보드는 이 두 파일만 읽는다.

`generated_at` 은 호출자가 넘긴다. 엔진이 시계를 읽으면 같은 입력에 같은 출력이라는
전제가 깨져 회귀 비교를 할 수 없다.
"""

from __future__ import annotations

import json
from pathlib import Path

from .caps import AXIS_LABEL
from .common import REASON_LABEL
from .grid import CellState
from .pipeline import Analysis, FloorAnalysis

PX_PER_MM = 0.02  # 36000mm → 720px

FILL = {
    "youth": "#4a7fb5",
    "newlywed": "#7b5ea7",
    "corridor": "#d8d8d8",
    "core": "#4a4a4a",
    "shaft": "#8a8a8a",
    "column": "#2a2a2a",
    "boundary": "#1a1a1a",
}

REASON_FILL = {
    "egress_over_limit": "#c94c4c",
    "no_window": "#d9a441",
    "daylight_short": "#e0c46a",
    "geometry": "#eeeeee",
}


# ---------------------------------------------------------------- result.json


def _unit_dict(u) -> dict:
    return {
        "type": u.type_id,
        "rect_mm": list(u.rect_mm),
        "side": u.side,
        "egress_dist_m": u.egress_dist_m,
        "shaft_dist_cells": u.shaft_dist_cells,
        "window_len_mm": u.window_len_mm,
        "daylight_ratio": u.daylight_ratio,
        "depth_from_window_m": u.depth_from_window_m,
    }


def _floor_dict(f: FloorAnalysis) -> dict:
    return {
        "floor": f.floor,
        "corridor_type": f.corridor.type,
        "corridor_axis": f.corridor.axis,
        "free_m2": f.free_m2,
        "egress": {
            "limit_m": f.egress.limit_m,
            "all_cores": f.egress.all_cores,
            "stair_count": f.egress.stair_count,
            "over_limit_cells": f.egress.over_limit_cells,
        },
        "units": [_unit_dict(u) for u in f.units],
        "rejected": [
            {
                "rect_mm": list(r.rect_mm),
                "reason": r.reason,
                "reason_label": REASON_LABEL[r.reason],
                "detail": r.detail,
            }
            for r in f.daylight.rejected
        ],
        "common_areas": [
            {
                "bbox_mm": list(a.bbox_mm),
                "area_m2": a.area_m2,
                "reason": a.reason,
                "reason_label": a.label,
                "detail": a.detail,
            }
            for a in f.commons
        ],
    }


def build_result(analysis: Analysis, generated_at: str | None = None) -> dict:
    inp = analysis.inputs
    grid = analysis.floors[0].grid if analysis.floors else None
    return {
        "meta": {
            "generated_at": generated_at,
            "rules_version": inp.rules.version,
            "strategy": analysis.strategy,
            "strategy_label": inp.units.strategies[analysis.strategy].label,
            "building": inp.building.name,
            "source_note": inp.building.source_note,
            "input_hash": dict(sorted(inp.input_hash.items())),
            "grid_mm": inp.rules.grid_mm,
            "grid_origin_mm": list(grid.origin_mm) if grid else None,
            "floors_analyzed": [f.floor for f in analysis.floors],
        },
        "per_floor": [_floor_dict(f) for f in analysis.floors],
        "caps": {
            "axes": [
                {
                    "axis": a.axis,
                    "label": AXIS_LABEL[a.axis],
                    "value": a.value,
                    "basis": a.basis,
                    "blocked_reason": a.blocked_reason,
                }
                for a in analysis.caps.axes
            ],
            "supply": analysis.caps.supply,
            "bottleneck": analysis.caps.bottleneck,
            "bottleneck_label": AXIS_LABEL[analysis.caps.bottleneck],
            "complete": analysis.caps.complete,
            "note": analysis.caps.note,
        },
        "quantities": analysis.quantities,
        "verdict": {"grade": analysis.grade, "reasons": list(analysis.reasons)},
        "disclaimer": (
            "본 결과는 매입 전 사전검토를 위한 개략분석이며, 구조·소방·인허가 "
            "관련 사항은 전문가의 현장조사와 정밀검토가 필요합니다."
        ),
    }


# ---------------------------------------------------------------- SVG


def _rect(x, y, w, h, fill, stroke=None, sw=0.5, opacity=None) -> str:
    parts = [f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}"',
             f'fill="{fill}"']
    if stroke:
        parts.append(f'stroke="{stroke}" stroke-width="{sw}"')
    if opacity is not None:
        parts.append(f'fill-opacity="{opacity}"')
    return " ".join(parts) + "/>"


def build_svg(f: FloorAnalysis, title: str) -> str:
    grid = f.grid
    ox, oy = grid.origin_mm
    w_mm = grid.cols * grid.grid_mm
    h_mm = grid.rows * grid.grid_mm
    W, H = w_mm * PX_PER_MM, h_mm * PX_PER_MM
    pad, header = 16, 34

    def px(x_mm, y_mm):
        """도면 좌표 → 화면 좌표. y 를 뒤집어 위쪽이 +y 가 되게 한다."""
        return (x_mm - ox) * PX_PER_MM + pad, (h_mm - (y_mm - oy)) * PX_PER_MM + header

    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{W + pad * 2:.0f}" height="{H + header + pad * 2:.0f}" '
        f'viewBox="0 0 {W + pad * 2:.0f} {H + header + pad * 2:.0f}" '
        f'font-family="sans-serif">',
        f'<rect width="100%" height="100%" fill="#ffffff"/>',
        f'<text x="{pad}" y="20" font-size="13" fill="#1a1a1a">{title}</text>',
    ]

    # 셀 단위 배경 (복도·코어·샤프트·기둥)
    state_fill = {
        CellState.CORRIDOR: FILL["corridor"],
        CellState.CORE: FILL["core"],
        CellState.SHAFT: FILL["shaft"],
        CellState.COLUMN: FILL["column"],
    }
    for r in range(grid.rows):
        for c in range(grid.cols):
            fill = state_fill.get(grid.cells[r][c])
            if not fill:
                continue
            x_mm, y_mm = grid.to_mm(r, c)
            x, y = px(x_mm, y_mm + grid.grid_mm)
            s = grid.grid_mm * PX_PER_MM
            out.append(_rect(x, y, s, s, fill))

    # 공용 전환 영역 (사유별)
    for a in f.commons:
        x_mm, y_mm, aw, ah = a.bbox_mm
        x, y = px(x_mm, y_mm + ah)
        out.append(
            _rect(x, y, aw * PX_PER_MM, ah * PX_PER_MM,
                  REASON_FILL[a.reason], "#bbbbbb", 0.4, 0.55)
        )

    # 배치 유닛
    for u in f.units:
        x_mm, y_mm, uw, uh = u.rect_mm
        x, y = px(x_mm, y_mm + uh)
        out.append(
            _rect(x, y, uw * PX_PER_MM, uh * PX_PER_MM,
                  FILL[u.type_id], "#ffffff", 0.8)
        )

    # 외벽
    out.append(_rect(pad, header, W, H, "none", FILL["boundary"], 1.2))

    counts: dict[str, int] = {}
    for u in f.units:
        counts[u.type_id] = counts.get(u.type_id, 0) + 1
    legend = " · ".join(f"{k} {v}" for k, v in sorted(counts.items())) or "세대 없음"
    out.append(
        f'<text x="{pad}" y="{H + header + 12:.0f}" font-size="10" fill="#555555">'
        f'{legend} · 복도 {f.corridor.type} · 피난한계 {f.egress.limit_m}m</text>'
    )
    out.append("</svg>")
    return "\n".join(out)


# ---------------------------------------------------------------- 쓰기


def write(analysis: Analysis, out_dir: str | Path, generated_at: str | None = None):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    result_path = out / "result.json"
    result_path.write_text(
        json.dumps(build_result(analysis, generated_at), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    written = [result_path]
    label = analysis.inputs.units.strategies[analysis.strategy].label
    for f in analysis.floors:
        p = out / f"floor_{f.floor:02d}.svg"
        p.write_text(
            build_svg(f, f"{analysis.inputs.building.name} · {f.floor}층 · {label}"),
            encoding="utf-8",
        )
        written.append(p)
    return written
