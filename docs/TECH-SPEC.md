# TECH-SPEC — Re:Space

작성일: 2026-08-07
설계 근거: `docs/plans/2026-08-07-lh-respace-design.md`

---

## 1. 구성

```
[ 외부 자료 ]    건축물대장 API          DXF 평면도
                      │                      │
[ 어댑터 ]       adapters/bdrg           adapters/dxf
                 (수치)                  (형상)
                      ↓                      ↓
                 building.json          floor_plan_NN.json
                      │                      │
[ 기준 데이터 ]  rules.json / units.json / exclusions.json / dxf_lexicon.json
                      │
[ 엔진 ]         Python 3.11+, 화면을 모름
                 floor_plan.json + building.json → result.json + *.svg
                      │
[ 표현 ]         HTML 대시보드, 계산을 모름 — result.json 을 읽어 렌더
```

**계층이 하나 늘었다 (2026-08-10).** 어댑터는 입력 계약 파일을 **만들기만** 하고,
엔진은 그 파일만 읽는다. 엔진은 어댑터를 import 하지 않는다 — 대시보드와 같은 방향의 단절이다.
어댑터가 없어도 엔진은 그대로 돌고, 어댑터를 바꿔도 엔진은 모른다.

입력 조달 방침: LH 가 받는 신청 서류 묶음 **원본은 대외비**다(공고가 심의용 도면조차
블라인드 처리를 요구한다). 그러나 그 안의 **수치는 대부분 공개**다 — 건축물대장이
표제부·층별개요·**오수정화시설**을 무료로 개방한다. 막히는 것은 평면 형상뿐이고
그것만 DXF 가 맡는다.

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

**CAD 처리 방침 (2026-08-10 개정).** 종전 방침은 *"레이어 명명이 표준화돼 있지 않으니
사람이 CAD 에서 외벽·코어·창호를 지정한다"* 였다. 이를 **철회한다.**

레이어명이 제각각인 것은 맞다. 그러나 한국 도면에는 **실명(室名) 텍스트**가 거의 항상
들어간다 — 계단실에 "계단실"이라고 쓰지 않는 도면은 없다. 레이어명보다 훨씬 안정적인
신호가 이미 도면 안에 있었던 것이다. 따라서 신호 순위를 이렇게 둔다.

1. 실명 텍스트 (TEXT/MTEXT) — 닫힌 영역 안의 문자열이 그 영역의 역할을 정한다
2. 기하 특성 — 최대 닫힌 폴리라인 = 외곽, 작은 반복 사각형 = 기둥
3. 레이어명 — **보조.** KS F 1542 패턴을 사전에 넣어 두었으나 전제하지 않는다

레이어 표준(건설CALS 전자도면 작성표준 / KS F 1542)을 전제하지 않는 이유: ①CALS 는
공공 발주 건설사업 납품 체계인데 매입 대상은 민간 건축물의 준공도면이고 ②KS 는
임의표준이며 LH 공고·가이드라인 어디에도 레이어 요구가 없고 ③대상 건물 상당수가
KS F 1542 제정(2010) 이전 준공이다.

