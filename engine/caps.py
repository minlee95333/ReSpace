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
from .exclude import (
    GRADE_CONDITIONAL,
    GRADE_EXCLUDED,
    GRADE_PASS,
    ExclusionResult,
)
from .place import PlacedUnit

AXES = ("plan", "parking", "septic")

AXIS_LABEL = {
    "plan": "평면",
    "parking": "주차",
    "septic": "정화조",
}


@dataclass(frozen=True)
class AxisCap:
    """한 축의 세대수 상한.

    value 가 None 인 경우가 **두 가지**라 구분한다.

    - `not_applicable=False` — 입력이 없어서 못 냈다 (**미확보**). 확보하면 병목일 수 있다.
    - `not_applicable=True`  — 이 축이 애초에 세대수를 제한하지 않는다 (**해당 없음**).
      공공하수도에 연결된 건물의 정화조 축이 여기다.

    둘을 같게 표시하면 없는 병목을 만들어내거나, 있는 공백을 감춘다.
    """

    axis: str
    value: int | None
    basis: str
    blocked_reason: str | None = None
    not_applicable: bool = False

    @property
    def available(self) -> bool:
        """상한 계산에 쓸 수 있는 숫자가 있는가."""
        return self.value is not None

    @property
    def is_blocked(self) -> bool:
        """입력이 없어서 못 낸 것인가 (해당 없음과 구분)."""
        return self.value is None and not self.not_applicable

    @property
    def state_label(self) -> str:
        if self.available:
            return "산출됨"
        return "해당 없음" if self.not_applicable else "미확보"

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
        return tuple(a for a in self.axes if a.is_blocked)

    @property
    def not_applicable(self) -> tuple[AxisCap, ...]:
        return tuple(a for a in self.axes if a.not_applicable)

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


def _parking_cap(
    rules: Rules, units: Units, building: Building, placed: tuple[PlacedUnit, ...]
) -> AxisCap:
    """주차 축.

    제37조⑤(종전 용도 기준)이 걸리면 **축 자체가 세대수를 제한하지 않는다.**
    종전 용도 기준으로 부설주차장을 보므로, 사용승인을 받은 건물이면 기존 주차가
    이미 그 기준을 충족한다. 계수로는 표현되지 않는 상태라 not_applicable 로 낸다.

    요건을 하나라도 못 맞추면 특례 없이 통상 계수로 떨어진다 — 못 받는 쪽이 보수적이다.
    """
    prior = rules.parking_prior_use
    if prior is not None:
        areas = tuple(units.by_id(u.type_id).area_m2 for u in placed)
        ok, notes = prior.check(
            building.use, building.converted_use, building.no_car_tenant, areas
        )
        if ok:
            return AxisCap(
                "parking", None,
                "제37조⑤ 종전 용도 기준 — 기존 주차대수가 그대로 인정되어 "
                "세대수를 제한하지 않는다",
                not_applicable=True,
            )
        # 특례 불가 → 통상 기준으로 계산하되, 왜 못 받았는지 남긴다.
        fallback_note = " / ".join(notes)
    else:
        fallback_note = ""

    if building.parking_existing is None:
        return AxisCap(
            "parking", None, "기존 주차대수 미입력",
            "building.json 의 parking_existing 이 null 이다",
        )
    if not placed:
        return AxisCap("parking", 0, "배치된 세대가 없어 계수를 정할 수 없다")

    coef = _mean_parking_coef(rules, units, placed)
    cap = int(building.parking_existing / coef)
    basis = f"기존 {building.parking_existing}대 ÷ 평균계수 {coef:.2f} = {cap}세대"
    if fallback_note:
        basis += f" (제37조⑤ 특례 불가 — {fallback_note})"
    return AxisCap("parking", cap, basis)


def mean_persons_per_household(units: Units, placed: tuple[PlacedUnit, ...]) -> float:
    """배치 구성의 세대당 평균 처리대상인원.

    원룸은 2.0인, 2거실은 2.7인이라 구성비가 정화조 상한을 직접 움직인다
    (기후에너지환경부고시 제2025-165호 별표).
    """
    ns = [units.by_id(u.type_id).persons_per_household for u in placed]
    return sum(ns) / len(ns)


