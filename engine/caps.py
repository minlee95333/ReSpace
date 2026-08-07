"""⑧ caps — 3축 상한과 병목 판정.

이 시스템이 유일하게 답하는 질문이 여기 있다: **무엇이 세대수를 묶고 있는가.**

평면·주차·정화조가 각각 세대수 상한을 만들고, 그중 가장 낮은 값이 실제 공급 가능량이다.

입력이 없는 축은 **숫자를 지어내지 않고 '미확보'로 보고한다.** 기본값을 넣으면 틀린
수치가 제안서까지 흘러간다. 대신 파이프라인은 멈추지 않으며, 확보된 축만으로 낸
잠정 상한임을 결과에 명시한다.
"""

from __future__ import annotations

from dataclasses import dataclass

from .contracts import Building, ContractError, Rules, Units
from .place import PlacedUnit

AXES = ("plan", "parking", "septic")

AXIS_LABEL = {
    "plan": "평면",
    "parking": "주차",
    "septic": "정화조",
}


@dataclass(frozen=True)
class AxisCap:
    axis: str
    value: int | None
    basis: str
    blocked_reason: str | None = None

    @property
    def available(self) -> bool:
        return self.value is not None

    @property
    def label(self) -> str:
        return AXIS_LABEL[self.axis]


@dataclass(frozen=True)
class Caps:
    axes: tuple[AxisCap, ...]
    supply: int
    bottleneck: str
    complete: bool

    def by_axis(self, axis: str) -> AxisCap:
        return next(a for a in self.axes if a.axis == axis)

    @property
    def blocked(self) -> tuple[AxisCap, ...]:
        return tuple(a for a in self.axes if not a.available)

    @property
    def note(self) -> str:
        if self.complete:
            return ""
        names = ", ".join(a.label for a in self.blocked)
        return f"{names} 축 입력 미확보 — 확보된 축만으로 낸 잠정 상한이다."


def _mean_parking_coef(rules: Rules, units: Units, placed: tuple[PlacedUnit, ...]) -> float:
    """실제 배치된 유형 구성의 평균 주차 계수.

    유형마다 전용면적이 달라 계수가 갈리므로 구성비를 반영한다.
    """
    coefs = [rules.parking_coef(units.by_id(u.type_id).area_m2) for u in placed]
    return sum(coefs) / len(coefs)


def compute(
    rules: Rules,
    units: Units,
    building: Building,
    placed: tuple[PlacedUnit, ...],
) -> Caps:
    plan = len(placed)
    axes = [
        AxisCap("plan", plan, f"층별 배치 세대수 합계 {plan}세대")
    ]

    # 주차
    if building.parking_existing is None:
        axes.append(
            AxisCap(
                "parking", None, "기존 주차대수 미입력",
                "building.json 의 parking_existing 이 null 이다",
            )
        )
    elif plan == 0:
        axes.append(
            AxisCap("parking", 0, "배치된 세대가 없어 계수를 정할 수 없다")
        )
    else:
        coef = _mean_parking_coef(rules, units, placed)
        cap = int(building.parking_existing / coef)
        axes.append(
            AxisCap(
                "parking", cap,
                f"기존 {building.parking_existing}대 ÷ 평균계수 {coef:.2f} = {cap}세대",
            )
        )

    # 정화조
    try:
        per_m3 = rules.septic_units_per_m3()
    except ContractError as e:
        axes.append(AxisCap("septic", None, "정화조 원단위 미확정", str(e)))
    else:
        if building.septic_capacity_m3 is None:
            axes.append(
                AxisCap(
                    "septic", None, "기존 정화조 용량 미입력",
                    "building.json 의 septic_capacity_m3 가 null 이다",
                )
            )
        else:
            cap = int(building.septic_capacity_m3 * per_m3)
            axes.append(
                AxisCap(
                    "septic", cap,
                    f"기존 {building.septic_capacity_m3}㎥ × {per_m3:.4f}세대/㎥ "
                    f"= {cap}세대",
                )
            )

    usable = [a for a in axes if a.available]
    winner = min(usable, key=lambda a: (a.value, AXES.index(a.axis)))
    return Caps(
        axes=tuple(axes),
        supply=winner.value,
        bottleneck=winner.axis,
        complete=all(a.available for a in axes),
    )


def verdict(caps: Caps, floors: int) -> tuple[str, tuple[str, ...]]:
    """판정 등급과 이유. 판정에는 반드시 이유가 붙는다 (설계 7.2절).

    안전·법규는 배점 항목이 아니라 필수 통과조건이므로, 공급량이 많다는 이유로
    통과시키지 않는다.
    """
    reasons: list[str] = []
    b = caps.by_axis(caps.bottleneck)

    if caps.supply == 0:
        reasons.append(f"{b.label} 축 상한이 0세대 — 필수조건 미충족")
        reasons.append(b.basis)
        return "부적합", tuple(reasons)

    reasons.append(
        f"병목은 {b.label} 축 — 공급 가능 {caps.supply}세대 "
        f"({floors}개 주거층 기준)"
    )
    for a in caps.axes:
        reasons.append(f"{a.label}: {a.basis}")

    if not caps.complete:
        reasons.append(caps.note)
        return "조건부 검토", tuple(reasons)

    if caps.bottleneck == "plan":
        reasons.append("인프라 여유가 있어 추가 투자 없이 공급 가능하다")
        return "우선검토", tuple(reasons)

    reasons.append(f"{b.label} 보강이 선행되어야 평면 상한만큼 공급할 수 있다")
    return "검토 가능", tuple(reasons)
