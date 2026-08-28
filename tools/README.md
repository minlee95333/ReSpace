# tools — 발표자료 생성

`outputs/*.json` 의 **실행 결과를 읽어** 슬라이드를 만든다. 숫자를 스크립트에 적어두지 않으므로
실험을 다시 돌리면 슬라이드도 따라 갱신된다.

## 실행 순서

```
python tools/install_fonts.py     # 최초 1회 ― Pretendard 설치
python tools/make_figures.py      # 그림     -> outputs/figures/*.png
python tools/build_brief.py       # 슬라이드 -> outputs/주제설명_3장.pptx
python tools/render_deck.py       # 실제 렌더 -> outputs/주제설명_3장_전달용/ (PDF + PNG)
```

`theme.py` 가 색·서체·활자 크기·판면을 한 곳에 모아둔다. 디자인을 바꾸려면 거기만 고친다.
본문 서체 Pretendard 는 `install_fonts.py` 가 받고, 제목 서체 **KoPub바탕체**는
kopus.org 에서 받아 설치한다(무료).

마지막 단계는 선택이 아니다. **눈으로 확인하지 않으면 잘린 슬라이드가 그대로 나간다.**

PowerPoint 로 pptx 를 열어둔 상태면 저장이 `PermissionError` 로 막힌다.
파일을 닫거나 `BRIEF_OUT=<경로> python tools/build_brief.py` 로 다른 이름에 쓴다.

## 산출물

| 파일 | 용도 |
|---|---|
| `outputs/주제설명_3장.pptx` | 편집용 |
| `outputs/주제설명_3장_전달용/*.pdf` | **배포용** ― 폰트가 박혀 어디서나 동일하다 |
| `outputs/주제설명_3장_전달용/*.png` | 200 dpi 슬라이드 이미지 |

## 의존

`python-pptx` · `matplotlib` · `pillow` · `fonttools` · `pymupdf`,
**LibreOffice** (`winget install TheDocumentFoundation.LibreOffice`),
**Pretendard** (`tools/install_fonts.py`). PowerPoint 는 없어도 된다.

---

# 내용 규칙 ― ADDENDUM-01

슬라이드 문구는 `ADDENDUM-01-prior-art.md` 의 재포지셔닝을 따른다.

- 방법론(확률 커버리지 배치·거리각도 감쇠·다중 결합·위험가중 탐욕)은 **기존 것**이다.
  우리가 하는 것은 **가정된 감쇠 함수 자리에 실측값을 채우는 일**이다.
- §4 **금지 표현**: "최초 · novel · unprecedented · 기존에 없던",
  "기존 연구는 중첩을 낭비로 본다"(사실 아님), "확률 커버리지 모델을 제안한다".
  → `build_brief.py` 의 `gate_banned_words()` 가 빌드를 실패시킨다.
- §5.4 **3단 비교**(기하 / 가정 곡선 / 실측 곡선)가 기여를 증명하는 유일한 그림이다.
  3장 슬라이드의 결론이 이것이다.

---

# 함정 ― 겪고 나서 적은 것

### 1. python-pptx 의 `font.name` 은 한글에 적용되지 않는다 ⭐

OOXML 은 폰트 슬롯이 세 개다 ― `<a:latin>`(영문) · `<a:ea>`(동아시아) · `<a:cs>`.
`font.name` 은 **latin 만** 채운다. `ea` 가 비면 PowerPoint 는 한글을 테마 기본값
(맑은 고딕)으로 그린다.

**LibreOffice 는 latin 을 전체에 적용하므로 렌더 확인으로도 안 잡힌다.**
폰트를 바꿨다고 생각했는데 PowerPoint 에서는 그대로였던 적이 있다.

→ `build_brief.py` 의 `set_font()` 가 세 슬롯을 모두 채우고,
  `assert_font_slots()` 가 저장 직전 전 런을 검사해 빌드를 실패시킨다.

### 2. 한글 폰트는 글리프 구멍이 많다

맑은 고딕에 `−`(U+2212)가 없고, Hancom Gothic 에는 `—`(U+2014)·`–`(U+2013)·`−` 가
전부 없다. 없는 문자는 두부(빈 사각형)나 빈칸으로 나간다.

Pretendard 는 14,336자로 구멍이 없어 지금은 문제가 없지만, 폰트를 바꾸면 다시 터진다.
→ `fonts.assert_glyphs()` 가 저장 직전 폰트 cmap 과 대조해 빌드를 실패시킨다.

### 3. 폰트를 바꾸면 레이아웃이 깨진다

글자 폭이 달라진다. Hancom Gothic 으로 바꿨을 때 불릿 마지막 항목이 통째로 사라졌다.
폰트 교체 후에는 반드시 `render_deck.py` 로 다시 본다.

### 4. LibreOffice 행간이 PIL 근사보다 넓다

직접 만든 근사 렌더러로 "여유 있음" 이던 것이 실제로는 넘쳤다. 실제 렌더만 믿는다.

### 5. 그림은 슬라이드에 놓을 폭과 같은 `figsize` 로 그린다

13.5 in 로 그려 11 in 로 줄여 넣으면 차트 글씨가 본문의 60% 크기가 되어 읽히지 않는다.

### 6. 폰트 크기 규격은 캔버스 폭에 비례한다

"본문 20 pt 하한" 같은 기준은 10 in 캔버스 전제다. 13.333 in 16:9 에서는 ×1.333 해야
같은 크기로 보인다.

### 7. 배포는 PDF 로 한다

