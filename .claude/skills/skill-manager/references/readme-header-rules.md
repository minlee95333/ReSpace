# README Header Rules - 개발 프로젝트 상태 표시 가이드

개발 진행 중인 프로젝트의 README 상단에 표시할 개발 상태, 기술 스택, 사용된 스킬 정보를 기재하는 규칙입니다.

---

## 1. 개발 진행 상황 (Progress Bar)

### 위치
README.md 최상단, 프로젝트 제목 바로 아래

### 형식

```markdown
## 📊 개발 진행 상황

| 단계 | 상태 | 진행률 |
|------|:----:|--------|
| 기획/설계 | ✅ | `████████████████████` 100% |
| 핵심 기능 | 🔄 | `████████████░░░░░░░░` 60% |
| UI/UX | ⏳ | `████░░░░░░░░░░░░░░░░` 20% |
| 테스트 | ⏳ | `░░░░░░░░░░░░░░░░░░░░` 0% |
| 문서화 | ⏳ | `░░░░░░░░░░░░░░░░░░░░` 0% |
| 배포 | ⏳ | `░░░░░░░░░░░░░░░░░░░░` 0% |

**전체 진행률**: `████████░░░░░░░░░░░░` **40%**
```

### Progress Bar 문자열 생성 규칙

```
진행률 0%:   ░░░░░░░░░░░░░░░░░░░░  (20칸 모두 빈칸)
진행률 25%:  █████░░░░░░░░░░░░░░░  (5칸 채움)
진행률 50%:  ██████████░░░░░░░░░░  (10칸 채움)
진행률 75%:  ███████████████░░░░░  (15칸 채움)
진행률 100%: ████████████████████  (20칸 모두 채움)

계산식: 채움 칸수 = round(진행률 / 5)
```

### 상태 아이콘

| 아이콘 | 의미 | 사용 시점 |
|:------:|------|----------|
| ✅ | 완료 | 100% 완료 |
| 🔄 | 진행중 | 현재 작업 중 (1~99%) |
| ⏳ | 대기 | 아직 시작 안함 (0%) |
| ⚠️ | 차단됨 | 외부 의존성으로 진행 불가 |
| 🔴 | 중단 | 개발 일시 중단 |

### 단계 정의

**기본 6단계** (필수):

1. **기획/설계** - 요구사항 분석, 아키텍처 설계, 데이터 모델링
2. **핵심 기능** - 비즈니스 로직, API, 데이터베이스 구현
3. **UI/UX** - 프론트엔드, 사용자 인터페이스, 반응형 디자인
4. **테스트** - 단위 테스트, 통합 테스트, E2E 테스트
5. **문서화** - API 문서, 사용자 가이드, 개발자 문서
6. **배포** - CI/CD, 인프라 구성, 프로덕션 배포

**확장 단계** (선택):

- **보안 감사** - 취약점 점검, 보안 테스트
- **성능 최적화** - 부하 테스트, 캐싱, 쿼리 최적화
- **국제화(i18n)** - 다국어 지원
- **접근성(a11y)** - WCAG 준수

### 전체 진행률 계산

```
전체 진행률 = Σ(각 단계 진행률) / 단계 수

예시:
- 기획/설계: 100%
- 핵심 기능: 60%
- UI/UX: 20%
- 테스트: 0%
- 문서화: 0%
- 배포: 0%

전체 = (100 + 60 + 20 + 0 + 0 + 0) / 6 = 30%
```

### 대안 형식 (단순화)

작은 프로젝트용 간소화 버전:

```markdown
## 📊 개발 진행 상황

`████████████░░░░░░░░` **60%** - 핵심 기능 개발 중

- [x] 기획 완료
- [x] 데이터베이스 설계
- [x] API 구현
- [ ] 프론트엔드 개발
- [ ] 테스트 작성
- [ ] 배포
```

---

## 2. 기술 스택 (Tech Stack)

### 위치
개발 진행 상황 바로 아래

### 형식

