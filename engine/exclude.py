"""⓪ exclude — 매입제외 사전판정.

3축을 계산하기 전에 먼저 답해야 할 질문이 있다: **LH 가 이 건물을 애초에 매입하는가.**
세대수를 아무리 많이 낼 수 있어도 제외 대상이면 답은 0이다. 이 단계가 없으면
매입 자체가 불가능한 건물에 "80세대 가능" 이라고 답하게 된다.

조건은 셋으로 갈린다.

- **auto**  도면·건축물대장만으로 판정된다.
- **ask**   사실관계(소유·분쟁·용도 사용실태)라 도면에 없다. 답을 받아야 한다.
- **geo**   위치와 주변시설 데이터가 필요하다.

확인되지 않은 것을 통과로 처리하지 않는다. 하나라도 미확인이면 '통과' 가 아니라
'조건부 통과' 다 — LH 자체 3구분(공고 '통과, 조건부 통과, 매입제외')의 가운데다.
"""

from __future__ import annotations

from dataclasses import dataclass

from .contracts import (
    Building,
    ContractError,
    ExclusionCondition,
    Exclusions,
    FloorPlan,
)

#: 판정 결과. 순서가 곧 심각도이며 등급 결정에 쓴다.
STATUS = ("excluded", "unknown", "ok")

STATUS_LABEL = {
    "excluded": "매입제외",
    "unknown": "미확인",
    "ok": "해당 없음",
}

#: LH 공고의 3구분을 그대로 쓴다. 자체 등급을 새로 만들면 심의 용어와 어긋난다.
GRADE_EXCLUDED = "매입제외"
GRADE_CONDITIONAL = "조건부 통과"
GRADE_PASS = "통과"


@dataclass(frozen=True)
class ExclusionCheck:
    id: str
    label: str
    status: str
    detail: str
    source: str
    check: str  # auto | ask | geo

    @property
    def status_label(self) -> str:
        return STATUS_LABEL[self.status]


@dataclass(frozen=True)
class ExclusionResult:
    checks: tuple[ExclusionCheck, ...]

    @property
    def excluded(self) -> tuple[ExclusionCheck, ...]:
        return tuple(c for c in self.checks if c.status == "excluded")

    @property
    def unknown(self) -> tuple[ExclusionCheck, ...]:
        return tuple(c for c in self.checks if c.status == "unknown")

    @property
    def is_excluded(self) -> bool:
        return bool(self.excluded)

    @property
    def grade(self) -> str:
        if self.excluded:
            return GRADE_EXCLUDED
        if self.unknown:
            return GRADE_CONDITIONAL
        return GRADE_PASS

    @property
    def summary(self) -> str:
        if self.excluded:
            return "매입제외 — " + "; ".join(c.label for c in self.excluded)
        if self.unknown:
            return f"미확인 {len(self.unknown)}건 — 확인 전에는 통과로 볼 수 없다"
        return "매입제외 사유 없음"


# ---------------------------------------------------------------- auto 규칙


def _rule_residential_floor_below(
    cond: ExclusionCondition, building: Building, floors: tuple[FloorPlan, ...]
) -> tuple[str, str]:
    """분석 대상 주거층에 지정 층수 미만이 있는가 (지하·반지하 세대)."""
    limit = int(cond.param)
    bad = sorted(f.floor for f in floors if f.floor < limit)
    if bad:
        return "excluded", f"주거 대상 층에 {limit}층 미만이 있다: {bad}"
    return "ok", f"분석 대상 층이 모두 {limit}층 이상 ({sorted(f.floor for f in floors)})"


def _rule_building_flag_true(
    cond: ExclusionCondition, building: Building, floors: tuple[FloorPlan, ...]
) -> tuple[str, str]:
    """building.json 의 불리언 필드가 참이면 제외. None 이면 미확인."""
    field = str(cond.param)
    if not hasattr(building, field):
        raise ContractError(
            f"exclusions.json:{cond.id}: building 에 '{field}' 필드가 없다."
        )
    v = getattr(building, field)
    if v is None:
        return "unknown", f"building.json 의 '{field}' 가 미입력이다"
    if v:
        return "excluded", f"building.json 의 '{field}' 가 참이다"
    return "ok", f"building.json 의 '{field}' 가 거짓이다"


_AUTO_RULES = {
    "residential_floor_below": _rule_residential_floor_below,
    "building_flag_true": _rule_building_flag_true,
}


# ---------------------------------------------------------------- 판정


def check(
    exclusions: Exclusions,
    building: Building,
    floors: tuple[FloorPlan, ...],
) -> ExclusionResult:
    """조건을 선언 순서대로 판정한다. 순서가 고정이라 결과가 결정론적이다."""
    answers = building.exclusion_answers
    out: list[ExclusionCheck] = []

    for cond in exclusions.conditions:
        if cond.is_auto:
            fn = _AUTO_RULES.get(cond.rule or "")
            if fn is None:
                raise ContractError(
                    f"exclusions.json:{cond.id}: 알 수 없는 rule '{cond.rule}'. "
                    f"구현된 규칙: {', '.join(sorted(_AUTO_RULES))}."
                )
            status, detail = fn(cond, building, floors)
        elif cond.id in answers:
            # 답은 "제외 사유에 해당하는가" 로 받는다. 참이면 제외다.
            hit = answers[cond.id]
            status = "excluded" if hit else "ok"
            detail = f"building.json 의 exclusion_answers 로 답변됨 ({hit})"
        else:
            status = "unknown"
            detail = cond.needs_label or "답변 없음"
            # 판단 재료가 있으면 함께 보여준다. 판정은 하지 않는다.
            if cond.id == "use_change_impossible" and building.zoning:
                detail += " · 수집된 지정사항 — " + "; ".join(
                    f"{k}: {', '.join(v)}" for k, v in building.zoning.items()
                )

        out.append(
            ExclusionCheck(
                id=cond.id,
                label=cond.label,
                status=status,
                detail=detail,
                source=cond.source,
                check=cond.check,
            )
        )

    return ExclusionResult(tuple(out))