PPTX 는 상대 PC 에 Pretendard 가 없으면 폰트가 대체된다. PPTX 를 보내야 한다면
PowerPoint 에서 `파일 > 옵션 > 저장 > 파일에 글꼴 포함` 을 체크하고 저장한다.

### 8. KoPub 은 굵기마다 패밀리 이름이 다르다

`KoPubBatang Bold` · `KoPubBatang Medium` · `KoPubBatang Light` 가 각각 별개 패밀리다.
`bold=True` 를 쓰면 PowerPoint 가 가짜 볼드를 합성한다. 굵기별 패밀리명을 직접 지정한다.

### 9. Pretendard 배포 zip 은 두 종류다

`PretendardStd-*.zip` 은 **라틴 서브셋으로 한글이 0자다**. 전체판 `Pretendard-*.zip`(46 MB)
을 써야 한다. `install_fonts.py` 가 알아서 전체판을 고른다.

---

# 디자인 ― 왜 이렇게 생겼나

[hallmark](https://github.com/nutlope/hallmark)(anti-AI-slop 스킬)의 editorial 장르 규칙을
따랐다. 스킬은 `~/.claude/skills/hallmark` 에 설치되어 있다.

이전 판이 밟고 있던 금지 패턴:

| 패턴 | 왜 AI 티인가 |
|---|---|
| 제목 왼쪽 세로 색 스트라이프 | *side-stripe card* ― 비대칭 굵은 띠 금지 |
| 번호 왼쪽 · 제목 오른쪽 2단 헤더 | *hanging header* ― 게이트 54, 하드 밴 |
| 연한 파란 라운드 박스 5개 | *card-in-card* ― 카드 대신 헤어라인 |
| 3등분 동일 카드 | *3-column feature grid* ― 모든 LLM 이 뱉는 형태 |
| 순백 배경 | *pure white* ― 앵커 색조로 틔워야 한다 |
| 슬라이드 3장 동일 골격 | *default-attractor sameness* ― 구조 반복 = 템플릿 |
| 촘촘한 활자 급간(13~29pt) | 큰 순간이 없다 |

지금 판:

- 슬라이드마다 **구조가 다르다** ― 1) 비대칭 2단 긴 문서 2) 그림 지배 + 큰 숫자 3열
  3) 명조 선언 문장 + 근거 그림
- 종이 `#FBFAF6`, 잉크 `#1C1A17` ― 순백·순흑 없음
- 강조색 **하나**(`#A33B29`), 결론을 지는 계열에만
- 카드 없음. 가로·세로 헤어라인과 겹줄만
- 쪽번호는 하단 folio 로 (제목 옆 번호 금지)
- 차트는 격자·프레임 제거, 범례 대신 직접 라벨

# 폰트를 왜 이렇게 짝지었나

**제목 KoPub바탕체(명조) + 본문 Pretendard(산세리프).**
한 서체만 쓰면 템플릿처럼 보인다는 것이 hallmark 의 지적이고, 출판용 명조는
"사료적·널리지식" 톤에 맞는다.

본문 서체 후보는 실제로 렌더해 비교했다.

| 후보 | 판단 |
|---|---|
| 맑은 고딕 | 한글 자간이 벌어져 제목이 띄엄띄엄하다. `−` 누락 |
| Hancom Gothic | 자간은 정상. `—`·`–`·`−` 3종 누락 |
| 함초롬돋움 | 본문체 성격. 제목에서 자간이 느슨하다 |
| Noto Sans KR | 가변폰트 단일 파일이라 PowerPoint 가 볼드를 합성해 뭉갤 수 있다 |
| **Pretendard** | **자간이 고르고 숫자 조판이 가장 정돈된다. 글리프 누락 없음. Regular/Bold 별도 파일** |

이 자료는 수치가 주인공(`66.8% → 70.0%`, `334 → 168`)이라 숫자 조판 품질이 컸다.
서체를 바꾸려면 `tools/theme.py` 의 `DISPLAY`·`TEXT`·`FONT_FILES` 만 고친다.

## 이식된 테스트 (2026-08-27)

`feat/mockup-and-eval` 에서 배치 기능(`mockup/engine.js` · `mockup/mounts.js`)을
가져오면서 **두 구현이 같은 값을 내는지**를 고정한 테스트를 함께 둔다. 화면과
보고서가 다른 말을 하면 안 되는데, 눈으로는 드러나지 않는 종류의 오류다.

| 테스트 | 대조 대상 | 만드는 곳 |
|---|---|---|
| `test_obb.mjs` | 회전 상자 광선판정 — `src/geometry.py:_ray_hits_box` | `make_obb_fixture.py` |
| `test_engine.mjs` | 복셀별 검출확률 — `geometry.pair` + `detect_model` | `make_engine_fixture.py` |

```
python tools/make_obb_fixture.py    && node tools/test_obb.mjs
python tools/make_engine_fixture.py && node tools/test_engine.mjs
```

`test_engine.mjs` 는 `mockup/site.json` 을 읽으므로 현장이나 곡선을 바꿨으면
`python src/export_site.py` 를 먼저 돌린다.

**`test_mounts.mjs` 는 가져오지 않았다.** 설치 자리 규칙 자체는 옳지만, 그쪽
현장(100×60m · 솔리드 12 · 가설장비 없음)의 좌표와 개수를 단언문에 박아 둔
테스트라 이 갈래 현장(210×125m · 솔리드 59 · 타워크레인·펜스 있음)에서는 16건이
실패한다. 규칙의 결함이 아니라 대조표가 다른 현장의 것이다.
