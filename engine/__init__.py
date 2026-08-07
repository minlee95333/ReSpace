"""Re:Space 엔진 — 비주택 매입 사전판정.

파이프라인 9단계 전부 구현. ⑧ caps 는 입력이 없는 축을 '미확보'로 보고한다 —
숫자를 지어내지 않으면서 파이프라인은 끝까지 돈다.

    python -m engine.inspect <building_dir>   도면 입력 검사
    python -m engine.report  <building_dir>   result.json + 층별 SVG

설계: docs/plans/2026-08-07-lh-respace-design.md
"""

from .caps import AxisCap, Caps, compute as compute_caps, verdict
from .common import CommonArea, collect as collect_common, summarize
from .contracts import (
    Building,
    ContractError,
    FloorPlan,
    Inputs,
    Rules,
    Units,
    load_inputs,
)
from .corridor import CorridorResult, generate as generate_corridor
from .daylight import DaylightResult, RejectedUnit, evaluate as evaluate_daylight
from .egress import EgressMap, compute as compute_egress
from .emit import build_result, build_svg, write
from .grid import CellState, Grid, gridify
from .pipeline import Analysis, FloorAnalysis, analyze, analyze_floor
from .place import PlacedUnit, PlacementResult, place

__all__ = [
    "Analysis",
    "AxisCap",
    "Building",
    "Caps",
    "CellState",
    "CommonArea",
    "ContractError",
    "CorridorResult",
    "DaylightResult",
    "EgressMap",
    "FloorAnalysis",
    "FloorPlan",
    "Grid",
    "Inputs",
    "PlacedUnit",
    "PlacementResult",
    "RejectedUnit",
    "Rules",
    "Units",
    "analyze",
    "analyze_floor",
    "build_result",
    "build_svg",
    "collect_common",
    "compute_caps",
    "compute_egress",
    "evaluate_daylight",
    "generate_corridor",
    "gridify",
    "load_inputs",
    "place",
    "summarize",
    "verdict",
    "write",
]
