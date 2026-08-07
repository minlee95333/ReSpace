# Integration Guide

dev-doc-system과 다른 도구들의 통합 방법을 설명합니다.

---

## 도구 조합 매트릭스

### 워크플로우별 도구 조합

| 워크플로우 | Primary Tool | Secondary Tools | 문서 출력 |
|-----------|--------------|-----------------|-----------|
| 프로젝트 시작 | `dev-doc-system init` | `prd-writer` | VISION, ROADMAP |
| 기능 기획 | `prd-writer` | `dev-doc-system` | PRD, BACKLOG |
| 기술 설계 | `tech-spec-writer` | `dev-doc-system decision` | tech-spec, DECISIONS |
| 개발 진행 | `progress-tracker` | `dev-doc-system current` | progress, CURRENT |
| 스코프 변경 | `dev-doc-system scope-change` | `prd-writer` | SCOPE-CHANGES |
| 이슈 해결 | `dev-doc-system issue` | `git-troubleshooter` | ISSUES, LEARNINGS |
| 스프린트 완료 | `dev-doc-system retro` | `commit-helper` | RETRO, CHANGELOG |
| 문서 검증 | `doc-validator` | - | 검증 리포트 |
| README 업데이트 | `skill-manager update-header` | `dev-doc-system` | README |

---

## Agent 통합

### prd-writer 통합

**호출 시점**:
- 새 기능 기획 시
- VISION.md 초기 작성 시
- BACKLOG 항목 상세화 시

**연동 방법**:
```
1. /dev-doc-system init → VISION.md 생성
2. prd-writer 호출 → PRD 상세 작성
3. /dev-doc-system decision → 주요 결정 기록
4. 자동으로 BACKLOG.md에 항목 추가
```

**데이터 흐름**:
```
prd-writer
    │
    ├──► docs/prd/{feature}-prd.md
    │
    └──► dev-doc-system
            │
            ├──► direction/DECISIONS.md (기술 결정)
            └──► planning/BACKLOG.md (백로그 항목)
```

### tech-spec-writer 통합

**호출 시점**:
- 아키텍처 결정 필요 시
- 기술 설계 시
- ADR 작성 시

**연동 방법**:
```
1. PRD 확인 → 기술 요구사항 파악
2. tech-spec-writer 호출 → 기술 설계서 작성
3. /dev-doc-system decision → ADR 자동 생성
4. ROADMAP.md에 기술 마일스톤 반영
```

### progress-tracker 통합

**호출 시점**:
- 작업 상태 업데이트 시
- 진행률 체크 시
- 블로커 발생 시

**연동 방법**:
```
1. progress-tracker 호출 → progress/{feature}-progress.md 업데이트
2. /dev-doc-system current → CURRENT.md 자동 동기화
3. 블로커 발견 시 → ISSUES.md에 자동 추가
4. ROADMAP.md 진행률 자동 업데이트
```

### doc-validator 통합

**호출 시점**:
- 마일스톤 완료 전
- PR 생성 전
- 정기 문서 검토 시

**연동 방법**:
```
1. doc-validator 호출 → 전체 문서 검증
2. 누락 항목 발견 → ISSUES.md에 문서 이슈로 추가
3. 검증 통과 → CHANGELOG.md에 기록
```

### commit-helper 통합

**호출 시점**:
- 코드 커밋 시
- CHANGELOG 업데이트 시

**연동 방법**:
```
1. commit-helper 호출 → 커밋 메시지 생성
2. 커밋 완료 → CHANGELOG.md 자동 업데이트
3. 주요 변경 → CURRENT.md 자동 반영
```

### git-troubleshooter 통합

**호출 시점**:
- Git 관련 이슈 발생 시
- 충돌 해결 시

**연동 방법**:
```
1. git-troubleshooter 호출 → 이슈 분석
2. 해결 후 → ISSUES.md에 기록
3. 교훈 도출 → LEARNINGS.md에 추가
```

---

## Skill 통합

### skill-manager 통합

**update-header 워크플로우**:
```
skill-manager update-header
    │
    ├──► 진행 상황 수집 ← CURRENT.md, ROADMAP.md
    ├──► Tech Stack 감지 ← package.json, tsconfig.json, etc.
    ├──► Used Skills 수집 ← .claude/project-skills.yml
    │
    └──► docs/README.md 헤더 업데이트
```

**연동 포인트**:
- ROADMAP.md의 Phase 진행률 → README 진행 상황
- CURRENT.md의 이번 주 목표 → README 빠른 상태
- BACKLOG.md의 P0/P1 항목 → README 다음 예정

### context-optimizer 통합

**문서 컨텍스트 최적화**:
```
대용량 문서 작업 시:
1. context-optimizer 호출
2. 현재 작업에 필요한 문서만 로드:
   - CURRENT.md (항상)
   - 관련 PRD/tech-spec (필요시)
   - DECISIONS.md (결정 필요시)
3. 불필요한 문서 컨텍스트 제거
```

---

## Command 통합

### dev-doc-planner 통합

**기존 구조와의 호환**:
```
dev-doc-planner (기존)
├── prd/            ──► 그대로 유지
├── tech-specs/     ──► 그대로 유지
└── progress/       ──► 그대로 유지

dev-doc-system (신규)
├── direction/      ──► 새로 추가
├── status/         ──► 새로 추가 (progress/ 확장)
├── planning/       ──► 새로 추가
├── changes/        ──► 새로 추가
└── feedback/       ──► 새로 추가
```

**마이그레이션**:
```bash
# 기존 progress/ 내용을 status/로 확장
/dev-doc-system migrate --from progress --to status
```

