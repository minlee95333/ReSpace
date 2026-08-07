# TECH-SPEC — Re:Space

작성일: 2026-08-07
설계 근거: `docs/plans/2026-08-07-lh-respace-design.md`

---

## 1. 구성

```
[ 기준 데이터 ]  rules.json / units.json
                      │
[ 엔진 ]         Python 3.11+, 화면을 모름
                 floor_plan.json + building.json → result.json + *.svg
                      │
[ 표현 ]         HTML 대시보드, 계산을 모름 — result.json 을 읽어 렌더
```

의존성은 최소로 유지한다. 실행은 `run.bat` 하나로 감싸 비개발자가 명령어 없이 돌린다.

**계층 규칙**: 엔진은 대시보드를 import 하지 않는다. 렌더러(SVG)는 엔진 안에 있으나
판정 로직에 의존만 하고 역방향은 없다.

---

## 2. 좌표계와 단위

| 항목 | 규칙 |
|---|---|
| 입력 좌표 단위 | **mm** (정수) |
| 원점 | 각 층 도면의 좌하단. 층 간 원점은 일치해야 함 |
| 격자 | 600mm 정사각 |
| 격자 인덱스 | `(col, row)`, 좌하단 `(0,0)`, col 은 +x, row 는 +y |
| 원점 오프셋 | `boundary` 바운딩박스 최소점을 격자 원점으로 삼고 `grid_origin_mm` 에 기록 |

결과를 원래 좌표계로 되돌리려면 `grid_origin_mm` 과 `grid_mm` 이 함께 필요하다.
둘 다 `result.json` 에 기록한다.

---

## 3. 입력 규격

### 3.1 `floor_plan.json` — 층마다 1개

```jsonc
{
  "floor": 5,
  "unit": "mm",
  "boundary": [[0,0],[36000,0],[36000,18000],[0,18000]],   // 외벽 폴리곤, CCW
  "cores": [
    {"type": "stair", "rect": [16800, 7200, 3600, 3600]},  // [x, y, w, h]
    {"type": "ev",    "rect": [20400, 7200, 2400, 3600]}
  ],
  "shafts":  [{"rect": [15600, 7200, 1200, 3600]}],
  "columns": [{"center": [7200, 3600], "size": [600, 600]}],
  "windows": [
    {"start": [0,0], "end": [36000,0], "sill": 900, "height": 1500}
  ]
}
```

| 필드 | 의미 | 비고 |
|---|---|---|
| `boundary` | 외벽 폴리곤 꼭짓점 | 닫힌 폴리곤, 첫 점 반복 금지 |
| `cores[].type` | `stair` \| `ev` | **피난 BFS 출발점은 `stair` 만** |
| `shafts` | PS 등 설비 샤프트 | 배치 불가 영역이자 재사용률 기준점 |
| `columns` | 기둥 중심과 단면 | 배치 불가 |
| `windows` | 창 구간 | **독립 좌표.** 외벽 변 인덱스를 쓰지 않음 |

`windows` 를 변 인덱스가 아닌 독립 좌표로 두는 이유: IFC 에서 창을 추출하면 벽과의
관계가 아니라 절대 좌표로 나오고, 사람이 입력할 때도 변 인덱스를 세는 것은 실수가 잦다.

**DWG 처리 방침**: DWG 는 비공개 바이너리 포맷이며 국내 도면의 레이어 명명 규칙이
표준화돼 있지 않아 자동 추출은 오류 위험이 크다. **사람이 CAD 에서 외벽·코어·창호를
지정해 중간표현으로 내보내는 단계를 명시적으로 둔다.** 자동화 실패가 아니라 설계 판단이다.

### 3.2 `building.json`

```jsonc
{
  "name": "에스키스 가산 (공개정보 재구성)",
  "use": "숙박시설",
  "approval_year": 2003,
  "gfa_m2": 24000,
  "floors_total": 19,
  "floors_residential": [4, 19],      // 주거 전환 대상 층 범위 (inclusive)
  "seismic": true,
  "fire_resistant": true,             // → 피난 한계 50m
  "floor_height_mm": 3000,
  "parking_existing": 30,
  "septic_capacity_m3": 45.0,
  "source_note": "원본 도면 아님. 공개 정보 기반 재구성"
}
```

### 3.3 `rules.json` — 법규 수치 전부

