#!/usr/bin/env bash
# Lifecycle Tracker — PostToolUse hook
# 파일 변경 시 해당 도메인과 lifecycle stage를 추적

TOOL_NAME="$1"
LOG_DIR=".claude/logs"
LOG_FILE="$LOG_DIR/lifecycle-activity.jsonl"
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

# 로그 디렉토리 생성
mkdir -p "$LOG_DIR"

# stdin에서 도구 입력 읽기
INPUT=$(cat)

# 파일 경로 추출
case "$TOOL_NAME" in
  Write|Edit)
    FILE_PATH=$(echo "$INPUT" | jq -r '.file_path // ""' 2>/dev/null)
    ;;
  Bash)
    FILE_PATH=""
    ;;
  *)
    exit 0
    ;;
esac

# 파일 경로에서 도메인 분류
classify_domain() {
  local path="$1"
  case "$path" in
    *component*|*page*|*layout*|*style*|*.css|*.scss)
      echo "frontend" ;;
    *route*|*controller*|*service*|*middleware*|*api*)
      echo "backend" ;;
    *prisma*|*migration*|*schema*|*seed*)
      echo "database" ;;
    *docker*|*Dockerfile*|*.yml|*deploy*|*terraform*|*k8s*)
      echo "infrastructure" ;;
    *auth*|*security*|*permission*|*rbac*)
      echo "security" ;;
    *test*|*spec*|*__test__*)
      echo "testing" ;;
    *monitor*|*metric*|*health*|*alert*)
      echo "observability" ;;
    *.md|*doc*)
      echo "documentation" ;;
    *)
      echo "other" ;;
  esac
}

if [ -n "$FILE_PATH" ]; then
  DOMAIN=$(classify_domain "$FILE_PATH")

  # JSONL 로그 기록
  echo "{\"timestamp\":\"$TIMESTAMP\",\"tool\":\"$TOOL_NAME\",\"file\":\"$FILE_PATH\",\"domain\":\"$DOMAIN\"}" >> "$LOG_FILE"

  # 로그 크기 관리 (1000줄 초과 시 최근 500줄만 유지)
  if [ -f "$LOG_FILE" ]; then
    LINE_COUNT=$(wc -l < "$LOG_FILE")
    if [ "$LINE_COUNT" -gt 1000 ]; then
      tail -500 "$LOG_FILE" > "$LOG_FILE.tmp" && mv "$LOG_FILE.tmp" "$LOG_FILE"
    fi
  fi
fi

exit 0
