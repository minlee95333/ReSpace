---
name: claude-office
description: Office document automation -- PPTX presentations, DOCX documents, XLSX spreadsheets, PDF reports. "office", "pptx", "docx", "xlsx", "pdf", "프레젠테이션", "presentation", "보고서", "report", "엑셀", "워드" 키워드에 반응.
---

# Claude Office Skills -- Document Automation

Office 문서 자동화 스킬. PPTX, DOCX, XLSX, PDF 문서를 프로그래밍 방식으로 생성합니다.

## Installation

```bash
npx skills add tfriedel/claude-office-skills
```

## System Dependencies

| Dependency | Purpose | Install (Ubuntu) | Install (macOS) | Check |
|------------|---------|-----------------|-----------------|-------|
| LibreOffice | 문서 변환 | `sudo apt install libreoffice` | `brew install --cask libreoffice` | `soffice --version` |
| Poppler | PDF 렌더링 | `sudo apt install poppler-utils` | `brew install poppler` | `pdftoppm -v` |
| Pandoc | 포맷 변환 | `sudo apt install pandoc` | `brew install pandoc` | `pandoc --version` |

## Pre-check

```bash
command -v soffice && echo "LibreOffice OK" || echo "LibreOffice MISSING"
command -v pdftoppm && echo "Poppler OK" || echo "Poppler MISSING"
command -v pandoc && echo "Pandoc OK" || echo "Pandoc MISSING"
```

---

## Document Types

### PPTX -- Presentations

| Use Case | Input | Output |
|----------|-------|--------|
| 프로젝트 리포트 | SUMMARY.md + analysis/*.md | project-report.pptx |
| 스프린트 리뷰 | Sprint 데이터 | sprint-N-review.pptx |
| 아키텍처 개요 | architecture.md | architecture.pptx |
| 릴리스 데모 | CHANGELOG.md + 스크린샷 | release-demo.pptx |

Features: HTML/CSS → PowerPoint 변환, 템플릿 기반 슬라이드, 레이아웃 검증

### DOCX -- Word Documents

| Use Case | Input | Output |
|----------|-------|--------|
| 기술 문서 | TECH-SPEC.md | tech-spec.docx |
| PRD 내보내기 | PRD.md | prd.docx |
| Gate 리뷰 문서 | Gate 검증 결과 | gate-review.docx |
| API 문서 | API-SPEC.md | api-spec.docx |

Features: 변경 추적(redlining), OOXML 조작, 텍스트 추출

### XLSX -- Spreadsheets

| Use Case | Input | Output |
|----------|-------|--------|
| 비용 분석 | CLI 사용량 + 토큰 비용 | cost-analysis.xlsx |
| 스프린트 메트릭 | Velocity/burndown 데이터 | sprint-metrics.xlsx |
| 테스트 커버리지 | Coverage 데이터 | test-coverage.xlsx |

Features: 수식 기반 재무 모델, 색상 코딩, 데이터 유효성 검증

### PDF -- Reports

| Use Case | Input | Output |
|----------|-------|--------|
| 포트폴리오 PDF | site/ 콘텐츠 | portfolio-export.pdf |
| 릴리스 노트 | CHANGELOG.md | release-notes.pdf |
| 종합 리포트 | 모든 아티팩트 | full-report.pdf |

Features: 양식 자동 채우기, 문서 병합, 데이터 추출

---

## Conversion Pipeline

```
Markdown ──→ Pandoc ──→ DOCX
Markdown ──→ Pandoc ──→ PPTX (via reference template)
Data (JSON) ──→ Python/JS ──→ XLSX
HTML ──→ soffice --convert-to pdf ──→ PDF
  or
Markdown ──→ Pandoc ──→ PDF
```

Output directory: `out/documents/` (configurable via `external_skills.claude_office.output_dir`)

---

## Fallback

의존성 미설치 시 단계적 대체:
1. LibreOffice 없음 → Pandoc만으로 변환 (DOCX, PDF)
2. Pandoc 없음 → Markdown 형식으로 출력
3. PPTX 불가 → Markdown 아웃라인 출력
4. XLSX 불가 → CSV 출력

## Error Handling

| Situation | Action |
|-----------|--------|
| LibreOffice 미설치 | 설치 안내 + Pandoc fallback |
| Poppler 미설치 | 설치 안내 (PDF 이미지 변환만 불가) |
| Pandoc 미설치 | 설치 안내 + raw Markdown 출력 |
| 변환 실패 | 에러 로그 + 원본 콘텐츠 제공 |

## Configuration

`.claude/settings.json` > `external_skills.claude_office`

## Related

| Skill | Purpose |
|-------|---------|
| `analytics` | XLSX 리포트용 데이터 소스 |
| `gemini` | 프레젠테이션용 시각 자산 생성 |
| `remotion` | 비디오 리포트 (정적 문서 대안) |
