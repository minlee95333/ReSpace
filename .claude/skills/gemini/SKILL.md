---
name: fc-gemini
description: Invoke Gemini CLI for design, UI/UX, and visual asset generation within foliocraft pipeline. "gemini", "제미나이", "디자인", "design", "UI", "UX", "시각화", "SVG" 키워드에 반응.
---

# fc-gemini — Gemini CLI Skill for foliocraft

foliocraft 파이프라인에서 디자인, UI/UX, 시각화 작업에 Gemini CLI를 활용하는 스킬.

## Use Cases

| Phase | Agent | Use Case | Description |
|-------|-------|----------|-------------|
| 2 | design-agent | Generate design-profile.yaml | 프로젝트 분석 → 최적 디자인 프로파일 생성 |
| 3 | figure-designer | Mermaid diagrams, SVG visuals | 아키텍처 다이어그램, 시각 자산 생성 |
| 3 | page-writer | CSS animation suggestions | 선택적. 복잡한 CSS 애니메이션 제안 |

## Model Selection

| Task | Default Model | Upgrade Condition | Upgrade Model |
|------|---------------|-------------------|---------------|
| Phase 2 디자인 생성 | `gemini-2.5-flash` | 섹션 5+개 또는 커스텀 팔레트 필요 시 | `gemini-2.5-pro` |
| Phase 3 Mermaid 다이어그램 | `gemini-2.5-flash` | 복잡한 아키텍처 (노드 10+) | `gemini-2.5-pro` |
| Phase 3 SVG 생성 | `gemini-2.5-pro` | — (시각 품질 중요, 항상) | — |

### Selection Logic

```
1. 기본 모델: gemini-2.5-flash (fast, free tier)
2. 업그레이드 조건 확인:
   - 섹션 5+개 → gemini-2.5-pro
   - 커스텀 팔레트 필요 → gemini-2.5-pro
   - 복잡한 아키텍처 (노드 10+) → gemini-2.5-pro
   - SVG 생성 → 항상 gemini-2.5-pro
3. 수동 오버라이드: -m 플래그로 사용자 지정 가능
4. .state.yaml log에 사용 모델 기록
```

## Invocation Patterns

모든 호출에 `-y` (yolo/auto-approve) 플래그를 반드시 포함합니다. 파이프라인 자동화를 위한 비대화형 실행.

### Design Profile Generation

```bash
gemini -p "PROMPT" -y -m MODEL -o text
```

### Mermaid Diagram Generation

```bash
gemini -p "PROMPT" -y -m MODEL -o text
```

### SVG Generation

```bash
gemini -p "PROMPT" -y -m gemini-2.5-pro -o text
```

## Prompt Templates

### 1. Design Profile Generation

```
Given this project analysis:

---SUMMARY.md---
{summary_md_content}
---END---

---stack-profile.md---
{stack_profile_content}
---END---

Design presets for domain "{domain}":

Palette:
{palette_yaml_content}

Typography:
{typography_yaml_content}

Layout:
{layout_yaml_content}

Generate a design-profile.yaml for this project. Include:
- project: name, tagline (one-line), domain
- template: recommended template name from [sveltekit-dashboard, astro-landing]
- palette: customized colors (modify max 3 colors from the provided preset)
- typography: selected preset with any font-size adjustments
- layout: selected archetype with section ordering
- sections: ordered list of section types with content hints

Output valid YAML only. Include YAML comments (# ...) explaining each design choice.
Do not wrap in code fences.
```

### 2. Mermaid Diagram Generation

```
Generate a Mermaid {diagram_type} diagram based on the following architecture:

{architecture_content}

Color scheme:
- accent: {accent_color}
- background: {bg_primary}
- text: {text_primary}

Requirements:
- Use {diagram_type} syntax (graph TB, sequenceDiagram, timeline, etc.)
- Style: clean, minimal, professional
- Appropriate level of abstraction (major modules/layers, not individual files)
- Apply colors via classDef where applicable

Output only valid Mermaid syntax. Do not include code fences or explanations.
```

### 3. SVG Generation

```
Create an SVG visualization for: {description}

Color palette (use these CSS custom property values):
- --pn-accent: {accent_color}
- --pn-bg-primary: {bg_color}
- --pn-text-primary: {text_color}
- --pn-accent-secondary: {accent_secondary}

Style requirements:
- Geometric, modern, minimal aesthetic
- Maximum dimensions: 800x600
- Use the provided color palette exclusively
- Include appropriate viewBox attribute
- Optimize for web (no unnecessary metadata)

Output only valid SVG markup. Start with <svg and end with </svg>.
No code fences, no explanations.
```

## Output Handling

### Design Profile (YAML)

```
1. Capture gemini output to variable
2. Validate: parse as YAML (yq or python -c "import yaml; yaml.safe_load(open(...))")
3. Check required fields: project, template, domain, palette, typography, layout, sections
4. Check palette colors are valid CSS color values
5. Check template is one of: sveltekit-dashboard, astro-landing
6. If valid → write to workspace/{project}/design-profile.yaml
7. If invalid → retry with simplified prompt
```

### Mermaid Diagram

```
1. Capture gemini output
2. Validate: output contains one of: graph, sequenceDiagram, timeline, flowchart, classDiagram, erDiagram
3. Strip any accidental code fences (```mermaid ... ```)
4. If valid → write to workspace/{project}/site/src/diagrams/{name}.mmd
5. If invalid → retry with explicit syntax instruction
```

### SVG Markup

```
1. Capture gemini output
2. Validate: output starts with <svg (allowing whitespace) and ends with </svg>
3. Strip any text before <svg or after </svg>
4. If valid → write to workspace/{project}/site/src/diagrams/{name}.svg
5. If invalid → retry with stricter output instruction
```

## Error Handling

```
1. Execute gemini CLI command
2. If exit code != 0 or timeout (120s):
   a. Log error to .state.yaml (event: "error", agent: caller, message: stderr)
   b. Retry once with simplified prompt (remove optional context, keep essentials)
3. If retry fails:
   a. Log fallback event to .state.yaml (event: "cli_fallback", details: {from: "gemini", to: "claude"})
   b. Fall back to Claude for the same task
   c. Claude uses identical inputs but generates output directly
4. Update .state.yaml with cli_used field accordingly
```

## State Integration

모든 Gemini CLI 호출은 `.state.yaml`에 기록됩니다:

```yaml
# 호출 시작
log:
  - timestamp: {ISO-8601}
    event: cli_invocation
    agent: {calling_agent}
    message: "Gemini CLI invoked for {task}"
    details:
      cli: gemini
      model: {model_used}
      task: {design|mermaid|svg}

# 성공 시
log:
  - timestamp: {ISO-8601}
    event: agent_complete
    agent: {calling_agent}
    message: "Gemini CLI completed {task}"
    details:
      cli: gemini
      model: {model_used}
      output_file: {path}

# 실패/폴백 시
log:
  - timestamp: {ISO-8601}
    event: cli_fallback
    agent: {calling_agent}
    message: "Gemini CLI failed, falling back to Claude"
    details:
      from: gemini
      to: claude
      error: {error_message}
```
