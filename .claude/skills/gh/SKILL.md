---
name: gh
description: GitHub CLI 통합 스킬. 이슈, PR, CI/CD, 릴리스, 상태 관리. "gh", "github", "이슈", "issue", "CI", "workflow", "release", "상태" 키워드에 반응.
---

# GitHub CLI Skill

gh CLI를 활용한 GitHub 통합 관리 스킬입니다.

## Pre-check: Target Repository

All `gh` commands use the current directory's git remote (`origin`).
Ensure it points to YOUR project repository, not the cc-initializer framework source.

```bash
# Verify current repo context
gh repo view --json nameWithOwner -q '.nameWithOwner'
```

## Usage

```bash
/gh <command> [subcommand] [options]
```

## Commands

### Status & Dashboard

| Command | Description |
|---------|-------------|
| `/gh status` | GitHub 상태 대시보드 (이슈, PR, 리뷰 요청, 멘션) |
| `/gh dashboard` | 현재 repo 전체 현황 |

### Issue Management

| Command | Description |
|---------|-------------|
| `/gh issue list` | 이슈 목록 |
| `/gh issue create` | 새 이슈 생성 |
| `/gh issue view <n>` | 이슈 상세 보기 |
| `/gh issue close <n>` | 이슈 닫기 |
| `/gh issue develop <n>` | 이슈에서 브랜치 생성 |

### Pull Request

| Command | Description |
|---------|-------------|
| `/gh pr list` | PR 목록 |
| `/gh pr create` | PR 생성 |
| `/gh pr view <n>` | PR 상세 |
| `/gh pr checks <n>` | PR CI 상태 |
| `/gh pr merge <n>` | PR 머지 |
| `/gh pr review <n>` | PR 리뷰 |

### CI/CD (GitHub Actions)

| Command | Description |
|---------|-------------|
| `/gh ci status` | 최근 CI 실행 상태 |
| `/gh ci watch` | 현재 실행 모니터링 |
| `/gh ci logs <id>` | 실행 로그 보기 |
| `/gh ci rerun <id>` | 실패한 실행 재시도 |
| `/gh workflow list` | 워크플로우 목록 |
| `/gh workflow run <name>` | 워크플로우 트리거 |

### Release

| Command | Description |
|---------|-------------|
| `/gh release list` | 릴리스 목록 |
| `/gh release create <tag>` | 릴리스 생성 |
| `/gh release view <tag>` | 릴리스 상세 |

### Search

| Command | Description |
|---------|-------------|
| `/gh search issues <query>` | 이슈 검색 |
| `/gh search prs <query>` | PR 검색 |
| `/gh search code <query>` | 코드 검색 |

---

## Quick Examples

### 1. 상태 확인

```bash
/gh status
```

Output:
```
## GitHub Status Dashboard

### Assigned to You
- #123 Fix login bug (myorg/app)
- #456 Add dark mode (myorg/app)

### Review Requests
- PR #789 feat: add auth (waiting for your review)

### Recent CI
- ✅ CI passed (3m ago)
- ✅ Deploy completed (10m ago)
```

### 2. 이슈 기반 개발 시작

```bash
/gh issue develop 123
```

Actions:
1. 이슈 #123 확인
2. `feature/123-fix-login-bug` 브랜치 생성
3. 브랜치 체크아웃
4. 이슈와 브랜치 연결

### 3. PR 생성 + CI 모니터링

```bash
/gh pr create
/gh pr checks --watch
```

Actions:
1. 현재 브랜치에서 PR 생성
2. CI 실행 실시간 모니터링
3. 완료 시 결과 알림

### 4. CI 실패 분석

```bash
/gh ci logs --failed
```

Output:
```
## CI Failure Analysis

**Job**: test
**Error**:
```
FAIL src/auth.test.ts
  ✕ should authenticate user (15ms)
    Expected: 200
    Received: 401
```

**Suggestion**: Check mock authentication setup
```

### 5. 릴리스 생성

```bash
/gh release create v1.2.0
```

Actions:
1. 최근 커밋 분석
2. 릴리스 노트 자동 생성
3. 태그 생성
4. GitHub Release 발행

---

## Integration with cc-initializer

### Sprint → Issue

```bash
/gh issue create --from-sprint
```

Sprint TASKS에서 이슈 자동 생성:
- 라벨: `sprint:N`
- 마일스톤 연결
- 담당자 할당

### Phase → Milestone

```bash
/gh milestone create --from-phase
```

Phase를 GitHub Milestone으로 변환

### TODO → Issue

```bash
/gh issue create --from-todo
```

코드의 TODO 주석을 이슈로 변환

### Release Workflow

```bash
/gh release create --with-changelog
```

1. CHANGELOG.md 분석
2. 시맨틱 버전 계산
3. 릴리스 노트 생성
4. GitHub Release 발행

---

## Configuration

`.claude/settings.json`:

```json
{
  "github": {
    "default_base_branch": "main",
    "pr_template": ".github/PULL_REQUEST_TEMPLATE.md",
    "auto_assign_reviewers": true,
    "ci_watch_timeout": 600,
    "release_generate_notes": true
  }
}
```

---

## Prerequisites

### gh CLI 설치 확인

```bash
gh --version
gh auth status
```

### 인증 안 된 경우

```bash
gh auth login --web
```

---

## Command Reference

### Issue Commands

```bash
# 목록
gh issue list [--state open|closed|all] [--label <label>] [--assignee @me]

# 생성
gh issue create --title "Title" --body "Body" [--label bug] [--assignee @me]

# 보기
gh issue view <number> [--web] [--json fields]

# 브랜치 생성
gh issue develop <number> [--checkout] [--name <branch-name>]

# 닫기
gh issue close <number> [--reason completed|"not planned"]

# 코멘트
gh issue comment <number> --body "Comment"
```

### PR Commands

```bash
# 목록
gh pr list [--state open|closed|merged|all] [--author @me]

# 생성
gh pr create --title "Title" --body "Body" [--draft] [--reviewer user1]

# 보기
gh pr view <number> [--web] [--json fields]

# CI 상태
gh pr checks <number> [--watch]

# 리뷰
gh pr review <number> --approve|--request-changes|--comment [--body "Comment"]

# 머지
gh pr merge <number> [--squash|--rebase] [--auto] [--delete-branch]
```

### CI Commands

```bash
# 실행 목록
gh run list [--workflow <name>] [--branch <branch>] [--status failure]

# 실행 보기
gh run view <run-id> [--log] [--log-failed] [--web]

# 실시간 모니터링
gh run watch [<run-id>]

# 재실행
gh run rerun <run-id> [--failed]

# 워크플로우 트리거
gh workflow run <workflow> [--ref <branch>] [-f key=value]
```

### Release Commands

```bash
# 목록
gh release list [--limit N]

# 생성
gh release create <tag> [files...] --title "Title" --notes "Notes" [--draft] [--prerelease] [--generate-notes]

# 보기
gh release view <tag> [--web]

# 다운로드
gh release download <tag> [--pattern "*.zip"]
```

---

## Related

- **Agent**: `github-manager` - 상세 GitHub 작업
- **Agent**: `pr-creator` - PR 생성 전문
- **Agent**: `branch-manager` - 브랜치 관리
- **Command**: `/release` - 릴리스 워크플로우