```markdown
## 🛠️ Tech Stack

### Core
| 분류 | 기술 | 버전 | 용도 |
|------|------|------|------|
| Language | TypeScript | 5.x | 타입 안전성 |
| Runtime | Node.js | 20.x | 서버 런타임 |
| Framework | Next.js | 15.x | 풀스택 프레임워크 |

### Frontend
| 분류 | 기술 | 버전 | 용도 |
|------|------|------|------|
| UI Library | React | 19.x | 컴포넌트 기반 UI |
| Styling | Tailwind CSS | 3.x | 유틸리티 CSS |
| Components | shadcn/ui | latest | UI 컴포넌트 |
| State | Zustand | 5.x | 클라이언트 상태 관리 |
| Data Fetching | TanStack Query | 5.x | 서버 상태 관리 |

### Backend
| 분류 | 기술 | 버전 | 용도 |
|------|------|------|------|
| Database | PostgreSQL | 16.x | 관계형 DB |
| ORM | Prisma | 5.x | 데이터베이스 ORM |
| Auth | NextAuth.js | 5.x | 인증/인가 |

### DevOps
| 분류 | 기술 | 버전 | 용도 |
|------|------|------|------|
| Deploy | Vercel | - | 호스팅 플랫폼 |
| CI/CD | GitHub Actions | - | 자동화 파이프라인 |
```

### 배지 형식 (대안)

shields.io 배지 활용:

```markdown
## 🛠️ Tech Stack

![TypeScript](https://img.shields.io/badge/TypeScript-5.x-3178C6?logo=typescript&logoColor=white)
![Next.js](https://img.shields.io/badge/Next.js-15-000000?logo=next.js&logoColor=white)
![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black)
![Tailwind CSS](https://img.shields.io/badge/Tailwind_CSS-3-06B6D4?logo=tailwindcss&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?logo=postgresql&logoColor=white)
![Prisma](https://img.shields.io/badge/Prisma-5-2D3748?logo=prisma&logoColor=white)
```

### Tech Stack 감지 규칙

프로젝트 파일 기반 자동 감지:

| 파일 | 감지 기술 |
|------|----------|
| `package.json` | Node.js 의존성 (next, react, tailwindcss 등) |
| `tsconfig.json` | TypeScript |
| `Cargo.toml` | Rust |
| `pyproject.toml` / `requirements.txt` | Python |
| `go.mod` | Go |
| `pubspec.yaml` | Flutter/Dart |
| `docker-compose.yml` | Docker |
| `.github/workflows/` | GitHub Actions |
| `vercel.json` | Vercel |
| `prisma/schema.prisma` | Prisma |

---

## 3. 사용된 스킬 (Used Skills)

### 위치
Tech Stack 바로 아래

### 형식

```markdown
## 🎯 Used Skills

이 프로젝트는 [my-skills](https://github.com/tygwan/my-skills) 저장소의 다음 스킬을 활용하여 개발되었습니다:

| 스킬 | 용도 | 단계 |
|------|------|------|
| [nextjs15-init](https://github.com/tygwan/my-skills/tree/master/nextjs15-init) | 프로젝트 초기 설정 | 기획/설계 |
| [landing-page-guide](https://github.com/tygwan/my-skills/tree/master/landing-page-guide) | 랜딩 페이지 구현 | UI/UX |
| [test-driven-development](https://github.com/tygwan/my-skills/tree/master/test-driven-development) | TDD 워크플로우 | 테스트 |
| [systematic-debugging](https://github.com/tygwan/my-skills/tree/master/systematic-debugging) | 버그 해결 | 핵심 기능 |
| [senior-secops](https://github.com/tygwan/my-skills/tree/master/senior-secops) | 보안 검토 | 보안 감사 |
```

### 간소화 형식

```markdown
## 🎯 Used Skills

- **nextjs15-init** - 프로젝트 초기 설정
- **landing-page-guide** - 랜딩 페이지 구현
- **test-driven-development** - TDD 워크플로우
- **skill-manager** - 버전 관리 및 배포
```

### 스킬 사용 추적

개발 과정에서 스킬 사용 시 자동 기록:

```yaml
# .claude/project-skills.yml (선택적 생성)
project: my-awesome-app
skills_used:
  - name: nextjs15-init
    used_at: 2025-01-15
    phase: 기획/설계
    notes: "프로젝트 초기 구조 생성"

  - name: test-driven-development
    used_at: 2025-01-20
    phase: 테스트
    notes: "인증 모듈 TDD 적용"

  - name: systematic-debugging
    used_at: 2025-01-25
    phase: 핵심 기능
    notes: "API 응답 지연 문제 해결"
```

---

## 4. 전체 README 헤더 템플릿

