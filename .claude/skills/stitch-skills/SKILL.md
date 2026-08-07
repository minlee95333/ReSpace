---
name: stitch-skills
description: Google Labs stitch-skills integration for design systems, React components, multi-page websites, prompt enhancement, walkthrough videos, and shadcn/ui. "stitch", "stitch-skills", "design system", "react components", "stitch-loop", "enhance-prompt", "shadcn" 키워드에 반응.
---

# Stitch Skills -- Google Labs Integration

Google Labs의 stitch-skills 패키지를 통한 디자인 시스템 생성, React 컴포넌트 변환, 멀티페이지 사이트 빌드.

## Installation

```bash
# List available skills
npx skills add google-labs-code/stitch-skills --list

# Install individual sub-skills
npx skills add google-labs-code/stitch-skills --skill design-md --global
npx skills add google-labs-code/stitch-skills --skill react-components --global
npx skills add google-labs-code/stitch-skills --skill stitch-loop --global
npx skills add google-labs-code/stitch-skills --skill enhance-prompt --global
npx skills add google-labs-code/stitch-skills --skill remotion --global
npx skills add google-labs-code/stitch-skills --skill shadcn-ui --global
```

## Pre-check

```bash
npx skills list | grep stitch
```

If not installed, inform the user and provide installation commands above.

## Sub-skills

| Sub-skill | Purpose | Pipeline Phase |
|-----------|---------|----------------|
| `design-md` | 프로젝트 분석 → DESIGN.md 디자인 시스템 문서 생성 | Phase 2 (design) |
| `react-components` | 디자인 스크린 → React 컴포넌트 시스템 변환 + 검증 | Phase 3 (build) |
| `stitch-loop` | 단일 프롬프트 → 멀티페이지 웹사이트 빌드 | Phase 3 (build) |
| `enhance-prompt` | UI 아이디어 → 프레임워크 최적화 프롬프트로 변환 | Phase 2 입력, Phase 4 |
| `remotion` | 디자인 프로젝트 → 워크스루 비디오 생성 | Phase 3-4 (visuals) |
| `shadcn-ui` | shadcn/ui 컴포넌트 통합 가이드 | Phase 3 (build) |

---

## Pipeline Integration

### Phase 2 -- Design Enhancement

**enhance-prompt**: 디자인 프롬프트 최적화
1. SUMMARY.md + stack-profile.md를 컨텍스트로 제공
2. `enhance-prompt`로 디자인 생성 프롬프트 정제
3. 정제된 프롬프트를 Gemini CLI (design-agent)에 전달

**design-md**: 디자인 시스템 문서화
1. design-profile.yaml 생성 후
2. `design-md`로 DESIGN.md 생성 (디자인 토큰, 컴포넌트 스펙)

### Phase 3 -- Build Enhancement

**react-components**: React 기반 템플릿 사용 시
1. Input: design-profile.yaml + DESIGN.md
2. React 컴포넌트 스켈레톤 생성
3. SvelteKit/Next.js 템플릿에 통합

**stitch-loop**: 멀티페이지 사이트 빠른 빌드
1. Input: content.json + design tokens
2. 전체 사이트 페이지 생성
3. Claude가 커스터마이징

**shadcn-ui**: shadcn/ui 컴포넌트 사용 시
1. 적절한 import/usage 패턴 생성

### Phase 4 -- Demo Videos

**remotion** (sub-skill): 사이트 워크스루 비디오
1. site/ 빌드 완료 후
2. 포트폴리오 워크스루 비디오 생성
3. MP4 출력

---

## Fallback

stitch-skills 미설치 시:
1. 미설치 로그 기록
2. Claude 내장 기능으로 디자인/컴포넌트 생성 대체
3. 사용자에게 설치 안내

## Related

| Skill | Relationship |
|-------|-------------|
| `remotion` (standalone) | 고급 커스텀 비디오 — stitch/remotion은 간단 워크스루용 |
| `gemini` | 디자인 생성 — stitch enhance-prompt로 프롬프트 정제 가능 |
| `codex` | 코드 검증 — stitch 생성 컴포넌트를 codex로 검증 |

## Configuration

`.claude/settings.json` > `external_skills.stitch_skills`
