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


def _int_required(d: dict, key: str, where: str) -> int:
    """필수 정수. null 이면 무엇을 어디서 채워야 하는지 알려준다.

    어댑터는 대장에 없는 값을 지어내지 않고 null 로 준다. 그때 TypeError 대신
    사람이 읽을 수 있는 메시지가 나와야 한다.
    """
    v = _require(d, key, where)
    if v is None:
        raise ContractError(
            f"{where}: '{key}' 가 null 이다. 자동 수집으로 채워지지 않았으므로 "
            f"도면이나 건축물대장 등본에서 확인해 직접 넣을 것."
        )
    return int(v)


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
class PriorUseParking:
    """공공주택특별법 시행령 제37조⑤ — 종전 용도 기준 부설주차장.

    요건을 모두 갖추면 **용도변경 전 용도를 기준으로** 주차장법 제19조를 적용한다.
    사용승인을 받은 건물이라면 기존 주차대수가 이미 종전 기준을 충족하므로,
    세대수가 늘어도 추가 주차를 요구하지 않는다 — 주차 축이 세대수를 제한하지 않는다.

    대상이 제37조①제3호(근생·노유자·수련·업무·숙박)로 한정된다는 점이 중요하다.
    **비주택만** 받을 수 있어 이 사업의 정의와 정확히 겹친다.
    """

    eligible_prior_uses: tuple[str, ...]
    converted_use_allowed: tuple[str, ...]
    max_exclusive_area_m2: float

    def check(
        self, prior_use: str, converted_use: str | None,
        no_car_tenant: bool | None, areas: tuple[float, ...],
    ) -> tuple[bool, tuple[str, ...]]:
        """→ (요건 충족 여부, 항목별 판정 문구). 하나라도 못 맞추면 특례를 못 받는다."""
        notes: list[str] = []
        ok = True

        if prior_use in self.eligible_prior_uses:
            notes.append(f"대상 건축물 — 종전 용도 '{prior_use}' (제37조①제3호)")
        else:
            ok = False
            notes.append(
                f"대상 아님 — 종전 용도 '{prior_use or '미입력'}' 는 제37조①제3호"
                f"({', '.join(self.eligible_prior_uses)})에 없다"
            )

        if converted_use is None:
            ok = False
            notes.append("요건1 미확인 — 변경 후 용도(converted_use)가 입력되지 않았다")
        elif converted_use in self.converted_use_allowed:
            notes.append(f"요건1 충족 — 준주택 '{converted_use}' 로 변경")
        else:
            ok = False
            notes.append(
                f"요건1 미충족 — '{converted_use}' 는 「주택법 시행령」 제4조의 준주택"
                f"({', '.join(self.converted_use_allowed)})이 아니다"
            )

        if not areas:
            ok = False
            notes.append("요건2 판정 불가 — 배치된 세대가 없다")
        else:
            over = sorted({a for a in areas if a >= self.max_exclusive_area_m2})
            if over:
                ok = False
                notes.append(
                    f"요건2 미충족 — 전용 {self.max_exclusive_area_m2}㎡ 이상 세대가 있다 "
                    f"({', '.join(f'{a}㎡' for a in over)})"
                )
            else:
                notes.append(
                    f"요건2 충족 — 전 세대 전용 {max(areas)}㎡ < "
                    f"{self.max_exclusive_area_m2}㎡"
                )

        if no_car_tenant is None:
            ok = False
            notes.append("요건3 미확인 — 자동차 미소유 임차인 자격요건 적용 여부(no_car_tenant) 미입력")
        elif no_car_tenant:
            notes.append("요건3 충족 — 자동차 미소유를 임차인 자격요건으로 함")
        else:
            ok = False
            notes.append("요건3 미충족 — 자동차 미소유 자격요건을 걸지 않음")

        return ok, tuple(notes)


@dataclass(frozen=True)
class CommunityRules:
    """주민공동시설(커뮤니티) 의무 설치.

    LH 공고 p5 — 50세대 이상이면 세대당 1.0㎡ 이상. 세대수가 면적을 정하고
    그 면적이 다시 세대수를 줄이므로 순환이며, community.py 가 고정점까지 반복한다.
    """

    required_from_households: int
    area_per_household_m2: float
    guard_office_from_households: int
    admin_office_from_households: int

    def required_area_m2(self, households: int) -> float:
        if households < self.required_from_households:
            return 0.0
        return households * self.area_per_household_m2

    def offices_required(self, households: int) -> tuple[str, ...]:
        """면적 기준이 공고에 없어 설치 필요 여부만 낸다."""
        out = []
        if households >= self.guard_office_from_households:
            out.append("경비실")
        if households >= self.admin_office_from_households:
            out.append("관리사무소")
        return tuple(out)


