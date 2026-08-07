"""자립형 HTML 대시보드 생성.

데이터를 HTML 안에 심는다. `fetch()` 는 `file://` 에서 CORS 로 막히므로, 별도 파일을
읽는 방식은 비개발자가 더블클릭으로 열 수 없다. 심어두면 파일 하나가 그대로
공개 링크이자 PT 시연 화면이 된다.

UI 는 `dashboard/template.html` 에 있다. 여기서는 데이터만 만들어 끼운다 —
계산은 엔진에, 표현은 템플릿에.
"""

from __future__ import annotations

import json
from pathlib import Path

from .caps import AXIS_LABEL
from .emit import build_result, build_svg
from .pipeline import Analysis

#: 신뢰도가 낮은 순. 여러 층의 출처가 섞이면 가장 약한 쪽으로 표시한다.
PLAN_ORDER = ("placeholder", "synthetic", "reconstructed", "survey")

MARKER = "<!--RESPACE_DATA-->"
TEMPLATE = Path(__file__).resolve().parent.parent / "dashboard" / "template.html"


def _strategy_payload(analysis: Analysis) -> dict:
    r = build_result(analysis)
    mix: dict[str, int] = {}
    for u in analysis.units:
        label = analysis.inputs.units.by_id(u.type_id).label
        mix[label] = mix.get(label, 0) + 1
    return {
        "label": r["meta"]["strategy_label"],
        "caps": r["caps"],
        "quantities": r["quantities"],
        "verdict": r["verdict"],
        "per_floor": r["per_floor"],
        "input_hash": r["meta"]["input_hash"],
        "mix": mix,
        "rejected_total": sum(len(f["rejected"]) for f in r["per_floor"]),
        "svgs": {
            f.floor: build_svg(
                f, f"{analysis.inputs.building.name} · {f.floor}층 · "
                   f"{r['meta']['strategy_label']}"
            )
            for f in analysis.floors
        },
    }


def _building_payload(
    analyses: dict[str, Analysis], recommended: str, reasons: tuple[str, ...]
) -> dict:
    any_a = next(iter(analyses.values()))
    b = any_a.inputs.building
    plans = any_a.inputs.floors
    # 가장 약한 출처를 대표로 삼는다. 한 층이라도 예시 형상이면 그 건물의 결과는
    # 사례 대조에 쓸 수 없다.
    weakest = min(plans, key=lambda f: PLAN_ORDER.index(f.status))
    return {
        "name": b.name,
        "use": b.use,
        "floors_total": b.floors_total,
        "floors_analyzed": [f.floor for f in any_a.floors],
        "source_note": b.source_note,
        "plan_status": weakest.status,
        "plan_status_label": weakest.status_label,
        "trustworthy": weakest.is_trustworthy,
        "recommended": recommended,
        "recommend_reasons": list(reasons),
        "strategies": {k: _strategy_payload(a) for k, a in analyses.items()},
    }


def build_payload(buildings: list[dict], rules_version: str, grid_mm: int,
                  generated_at: str | None) -> dict:
    return {
        "generated_at": generated_at,
        "rules_version": rules_version,
        "grid_mm": grid_mm,
        "axis_labels": AXIS_LABEL,
        "buildings": buildings,
        "disclaimer": (
            "본 결과는 매입 전 사전검토를 위한 개략분석이며, 구조·소방·인허가 "
            "관련 사항은 전문가의 현장조사와 정밀검토가 필요합니다."
        ),
    }


def render(payload: dict) -> str:
    html = TEMPLATE.read_text(encoding="utf-8")
    if MARKER not in html:
        raise RuntimeError(f"{TEMPLATE}: {MARKER} 자리표시자가 없다.")
    data = json.dumps(payload, ensure_ascii=False)
    # </script> 가 데이터 안에 있으면 스크립트 블록이 조기 종료된다.
    data = data.replace("</", "<\\/")
    return html.replace(
        MARKER, f"<script>window.__RESPACE__ = {data};</script>"
    )


def write(payload: dict, out_path: str | Path) -> Path:
    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(render(payload), encoding="utf-8")
    return p
