"""Re:Space 엔진 — 비주택 매입 사전판정.

파이프라인 9단계 중 ①load ②gridify ③corridor ④reachability ⑤place
⑥daylight ⑦common 구현. 남은 것은 ⑧caps ⑨emit.
설계: docs/plans/2026-08-07-lh-respace-design.md
"""

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
from .grid import CellState, Grid, gridify
from .place import PlacedUnit, PlacementResult, place

__all__ = [
    "Building",
    "CellState",
    "CommonArea",
    "ContractError",
    "CorridorResult",
    "DaylightResult",
    "EgressMap",
    "FloorPlan",
    "Grid",
    "Inputs",
    "PlacedUnit",
    "PlacementResult",
    "RejectedUnit",
    "Rules",
    "Units",
    "collect_common",
    "compute_egress",
    "evaluate_daylight",
    "generate_corridor",
    "gridify",
    "load_inputs",
    "place",
    "summarize",
]