```jsonc
{
  "version": "2026-08-07",
  "grid_mm": 600,
  "corridor_width_mm": 1800,
  "corridor_side_usable_coverage": 0.5,   // 알고리즘 파라미터 (법규 아님)
  "shaft_reuse_threshold_cells": 12,      // 7.2m. 재사용률 정의이자 저개입형 한계
  "ceiling_min_mm": 2100,
  "daylight": { "area_ratio": 0.1 },
  "egress": {
    "base_m": 30,
    "fire_resistant_m": 50,
    "highrise_m": 40,
    "highrise_from_floor": 16,
    "all_cores": true            // 스위치. 4.2절 참조
  },
  "parking": [
    { "max_area_m2": 30, "exclusive": true,  "coef": 0.5 },
    { "max_area_m2": 60, "exclusive": false, "coef": 0.6 }
  ],
  "septic": {
    "persons_per_unit": null,    // 미확정 — 하수도법 시행령 별표 확인 필요
    "load_lpcd": null            // 미확정
  }
}
```

`egress.all_cores` 는 `true` / `false` 양쪽을 실행해 비교한다.
`true` 이면 셀 판정이 `max(각 stair 코어까지 거리) ≤ 한계`, `false` 이면 `min(...) ≤ 한계`.

**하드코딩 금지**: 위 수치는 코드에 나타나면 안 된다.

### 3.4 `units.json`

```jsonc
[
  { "id": "youth",    "label": "청년형", "w_mm": 3000, "d_mm": 6000, "area_m2": 18.0 },
  { "id": "newlywed", "label": "신혼형", "w_mm": 4800, "d_mm": 6000, "area_m2": 28.8 }
]
```

600mm 격자에서 각각 5×10셀, 8×10셀. 둘 다 전용 30㎡ 미만이라 주차 계수 0.5.

---

## 4. 셀 상태

| 값 | 의미 | 배치 |
|---|---|---|
| `FREE` | 사용가능 | 가능 |
| `CORE` | 계단·EV | 불가 |
| `SHAFT` | 설비 샤프트 | 불가 (인접 셀은 재사용률 가점) |
| `COLUMN` | 기둥 | 불가 |
| `CORRIDOR` | 복도 | 불가 (통행) |
| `OUTSIDE` | 외벽 밖 | 불가 |

부분적으로 걸치는 셀은 **보수적으로** 처리한다 — 기둥·코어·샤프트가 셀에 조금이라도
걸치면 그 셀 전체를 해당 상태로 본다.

---

## 5. 모듈 규격

| # | 모듈 | 입력 | 출력 |
|---|---|---|---|
| ① | `load` | 파일 경로 | 검증된 dict + SHA-256 해시 |
| ② | `gridify` | floor_plan, rules | `Grid(cells, origin_mm, grid_mm)` |
| ③ | `corridor` | Grid | Grid(CORRIDOR 마킹), `corridor_type` |
| ④ | `reachability` | Grid, rules, building | `dist[cell] → m`, `blocked[]` |
| ⑤ | `place` | Grid, units, 전략 | `placed[]`, `leftover[]` |
| ⑥ | `daylight` | placed, windows, rules | `placed[].daylight_ratio`, 탈락 목록 |
| ⑦ | `common` | leftover | `common_areas[]` |
| ⑧ | `caps` | 전 층 placed, building, rules | `caps`, `bottleneck` |
| ⑨ | `emit` | 전부 | `result.json`, `*.svg` |

③~⑦ 은 층마다, ⑧ 은 전 층 합계로 1회 실행.

### 5.1 ③ corridor

```
코어(stair+ev) 2개 이상 → 코어 중심 잇는 격자 경로(직선 또는 L자), 폭 3셀
코어 1개                → boundary 바운딩박스 장변 방향으로 코어에서 양쪽 연장
```

축 확정 후 양옆 깊이 측정:

| 조건 | 결과 |
|---|---|
| 양쪽 다 ≥ 10셀(6m) | `corridor_type = "double"` (중복도) |
| 한쪽만 ≥ 10셀 | `corridor_type = "single"`, 복도를 외벽 쪽으로 오프셋 |
| 어느 쪽도 미달 | 해당 구간 배치 불가 → `common` 후보 |

### 5.2 ④ reachability

