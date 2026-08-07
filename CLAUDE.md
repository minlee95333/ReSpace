# Re:Space

프로젝트 이름은 **Re:Space**다. 폴더명이 `ReSpace` 인 이유는 Windows 가 폴더명에 `:` 를
허용하지 않기 때문이며(드라이브 문자·NTFS 대체 데이터 스트림 예약), 문서·저장소·Notion 등
`:` 를 쓸 수 있는 곳에서는 `Re:Space` 로 표기한다.

**Re:Space — 비주택 매입 사전판정 시스템.** 제17회 LH 국토기술대전 출품작
(접수 마감 2026-08-28 18:00). 비주택 건물의 기준층 형상과 제원을 입력받아
평면·주차·정화조 세 축의 세대수 상한을 계산하고 **무엇이 병목인지** 가려낸다.

진실 원천은 아래 4개다. 작업 전 반드시 읽고, 단계를 완료하면 상태를 갱신한다.

| 문서 | 내용 |
|---|---|
| [docs/PRD.md](docs/PRD.md) | 문제 정의, 범위, 산출물, 심사 배점 대응 |
| [docs/TECH-SPEC.md](docs/TECH-SPEC.md) | 데이터 계약 5종, 모듈 규격, 테스트 |
| [docs/PROGRESS.md](docs/PROGRESS.md) | 7일 일정, 작업 목록, 미결정 추적, 위험 |
| [docs/plans/2026-08-07-lh-respace-design.md](docs/plans/2026-08-07-lh-respace-design.md) | 설계 확정안과 그 근거 |

작업 시 지켜야 할 불변식:

- **격자 600mm, 세대 18.0 / 28.8㎡** — 임의로 바꾸지 않는다. 근거는 설계안 1절.
- **법규 수치는 `rules.json` 에만.** 코드에 하드코딩 금지.
- **난수 금지.** 배치는 규칙 기반이며 같은 입력 → 같은 출력이어야 한다.
- **엔진은 대시보드를 모른다.** 엔진이 `result.json` + SVG 를 뱉고 대시보드는 읽기만 한다.
- **8/14 이후 코드 동결.** 제안서 11일과 서류 4일을 침범하지 않는다.

- 저장소: https://github.com/minlee95333/ReSpace (Private)
- **공개 대시보드: https://respace-production.up.railway.app** (Railway `respace`, `railway up` 으로 재배포)
- 프레임워크: open-claude-office 전체 모듈 (agents 48 / skills 32 / commands 16 / hooks 10)

공개 URL 은 누구나 접근한다. 대시보드에는 도면 좌표와 분석 수치가 그대로 들어가므로,
**실제 건물 데이터를 넣고 재배포하기 전에 사용자에게 확인한다.**
도면에는 `status` 필드로 출처(`survey`/`reconstructed`/`synthetic`/`placeholder`)를 반드시
밝히며, 신뢰할 수 없는 도면은 화면에 경고가 뜬다.

---

## Notion 연동 규칙

`.claude/skills/notion/SKILL.md` 는 **수정하지 않는다.** 업스트림 원본을 보존하기 위해,
아래 두 가지를 이 파일에서 보완한다.

### 1. 쓰기 범위 격리 (필수)

Notion 워크스페이스에는 A_mi 원본 문서가 있고 Obsidian 과 양방향 미러링 중이다.
Re:Space 작업이 거기에 섞이면 되돌리기 어렵다. 따라서:

| 대상 | 허용 |
|---|---|
| `Re:Space` 페이지와 그 하위 전체 | 읽기 / 쓰기 / 생성 / 삭제 |
| 그 밖의 모든 Notion 페이지 | **읽기만.** 쓰기·생성·이동 금지 |

- 격리 기준 페이지: `Re:Space`
- 페이지 ID: `3b54987af0d880358f96d30bd53f844f`
- URL: https://app.notion.com/p/Re-Space-3b54987af0d880358f96d30bd53f844f
- 워크스페이스: **이승민의 Notion** (minlee95333@inu.ac.kr)

MCP 인증이 다른 워크스페이스로 붙으면 페이지 ID 가 존재하지 않아 조용히 엉뚱한 곳에
쓰게 된다. 작업 전 `notion-fetch` 에 `self` 를 넘겨 워크스페이스가 위와 같은지 확인하고,
다르면 중단하고 사용자에게 알린다. `settings.json > notion.workspace` 에도 같은 값이 있다.

