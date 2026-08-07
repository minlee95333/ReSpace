# Re:Space

프로젝트 이름은 **Re:Space**다. 폴더명이 `ReSpace` 인 이유는 Windows 가 폴더명에 `:` 를
허용하지 않기 때문이며(드라이브 문자·NTFS 대체 데이터 스트림 예약), 문서·저장소·Notion 등
`:` 를 쓸 수 있는 곳에서는 `Re:Space` 로 표기한다.

프로젝트의 목적·범위·기술 스택은 아직 정의되지 않았다. `/init` 실행 시 생성되는
`docs/DISCOVERY.md` → `docs/PRD.md` → `docs/TECH-SPEC.md` 가 진실 원천이 된다.
그 문서들이 생기면 이 절을 그쪽으로 넘기고 여기서는 링크만 유지한다.

- 저장소: https://github.com/minlee95333/ReSpace (Private)
- 프레임워크: open-claude-office 전체 모듈 (agents 48 / skills 32 / commands 16 / hooks 10)

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

### 4. 중복 기록 회피

SessionEnd 훅이 Obsidian(`C:\Users\wf\iAm`)에 세션 로그를 남긴다.
Notion 의 Activity Log DB 를 함께 켜면 같은 내용이 두 곳에 쌓인다.
서술형 세션 로그는 Obsidian, 태스크·스프린트·게이트 같은 구조화 데이터는 Notion 으로 나눈다.

### 5. 공개 전환 시

`/notion init` 은 DB ID 8개를 `.claude/settings.json` 에 기록하며, 이 파일은 git 추적 대상이다.
현재 저장소가 Private 이라 문제되지 않지만, 공개로 전환할 때는 DB ID 를
`.claude/settings.local.json`(gitignore 됨)으로 옮긴다.