`cores[].type == "stair"` 셀을 출발점으로 `CORRIDOR` + `FREE` 위 4방향 BFS.
거리 = 셀 수 × `grid_mm` / 1000 (m).

한계값 선택:

```
limit = highrise_m   if building.floors_total >= 16 and floor >= 16
        fire_resistant_m  if building.fire_resistant
        base_m            otherwise
```

### 5.3 ⑤ place

- **유닛은 외벽에 붙인다.** 복도에 붙이면 깊은 평면에서 창에 닿지 못해 ⑥ 에서
  전멸한다. 복도와 유닛 사이에 남는 띠는 ⑦ 이 공용으로 가져간다.
  여러 레인에 걸치면 가장 얕은 레인에 맞춘다(보수적).
- 유닛 깊이는 복도 수직 방향 10셀 고정. 회전 배치 없음.
- **스캔 순서**: 좌상단부터 행 우선(row-major). 동점이면 인덱스 낮은 쪽.
- 난수 없음. 같은 입력 → 같은 배치.

전략별 차이:

| 전략 | 후보 선택 키 | 제약 |
|---|---|---|
| `supply` (공급우선형) | `(side, lane, type_index)` | 없음 |
| `balanced` (균형형) | `(side, lane, 해당 유형 배치수, type_index)` — 적게 놓인 유형을 먼저 집어 교대가 된다 | 없음 |
| `minimal` (저개입형) | `(샤프트 거리, side, lane, type_index)` | **`shaft_reuse_threshold_cells` 밖 배치 금지** |

`_fits` 는 유닛 사각형의 **모든 셀**이 FREE 이고 미점유이며 피난 한계 이내일 것을
요구한다. 보행거리는 "거실의 각 부분"이 기준이므로 유닛 전체를 본다 (보수적).
`egress_dist_m` 은 유닛 셀 중 **최댓값**을 기록한다.

저개입형의 배치 금지 제약이 없으면 그리디가 먼 자리까지 다 채워 공급우선형과 같은
집합이 되고, 설비 재사용률이 오히려 낮아진다 (실측: 33.3% vs 37.5%).
샤프트 입력이 없는 건물에서 저개입형이 0세대가 되는 것은 의도된 결과다.

### 5.4 ⑥ daylight

유닛별로 접한 외벽 구간과 `windows` 를 교집합해 창 길이를 구한다.

```
window_area = Σ(교집합 길이) × window.height
required    = unit.area_m2 × rules.daylight.area_ratio
pass        = window_area >= required
```

창 접면이 0 인 유닛은 `no_window`, 비율 미달은 `daylight_short` 로 탈락하며
둘 다 ⑦ 로 넘어간다. 거리 기반 값(창에서 유닛 최심부까지 깊이)은
`depth_from_window_m` 로 **기록만** 한다 (법정 요건 아님, 거주성 보조지표).

`_segment_on_rect` 는 **축 정렬 창만** 지원한다. 대각선 창은 조용히 0 을 돌려주면
유닛이 부당하게 탈락하므로 `ContractError` 를 던진다.

모서리 유닛은 두 변에서 창을 받는다 (G2 실측: 아래변 3000 + 좌변 6000 = 9000mm,
비율 0.75). 중간 유닛은 한 변만 (3000mm, 비율 0.25). 둘 다 기준 0.1 을 넘는다.

### 5.5 ⑦ common

잔여 영역을 사유별로 묶는다. 사유 우선순위:
`egress_over_limit` > `no_window` > `daylight_short` > `geometry`.

- **탈락 유닛은 사각형 그대로** 내보낸다. 잔여 영역에 흡수시키면 "왜 여기가 세대가
  아닌가"가 큰 덩어리에 뭉개진다.
- **피난 초과 셀은 따로 성분을 만든다.** 통과 셀과 섞어 4-연결로 묶으면 통과 셀 하나
  때문에 초과 구역 전체가 `geometry` 로 뭉개져 화면에서 사라진다.
- 불변식: `FREE 면적 = 세대 면적 + 공용 면적`. 전 골든케이스에서 검증한다.
- 공용 영역은 FREE 셀만 덮는다. 한계를 넘은 복도 셀은 여전히 복도다.

### 5.6 ⑧ caps

