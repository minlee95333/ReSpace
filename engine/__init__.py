"""Re:Space 엔진 — 비주택 매입 사전판정.

파이프라인 9단계 중 현재 ①load ②gridify ③corridor ④reachability ⑤place 구현.
설계: docs/plans/2026-08-07-lh-respace-design.md
"""

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
from .egress import EgressMap, compute as compute_egress
from .grid import CellState, Grid, gridify
from .place import PlacedUnit, PlacementResult, place

__all__ = [
    "Building",
    "CellState",
    "ContractError",
    "CorridorResult",
    "EgressMap",
    "FloorPlan",
    "Grid",
    "Inputs",
    "PlacedUnit",
    "PlacementResult",
    "Rules",
    "Units",
    "compute_egress",
    "generate_corridor",
    "gridify",
    "load_inputs",
    "place",
]
