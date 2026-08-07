#!/usr/bin/env bash
# state-transition.sh — Bridge hook: State Machine ↔ Quality Gates ↔ Feedback
# Triggered on PostToolUse (Write) when .state.yaml is modified.
# Detects state transitions and triggers appropriate automation.

set -euo pipefail

TOOL_NAME="${1:-}"
PROJECT_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
LOG_DIR="$PROJECT_ROOT/.claude/logs"
mkdir -p "$LOG_DIR"

# Only process Write/Edit tool calls
[[ "$TOOL_NAME" != "Write" && "$TOOL_NAME" != "Edit" ]] && exit 0

# Check if stdin contains .state.yaml path
INPUT=$(cat /dev/stdin 2>/dev/null || echo "")
if ! echo "$INPUT" | grep -q '\.state\.yaml'; then
  exit 0
fi

# Extract project name from the file path
STATE_FILE=$(echo "$INPUT" | grep -oP 'workspace/\K[^/]+(?=/\.state\.yaml)' || true)
[[ -z "$STATE_FILE" ]] && exit 0

FULL_STATE_PATH="$PROJECT_ROOT/workspace/$STATE_FILE/.state.yaml"
[[ ! -f "$FULL_STATE_PATH" ]] && exit 0

# Read current state
CURRENT_STATE=$(grep -oP 'current_state:\s*\K\S+' "$FULL_STATE_PATH" 2>/dev/null || echo "unknown")
PREVIOUS_STATE=$(grep -oP 'previous_state:\s*\K\S+' "$FULL_STATE_PATH" 2>/dev/null || echo "null")

TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

log_event() {
  echo "[$TIMESTAMP] state-transition: $1" >> "$LOG_DIR/state-transitions.log"
}

# === Transition-based actions ===

case "$CURRENT_STATE" in
  analyzed)
    # Phase 1 complete → suggest PROGRESS.md update
    log_event "$STATE_FILE: analyzing → analyzed (Phase 1 complete)"
    echo "Phase 1 analysis complete for $STATE_FILE. PROGRESS.md update recommended."
    ;;

  design_review)
    # Phase 2 complete → awaiting user review
    log_event "$STATE_FILE: designing → design_review (awaiting approval)"
    ;;

  validating)
    # Phase 3 → 3.5: Quality gate pre-build check
    log_event "$STATE_FILE: building → validating (quality-gate pre-build)"
    echo "Quality gate: pre-build validation triggered for $STATE_FILE."
    ;;

  build_review)
    # Validation passed → awaiting user preview approval
    log_event "$STATE_FILE: validating → build_review (validation passed)"
    ;;

  done)
    # Pipeline complete → suggest feedback loop + portfolio sync
    log_event "$STATE_FILE: deploying → done (pipeline complete)"
    echo "Pipeline complete for $STATE_FILE."
    echo "  - Consider running /craft-sync to update portfolio"
    echo "  - Consider capturing learnings with feedback-loop"
    ;;

  failed)
    # Error state → log for recovery
    log_event "$STATE_FILE: → failed (error recovery needed)"
    echo "Project $STATE_FILE entered failed state. Use /craft-state $STATE_FILE resume --retry to recover."
    ;;

  paused)
    # User paused → log
    log_event "$STATE_FILE: $PREVIOUS_STATE → paused (user interrupt)"
    ;;

  *)
    # Other transitions → just log
    log_event "$STATE_FILE: state=$CURRENT_STATE"
    ;;
esac

exit 0
