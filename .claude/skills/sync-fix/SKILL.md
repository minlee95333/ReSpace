---
name: sync-fix
description: Phase, Sprint, 문서 간 동기화 문제 해결. 불일치 감지 및 자동 수정.
---

# /sync-fix - 동기화 문제 해결 스킬

## Usage

```bash
/sync-fix [target] [options]
```

### Targets

| Target | Description |
|--------|-------------|
| `--phase` | Phase 문서 동기화 |
| `--sprint` | Sprint 문서 동기화 |
| `--progress` | PROGRESS.md 동기화 |
| `--all` | 전체 동기화 (기본) |

### Options

| Option | Description |
|--------|-------------|
| `--dry-run` | 변경 없이 문제만 표시 |
| `--force` | 강제 동기화 (충돌 시 덮어쓰기) |
| `--backup` | 수정 전 백업 생성 |

## Sync Workflow

```
┌────────────────────────────────────────────────────────────────────┐
│                     /sync-fix WORKFLOW                              │
├────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  1. 불일치 감지                                                     │
│     ├── Phase Task ↔ PROGRESS.md 진행률 비교                        │
│     ├── Sprint Backlog ↔ Phase Task 비교                            │
│     ├── CHANGELOG ↔ Git commits 비교                                │
│     └── 문서 간 링크 유효성 검사                                    │
│                                                                     │
│  2. 충돌 분석                                                       │
│     ├── 데이터 소스 우선순위 결정                                   │
│     ├── 자동 병합 가능 여부 판단                                    │
│     └── 수동 개입 필요 항목 분류                                    │
│                                                                     │
│  3. 자동 동기화                                                     │
│     ├── Phase 진행률 재계산                                         │
│     ├── Sprint 상태 업데이트                                        │
│     ├── PROGRESS.md 재생성                                          │
│     └── 링크 수정                                                   │
│                                                                     │
│  4. 결과 보고                                                       │
│     └── 변경 사항 요약 및 검증                                      │
│                                                                     │
└────────────────────────────────────────────────────────────────────┘
```

## Detectable Issues

### Phase ↔ Progress

```yaml
Sync Issues:
  - progress_mismatch: PROGRESS.md 진행률 ≠ TASKS.md 계산값
  - missing_phase: Phase 디렉토리 존재하나 PROGRESS에 없음
  - orphan_entry: PROGRESS에 있으나 Phase 없음
  - status_inconsistent: Phase 완료 상태 불일치

Auto-Fix:
  - recalculate: 진행률 재계산
  - add_phase: 누락 Phase 추가
  - remove_orphan: 고아 항목 제거
```

### Sprint ↔ Phase

```yaml
Sync Issues:
  - task_not_linked: Sprint Task가 Phase에 연결 안됨
  - completed_not_reflected: Sprint 완료가 Phase에 반영 안됨
  - points_mismatch: Story Point 불일치
  - duplicate_task: 중복 Task 존재

Auto-Fix:
  - link_task: Task 연결
  - sync_status: 상태 동기화
  - recalculate_points: 포인트 재계산
  - remove_duplicate: 중복 제거
```

### Document Links

```yaml
Sync Issues:
  - broken_link: 깨진 내부 링크
  - wrong_path: 잘못된 경로 참조
  - missing_anchor: 앵커 누락

Auto-Fix:
  - fix_path: 경로 수정
  - remove_broken: 깨진 링크 제거
  - add_anchor: 앵커 추가
```

## Output Examples

### Dry Run Mode

```
🔍 SYNC-FIX: Dry Run Analysis
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Found 4 sync issues:

[1] Phase ↔ Progress Mismatch
    Phase 1 progress: 75% (calculated) vs 50% (displayed)
    Would fix: Update PROGRESS.md

[2] Sprint Task Not Linked
    Sprint 1 Task S1-03 not linked to any Phase
    Would fix: Link to Phase 1 T1-05

[3] Completed Task Not Reflected
    Phase 2 T2-01 marked complete but Sprint shows pending
    Would fix: Update Sprint Backlog

[4] Broken Link
    docs/PROGRESS.md:45 → docs/phases/phase-3/SPEC.md (not found)
    Would fix: Remove broken link

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Run `/sync-fix --all` to apply fixes
```

### Auto Fix Mode

```
🔧 SYNC-FIX: Synchronizing...
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[1/4] Syncing Phase ↔ Progress...
      ✅ Updated Phase 1: 50% → 75%

[2/4] Linking Sprint Tasks...
      ✅ Linked S1-03 → T1-05

[3/4] Syncing Sprint Status...
      ✅ Updated Sprint 1 Backlog (T2-01: pending → complete)

[4/4] Fixing Document Links...
      ✅ Removed broken link at PROGRESS.md:45

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Sync Summary
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Fixed: 4
Skipped: 0
Failed: 0

All systems synchronized ✅
```

## Integration

### With /agile-sync

```bash
# agile-sync 실패 시 sync-fix 연계
/agile-sync || /sync-fix --all
```

### With /validate

```bash
# validate 후 sync-fix 실행
/validate --full && /sync-fix --dry-run
```

### With Hooks

```bash
# phase-progress.sh 실패 시 자동 호출
# error-recovery.sh에서 트리거
```

## Configuration

```json
// settings.json
{
  "sync": {
    "auto_sync_on_commit": true,
    "priority_source": {
      "progress": "phase",
      "sprint": "phase",
      "changelog": "git"
    },
    "conflict_resolution": "ask",
    "backup_before_sync": true
  }
}
```

## Related

| Command | Purpose |
|---------|---------|
| `/agile-sync` | 전체 문서 동기화 |
| `/repair` | 시스템 복구 |
| `/validate` | 설정 검증 |
| `phase-progress.sh` | 진행률 자동 업데이트 |