@dataclass(frozen=True)
class SepticMode:
    """오수 처리 방식. 건축물대장 오수정화시설의 modeCd / modeCdNm 에서 온다."""

    id: str
    label: str
    limits: bool  # 이 방식이 세대수를 제한하는가
    volume_conversion: bool  # 별표12 인원↔용량 환산을 적용해도 되는가
    code_prefix: str
    match: tuple[str, ...]

    @property
    def not_applicable(self) -> bool:
        return not self.limits


@dataclass(frozen=True)
class SepticRules:
    """정화조 — 처리대상인원과 유효용량의 환산.

    법령 사슬: 하수도법 제34조④·제35조② → 시행령 제24조⑤(고시 위임)
    → 기후에너지환경부고시 제2025-165호 별표(용도별 인원산정식)
    → 하수도법 시행규칙 [별표 12](인원 → 유효용량).

    세대당 처리대상인원은 유형마다 다르므로 units.json 에 있다.
    """

    small_m3: float
    small_persons_max: int
    base_m3: float
    base_persons: int
    increment_m3: float
    increment_persons: int
    person_per_m2_by_use: dict[str, float]
    modes: tuple[SepticMode, ...] = ()

    def mode_for(self, raw: str, code: str | None = None) -> SepticMode:
        """건축물대장 오수정화시설 → 처리 방식.

        **코드 앞자리를 1순위로 본다.** 공법 이름은 수십 종(접촉산화·접촉폭기·
        장기폭기·살수여상…)인데 `modeCd` 앞자리는 세 갈래로 안정적이다
        (1=오수처리시설, 2=정화조, 3=공공하수도 연결). 처음 보는 공법이 와도
        앞자리만 맞으면 분류된다. 이름 부분일치는 코드가 없을 때의 보조다.

        하수처리구역 안의 건물은 공공하수도로 내보내므로 자체 용량이 세대수를
        제한하지 않는다. 이것을 '입력 미확보' 와 같게 다루면 없는 병목이 생긴다.
        어느 쪽으로도 걸리지 않으면 단정하지 않고 실패시킨다.
        """
        cd = (code or "").strip()
        if cd:
            for m in self.modes:
                if m.code_prefix and cd.startswith(m.code_prefix):
                    return m

        text = (raw or "").replace(" ", "")
        for m in self.modes:
            if any(kw in text for kw in m.match):
                return m

        known = ", ".join(f"{m.code_prefix}xx={m.label}" for m in self.modes)
        raise ContractError(
            f"오수처리 방식을 알 수 없다 (modeCd={code!r}, modeCdNm={raw!r}). "
            f"확인된 분류: {known}. 건축물대장 오수정화시설 코드를 확인해 "
            f"rules.json 의 septic.modes 에 추가할 것. 임의로 정화조라고 단정하면 "
            f"공공하수도 연결 건물에 없는 병목이 생긴다."
        )

    def volume_for_persons(self, persons: float) -> float:
        """처리대상인원 N → 필요 총유효용량(㎥). 시행규칙 별표 12."""
        if persons <= self.small_persons_max:
            return self.small_m3
        if persons <= self.base_persons:
            return self.base_m3
        over = persons - self.base_persons
        return self.base_m3 + over * (self.increment_m3 / self.increment_persons)

    def persons_for_volume(self, volume_m3: float) -> float:
        """유효용량(㎥) → 감당 가능한 처리대상인원. volume_for_persons 의 역함수."""
        if volume_m3 <= self.small_m3:
            return float(self.small_persons_max)
        if volume_m3 <= self.base_m3:
            return float(self.base_persons)
        over = volume_m3 - self.base_m3
        return self.base_persons + over * (self.increment_persons / self.increment_m3)

    def persons_for_use(self, use: str, area_m2: float) -> float:
        """용도별 연면적 → 처리대상인원. 고시 별표 인원산정식 N = 계수 × A."""
        coef = self.person_per_m2_by_use.get(use)
        if coef is None:
            known = ", ".join(sorted(self.person_per_m2_by_use))
            raise ContractError(
                f"rules.septic.person_per_m2_by_use 에 용도 '{use}' 의 계수가 없다. "
                f"확인된 용도: {known}. "
                f"기후에너지환경부고시 제2025-165호 별표에서 확인해 추가할 것. "
                f"유사 용도의 계수를 임의로 가져다 쓰면 틀린 수치가 제안서까지 흘러간다."
            )
        return coef * area_m2