**DWG 는 지원하지 않는다.** ASCII DXF 로 내보내야 한다 — 비공개 바이너리를 직접
읽으면 의존성이 늘고 오류를 조용히 삼킨다.

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
  "septic_capacity_persons": 440,     // 건축물대장 capaPsper. 실무상 이쪽이 채워진다
  "septic_capacity_m3": 45.0,         // capaLube. 실 표본에서는 대개 0
  "septic_mode_raw": "부패탱크방법",   // modeCdNm — 형식이 아니라 처리공법이다
  "septic_mode_code": "201",          // modeCd — 앞자리가 분류 (1/2/3)
  "violation": false,                 // 위반건축물. 미수집이면 null → '미확인'
  "exclusion_answers": { "development_zone": false },
  "source_note": "원본 도면 아님. 공개 정보 기반 재구성"
}
```

`septic_*` 4종은 `adapters/bdrg` 가 건축물대장에서 채운다. **용량(㎥)이 아니라
처리대상인원이 실질 경로다** — 실 API 표본에서 `capaLube` 는 거의 전부 0 이었다.
`exclusion_answers` 는 도면에 없는 사실관계(소유·분쟁·개발예정지구)의 답이며,
비어 있으면 해당 항목이 '미확인'으로 남아 등급이 '조건부 통과'가 된다.

### 3.3 `rules.json` — 법규 수치 전부

```jsonc
{
  "version": "2026-08-10",
  "grid_mm": 600,
  "corridor_width_mm": 1800,          // 중복도
  "corridor_single_width_mm": 1200,   // 편복도. 2패스로 유형↔폭 순환을 푼다
  "corridor_side_usable_coverage": 0.5,   // 알고리즘 파라미터 (법규 아님)
  "shaft_reuse_threshold_cells": 12,      // 7.2m. 재사용률 정의이자 저개입형 한계
  "ceiling_min_mm": 2300,
  "community": {                      // LH 공고 p5
    "required_from_households": 50,
    "area_per_household_m2": 1.0,
    "guard_office_from_households": 50,
    "admin_office_from_households": 150
  },
  "daylight": { "area_ratio": 0.1 },
  "egress": {
    "base_m": 30,
    "fire_resistant_m": 50,
    "highrise_m": 40,
    "highrise_from_floor": 16,
    "all_cores": false           // 건축법 시행령 제34조① — 가장 가까운 1개소 기준
  },
  "parking": {
    "mode": "statutory",              // 스위치. 아래 modes 중 하나
    "modes": {
      "statutory":     { "bands": [...], "default_coef": 1.0 },
      "relaxed_037_4": { "flat_coef": 0.3, "max_exclusive_area_m2": 30,
                         "fallback": "statutory" }
    }
  },
  "septic": {
    "modes": {                        // 건축물대장 modeCd 앞자리로 분류
      "sewage_treatment": { "limits": true,  "volume_conversion": false, "code_prefix": "1" },
      "septic_tank":      { "limits": true,  "volume_conversion": true,  "code_prefix": "2" },
      "public_sewer":     { "limits": false, "volume_conversion": false, "code_prefix": "3" }
    },
    "tank_volume": {                  // 하수도법 시행규칙 [별표 12]
      "small_m3": 1.0, "small_persons_max": 3,
      "base_m3": 1.5,  "base_persons": 5,
      "increment_m3": 0.5, "increment_persons": 5
    },
    "person_per_m2_by_use": {         // 기후에너지환경부고시 제2025-165호 별표
      "숙박시설": 0.080, "업무시설": 0.075,
      "오피스텔": 0.050, "기숙사": 0.038
    }
  }
}
```

**주차 모드**는 병목이 기준에 따라 뒤집히는 것을 시연하는 스위치다. `relaxed_037_4` 는
공공주택특별법 시행령 제37조④ 의 0.3대이며, 조문이 *"전용면적이 30㎡ 미만인 **세대는**"*
이라고 세대 단위로 쓰므로 혼합 구성이면 기준을 넘는 세대는 `statutory` 로 떨어진다.
조문에 입지 요건은 없다 — LH 공고가 운영상 역세권 500m 를 추가로 건다.
**제37조⑤(종전 용도 기준)** 은 계수가 아니라 **축을 없애는** 특례다. 요건을 모두 갖추면
용도변경 전 용도로 부설주차장을 보므로, 사용승인을 받은 건물이면 기존 주차가 이미 그
기준을 충족한다 — 세대수가 늘어도 추가를 요구하지 않는다. `AxisCap.not_applicable` 로 낸다.

대상이 **제37조①제3호(제1·2종 근생, 노유자, 수련, 업무, 숙박)로 한정**된다는 점이 중요하다.
공동주택·단독주택은 못 받는다. 즉 **비주택만** 받을 수 있어 이 사업의 정의와 정확히 겹친다.
요건1의 「주택법 시행령」 제4조 각 호는 **준주택**(기숙사·다중생활시설·노인복지주택·오피스텔)
이므로, 공동주택으로 변경하면 특례를 못 받는다. 요건을 하나라도 못 맞추면 통상 계수로
떨어지며 그 사유가 판정 근거에 남는다 — 특례를 못 받는 쪽이 보수적이다.

**정화조 처리방식 3갈래**는 `modeCd` 앞자리로 가른다 (1=오수처리시설, 2=정화조,
3=공공하수도 연결). 공법 이름은 수십 종이지만 앞자리는 안정적이라, 처음 보는 공법이
와도 분류된다. **공공하수도에 연결된 건물은 정화조 축이 '해당 없음'이다** — 이것을
'미확보'와 같게 다루면 없는 병목이 생긴다. 도심 건물 상당수가 여기에 해당한다.

**정화조 파라미터의 위치**: 세대당 처리대상인원은 유형마다 다르므로(원룸 2.0인,
2거실 2.7인) `units.json` 에 있다. `rules.json` 에는 인원↔용량 환산과 용도별 인원산정식만
둔다. 목록에 없는 용도는 계수를 지어내지 않고 `ContractError` 로 실패한다.

`egress.all_cores` 는 **`false` 로 확정**했다 (2026-08-11, 미결정 ⑨ 종결).
건축법 시행령 제34조① 이 *"거실의 각 부분으로부터 **계단(거실로부터 가장 가까운 거리에
있는 1개소의 계단을 말한다)** 에 이르는 보행거리"* 로 괄호 안에 정의를 박아 두었다.
`true` 이면 셀 판정이 `max(각 stair 코어까지 거리) ≤ 한계`, `false` 이면 `min(...) ≤ 한계`.
`true` 로 두면 계단이 늘수록 불리해져 더 안전한 건물을 벌준다 — 스위치는 남기되 기본은 `false`.

**하드코딩 금지**: 위 수치는 코드에 나타나면 안 된다.

### 3.4 `units.json`

```jsonc
[
  { "id": "youth",    "label": "청년형", "w_mm": 3600, "d_mm": 6000,
    "area_m2": 21.6, "rooms": 1, "persons_per_household": 2.0 },
  { "id": "newlywed", "label": "신혼형", "w_mm": 6000, "d_mm": 6000,
    "area_m2": 36.0, "rooms": 2, "persons_per_household": 2.7 }
]
```

600mm 격자에서 각각 6×10셀, 10×10셀.

**면적 하한은 LH 매입 대상 기준이다** (매입 공고 3장 공급유형표).

| 공급유형 | 면적 | 방 개수 |
|---|---|---|
| 청년Ⅱ (리모델링) | 전용 **19㎡ 이상** 60㎡ 이하 | 1개 이상 |
| 신혼·신생아 | 전용 **36㎡ 이상** 85㎡ 이하 | 2개 이상 |

하한 미달이면 매입 대상이 아니라, 세대수를 아무리 많이 뽑아도 무효다. 종전 규격
(18.0 / 28.8㎡)은 둘 다 하한에 걸렸다. 주차 계수 0.5 구간에 넣으려던 최적화가
매입 기준에서 이탈시킨 것이다.

**깊이는 두 유형 모두 6000mm(10셀)로 고정한다.** 복도 양옆 유효깊이 판정이
`units.min_depth_mm` 에 걸려 있어, 깊이를 바꾸면 골든케이스 전체가 흔들린다.
면적은 폭으로만 조정한다.

주차 계수가 유형별로 갈린다 — 청년형 21.6㎡ 는 0.5, 신혼형 36.0㎡ 는 0.6 이다.
**36㎡ 이상은 제37조 완화(30㎡ 미만) 대상에서도 빠진다.** 즉 유형 선택이 주차와
정화조 두 축을 동시에 움직인다.

`persons_per_household` 는 정화조 처리대상인원이다 (기후에너지환경부고시 별표:
공동주택 `N = 2.7+(R−2)×0.5`, 단 1호 1거실이면 2인).

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
| ⓪ | `exclude` | exclusions, building, floors | 매입제외 판정 (auto/ask/geo) |
| ① | `load` | 파일 경로 | 검증된 dict + SHA-256 해시 |
| ② | `gridify` | floor_plan, rules | `Grid(cells, origin_mm, grid_mm)` |
| ③ | `corridor` | Grid | Grid(CORRIDOR 마킹), `corridor_type` |
| ④ | `reachability` | Grid, rules, building | `dist[cell] → m`, `blocked[]` |
| ⑤ | `place` | Grid, units, 전략 | `placed[]`, `leftover[]` |
| ⑥ | `daylight` | placed, windows, rules | `placed[].daylight_ratio`, 탈락 목록 |
| ⑦ | `common` | leftover | `common_areas[]` |
| ⑦-b | `community` | 전 층 placed, rules | 의무면적 반영 후 placed, `CommunityResult` |
| ⑧ | `caps` | 전 층 placed, building, rules | `caps`, `bottleneck` |
| ⑨ | `emit` | 전부 | `result.json`, `*.svg` |

③~⑦ 은 층마다, ⑦-b·⑧ 은 전 층 합계로 1회 실행.
⓪ 는 3축과 무관하게 돌며, 결과가 `verdict` 에서 3축보다 **앞선다**.

**보조 모듈 (엔진 밖).**

| 모듈 | 입력 | 출력 |
|---|---|---|
| `adapters/bdrg` | 시군구·법정동 코드 + 번지 | `building.json` + `_api_cache/*.json` |
| `adapters/dxf` | DXF 파일, 층 번호 | `floor_plan_NN.json` |

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
septic  = int(정화조가 감당하는 처리대상인원 / 배치 구성의 세대당 평균 인원)

supply     = min(확보된 축)
bottleneck = argmin
```

**정화조 축의 계산 사슬** (하수도법 제34조④·제35조② → 시행령 제24조⑤ → 고시 → 시행규칙):

```
용량 → 인원   N_capacity = 5 + (V − 1.5) × 10          [시행규칙 별표12 역산]
              또는 용량 미입력 시 N = 계수 × A(종전 용도 연면적)  [고시 별표]
세대 → 인원   세대당 2.0인(원룸) / 2.7인(2거실)         [고시 별표]
```

**필요 용량은 세대수에 비례하지 않는다.** 1.5㎥ 기본 + 5인당 0.5㎥ 가산이라
원점을 지나지 않는다. 종전의 `septic_capacity_m3 × units_per_m3` 는 선형 비례를
가정해 틀렸다.

용량을 몰라도 종전 용도의 연면적이 있으면 축이 돈다 — *"기존 정화조가 종전 용도의
법정 인원을 감당하도록 설치돼 있다"* 는 가정이며, 실측이 없을 때의 대체 경로다.

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

### 6.3 대시보드 (`dashboard.html`)

**자립형 단일 파일.** 데이터를 HTML 안에 심는다 — `fetch()` 는 `file://` 에서 CORS 로
막히므로 별도 파일을 읽는 방식은 비개발자가 더블클릭으로 열 수 없다. 심어두면
파일 하나가 그대로 공개 링크이자 PT 시연 화면이 된다. 외부 리소스 참조 0.

- UI 는 `dashboard/template.html` (편집 가능한 실제 HTML)
- `engine/dashboard.py` 가 `<!--RESPACE_DATA-->` 자리에 `window.__RESPACE__` 를 주입
- 데이터의 `</` 를 `<\/` 로 이스케이프해 스크립트 블록 조기 종료를 막는다
- 계산은 엔진에, 표현은 템플릿에. 추천안 선정도 엔진(`pipeline.recommend`)에 둔다

**4화면** — ① 후보 건물 ② 건물 상세분석 ③ 대안 비교 ④ 검토보고서.
모든 화면 상단에 **몇 세대 / 무엇이 병목 / 무슨 위험**을 고정 표시한다(설계 7.1절 UI 원칙).

**해시 라우팅** `#t2/b1/f3` = 대안 비교 · 두 번째 건물 · 4번째 층. 링크 공유와
헤드리스 캡처에 쓴다.

**추천안 선정** (`pipeline.recommend`)
1. 공급 가능 세대수가 많은 안
2. 동수면 설비 재사용률이 높은 안 (배관 신설 적음)
3. 그것도 같으면 신설 벽체가 적은 안 (같은 결과면 덜 뜯는 쪽)

인프라가 병목이면 여러 안이 같은 공급량에 걸리므로 2·3 이 실제 갈림길이 된다.

### 6.4 실행

```
python -m engine.inspect <building_dir>                 도면 입력 검사 (격자 그림)
python -m engine.report  <dir> [<dir> ...] [--out DIR]  result.json + SVG + dashboard.html
run.bat check|report|test ...                           비개발자용 래퍼
```

### 6.5 배포

**https://respace-production.up.railway.app** (Railway, 프로젝트 `respace`)

```
railway up            재배포 (한 줄)
railway domain        도메인 확인
railway logs          로그
railway usage         크레딧 사용량
```

`railway.json`

| 단계 | 명령 |
|---|---|
| build | `python -m unittest discover -s tests -t . && python -m engine.report … --dashboard public/index.html` |
| start | `python -m http.server $PORT --directory public` |

**빌드 단계에서 테스트를 먼저 돌린다.** 실패하면 배포가 중단되므로 틀린 수치가
공개 URL 로 나가지 않는다. 의존성 0(`requirements.txt` 는 Nixpacks 인식용),
Python 3.12 고정(`.python-version`).

`public/`, `build/` 는 gitignore 대상이라 업로드되지 않고 빌드 시점에 생성된다.

### 6.6 대시보드 검증

브라우저 확장이 없어도 검증 가능한 범위를 테스트로 고정했다.

| 방법 | 확인 내용 |
|---|---|
| Python | 주입 성공, JSON 재파싱, 외부 리소스 0, 데이터가 앱 스크립트보다 앞 |
| Node + DOM 스텁 (`tests/smoke_dashboard.mjs`) | 4탭 × 전 건물 × 전 전략 × 전 층 렌더, `undefined`/`NaN` 미출력, 해시 라우팅 |
| 헤드리스 Chrome | 실제 렌더 육안 확인 (수동) |

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
| IFC 입력 어댑터 | 미구현. DXF 어댑터로 대체했다 (2026-08-10) |
| 정화조 파라미터 | **확보 (2026-08-09)** — 고시 + 시행규칙 별표12 |
| 정화조 처리방식 3갈래 | **구현 (2026-08-10)** — 공공하수도 연결은 '해당 없음', 오수처리시설은 산정식 미확인 |
| 오수처리시설 규모 산정식 | **불필요해짐 (2026-08-10).** 대장이 처리대상인원(`capaPsper`)을 직접 싣는다 — 환산할 일이 없다. 인원이 없고 용량(㎥)만 있는 경우에만 막히며, 그때는 별표12 를 적용하지 않고 실패시킨다 |
| 주차 제37조⑤ (종전 용도 기준) | 미구현. 다만 `AxisCap.not_applicable` 이 생겨 '비병목 상태' 표현 수단은 마련됐다 |
| 편복도 1,200mm | **구현 (2026-08-10)** — 2패스로 순환을 푼다 |
| 매입제외 사전필터 | **구현 (2026-08-10)** — 공고 pp.8~11 을 `exclusions.json` 으로. auto 2건, 나머지는 답변·위치 데이터 필요 |
| 의무 공용면적 | **구현 (2026-08-10)** — 커뮤니티 50세대↑ 세대당 1.0㎡ 를 고정점 반복으로 반영 |
| 경비실·관리사무소 면적 | **미구현.** 공고가 면적 기준을 제시하지 않는다(관리사무소는 '최소 3인 이상의 사무공간'이라는 정성 문구뿐). 설치 필요 여부만 플래그로 낸다 |
| 위반건축물 수집 | **미구현.** 표제부가 아니라 기본개요(`getBrBasisOulnInfo`)에 있다. `violation` 이 null 이라 매입제외에서 '미확인'으로 남는다 |
| 대장 층수 결측 | 실 API 에 `grndFlrCnt: 0` 인 건물이 있다(르메르디앙서울호텔 등). 0 을 믿지 않고 `floors_total` 을 null 로 두어 계약이 명시적으로 실패한다 — 사람이 등본에서 채워야 한다 |
| 오수시설 기록 상충 | 한 대지에 정화조(2xx)와 하수도연결(3xx)이 함께 등재되는 사례가 실재한다. **제약이 있는 쪽을 대표로 삼고**(보수적) 전체 기록을 `_detail` 에 남긴다. 등본 확인 후 정정 필요 |
| 주소 → 법정동코드 변환 | **미구현.** code.go.kr 전체자료가 폼 전용이라 자동 수집이 막혔다. 코드를 직접 넣어야 한다 |
| 창 입면 치수 | DXF 에 없다. `dxf_lexicon.window_assumption` 의 **가정값**(sill 900 / height 1500)을 쓰고 결과의 `_assumptions` 에 명시한다 |
| DXF BLOCK/INSERT 전개 | 미구현. INSERT 안의 도형은 읽지 않는다. 코어가 블록으로만 그려진 도면은 계단실 미검출로 실패한다 |
| 용도지역별 주택 허용 조건 | **미확정** — 상업지역·준공업지역 차이 |
| 내부 벽 입력 | 규격 없음. 저개입형을 설비 재사용률로 재정의해 회피 |
| 피난 40m 적용 범위 | 조문상 '16층 이상 **공동주택**'에만 걸리는데 엔진은 용도를 가리지 않고 적용한다. 준주택(오피스텔)에는 실제(50m)보다 엄격 — 과소 산출 방향이라 안전하다. 미구현 |
| 반자 높이 판정 | `ceiling_min_mm` 2,300 은 읽기만 하고 판정에 쓰지 않는다. 리모델링은 기존 층고가 고정이라 필수 통과조건이 아니라 위험 플래그가 맞다 |
