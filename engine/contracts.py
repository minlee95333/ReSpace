"""① load — 입력 계약 로딩과 검증.

밑줄로 시작하는 키는 사람이 읽는 주석이므로 로딩 시 제거한다 (data/*.json 규약).
격자 정합 위반은 조용히 반올림하지 않고 즉시 실패시킨다. 반올림하면 면적이
말없이 줄어들어 세대수가 틀어지는데, 그 원인을 나중에 추적할 수 없다.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

Rect = tuple[int, int, int, int]  # (x, y, w, h) mm
Point = tuple[int, int]  # (x, y) mm


class ContractError(ValueError):
    """입력 계약 위반. 메시지에 위반 위치와 값을 담는다."""


# ---------------------------------------------------------------- 원시 로딩


def _strip_comments(obj):
    """밑줄로 시작하는 키를 재귀적으로 제거한다."""
    if isinstance(obj, dict):
        return {k: _strip_comments(v) for k, v in obj.items() if not k.startswith("_")}
    if isinstance(obj, list):
        return [_strip_comments(v) for v in obj]
    return obj


def load_json(path: str | Path) -> dict:
    path = Path(path)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ContractError(f"{path}: JSON 파싱 실패 — {e}") from e
    return _strip_comments(raw)


def sha256(path: str | Path) -> str:
    return "sha256:" + hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _require(d: dict, key: str, where: str):
    if key not in d:
        raise ContractError(f"{where}: 필수 항목 '{key}' 누락")
    return d[key]


def _check_grid(values, grid_mm: int, where: str):
    bad = [v for v in values if v % grid_mm]
    if bad:
        raise ContractError(
            f"{where}: 격자({grid_mm}mm) 정합 위반 {bad}. "
            f"좌표는 {grid_mm} 의 정수 배여야 한다."
        )


# ---------------------------------------------------------------- rules


@dataclass(frozen=True)
class Egress:
    base_m: float
    fire_resistant_m: float
    highrise_m: float
    highrise_from_floor: int
    all_cores: bool

    def limit_m(self, *, fire_resistant: bool, floor: int, floors_total: int) -> float:
        if floors_total >= self.highrise_from_floor and floor >= self.highrise_from_floor:
            return self.highrise_m
        if fire_resistant:
            return self.fire_resistant_m
        return self.base_m


@dataclass(frozen=True)
class Rules:
    version: str
    grid_mm: int
    corridor_width_mm: int
    corridor_side_usable_coverage: float
    ceiling_min_mm: int
    daylight_area_ratio: float
    egress: Egress
    parking_bands: tuple[tuple[float, bool, float], ...]  # (max_area, inclusive, coef)
    parking_default_coef: float
    septic_persons_per_unit: float | None
    septic_load_lpcd: float | None

    @property
    def corridor_width_cells(self) -> int:
        return self.corridor_width_mm // self.grid_mm

    def parking_coef(self, area_m2: float) -> float:
        """전용면적 → 주차 계수. '30㎡ 미만'은 strict, '60㎡ 이하'는 inclusive."""
        for max_area, inclusive, coef in self.parking_bands:
            if (area_m2 <= max_area) if inclusive else (area_m2 < max_area):
                return coef
        return self.parking_default_coef

    def septic_units_per_m3(self) -> float:
        if self.septic_persons_per_unit is None or self.septic_load_lpcd is None:
            raise ContractError(
                "rules.septic 파라미터가 미확정(null)이다. "
                "하수도법 시행령 별표 확인 필요 (PROGRESS.md 미결정 ⑤). "
                "기본값을 임의로 넣으면 틀린 수치가 제안서까지 흘러간다."
            )
        return 1.0 / (self.septic_persons_per_unit * self.septic_load_lpcd / 1000.0)

    @staticmethod
    def from_dict(d: dict) -> "Rules":
        w = "rules.json"
        grid = int(_require(d, "grid_mm", w))
        corridor = int(_require(d, "corridor_width_mm", w))
        if corridor % grid:
            raise ContractError(
                f"{w}: corridor_width_mm({corridor}) 가 grid_mm({grid}) 의 배수가 아니다."
            )
        eg = _require(d, "egress", w)
        pk = _require(d, "parking", w)
        sp = _require(d, "septic", w)
        return Rules(
            version=str(_require(d, "version", w)),
            grid_mm=grid,
            corridor_width_mm=corridor,
            corridor_side_usable_coverage=float(
                _require(d, "corridor_side_usable_coverage", w)
            ),
            ceiling_min_mm=int(_require(d, "ceiling_min_mm", w)),
            daylight_area_ratio=float(_require(d, "daylight", w)["area_ratio"]),
            egress=Egress(
                base_m=float(eg["base_m"]),
                fire_resistant_m=float(eg["fire_resistant_m"]),
                highrise_m=float(eg["highrise_m"]),
                highrise_from_floor=int(eg["highrise_from_floor"]),
                all_cores=bool(eg["all_cores"]),
            ),
            parking_bands=tuple(
                (float(b["max_area_m2"]), bool(b["inclusive"]), float(b["coef"]))
                for b in pk["bands"]
            ),
            parking_default_coef=float(pk["default_coef"]),
            septic_persons_per_unit=sp["persons_per_unit"],
            septic_load_lpcd=sp["load_lpcd"],
        )


# ---------------------------------------------------------------- units


@dataclass(frozen=True)
class UnitType:
    id: str
    label: str
    w_mm: int
    d_mm: int
    area_m2: float

    def cells(self, grid_mm: int) -> tuple[int, int]:
        return self.w_mm // grid_mm, self.d_mm // grid_mm


@dataclass(frozen=True)
class Strategy:
    id: str
    label: str
    fill_order: tuple[str, ...]
    priority: str | None


@dataclass(frozen=True)
class Units:
    types: tuple[UnitType, ...]
    strategies: dict[str, Strategy]

    def by_id(self, unit_id: str) -> UnitType:
        for u in self.types:
            if u.id == unit_id:
                return u
        raise ContractError(f"units.json: 알 수 없는 유형 '{unit_id}'")

    @property
    def min_depth_mm(self) -> int:
        return min(u.d_mm for u in self.types)

    @staticmethod
    def from_dict(d: dict, grid_mm: int) -> "Units":
        w = "units.json"
        types = []
        for u in _require(d, "units", w):
            _check_grid([u["w_mm"], u["d_mm"]], grid_mm, f"{w}:{u['id']}")
            declared = float(u["area_m2"])
            computed = u["w_mm"] * u["d_mm"] / 1_000_000
            if abs(declared - computed) > 1e-9:
                raise ContractError(
                    f"{w}:{u['id']}: area_m2 {declared} 가 치수 계산값 {computed} 와 다르다."
                )
            types.append(
                UnitType(u["id"], u["label"], int(u["w_mm"]), int(u["d_mm"]), declared)
            )
        strategies = {
            k: Strategy(k, v["label"], tuple(v["fill_order"]), v.get("priority"))
            for k, v in _require(d, "strategies", w).items()
        }
        units = Units(tuple(types), strategies)
        for s in strategies.values():
            for uid in s.fill_order:
                units.by_id(uid)  # 존재 검증
        return units


# ---------------------------------------------------------------- building


@dataclass(frozen=True)
class Building:
    name: str
    use: str
    floors_total: int
    floors_residential: tuple[int, int] | None
    seismic: bool
    fire_resistant: bool
    floor_height_mm: int
    approval_year: int | None
    gfa_m2: float | None
    parking_existing: int | None
    septic_capacity_m3: float | None
    source_note: str

    def require(self, field_name: str):
        """미확정(null) 필드를 쓰려 할 때 명확히 실패시킨다."""
        v = getattr(self, field_name)
        if v is None:
            raise ContractError(
                f"building.json: '{field_name}' 가 미확정(null)이다. "
                f"PROGRESS.md 2.3절 참조."
            )
        return v

    @staticmethod
    def from_dict(d: dict) -> "Building":
        w = "building.json"
        fr = d.get("floors_residential")
        return Building(
            name=str(_require(d, "name", w)),
            use=str(d.get("use", "")),
            floors_total=int(_require(d, "floors_total", w)),
            floors_residential=tuple(fr) if fr else None,
            seismic=bool(d.get("seismic", False)),
            fire_resistant=bool(d.get("fire_resistant", False)),
            floor_height_mm=int(d.get("floor_height_mm", 0)),
            approval_year=d.get("approval_year"),
            gfa_m2=d.get("gfa_m2"),
            parking_existing=d.get("parking_existing"),
            septic_capacity_m3=d.get("septic_capacity_m3"),
            source_note=str(d.get("source_note", "")),
        )


# ---------------------------------------------------------------- floor plan


@dataclass(frozen=True)
class Core:
    type: str  # "stair" | "ev"
    rect: Rect


@dataclass(frozen=True)
class Window:
    start: Point
    end: Point
    sill: int
    height: int

    @property
    def length_mm(self) -> int:
        dx = self.end[0] - self.start[0]
        dy = self.end[1] - self.start[1]
        return int(round((dx * dx + dy * dy) ** 0.5))


@dataclass(frozen=True)
class FloorPlan:
    floor: int
    boundary: tuple[Point, ...]
    cores: tuple[Core, ...]
    shafts: tuple[Rect, ...]
    columns: tuple[Rect, ...]  # 중심·크기를 rect 로 정규화해 보관
    windows: tuple[Window, ...]

    @property
    def bbox_mm(self) -> tuple[int, int, int, int]:
        xs = [p[0] for p in self.boundary]
        ys = [p[1] for p in self.boundary]
        return min(xs), min(ys), max(xs), max(ys)

    def stair_cores(self) -> tuple[Core, ...]:
        return tuple(c for c in self.cores if c.type == "stair")

    @staticmethod
    def from_dict(d: dict, grid_mm: int) -> "FloorPlan":
        floor = int(_require(d, "floor", "floor_plan"))
        w = f"floor_plan(floor={floor})"

        unit = d.get("unit", "mm")
        if unit != "mm":
            raise ContractError(f"{w}: 좌표 단위는 mm 만 지원한다 (받은 값: {unit})")

        boundary = [tuple(p) for p in _require(d, "boundary", w)]
        if len(boundary) < 4:
            raise ContractError(f"{w}: boundary 는 꼭짓점 4개 이상이어야 한다.")
        if boundary[0] == boundary[-1]:
            raise ContractError(f"{w}: boundary 의 첫 점을 마지막에 반복하지 않는다.")
        _check_grid([v for p in boundary for v in p], grid_mm, f"{w}.boundary")

        cores = []
        for c in _require(d, "cores", w):
            if c["type"] not in ("stair", "ev"):
                raise ContractError(
                    f"{w}.cores: type 은 'stair' 또는 'ev' 여야 한다 (받은 값: {c['type']})"
                )
            _check_grid(c["rect"], grid_mm, f"{w}.cores[{c['type']}]")
            cores.append(Core(c["type"], tuple(c["rect"])))

        shafts = []
        for s in d.get("shafts", []):
            _check_grid(s["rect"], grid_mm, f"{w}.shafts")
            shafts.append(tuple(s["rect"]))

        columns = []
        for col in d.get("columns", []):
            cx, cy = col["center"]
            cw, ch = col["size"]
            rect = (cx - cw // 2, cy - ch // 2, cw, ch)
            _check_grid(rect, grid_mm, f"{w}.columns(center={col['center']})")
            columns.append(rect)

        windows = []
        for win in d.get("windows", []):
            _check_grid(
                list(win["start"]) + list(win["end"]), grid_mm, f"{w}.windows"
            )
            windows.append(
                Window(
                    tuple(win["start"]),
                    tuple(win["end"]),
                    int(win["sill"]),
                    int(win["height"]),
                )
            )

        return FloorPlan(
            floor=floor,
            boundary=tuple(boundary),
            cores=tuple(cores),
            shafts=tuple(shafts),
            columns=tuple(columns),
            windows=tuple(windows),
        )


# ---------------------------------------------------------------- 묶음 로딩


@dataclass(frozen=True)
class Inputs:
    rules: Rules
    units: Units
    building: Building
    floors: tuple[FloorPlan, ...]
    input_hash: dict[str, str]


def load_inputs(
    building_dir: str | Path,
    data_dir: str | Path = "data",
) -> Inputs:
    """building_dir 의 building.json + floor_plan_*.json 과 공통 rules/units 를 읽는다."""
    building_dir = Path(building_dir)
    data_dir = Path(data_dir)

    rules_path = data_dir / "rules.json"
    units_path = data_dir / "units.json"
    building_path = building_dir / "building.json"

    rules = Rules.from_dict(load_json(rules_path))
    units = Units.from_dict(load_json(units_path), rules.grid_mm)
    building = Building.from_dict(load_json(building_path))

    plan_paths = sorted(building_dir.glob("floor_plan_*.json"))
    if not plan_paths:
        raise ContractError(f"{building_dir}: floor_plan_*.json 이 없다.")
    floors = tuple(
        FloorPlan.from_dict(load_json(p), rules.grid_mm) for p in plan_paths
    )

    hashes = {p.name: sha256(p) for p in [rules_path, units_path, building_path]}
    hashes.update({p.name: sha256(p) for p in plan_paths})

    return Inputs(rules, units, building, floors, hashes)