@dataclass(frozen=True)
class Rules:
    version: str
    grid_mm: int
    corridor_width_mm: int
    corridor_single_width_mm: int
    corridor_side_usable_coverage: float
    shaft_reuse_threshold_cells: int
    ceiling_min_mm: int
    daylight_area_ratio: float
    egress: Egress
    parking_bands: tuple[tuple[float, bool, float], ...]  # (max_area, inclusive, coef)
    parking_default_coef: float
    parking_mode: str
    parking_flat_coef: float | None  # 제37조④ 완화계수
    parking_flat_max_area_m2: float | None
    parking_prior_use: PriorUseParking | None  # 제37조⑤ (mode 가 relaxed_037_5 일 때만)
    septic: SepticRules
    community: CommunityRules

    @property
    def corridor_width_cells(self) -> int:
        return self.corridor_width_mm // self.grid_mm

    @property
    def corridor_single_width_cells(self) -> int:
        return self.corridor_single_width_mm // self.grid_mm

    def parking_coef(self, area_m2: float) -> float:
        """전용면적 → 세대당 주차 계수.

        `statutory` 는 주차장법 소형주택 특례 구간, `relaxed_037_4` 는 공공주택특별법
        시행령 제37조④ 의 0.3대다. 조문이 "…전용면적이 30제곱미터 미만인 **세대는**"
        이라고 세대 단위로 쓰므로, 혼합 구성이면 세대별로 갈리고 기준을 넘는 세대는
        statutory 로 떨어진다.
        """
        if self.parking_flat_coef is not None:
            assert self.parking_flat_max_area_m2 is not None
            if area_m2 < self.parking_flat_max_area_m2:
                return self.parking_flat_coef
        for max_area, inclusive, coef in self.parking_bands:
            if (area_m2 <= max_area) if inclusive else (area_m2 < max_area):
                return coef
        return self.parking_default_coef

    @staticmethod
    def from_dict(d: dict) -> "Rules":
        w = "rules.json"
        grid = int(_require(d, "grid_mm", w))
        corridor = int(_require(d, "corridor_width_mm", w))
        corridor_single = int(_require(d, "corridor_single_width_mm", w))
        for name, val in (
            ("corridor_width_mm", corridor),
            ("corridor_single_width_mm", corridor_single),
        ):
            if val % grid:
                raise ContractError(
                    f"{w}: {name}({val}) 가 grid_mm({grid}) 의 배수가 아니다."
                )
        if corridor_single > corridor:
            raise ContractError(
                f"{w}: 편복도 폭({corridor_single})이 중복도 폭({corridor})보다 넓다. "
                f"2패스 생성이 수렴한다는 전제가 깨진다."
            )
        eg = _require(d, "egress", w)
        pk = _require(d, "parking", w)
        sp = _require(d, "septic", w)
        cm = _require(d, "community", w)
        tv = _require(sp, "tank_volume", f"{w}:septic")

        modes = _require(pk, "modes", f"{w}:parking")
        mode = str(pk.get("mode", "statutory"))
        if mode not in modes:
            raise ContractError(
                f"{w}: parking.mode '{mode}' 가 parking.modes 에 없다. "
                f"정의된 모드: {', '.join(sorted(modes))}."
            )
        statutory = _require(modes, "statutory", f"{w}:parking.modes")
        active = modes[mode]
        return Rules(
            version=str(_require(d, "version", w)),
            grid_mm=grid,
            corridor_width_mm=corridor,
            corridor_single_width_mm=corridor_single,
            corridor_side_usable_coverage=float(
                _require(d, "corridor_side_usable_coverage", w)
            ),
            shaft_reuse_threshold_cells=int(
                _require(d, "shaft_reuse_threshold_cells", w)
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
                for b in statutory["bands"]
            ),
            parking_default_coef=float(statutory["default_coef"]),
            parking_mode=mode,
            parking_flat_coef=(
                float(active["flat_coef"]) if "flat_coef" in active else None
            ),
            parking_flat_max_area_m2=(
                float(active["max_exclusive_area_m2"])
                if "flat_coef" in active and "max_exclusive_area_m2" in active
                else None
            ),
            parking_prior_use=(
                PriorUseParking(
                    eligible_prior_uses=tuple(active["eligible_prior_uses"]),
                    converted_use_allowed=tuple(active["converted_use_allowed"]),
                    max_exclusive_area_m2=float(active["max_exclusive_area_m2"]),
                )
                if "eligible_prior_uses" in active
                else None
            ),
            septic=SepticRules(
                small_m3=float(tv["small_m3"]),
                small_persons_max=int(tv["small_persons_max"]),
                base_m3=float(tv["base_m3"]),
                base_persons=int(tv["base_persons"]),
                increment_m3=float(tv["increment_m3"]),
                increment_persons=int(tv["increment_persons"]),
                person_per_m2_by_use={
                    k: float(v)
                    for k, v in sp["person_per_m2_by_use"].items()
                    if not k.startswith("_")
                },
                modes=tuple(
                    SepticMode(
                        id=k,
                        label=str(v["label"]),
                        limits=bool(v["limits"]),
                        volume_conversion=bool(v["volume_conversion"]),
                        code_prefix=str(v.get("code_prefix", "")),
                        match=tuple(v["match"]),
                    )
                    for k, v in _require(sp, "modes", f"{w}:septic").items()
                ),
            ),
            community=CommunityRules(
                required_from_households=int(cm["required_from_households"]),
                area_per_household_m2=float(cm["area_per_household_m2"]),
                guard_office_from_households=int(cm["guard_office_from_households"]),
                admin_office_from_households=int(cm["admin_office_from_households"]),
            ),
        )


