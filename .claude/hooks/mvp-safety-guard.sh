#!/usr/bin/env bash
# MVP Safety Guard — PreToolUse hook
# 현재 lifecycle stage에 맞지 않는 과도한 작업을 경고

TOOL_NAME="$1"
SETTINGS_FILE=".claude/settings.json"

# settings.json에서 현재 stage 읽기
if [ -f "$SETTINGS_FILE" ]; then
  CURRENT_STAGE=$(jq -r '.lifecycle.current_stage // "mvp"' "$SETTINGS_FILE" 2>/dev/null)
else
  CURRENT_STAGE="mvp"
fi

# Write 도구 사용 시 파일 경로 기반 경고
if [ "$TOOL_NAME" = "Write" ]; then
  # stdin에서 파일 경로 추출
  INPUT=$(cat)
  FILE_PATH=$(echo "$INPUT" | jq -r '.file_path // ""' 2>/dev/null)

  if [ "$CURRENT_STAGE" = "mvp" ]; then
    # MVP에서 Production 수준 파일 생성 경고
    case "$FILE_PATH" in
      *terraform*|*k8s/*|*kubernetes*)
        echo "⚠️ [MVP Guard] IaC/K8s 파일은 Production 단계에서 필요합니다. 현재: MVP"
        ;;
      *monitoring/*|*dashboards/*|*alerts/*)
        echo "⚠️ [MVP Guard] 모니터링 설정은 PoC 단계부터 필요합니다. 현재: MVP"
        ;;
      *deploy/*|*Dockerfile*)
        echo "⚠️ [MVP Guard] Docker/배포 설정은 PoC 단계부터 필요합니다. 현재: MVP"
        ;;
    esac
  fi
fi

# Bash 도구 사용 시 위험 명령어 체크
if [ "$TOOL_NAME" = "Bash" ]; then
  INPUT=$(cat)
  COMMAND=$(echo "$INPUT" | jq -r '.command // ""' 2>/dev/null)

  # 환경 파괴 방지
  case "$COMMAND" in
    *"rm -rf /"*|*"rm -rf /*"*)
      echo "DENY: 루트 디렉토리 삭제 차단"
      exit 2
      ;;
    *"DROP DATABASE"*|*"drop database"*)
      echo "DENY: 데이터베이스 삭제 차단"
      exit 2
      ;;
  esac
fi

exit 0
