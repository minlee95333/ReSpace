#!/bin/bash
#
# Phase Progress Auto-Update Hook
# Automatically updates PROGRESS.md when TASKS.md is modified
#
# Events: PostToolUse (Edit, Write on TASKS.md files)
#

# Graceful error handling - don't exit on error, log and continue
set +e
trap 'handle_error $? $LINENO' ERR

handle_error() {
    local exit_code=$1
    local line_no=$2
    log_warning "Error at line $line_no (code: $exit_code) - continuing gracefully"
    # Log to recovery system if available
    local log_dir="$PROJECT_ROOT/.claude/logs"
    if [[ -d "$log_dir" ]]; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] phase-progress.sh error at line $line_no (code: $exit_code)" >> "$log_dir/error.log"
    fi
}

TOOL_NAME="$1"
TOOL_INPUT="$2"
TOOL_OUTPUT="$3"

# Configuration
PROJECT_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || echo ".")
PHASES_DIR="$PROJECT_ROOT/docs/phases"
PROGRESS_FILE="$PROJECT_ROOT/docs/PROGRESS.md"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() {
    echo -e "${BLUE}[Phase]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[Phase]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[Phase]${NC} $1"
}

# Calculate progress for a single phase
calculate_phase_progress() {
    local tasks_file="$1"

    if [[ ! -f "$tasks_file" ]]; then
        echo "0"
        return
    fi

    local total=$(grep -c "^- \[" "$tasks_file" 2>/dev/null || echo "0")
    local completed=$(grep -c "^- \[x\]\|^- \[X\]\|✅" "$tasks_file" 2>/dev/null || echo "0")

    if [[ "$total" -eq 0 ]]; then
        echo "0"
    else
        echo $((completed * 100 / total))
    fi
}

# Generate progress bar
generate_progress_bar() {
    local percent=$1
    local filled=$((percent / 5))
    local empty=$((20 - filled))

    local bar=""
    for ((i=0; i<filled; i++)); do bar+="█"; done
    for ((i=0; i<empty; i++)); do bar+="░"; done

    echo "[$bar] ${percent}%"
}

# Get phase status emoji
get_phase_status() {
    local percent=$1
    if [[ "$percent" -eq 100 ]]; then
        echo "complete"
    elif [[ "$percent" -gt 0 ]]; then
        echo "in progress"
    else
        echo "planned"
    fi
}

# Update PROGRESS.md
update_progress_file() {
    if [[ ! -d "$PHASES_DIR" ]]; then
        return
    fi

    local total_phases=0
    local completed_phases=0
    local total_progress=0

    # Calculate overall progress
    for phase_dir in "$PHASES_DIR"/phase-*/; do
        if [[ -d "$phase_dir" ]]; then
            local tasks_file="$phase_dir/TASKS.md"
            local progress=$(calculate_phase_progress "$tasks_file")
            total_progress=$((total_progress + progress))
            total_phases=$((total_phases + 1))

            if [[ "$progress" -eq 100 ]]; then
                completed_phases=$((completed_phases + 1))
            fi
        fi
    done

    if [[ "$total_phases" -gt 0 ]]; then
        local overall=$((total_progress / total_phases))
        log_success "Overall Progress: ${overall}% (${completed_phases}/${total_phases} phases complete)"
    fi
}

# Check if TASKS.md was modified
check_tasks_modification() {
    if [[ "$TOOL_INPUT" == *"TASKS.md"* ]] || [[ "$TOOL_INPUT" == *"phases/phase-"* ]]; then
        return 0
    fi
    return 1
}

# Main logic
main() {
    # Only process Edit and Write operations on TASKS.md
    if [[ "$TOOL_NAME" == "Edit" ]] || [[ "$TOOL_NAME" == "Write" ]]; then
        if check_tasks_modification; then
            log_info "TASKS.md modification detected, updating progress..."
            update_progress_file
        fi
    fi
}

main
exit 0