# ---------------------------------------------------------------- units


@dataclass(frozen=True)
class UnitType:
    id: str
    label: str
    w_mm: int
    d_mm: int
    area_m2: float
    rooms: int
    persons_per_household: float

    def cells(self, grid_mm: int) -> tuple[int, int]:
        return self.w_mm // grid_mm, self.d_mm // grid_mm


@dataclass(frozen=True)
class Strategy:
    id: str
    label: str
    fill_order: tuple[str, ...]
    priority: str | None
    constraint: str | None  # 예: "shaft_reuse_only"


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
                UnitType(
                    u["id"],
                    u["label"],
                    int(u["w_mm"]),
                    int(u["d_mm"]),
                    declared,
                    int(u["rooms"]),
                    float(u["persons_per_household"]),
                )
            )
        strategies = {
            k: Strategy(
                k,
                v["label"],
                tuple(v["fill_order"]),
                v.get("priority"),
                v.get("constraint"),
            )
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
    septic_capacity_persons: float | None  # 대장의 처리대상인원(capaPsper). 실무상 이쪽이 채워진다
    septic_mode_raw: str | None  # 건축물대장 오수정화시설 형식코드명(modeCdNm) 그대로
    septic_mode_code: str | None  # 형식코드(modeCd). 앞자리가 분류다
    converted_use: str | None  # 용도변경 후 용도. 제37조⑤ 요건1 판정에 쓴다
    no_car_tenant: bool | None  # 자동차 미소유를 임차인 자격요건으로 하는가 (제37조⑤ 요건3)
    zoning: dict[str, tuple[str, ...]]  # 용도지역·지구·구역. 판정하지 않고 표시만 한다
    violation: bool | None  # 건축물대장 위반건축물 표시
    exclusion_answers: dict[str, bool]
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
            floors_total=_int_required(d, "floors_total", w),
            floors_residential=tuple(fr) if fr else None,
            # 어댑터는 대장에 없는 값을 지어내지 않고 명시적 null 로 준다.
            # 미상을 False 로 떨어뜨리는 방향이 보수적인지 항목별로 확인했다:
            # fire_resistant 는 False 여야 피난 한계가 30m(엄격)로 잡힌다.
            seismic=bool(d.get("seismic") or False),
            fire_resistant=bool(d.get("fire_resistant") or False),
            floor_height_mm=int(d.get("floor_height_mm") or 0),
            approval_year=d.get("approval_year"),
            gfa_m2=d.get("gfa_m2"),
            parking_existing=d.get("parking_existing"),
            septic_capacity_m3=d.get("septic_capacity_m3"),
            septic_capacity_persons=d.get("septic_capacity_persons"),
            septic_mode_raw=d.get("septic_mode_raw"),
            septic_mode_code=(
                str(d["septic_mode_code"]) if d.get("septic_mode_code") else None
            ),
            converted_use=d.get("converted_use"),
            no_car_tenant=d.get("no_car_tenant"),
            zoning={
                k: tuple(v)
                for k, v in (d.get("zoning") or {}).items()
                if not k.startswith("_")
            },
            violation=d.get("violation"),
            exclusion_answers={
                k: bool(v)
                for k, v in (d.get("exclusion_answers") or {}).items()
                if v is not None
            },
            source_note=str(d.get("source_note", "")),
        )


# ---------------------------------------------------------------- 매입제외


