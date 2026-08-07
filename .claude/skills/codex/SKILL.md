---
name: fc-codex
description: Invoke Codex CLI for code review, research, and validation within foliocraft pipeline. "codex", "코덱스", "codex 실행", "코드 검증", "AI 리뷰", "validation" 키워드에 반응.
---

# Codex CLI Skill — foliocraft

Codex CLI를 통한 코드 분석, 검증, 리뷰 실행. foliocraft 파이프라인 내에서 Phase 1(분석)과 Phase 3.5(검증)에 활용됩니다.

## Use Cases

| Phase | Task | Purpose | Agent |
|-------|------|---------|-------|
| 1 | 코드 아키텍처 분석 | 대규모 레포의 모듈 구조, 의존성 그래프, 설계 패턴 추출 | code-analyst |
| 1 | 스택 감지 | monorepo/다중언어 프로젝트의 프레임워크, 빌드도구, 배포설정 감지 | stack-detector |
| 3.5 | 스키마 검증 | content.json/tokens.css가 스키마에 부합하는지 검증 | validation-agent |
| 3.5 | 코드 리뷰 | 빌드된 site/의 코드 품질, placeholder 잔존, 접근성 검사 | validation-agent |
| 3.5 | 교차 참조 | 템플릿 참조와 content.json 키 매칭 확인 | validation-agent |

## Model Selection

| Task | Default Model | Upgrade Condition | Upgrade Model |
|------|--------------|-------------------|---------------|
| Phase 1 코드 분석 | `gpt-5-mini` ($0.25/1M input) | 파일 100+개 또는 LoC 50K+ | `gpt-5-codex` ($1.25/1M input) |
| Phase 1 스택 감지 | `gpt-5-mini` | monorepo 또는 언어 3+개 | `gpt-5-codex` |
| Phase 3.5 스키마 검증 | `gpt-5-mini` | - (항상 경량) | - |
| Phase 3.5 코드 리뷰 | `gpt-5-codex` | - (항상 중량) | - |
| Phase 3.5 교차 참조 | `gpt-5-mini` | - (패턴 매칭만) | - |

**Manual override**: `--model <MODEL>` 플래그로 사용자가 언제든 모델을 지정할 수 있습니다.

**Dynamic selection logic**:
1. 입력 분석: 파일 수, LoC, 커밋 수 등 정량 지표 측정
2. 임계값 비교: 위 테이블의 업그레이드 조건과 비교
3. 모델 결정: 조건 충족 시 업그레이드 모델 사용
4. 수동 오버라이드: `--model` 플래그가 있으면 항상 우선
5. `.state.yaml` 기록: 사용된 모델을 log에 기록

## Invocation Patterns

### General execution
```bash
echo "PROMPT" | codex exec -m MODEL --sandbox read-only -C TARGET_DIR
```

> **NOTE**: Codex CLI는 `-p` 플래그가 profile 선택용이므로, 프롬프트는 반드시 stdin(echo pipe)으로 전달합니다.

### Phase 1 — Code analysis
```bash
echo "Analyze the architecture of this project. Focus on:
1. Module structure and dependency graph
2. Entry points and data flow
3. Design patterns used
4. Code metrics (LoC per module, test coverage indicators)
Provide file:line evidence for all claims." | codex exec -m gpt-5-mini --sandbox read-only -C {repo_path}
```

### Phase 1 — Stack detection
```bash
echo "Detect the complete technology stack:
1. All frameworks and versions (with file:line evidence)
2. Build tool chain (bundler, transpiler, etc.)
3. Deploy configuration (CI/CD, hosting)
4. Classify domain: automation|plugin-tool|ai-ml|research|saas|devtool|education|simulation
Provide confidence levels (high/medium/low) for each." | codex exec -m gpt-5-mini --sandbox read-only -C {repo_path}
```

### Phase 3.5 — Code review
```bash
codex review -C workspace/{project}/site/
```

### Phase 3.5 — Schema validation
```bash
echo "Validate content.json against the schema in templates/_tokens/content.schema.yaml.
Check tokens.css for all required --pn-* custom properties.
Report issues as: {severity: error|warning|info, file, line, message}" | codex exec -m gpt-5-mini --sandbox read-only -C workspace/{project}/
```

### Phase 3.5 — Cross-reference check
```bash
echo "Compare template component references with content.json keys.
Find any mismatches: missing keys, unused keys, type mismatches.
Report issues as: {severity: error|warning|info, file, line, message}" | codex exec -m gpt-5-mini --sandbox read-only -C workspace/{project}/
```

## Sandbox

**ALWAYS `read-only`.** foliocraft는 Codex CLI를 통해 절대 파일을 쓰지 않습니다.
분석과 검증만 수행하며, 모든 수정은 Claude 에이전트가 직접 합니다.

```bash
# CORRECT
echo "..." | codex exec --sandbox read-only -C ...

# NEVER USE
echo "..." | codex exec --sandbox workspace-write ...  # FORBIDDEN
echo "..." | codex exec --sandbox danger-full-access ... # FORBIDDEN
```

## Output Handling

1. Codex stdout를 캡처
2. 구조화된 결과로 파싱 (JSON/Markdown)
3. actionable items 추출 (이슈, 권장사항)
4. 결과를 해당 에이전트의 산출물에 통합
5. `.state.yaml` log에 invocation 기록

## Error Handling

| Situation | Action |
|-----------|--------|
| Non-zero exit code | Log error → 1회 재시도 (simplified prompt) |
| Retry 실패 | Claude 내장 도구(Read, Grep, Glob)로 fallback |
| Timeout (120s) | Kill → retry once → fallback |
| Partial results | 사용 가능한 부분 활용, 나머지 Claude fallback |

```
CLI 실행 → exit code != 0 또는 timeout(120s)
  → 1회 재시도 (simplified prompt)
  → 재시도 실패 → Claude 내장 도구로 동일 작업 수행
  → .state.yaml log에 fallback 기록
```

## State Integration

모든 Codex CLI 호출은 `.state.yaml`에 기록됩니다:

```yaml
log:
  - timestamp: "2026-02-21T14:30:00Z"
    event: cli_invocation
    agent: code-analyst
    message: "Codex exec for architecture analysis"
    details:
      cli: codex
      model: gpt-5-mini
      command: "echo '...' | codex exec --sandbox read-only"
      exit_code: 0
      duration_seconds: 45
```

Fallback 발생 시:
```yaml
  - timestamp: "2026-02-21T14:31:00Z"
    event: cli_fallback
    agent: code-analyst
    message: "Codex failed (exit 1), falling back to Claude tools"
    details:
      cli: codex
      original_error: "timeout after 120s"
      fallback_to: claude
```