```
plan    = Σ 층별 채광 통과 세대수
parking = int(parking_existing / 배치 구성의 평균 주차계수)
septic  = int(septic_capacity_m3 × units_per_m3)

supply     = min(확보된 축)
bottleneck = argmin
```

**입력이 없는 축은 숫자를 지어내지 않고 `value: null` + `blocked_reason` 으로 낸다.**
파이프라인은 멈추지 않고, 확보된 축만으로 낸 **잠정 상한**임을 `complete: false` 와
`note` 로 명시한다. 기본값을 넣으면 틀린 수치가 제안서까지 흘러간다.

주차 계수는 배치된 유형 구성의 **평균**을 쓴다. 유형마다 전용면적이 달라 계수가
갈리기 때문이다(현재 유형은 둘 다 0.5).

**판정 등급** (설계 7.2절, 판정에는 반드시 이유가 붙는다)

| 조건 | 등급 |
|---|---|
| `supply == 0` | 부적합 |
| 미확보 축이 있음 | 조건부 검토 |
| 병목이 주차·정화조 | 검토 가능 (인프라 보강 선행 필요) |
| 병목이 평면 | 우선검토 (추가 투자 없이 공급 가능) |

### 5.7 층 확장

기준층 도면 1개만 주고 `building.floors_residential` 을 지정하면 그 범위만큼
반복 분석한다. 층마다 피난 한계가 달라질 수 있으므로(16층 이상 40m) **실제 층
번호로 각각 계산**한다. 층별 도면이 모두 있으면 그대로 쓴다.

---

## 6. 출력 규격

### 6.1 `result.json`

```jsonc
{
  "meta": {
    "generated_at": "2026-08-13T10:00:00+09:00",   // 회귀 비교에서 제외
    "rules_version": "2026-08-07",
    "strategy": "balanced",
    "input_hash": {
      "building.json": "sha256:...",
      "floor_plan_05.json": "sha256:...",
      "rules.json": "sha256:...",
      "units.json": "sha256:..."
    },
    "grid_mm": 600,
    "grid_origin_mm": [0, 0]
  },
  "per_floor": [
    {
      "floor": 5,
      "corridor_type": "double",
      "units": [
        {
          "type": "youth",
          "rect_mm": [1200, 600, 3000, 6000],
          "daylight_ratio": 0.125,
          "egress_dist_m": 22.8,
          "shaft_dist_m": 9.6,
          "depth_from_window_m": 6.0,
          "ok": true
        }
      ],
      "common_areas": [{ "rect_mm": [...], "reason": "no_window" }],
      "rejected":     [{ "rect_mm": [...], "reason": "egress_over_limit" }]
    }
  ],
  "caps": {
    "axes": [
      { "axis": "plan",    "label": "평면",  "value": 100,
        "basis": "층별 배치 세대수 합계 100세대", "blocked_reason": null },
      { "axis": "parking", "label": "주차",  "value": 40,
        "basis": "기존 20대 ÷ 평균계수 0.50 = 40세대", "blocked_reason": null },
      { "axis": "septic",  "label": "정화조", "value": null,
        "basis": "정화조 원단위 미확정",
        "blocked_reason": "rules.septic 파라미터가 미확정(null)이다 …" }
    ],
    "supply": 40,
    "bottleneck": "parking",
    "bottleneck_label": "주차",
    "complete": false,
    "note": "정화조 축 입력 미확보 — 확보된 축만으로 낸 잠정 상한이다."
  },
  "quantities": {
    "units_total": 100,
    "demo_wall_m": null,          // 기존 내부 벽이 입력 규격에 없어 산출 불가
    "new_wall_m": 840.0,
    "shaft_reuse_ratio": 0.0,
    "common_area_m2": 180.0,
    "parking": { "basis": "평면 상한 세대수 전량 실현 기준",
                 "required": 50.0, "existing": 20, "shortfall": 30.0 },
    "septic":  { "basis": "평면 상한 세대수 전량 실현 기준",
                 "required_m3": null, "existing_m3": 30.0, "shortfall_m3": null }
  },
  "verdict": {
    "grade": "조건부 검토",
    "reasons": ["병목은 주차 축 — 공급 가능 40세대 (5개 주거층 기준)", "…"]
  },
  "disclaimer": "본 결과는 매입 전 사전검토를 위한 개략분석이며, …"
}
```