def _septic_capacity_persons(
    rules: Rules, building: Building, mode=None
) -> tuple[float, str]:
    """기존 오수처리시설이 감당 가능한 처리대상인원과 그 근거.

    순서가 중요하다.

    1. **대장의 처리대상인원을 그대로 쓴다.** 건축물대장 오수정화시설은 용량(㎥)이
       아니라 인원(capaPsper)을 싣는다 — 실 표본에서 ㎥ 는 거의 전부 0 이었다.
       인원이 곧 우리가 필요한 값이므로 환산 자체가 필요 없고, 환산 오차도 없다.
    2. 용량(㎥)만 있으면 시행규칙 별표12 로 역산한다. 단 **정화조일 때만** —
       오수처리시설은 규모 산정식이 달라(BOD 부하 기준) 별표12 를 쓰면 틀린다.
    3. 둘 다 없으면 용도변경 **전** 용도의 연면적에서 고시 별표 인원산정식으로
       추정한다. "기존 시설이 종전 용도의 법정 인원을 감당하도록 설치돼 있다"는
       가정이며, 축을 살려두기 위한 대체 경로다.
    """
    if building.septic_capacity_persons is not None:
        n = float(building.septic_capacity_persons)
        return n, f"건축물대장 처리대상인원 {n:.0f}인"

    if building.septic_capacity_m3 is not None:
        if mode is not None and not mode.volume_conversion:
            raise ContractError(
                f"{mode.label} 은 규모 산정식이 정화조와 달라(BOD 부하 기준) "
                f"시행규칙 별표12 의 인원↔용량 환산을 적용할 수 없다. "
                f"건축물대장의 처리대상인원(capaPsper)을 "
                f"septic_capacity_persons 에 넣을 것."
            )
        v = building.septic_capacity_m3
        n = rules.septic.persons_for_volume(v)
        return n, f"기존 용량 {v}㎥ → 처리대상인원 {n:.0f}인 (시행규칙 별표12 역산)"

    if building.gfa_m2 is not None and building.use:
        n = rules.septic.persons_for_use(building.use, building.gfa_m2)
        return n, (
            f"용량·인원 미입력 — 종전 용도 '{building.use}' 연면적 {building.gfa_m2}㎡ "
            f"× {rules.septic.person_per_m2_by_use[building.use]} = {n:.0f}인 으로 추정"
        )

    raise ContractError(
        "building.json 의 septic_capacity_persons / septic_capacity_m3 가 둘 다 null 이고, "
        "종전 용도 기반 추정에 필요한 use / gfa_m2 도 없다. 하나는 있어야 한다."
    )


def _septic_mode(rules: Rules, building: Building):
    """오수 처리 방식을 해석한다. → (mode, 실패했으면 AxisCap)

    방식이 입력되지 않았으면 (None, None) 을 돌려 용량 기반 경로로 넘어간다.
    """
    raw, code = building.septic_mode_raw, building.septic_mode_code
    if not raw and not code:
        return None, None
    try:
        return rules.septic.mode_for(raw or "", code), None
    except ContractError as e:
        return None, AxisCap(
            "septic", None, "오수처리 방식을 해석할 수 없다", str(e)
        )


