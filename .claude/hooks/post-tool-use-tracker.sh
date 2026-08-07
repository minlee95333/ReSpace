#!/bin/bash
#
# Post-Tool-Use Tracker Hook
# Tracks file changes and tool usage for session awareness
# Outputs structured JSONL metrics for analytics
#
# Events: PostToolUse (all tools)
#

TOOL_NAME="$1"
TOOL_INPUT="$2"
TOOL_OUTPUT="$3"
EXIT_CODE="${4:-0}"

# Configuration
PROJECT_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || echo ".")
SESSION_LOG="$PROJECT_ROOT/.claude/session.log"
CHANGES_LOG="$PROJECT_ROOT/.claude/changes.log"
METRICS_FILE="$PROJECT_ROOT/.claude/analytics/metrics.jsonl"
RETENTION_DAYS=30

# Ensure directories exist
mkdir -p "$(dirname "$SESSION_LOG")"
mkdir -p "$(dirname "$METRICS_FILE")"

# Get timestamps
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
ISO_TIMESTAMP=$(date -u '+%Y-%m-%dT%H:%M:%SZ')

# Determine success status
SUCCESS="true"
if [[ "$EXIT_CODE" != "0" ]]; then
    SUCCESS="false"
fi

# Extract filename if present
extract_filename() {
    local input="$1"
    local filename=""

    if [[ "$input" =~ file_path[\":\s]+\"?([^\",]+)\"? ]]; then
        filename="${BASH_REMATCH[1]}"
    elif [[ "$input" =~ \"path\"[:\s]+\"([^\"]+)\" ]]; then
        filename="${BASH_REMATCH[1]}"
    fi

    echo "$filename"
}

# Log tool usage to human-readable session log
log_tool_usage() {
    local tool="$1"
    local input="$2"

    local filename=$(extract_filename "$input")

    # Log to session log (last 100 entries)
    echo "[$TIMESTAMP] $tool: ${filename:-${input:0:50}}" >> "$SESSION_LOG"

    # Keep only last 100 lines
    if [[ -f "$SESSION_LOG" ]]; then
        tail -n 100 "$SESSION_LOG" > "$SESSION_LOG.tmp" && mv "$SESSION_LOG.tmp" "$SESSION_LOG"
    fi
}

# Write JSONL metrics for analytics
write_metrics() {
    local tool="$1"
    local input="$2"
    local success="$3"

    local filename=$(extract_filename "$input")

    # Determine tool category
    local category="other"
    case "$tool" in
        "Read"|"Write"|"Edit"|"MultiEdit"|"Glob"|"Grep")
            category="file"
            ;;
        "Bash"|"KillShell")
            category="shell"
            ;;
        "Task")
            category="agent"
            ;;
        "Skill")
            category="skill"
            ;;
        "WebFetch"|"WebSearch")
            category="web"
            ;;
        "TodoWrite")
            category="planning"
            ;;
        "AskUserQuestion"|"EnterPlanMode"|"ExitPlanMode")
            category="interaction"
            ;;
    esac

    # Extract additional context
    local context=""
    case "$tool" in
        "Task")
            if [[ "$input" =~ subagent_type[\":\s]+\"?([^\",]+)\"? ]]; then
                context="${BASH_REMATCH[1]}"
            fi
            ;;
        "Skill")
            if [[ "$input" =~ skill[\":\s]+\"?([^\",]+)\"? ]]; then
                context="${BASH_REMATCH[1]}"
            fi
            ;;
    esac

    # Escape special characters for JSON
    local safe_filename=$(echo "$filename" | sed 's/"/\\"/g' | tr '\n' ' ')
    local safe_context=$(echo "$context" | sed 's/"/\\"/g' | tr '\n' ' ')

    # Write JSONL entry
    local json_entry="{\"ts\":\"$ISO_TIMESTAMP\",\"type\":\"tool\",\"name\":\"$tool\",\"category\":\"$category\",\"success\":$success"

    if [[ -n "$safe_filename" ]]; then
        json_entry="$json_entry,\"file\":\"$safe_filename\""
    fi

    if [[ -n "$safe_context" ]]; then
        json_entry="$json_entry,\"context\":\"$safe_context\""
    fi

    json_entry="$json_entry}"

    echo "$json_entry" >> "$METRICS_FILE"

    # Rotate metrics file if too old
    rotate_metrics
}

# Track file modifications
track_file_change() {
    local tool="$1"
    local input="$2"

    case "$tool" in
        "Write"|"Edit"|"MultiEdit")
            # Extract file path
            if [[ "$input" =~ file_path[\":\s]+\"?([^\",]+)\"? ]]; then
                local filepath="${BASH_REMATCH[1]}"
                echo "[$TIMESTAMP] MODIFIED: $filepath" >> "$CHANGES_LOG"
            fi
            ;;
        "Bash")
            # Track git operations
            if [[ "$input" == *"git add"* ]] || [[ "$input" == *"git commit"* ]]; then
                echo "[$TIMESTAMP] GIT: ${input:0:80}" >> "$CHANGES_LOG"
            fi
            ;;
    esac

    # Keep only last 50 entries in changes log
    if [[ -f "$CHANGES_LOG" ]]; then
        tail -n 50 "$CHANGES_LOG" > "$CHANGES_LOG.tmp" && mv "$CHANGES_LOG.tmp" "$CHANGES_LOG"
    fi
}

# Rotate metrics file based on retention policy
rotate_metrics() {
    if [[ ! -f "$METRICS_FILE" ]]; then
        return
    fi

    # Check file size (rotate if > 10MB)
    local file_size=$(stat -f%z "$METRICS_FILE" 2>/dev/null || stat -c%s "$METRICS_FILE" 2>/dev/null || echo "0")

    if [[ "$file_size" -gt 10485760 ]]; then
        # Archive old metrics
        local archive_file="${METRICS_FILE%.jsonl}-$(date '+%Y%m%d').jsonl"
        mv "$METRICS_FILE" "$archive_file"

        # Remove archives older than retention period
        find "$(dirname "$METRICS_FILE")" -name "metrics-*.jsonl" -mtime "+$RETENTION_DAYS" -delete 2>/dev/null
    fi
}

# Main logic
main() {
    # Log all tool usage (human-readable)
    log_tool_usage "$TOOL_NAME" "$TOOL_INPUT"

    # Write structured metrics (JSONL)
    write_metrics "$TOOL_NAME" "$TOOL_INPUT" "$SUCCESS"

    # Track file modifications
    track_file_change "$TOOL_NAME" "$TOOL_INPUT"
}

main
exit 0