`quantities` 에 단가·금액 필드는 **없다.** 총사업비는 대시보드에서
사용자 입력 단가 × 물량으로 계산해 표시하며 "단가는 사용자 입력"임을 화면에 명시한다.
부족분은 **평면 상한 전량을 실현할 때** 기준이며, 이 값이 곧 "병목을 풀려면 무엇을
얼마나 보강해야 하는가"가 된다.

`shaft_dist_cells` 는 샤프트가 없으면 `null` 이다. 내부 정렬용 대체값이 결과로
새어나가지 않는다(회귀 테스트로 고정).

### 6.2 SVG

층별 1개 (`floor_NN.svg`). 축척 0.02 px/mm (36m → 720px). 외부 의존성 없음.

| 요소 | 표현 |
|---|---|
| 외벽 | 검정 외곽선 |
| 코어 / 샤프트 / 기둥 | 회색~검정 채움 |
| 복도 | 옅은 회색 면 |
| 배치 유닛 | 유형별 색 (청년 파랑 / 신혼 보라) |
| 공용 전환 영역 | 사유별 색 반투명 (피난 빨강 / 창 미접 주황 / 채광 부족 연노랑 / 형상 회색) |

`generated_at` 은 **호출자가 넘긴다.** 엔진이 시계를 읽으면 같은 입력에 같은 출력이라는
전제가 깨져 회귀 비교를 할 수 없다.

### 6.3 실행

```
python -m engine.inspect <building_dir>              도면 입력 검사 (격자 그림)
python -m engine.report  <building_dir> [--out DIR] [--all-strategies]
run.bat check|report|test ...                        비개발자용 래퍼
```

---

## 7. 테스트

### 7.1 회귀 (골든케이스)

손으로 검산되는 인공 평면. 기대값을 고정한다.

| # | 평면 | 기대 | 상태 |
|---|---|---|---|
| G1 | 30×12m, 중앙 코어 1개 | **세대 0** — 복도 제외 시 양옆 8·9셀 < 10셀 | 통과 |
| G2 | 30×15m, 중앙 코어 1개 | 중복도 성립(양옆 11셀), 공급우선형 20세대 | 통과 |
| G3 | 36×21m, 외벽 앞 샤프트 덩어리 + 끊긴 창 | 24배치 → 17통과, `no_window` 6 · `daylight_short` 1 | 통과 |
| G4 | 코어 1개, 장변 60m | 원단부 한계 초과 357셀, `all_cores` 무관 | 통과 |
| G5 | 코어 2개 양단 배치 | `all_cores` true/false 로 결과가 갈림 | 통과 |

**G5 가 확인한 것 — `egress.all_cores` 스위치의 실제 영향**

| `all_cores` | 한계 초과 셀 | 공급우선형 세대수 |
|---|---:|---:|
| `false` (가장 가까운 계단) | 0 | 40 |
| `true` (모든 계단 충족) | 678 | 24 |

같은 60×15m 평면에서 계단 1개인 G4 는 초과 357셀, 계단 2개인 G5 는 678셀이다.
**계단을 늘리면 불리해진다**는 역설이 수치로 확인됐다. 제안서에 어느 값을 쓸지는
이 대비를 근거로 정한다 (PROGRESS.md 미결정 ⑨).

### 7.2 사례 대조 (테스트 아님)

에스키스 가산. 실제 층당 11~12세대와 **다르게 나오는 것이 정상**이며 차이와 원인이
제안서 내용이 된다. 테스트에 포함하면 맞추려고 파라미터를 조정하게 되므로 분리한다.

### 7.3 결정론

`meta.generated_at` 을 제외한 `result.json` 전체가 같은 입력에 대해 바이트 단위로 동일해야 한다.

---

## 8. 미구현 / 미확정

| 항목 | 상태 |
|---|---|
| IFC 입력 어댑터 | 미구현. 제안서상 아키텍처로만 존치 |
| `septic.persons_per_unit`, `load_lpcd` | **미확정** — 하수도법 시행령 별표 확인 필요 |
| 용도지역별 주택 허용 조건 | **미확정** — 상업지역·준공업지역 차이 |
| 내부 벽 입력 | 규격 없음. 저개입형을 설비 재사용률로 재정의해 회피 |
| 반자 높이 판정 | `building.floor_height_mm` 입력만 받고 필터로 사용 |