def _septic_cap(
    rules: Rules,
    units: Units,
    building: Building,
    placed: tuple[PlacedUnit, ...],
    plan: int,
) -> AxisCap:
    mode, failure = _septic_mode(rules, building)
    if failure is not None:
        return failure

    # 하수처리구역 안의 건물은 오수를 공공하수처리시설로 보내므로 자체 처리용량이
    # 세대수를 제한하지 않는다. 도심 건물 상당수가 여기다. 이걸 모르고 무조건
    # 상한을 계산하면 **없는 병목**이 생긴다. '미확보'와도 구분해야 한다.
    if mode is not None and not mode.limits:
        return AxisCap(
            "septic", None,
            f"{mode.label} — 자체 처리용량이 세대수를 제한하지 않는다",
            not_applicable=True,
        )

    if plan == 0:
        return AxisCap("septic", 0, "배치된 세대가 없어 세대 구성을 정할 수 없다")
    try:
        capacity_n, basis = _septic_capacity_persons(rules, building, mode)
    except ContractError as e:
        return AxisCap("septic", None, "오수처리 용량 입력 미확보", str(e))

    per_household = mean_persons_per_household(units, placed)
    cap = int(capacity_n / per_household)
    label = f"{mode.label} · " if mode is not None else ""
    return AxisCap(
        "septic", cap,
        f"{label}{basis} ÷ 세대당 평균 {per_household:.2f}인 = {cap}세대",
    )


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
    axes.append(_parking_cap(rules, units, building, placed))

    # 정화조
    axes.append(_septic_cap(rules, units, building, placed, plan))

    usable = [a for a in axes if a.available]
    winner = min(usable, key=lambda a: (a.value, AXES.index(a.axis)))
    return Caps(
        axes=tuple(axes),
        supply=winner.value,
        bottleneck=winner.axis,
        # '해당 없음'은 공백이 아니다. 그 축은 답이 나온 것이므로 complete 를 깨지 않는다.
        complete=not any(a.is_blocked for a in axes),
    )


def verdict(
    caps: Caps, floors: int, exclusion: "ExclusionResult | None" = None
) -> tuple[str, tuple[str, ...]]:
    """판정 등급과 이유. 판정에는 반드시 이유가 붙는다 (설계 7.2절).

    등급은 **LH 자체 3구분을 그대로 쓴다** — 공고 '통과, 조건부 통과(조건사항 충족 시
    통과), 매입제외로 구분'. 자체 용어를 새로 만들면 심의 문서와 대조가 안 된다.

    안전·법규는 배점 항목이 아니라 필수 통과조건이므로, 공급량이 많다는 이유로
    통과시키지 않는다. 확인되지 않은 것도 통과로 처리하지 않는다.
    """
    reasons: list[str] = []
    b = caps.by_axis(caps.bottleneck)

    # ⓪ 매입제외가 3축보다 먼저다. 매입 자체가 불가하면 세대수는 의미가 없다.
    if exclusion is not None and exclusion.is_excluded:
        for c in exclusion.excluded:
            reasons.append(f"매입제외 — {c.label} ({c.source})")
            reasons.append(c.detail)
        reasons.append(f"참고: 3축 계산상 공급 가능 세대수는 {caps.supply}세대였다")
        return GRADE_EXCLUDED, tuple(reasons)

    if caps.supply == 0:
        reasons.append(f"{b.label} 축 상한이 0세대 — 필수조건 미충족")
        reasons.append(b.basis)
        return GRADE_EXCLUDED, tuple(reasons)

    reasons.append(
        f"병목은 {b.label} 축 — 공급 가능 {caps.supply}세대 "
        f"({floors}개 주거층 기준)"
    )
    for a in caps.axes:
        if a.not_applicable:
            reasons.append(f"{a.label}: 해당 없음 — {a.basis}")
        else:
            reasons.append(f"{a.label}: {a.basis}")

    conditional: list[str] = []
    if not caps.complete:
        conditional.append(caps.note)
    if exclusion is not None and exclusion.unknown:
        names = ", ".join(c.label for c in exclusion.unknown)
        conditional.append(
            f"매입제외 항목 {len(exclusion.unknown)}건 미확인 — {names}"
        )

    if conditional:
        reasons.extend(conditional)
        return GRADE_CONDITIONAL, tuple(reasons)

    if caps.bottleneck == "plan":
        reasons.append("인프라 여유가 있어 추가 투자 없이 공급 가능하다")
    else:
        reasons.append(f"{b.label} 보강이 선행되어야 평면 상한만큼 공급할 수 있다")
    return GRADE_PASS, tuple(reasons)
