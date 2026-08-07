#!/bin/bash
#
# Notion Auto-Sync Hook
# Detects document/state changes and queues pending sync for Notion.
# Actual Notion API calls happen via Claude MCP or REST API, not this hook.
#
# Events: PostToolUse (Write, Edit, Bash)
# Trigger: docs, state, sprint, deploy, craft artifacts changes
#

set +e

TOOL_NAME="$1"

# Process Write, Edit, and Bash (git commit) operations
if [[ "$TOOL_NAME" == "Bash" ]]; then
    TOOL_INPUT="${TOOL_INPUT:-$2}"
    # Bash: only trigger on git commit events
    if [[ "$TOOL_INPUT" != *"git commit"* ]]; then
        exit 0
    fi
    SYNC_TRIGGER="commit"
elif [[ "$TOOL_NAME" == "Write" || "$TOOL_NAME" == "Edit" ]]; then
    SYNC_TRIGGER="file_change"
else
    exit 0
fi

# Configuration
PROJECT_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || echo ".")
SETTINGS_FILE="$PROJECT_ROOT/.claude/settings.json"
CACHE_DIR="$PROJECT_ROOT/.claude/cache/notion"
LOG_DIR="$PROJECT_ROOT/.claude/logs"

# Read tool input
TOOL_INPUT="${TOOL_INPUT:-$2}"
if [[ -z "$TOOL_INPUT" ]]; then
    exit 0
fi

# Check if Notion sync is enabled (verify enabled: true, not just key existence)
if [[ ! -f "$SETTINGS_FILE" ]]; then
    exit 0
fi

NOTION_BLOCK=$(sed -n '/"notion"/,/^  }/p' "$SETTINGS_FILE" 2>/dev/null)
if ! echo "$NOTION_BLOCK" | grep -q '"enabled".*true'; then
    exit 0
fi

# Ensure cache directory
mkdir -p "$CACHE_DIR" 2>/dev/null || true

# Check if the changed file is a sync target
is_sync_target() {
    case "$TOOL_INPUT" in
        # Documents
        *docs/*|*PROGRESS.md|*TASKS.md|*SPEC.md|*CHECKLIST.md|*PRD.md|*TECH-SPEC.md)
            return 0 ;;
        # State machine
        *.state.yaml)
            return 0 ;;
        # Sprint data
        *SPRINT.md|*sprints/*)
            return 0 ;;
        # Deploy config
        *deploy.yaml)
            return 0 ;;
        # Changelog, README
        *CHANGELOG.md|*README.md)
            return 0 ;;
        # Craft pipeline artifacts
        *content.json|*tokens.css|*design-profile.yaml|*SUMMARY.md)
            return 0 ;;
        # Analysis artifacts
        *analysis/*.md|*architecture.md|*narrative.md|*stack-profile.md|*experience-blocks.md)
            return 0 ;;
        *)
            return 1 ;;
    esac
}

# Route file to target Notion DB
get_target_db() {
    case "$TOOL_INPUT" in
        *.state.yaml)                                        echo "activity_log" ;;
        *deploy.yaml)                                        echo "projects" ;;
        *SPRINT.md|*sprints/*)                               echo "sprints" ;;
        *TASKS.md|*CHECKLIST.md)                             echo "tasks" ;;
        *CHANGELOG.md|*README.md)                            echo "activity_log" ;;
        *docs/*|*PROGRESS.md|*SPEC.md|*PRD.md|*TECH-SPEC.md) echo "documents" ;;
        *content.json|*tokens.css|*design-profile.yaml|*SUMMARY.md) echo "documents" ;;
        *analysis/*.md|*architecture.md|*narrative.md|*stack-profile.md|*experience-blocks.md) echo "documents" ;;
        *)                                                   echo "unknown" ;;
    esac
}

if ! is_sync_target; then
    exit 0
fi

TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || date +"%Y-%m-%dT%H:%M:%SZ")
TARGET_DB=$(get_target_db)

# Append to sync queue (JSONL format — one JSON per line, append-only)
QUEUE_FILE="$CACHE_DIR/pending-sync.jsonl"
echo "{\"timestamp\":\"$TIMESTAMP\",\"file\":\"$TOOL_INPUT\",\"tool\":\"$TOOL_NAME\",\"trigger\":\"$SYNC_TRIGGER\",\"target_db\":\"$TARGET_DB\"}" >> "$QUEUE_FILE" 2>/dev/null

# Update summary file for quick status checks
QUEUE_COUNT=$(wc -l < "$QUEUE_FILE" 2>/dev/null || echo 0)
cat > "$CACHE_DIR/pending-sync.json" 2>/dev/null <<EOF
{
  "pending_sync": true,
  "last_change": "$TIMESTAMP",
  "queue_file": "pending-sync.jsonl",
  "queue_count": $QUEUE_COUNT
}
EOF

# Log
mkdir -p "$LOG_DIR" 2>/dev/null || true
echo "[$TIMESTAMP] notion-sync: queued $TOOL_INPUT -> $TARGET_DB ($SYNC_TRIGGER)" >> "$LOG_DIR/notion-sync.log" 2>/dev/null || true

exit 0