`/notion init` 으로 만드는 DB 8개는 **반드시 이 페이지의 하위**에 생성한다.
상위 페이지를 지정하지 않으면 워크스페이스 루트에 생성되므로, `parent` 를 항상 명시할 것.

Re:Space 바깥에 무언가를 써야 하는 상황이 생기면, 실행하지 말고 먼저 사용자에게 확인한다.

### 2. MCP 도구 이름 대응

SKILL.md 는 `mcp__notion__<snake_case>` 형태로 적혀 있으나, 실제 Notion MCP 서버
(`https://mcp.notion.com/mcp`, 서버 이름 `notion`)가 노출하는 이름은 다르다.
SKILL.md 를 고치는 대신 호출 시점에 아래로 치환한다.

| SKILL.md 표기 | 실제 호출할 도구 |
|---|---|
| `mcp__notion__search` | `mcp__notion__notion-search` |
| `mcp__notion__get_page` | `mcp__notion__notion-fetch` |
| `mcp__notion__create_page` | `mcp__notion__notion-create-pages` |
| `mcp__notion__update_page` | `mcp__notion__notion-update-page` |
| `mcp__notion__query_database` | `mcp__notion__notion-query-data-sources` |
| (SKILL.md 에 표기 없음) | `mcp__notion__notion-create-database` — DB 생성용 |

MCP 서버를 `notion` 이외의 이름으로 등록했다면 접두사가 달라지므로 이 표를 갱신할 것.

### 3. 단계적 활성화

`.claude/settings.json` 의 `notion.enabled` 는 현재 `false` 이고,
자동 동기화 플래그 3개도 꺼 두었다. 무엇이 어디에 쓰이는지 확인하기 전에 자동 쓰기를
켜지 않기 위해서다. 순서는:

1. MCP 연결 + 인증 → `/notion init --db-only` (`--migrate` 는 쓰지 않는다)
2. `/notion status`, `/notion diff` 로 검증, `/notion push` 를 수동으로 몇 번 실행
3. 결과가 예상대로면 `enabled` 와 자동 플래그를 하나씩 켠다

### 4. `/notion init` 이후 알아야 할 것 (2026-08-07 완료)

DB 8개는 `--db-only` 로 생성됐고 **행은 전부 0개**다. Relation 은 전부 DUAL(양방향)로,
Projects 에 나머지 7개 DB 의 역방향 속성이 자동 생성돼 있다.

**`notion.data_sources` 를 반드시 쓸 것.** MCP 의 `notion-query-data-sources` 는
database ID 가 아니라 **data source ID** 를 요구한다. `settings.json` 에
`notion.databases`(database ID)와 `notion.data_sources`(data source ID)가 같은 8개 키로
나란히 들어 있다. SKILL.md 는 `data_sources` 의 존재를 모르므로(원본 보존 원칙상 수정하지
않았다), 쿼리할 때는 SKILL.md 대신 이 규칙을 따른다:

| 용도 | 쓸 값 |
|---|---|
| 행 조회 (`notion-query-data-sources`) | `notion.data_sources.<db>` |
| 페이지 생성 시 parent, DB 자체 조회 | `notion.databases.<db>` |

**Tasks DB 의 Task ID 접두사는 `TSK`** 다. 스펙상 `T` 였으나 Notion 이 1글자 접두사를
거부했다(`prefix must start with a letter, followed by one or more (up to 9)
alphanumeric characters`). 문서·스크립트에서 `T-1` 형식을 가정하지 말 것.

### 5. 중복 기록 회피

SessionEnd 훅이 세션 로그를 이 저장소의 `obsidian/` 에 쓰고, vault 쪽
`C:\Users\wf\iAm\AI-작업로그\프로젝트\ReSpace\repository` 로 링크한다.
이 폴더는 설계상 저장소에 함께 커밋한다(crane-sim 등 다른 프로젝트와 같은 구조).
Notion 의 Activity Log DB 를 함께 켜면 같은 내용이 두 곳에 쌓인다.
서술형 세션 로그는 Obsidian, 태스크·스프린트·게이트 같은 구조화 데이터는 Notion 으로 나눈다.

### 6. 공개 전환 시

`/notion init` 은 DB ID 8개를 `.claude/settings.json` 에 기록하며, 이 파일은 git 추적 대상이다.
현재 저장소가 Private 이라 문제되지 않지만, 공개로 전환할 때는 DB ID 를
`.claude/settings.local.json`(gitignore 됨)으로 옮긴다.