```markdown
# 프로젝트명

프로젝트 한 줄 설명

---

## 📊 개발 진행 상황

| 단계 | 상태 | 진행률 |
|------|:----:|--------|
| 기획/설계 | ✅ | `████████████████████` 100% |
| 핵심 기능 | 🔄 | `████████████░░░░░░░░` 60% |
| UI/UX | ⏳ | `████░░░░░░░░░░░░░░░░` 20% |
| 테스트 | ⏳ | `░░░░░░░░░░░░░░░░░░░░` 0% |
| 문서화 | ⏳ | `░░░░░░░░░░░░░░░░░░░░` 0% |
| 배포 | ⏳ | `░░░░░░░░░░░░░░░░░░░░` 0% |

**전체 진행률**: `██████░░░░░░░░░░░░░░` **30%**

---

## 🛠️ Tech Stack

### Core
| 분류 | 기술 | 버전 |
|------|------|------|
| Language | TypeScript | 5.x |
| Framework | Next.js | 15.x |
| Database | PostgreSQL | 16.x |

### Frontend
| 분류 | 기술 | 버전 |
|------|------|------|
| UI | React | 19.x |
| Styling | Tailwind CSS | 3.x |
| Components | shadcn/ui | latest |

---

## 🎯 Used Skills

| 스킬 | 용도 |
|------|------|
| nextjs15-init | 프로젝트 초기 설정 |
| landing-page-guide | 랜딩 페이지 구현 |
| test-driven-development | TDD 워크플로우 |

---

## 개요

(여기부터 기존 README 내용 시작)
```

---

## 5. skill-manager 통합 워크플로우

### Workflow: README 헤더 업데이트

**Purpose**: 프로젝트 README 상단의 개발 상태, Tech Stack, Used Skills 업데이트

**Steps**:

1. **진행 상황 업데이트 (Progress Update)**
   ```
   사용자 요청: "진행상황 업데이트해줘" 또는 "핵심 기능 80%로 변경해줘"

   → 각 단계의 진행률 입력 요청
   → 전체 진행률 자동 계산
   → README.md 업데이트
   ```

2. **Tech Stack 감지 (Auto-detect Tech Stack)**
   ```
   프로젝트 파일 스캔:
   - package.json → dependencies 분석
   - tsconfig.json → TypeScript 확인
   - prisma/schema.prisma → DB/ORM 확인
   - docker-compose.yml → 컨테이너화 확인

   → Tech Stack 테이블 자동 생성
   ```

3. **Used Skills 기록 (Record Used Skills)**
   ```
   스킬 사용 시 자동 감지:
   - /skill <name> 호출 기록
   - SKILL.md 참조 기록

   → Used Skills 섹션 자동 업데이트
   ```

### 명령어 예시

```bash
# 진행상황 수동 업데이트
/skill-manager update-progress

# Tech Stack 자동 감지 및 업데이트
/skill-manager detect-techstack

# Used Skills 업데이트
/skill-manager update-skills

# 전체 헤더 재생성
/skill-manager refresh-header
```

---

## 6. Progress Bar 생성 유틸리티

### JavaScript/TypeScript

```typescript
function generateProgressBar(percentage: number): string {
  const totalBlocks = 20;
  const filledBlocks = Math.round(percentage / 5);
  const emptyBlocks = totalBlocks - filledBlocks;

  const filled = '█'.repeat(filledBlocks);
  const empty = '░'.repeat(emptyBlocks);

  return `\`${filled}${empty}\` ${percentage}%`;
}

// 사용 예시
generateProgressBar(60);  // `████████████░░░░░░░░` 60%
generateProgressBar(100); // `████████████████████` 100%
generateProgressBar(0);   // `░░░░░░░░░░░░░░░░░░░░` 0%
```

### Python

```python
def generate_progress_bar(percentage: int) -> str:
    total_blocks = 20
    filled_blocks = round(percentage / 5)
    empty_blocks = total_blocks - filled_blocks

    filled = '█' * filled_blocks
    empty = '░' * empty_blocks

    return f"`{filled}{empty}` {percentage}%"

# 사용 예시
generate_progress_bar(60)  # `████████████░░░░░░░░` 60%
```

---

## 7. 베스트 프랙티스

### DO (권장)

- ✅ 주요 마일스톤 달성 시 진행률 업데이트
- ✅ 실제 완료된 작업 기준으로 진행률 산정
- ✅ Tech Stack은 실제 사용 기술만 기재
- ✅ Used Skills는 실질적으로 활용한 스킬만 기재
- ✅ 버전 정보는 주요 버전(major.minor)만 기재

### DON'T (비권장)

- ❌ 매일 진행률 미세 조정 (의미 없는 업데이트)
- ❌ 계획된 기술을 미리 Tech Stack에 기재
- ❌ 실제 사용하지 않은 스킬 기재
- ❌ 과장된 진행률 기재

---

## References

- [Keep a Changelog](https://keepachangelog.com/)
- [shields.io](https://shields.io/)
- [Conventional Commits](https://www.conventionalcommits.org/)