### git-workflow 통합

**커밋 시 자동 연동**:
```
git commit 전:
1. pre-commit hook → doc-validator 체크
2. 문서 업데이트 필요 시 경고

git commit 후:
1. post-commit hook → CHANGELOG.md 업데이트
2. CURRENT.md 자동 갱신
```

### sc/atomic-commit 통합

**작업 단위 문서 연동**:
```
/sc:atomic-commit "feature: 사용자 인증 추가"
    │
    ├──► 커밋 생성
    ├──► CHANGELOG.md 업데이트
    └──► CURRENT.md 완료 항목 체크
```

---

## Hook 통합

### 추천 Hook 설정

**.claude/hooks/doc-sync.sh**:
```bash
#!/bin/bash
# 커밋 후 문서 동기화

HOOK_TYPE=$1

case $HOOK_TYPE in
  "post-commit")
    # CHANGELOG 업데이트
    echo "📝 Updating CHANGELOG.md..."
    # CURRENT.md 갱신
    echo "📋 Updating CURRENT.md..."
    ;;
  "pre-push")
    # 문서 검증
    echo "🔍 Validating documentation..."
    ;;
esac
```

### Hook 이벤트 매핑

| Hook Event | 실행 동작 | 관련 문서 |
|------------|----------|----------|
| `pre-commit` | 문서 완성도 체크 | 모든 문서 |
| `post-commit` | CHANGELOG 업데이트 | CHANGELOG.md, CURRENT.md |
| `pre-push` | 전체 문서 검증 | 모든 문서 |
| `post-merge` | 충돌 문서 체크 | DECISIONS.md, SCOPE-CHANGES.md |

---

## 자동화 설정

### 일일 자동화

```yaml
# .claude/automation/daily.yml
trigger: session_start
actions:
  - tool: progress-tracker
    target: docs/progress/
    action: sync_to_current

  - tool: dev-doc-system
    command: current
    action: refresh

  - tool: dev-doc-system
    command: issues
    action: check_active
```

### 주간 자동화

```yaml
# .claude/automation/weekly.yml
trigger: friday_or_manual
actions:
  - tool: dev-doc-system
    command: changelog
    action: weekly_summary

  - tool: dev-doc-system
    command: roadmap
    action: update_progress

  - tool: dev-doc-system
    command: backlog
    action: review_priorities
```

### 마일스톤 자동화

```yaml
# .claude/automation/milestone.yml
trigger: phase_complete
actions:
  - tool: dev-doc-system
    command: retro
    action: create_new

  - tool: dev-doc-system
    command: learnings
    action: extract_from_retro

  - tool: skill-manager
    command: update-header
    action: refresh_all
```

---

## 명령어 체인 예시

### 새 프로젝트 시작

```bash
# 1. 문서 시스템 초기화
/dev-doc-system init

# 2. 비전 작성
/dev-doc-system vision "프로젝트 설명"

# 3. 로드맵 설정
/dev-doc-system roadmap --phases 4

# 4. 첫 PRD 작성
"user-authentication PRD 작성해줘"  # → prd-writer 자동 호출

# 5. 기술 설계
"user-authentication 기술 설계서 작성해줘"  # → tech-spec-writer

# 6. 결정 기록
/dev-doc-system decision "JWT 인증 방식 선택"
```

### 스프린트 진행

```bash
# 1. 스프린트 계획
/dev-doc-system next-sprint --number 3

# 2. 일일 진행
/dev-doc-system current  # 상태 업데이트

# 3. 이슈 발생 시
/dev-doc-system issue "API 응답 지연 문제"

# 4. 스프린트 완료
/dev-doc-system retro --sprint 3

# 5. README 업데이트
/skill-manager update-header
```

### 스코프 변경

```bash
# 1. 변경 요청 기록
/dev-doc-system scope-change "소셜 로그인 추가"

# 2. 영향 분석 후 승인
/dev-doc-system scope-change SC-001 --approve

# 3. 관련 문서 업데이트
/dev-doc-system backlog --add "소셜 로그인 구현"
/dev-doc-system roadmap --update
```

---

## 트러블슈팅

### 문제: 문서 동기화 불일치

**증상**: CURRENT.md와 progress/*.md 내용이 다름

**해결**:
```bash
# 강제 동기화
/dev-doc-system sync --force

# 또는 수동 확인
/dev-doc-system validate
```

### 문제: 자동 업데이트 실패

**증상**: 커밋 후 CHANGELOG 미갱신

**확인**:
```bash
# Hook 상태 확인
ls -la .claude/hooks/

# Hook 권한 확인
chmod +x .claude/hooks/*.sh
```

### 문제: 문서 충돌

**증상**: 여러 도구가 같은 문서를 수정

**해결**:
```bash
# 충돌 해결
/dev-doc-system resolve --file CURRENT.md

# 변경 이력 확인
/dev-doc-system history --file CURRENT.md
```

---

## Best Practices

### DO

- ✅ 도구별 역할을 명확히 구분하여 사용
- ✅ 문서 간 상호 참조 링크 유지
- ✅ 정기적으로 `/dev-doc-system validate` 실행
- ✅ 마일스톤마다 `/skill-manager update-header` 실행
- ✅ Hook을 활용한 자동화 설정

### DON'T

- ❌ 같은 문서를 여러 도구로 동시에 수정
- ❌ 문서 업데이트 없이 코드만 커밋
- ❌ 검증 없이 마일스톤 완료 선언
- ❌ 오래된 문서 방치
