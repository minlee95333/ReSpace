---
name: remotion
description: Programmatic video generation with React using Remotion. JSX/CSS compositions rendered to MP4. "remotion", "video", "비디오", "MP4", "animation", "워크스루", "demo video", "영상" 키워드에 반응.
---

# Remotion -- Programmatic Video Generation

React 기반 프로그래밍 방식의 비디오 생성. JSX/CSS 컴포지션을 MP4로 렌더링합니다.

## Installation

```bash
# Create new remotion project
npx create-video@latest

# Or install skills into existing project
npx skills add remotion-dev/skills
```

## Pre-check

```bash
npx remotion --version 2>/dev/null || echo "Remotion not installed"
```

If not installed, provide installation commands above.

## Core Concepts

| Concept | Description |
|---------|-------------|
| **Composition** | React 컴포넌트로 정의된 비디오 |
| **useCurrentFrame()** | 현재 프레임 번호 반환 훅 |
| **interpolate()** | 프레임 범위 → 값 매핑 (opacity, position, scale) |
| **FPS** | 초당 프레임 (기본: 30) |
| **Duration** | 프레임 단위 길이 (300 = 30fps에서 10초) |

---

## Pipeline Integration

### Pipeline Replay Videos

파이프라인 실행 과정을 비디오로 생성:
1. Input: .state.yaml 타임라인 + 생성 아티팩트
2. 각 Phase 전환을 React 컴포지션으로 생성
3. 애니메이션 트랜지션
4. MP4 렌더링

### Sprint Retrospective Videos

스프린트 요약 비디오:
1. Input: Sprint 데이터 (velocity, burndown, 완료 태스크)
2. 데이터 시각화 컴포지션
3. 스프린트 메트릭 애니메이션
4. MP4 렌더링

### Release Demo Videos

릴리스 데모 비디오:
1. Input: CHANGELOG.md + 스크린샷
2. 각 기능별 컴포지션
3. 트랜지션 애니메이션
4. 타이틀 카드 포함 MP4

---

## Video Composition Pattern

```jsx
import { useCurrentFrame, interpolate, AbsoluteFill } from 'remotion';

export const PhaseTransition = ({ phase, title, progress }) => {
  const frame = useCurrentFrame();

  const opacity = interpolate(frame, [0, 30], [0, 1], {
    extrapolateRight: 'clamp',
  });

  const scale = interpolate(frame, [0, 30], [0.8, 1], {
    extrapolateRight: 'clamp',
  });

  return (
    <AbsoluteFill style={{ opacity, transform: `scale(${scale})` }}>
      <h1>Phase {phase}: {title}</h1>
      <div style={{ width: `${progress}%`, height: 8, background: '#4CAF50' }} />
    </AbsoluteFill>
  );
};
```

## Rendering

```bash
# Render to MP4
npx remotion render src/index.tsx CompositionName out/video.mp4

# Preview in browser
npx remotion preview src/index.tsx
```

---

## stitch-skills Overlap

| Use Case | Recommended |
|----------|-------------|
| 간단 사이트 워크스루 | `stitch-skills/remotion` sub-skill |
| 커스텀 애니메이션 | Standalone `remotion` |
| 데이터 시각화 비디오 | Standalone `remotion` |
| 스프린트/릴리스 비디오 | Standalone `remotion` |

## Fallback

remotion 미설치 시:
1. 미설치 로그 기록
2. 정적 대안 제안 (스크린샷 + Mermaid 다이어그램)
3. 사용자에게 설치 안내

## Dependencies

- Node.js 18+
- ffmpeg (MP4 인코딩)

## Configuration

`.claude/settings.json` > `external_skills.remotion`

## Related

| Skill | Purpose |
|-------|---------|
| `stitch-skills` | remotion sub-skill 포함 (간단 워크스루) |
| `gemini` | SVG/시각 자산 생성 (정적 대안) |