@dataclass(frozen=True)
class ExclusionCondition:
    id: str
    label: str
    check: str  # "auto" | "ask" | "geo"
    source: str
    rule: str | None
    param: object

    @property
    def is_auto(self) -> bool:
        return self.check == "auto"

    @property
    def needs_label(self) -> str:
        return {"ask": "사실관계 확인 필요", "geo": "위치 데이터 필요"}.get(self.check, "")


@dataclass(frozen=True)
class Exclusions:
    version: str
    conditions: tuple[ExclusionCondition, ...]

    @staticmethod
    def from_dict(d: dict) -> "Exclusions":
        w = "exclusions.json"
        kinds = ("auto", "ask", "geo")
        out = []
        for c in _require(d, "conditions", w):
            if c["check"] not in kinds:
                raise ContractError(
                    f"{w}:{c['id']}: check 는 {'/'.join(kinds)} 중 하나여야 한다 "
                    f"(받은 값: {c['check']})"
                )
            if c["check"] == "auto" and "rule" not in c:
                raise ContractError(
                    f"{w}:{c['id']}: check 가 'auto' 인데 rule 이 없다. "
                    f"엔진이 무엇으로 판정해야 하는지 알 수 없다."
                )
            out.append(
                ExclusionCondition(
                    id=str(c["id"]),
                    label=str(c["label"]),
                    check=str(c["check"]),
                    source=str(c.get("source", "")),
                    rule=c.get("rule"),
                    param=c.get("param"),
                )
            )
        return Exclusions(str(_require(d, "version", w)), tuple(out))


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


#: 도면 출처. 결과를 어디까지 믿을 수 있는지가 여기서 갈린다.
PLAN_STATUS = {
    "survey": "원본 도면 · 실측",
    "reconstructed": "공개 정보 기반 재구성",
    "synthetic": "인공 검증 평면 — 실제 건물 아님",
    "placeholder": "형상 예시 — 결과를 사례 대조에 쓸 수 없음",
}


@dataclass(frozen=True)
class FloorPlan:
    floor: int
    status: str
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

    @property
    def status_label(self) -> str:
        return PLAN_STATUS[self.status]

    @property
    def is_trustworthy(self) -> bool:
        """이 도면의 결과를 사례 대조·제안서에 쓸 수 있는가."""
        return self.status in ("survey", "reconstructed")

    def stair_cores(self) -> tuple[Core, ...]:
        return tuple(c for c in self.cores if c.type == "stair")

    @staticmethod
    def from_dict(d: dict, grid_mm: int) -> "FloorPlan":
        floor = int(_require(d, "floor", "floor_plan"))
        w = f"floor_plan(floor={floor})"

        unit = d.get("unit", "mm")
        if unit != "mm":
            raise ContractError(f"{w}: 좌표 단위는 mm 만 지원한다 (받은 값: {unit})")

        status = _require(d, "status", w)
        if status not in PLAN_STATUS:
            raise ContractError(
                f"{w}: status 는 {'/'.join(PLAN_STATUS)} 중 하나여야 한다 "
                f"(받은 값: {status}). 도면 출처를 밝히지 않은 결과는 "
                f"어디까지 믿어도 되는지 알 수 없다."
            )

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
            status=status,
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
    exclusions: Exclusions


def load_inputs(
    building_dir: str | Path,
    data_dir: str | Path = "data",
) -> Inputs:
    """building_dir 의 building.json + floor_plan_*.json 과 공통 rules/units 를 읽는다."""
    building_dir = Path(building_dir)
    data_dir = Path(data_dir)

    rules_path = data_dir / "rules.json"
    units_path = data_dir / "units.json"
    excl_path = data_dir / "exclusions.json"
    building_path = building_dir / "building.json"

    rules = Rules.from_dict(load_json(rules_path))
    units = Units.from_dict(load_json(units_path), rules.grid_mm)
    exclusions = Exclusions.from_dict(load_json(excl_path))
    building = Building.from_dict(load_json(building_path))

    plan_paths = sorted(building_dir.glob("floor_plan_*.json"))
    if not plan_paths:
        raise ContractError(f"{building_dir}: floor_plan_*.json 이 없다.")
    floors = tuple(
        FloorPlan.from_dict(load_json(p), rules.grid_mm) for p in plan_paths
    )

    hashes = {
        p.name: sha256(p)
        for p in [rules_path, units_path, excl_path, building_path]
    }
    hashes.update({p.name: sha256(p) for p in plan_paths})

    return Inputs(rules, units, building, floors, hashes, exclusions)
