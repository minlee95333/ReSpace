#!/bin/bash
#
# Auto Documentation Sync Hook
# Automatically updates documentation after code changes
#
# Events: PostToolUse (Write, Edit, Bash with git commit)
#

set -e

TOOL_NAME="$1"
TOOL_INPUT="$2"
TOOL_OUTPUT="$3"
EXIT_CODE="$4"

# Configuration
PROJECT_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || echo ".")
CHANGELOG_FILE="$PROJECT_ROOT/CHANGELOG.md"
README_FILE="$PROJECT_ROOT/README.md"
CLAUDE_DIR="$PROJECT_ROOT/.claude"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${BLUE}AUTO-SYNC:${NC} $1"
}

log_success() {
    echo -e "${GREEN}AUTO-SYNC:${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}AUTO-SYNC:${NC} $1"
}

# ============================================
# CHANGELOG Auto-Update
# ============================================
update_changelog() {
    local commit_msg="$1"
    local commit_type=""
    local commit_scope=""
    local commit_desc=""

    # Parse conventional commit using simple string operations
    # Pattern: type(scope): description or type: description
    if [[ "$commit_msg" == *"("*"): "* ]]; then
        # Has scope: feat(auth): description
        commit_type="${commit_msg%%(*}"
        local temp="${commit_msg#*(}"
        commit_scope="${temp%%):*}"
        commit_desc="${commit_msg#*): }"
    elif [[ "$commit_msg" == *": "* ]]; then
        # No scope: feat: description
        commit_type="${commit_msg%%:*}"
        commit_scope=""
        commit_desc="${commit_msg#*: }"
    else
        commit_desc="$commit_msg"
        commit_type="chore"
    fi

    local today=$(date +%Y-%m-%d)
    local entry=""

    case "$commit_type" in
        feat)
            entry="- **Added**: $commit_desc"
            ;;
        fix)
            entry="- **Fixed**: $commit_desc"
            ;;
        docs)
            entry="- **Docs**: $commit_desc"
            ;;
        refactor)
            entry="- **Changed**: $commit_desc"
            ;;
        test)
            entry="- **Test**: $commit_desc"
            ;;
        *)
            entry="- $commit_desc"
            ;;
    esac

    if [[ -n "$commit_scope" ]]; then
        entry="${entry} (\`${commit_scope}\`)"
    fi

    # Create CHANGELOG if not exists
    if [[ ! -f "$CHANGELOG_FILE" ]]; then
        cat > "$CHANGELOG_FILE" << 'EOF'
# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

EOF
        log_info "Created CHANGELOG.md"
    fi

    # Add entry under [Unreleased]
    if grep -q "## \[Unreleased\]" "$CHANGELOG_FILE"; then
        # Insert after [Unreleased] line
        sed -i "/## \[Unreleased\]/a\\
$entry" "$CHANGELOG_FILE"
        log_success "Added to CHANGELOG: $entry"
    fi
}

# ============================================
# README Skills/Agents Sync
# ============================================
sync_readme_components() {
    local component_type="$1"  # agents, skills, hooks, commands
    local section_name="$2"
    local dir_path="$CLAUDE_DIR/$component_type"

    if [[ ! -d "$dir_path" ]]; then
        return
    fi

    local count=0
    local items=""

    # Count and list items
    for file in "$dir_path"/*.md "$dir_path"/*/SKILL.md "$dir_path"/*/*.md; do
        if [[ -f "$file" ]]; then
            local name=$(basename "$(dirname "$file")" 2>/dev/null)
            if [[ "$name" == "$component_type" ]] || [[ "$name" == "." ]]; then
                name=$(basename "$file" .md)
            fi

            # Extract description from frontmatter
            local desc=$(grep -A1 "^description:" "$file" 2>/dev/null | tail -1 | sed 's/^description: *//' | head -c 60)

            if [[ -n "$name" ]] && [[ "$name" != "SKILL" ]]; then
                ((count++))
                items="$items\n| \`$name\` | $desc... |"
            fi
        fi
    done

    echo "$count"
}

update_readme_stats() {
    if [[ ! -f "$README_FILE" ]]; then
        return
    fi

    local agents_count=$(find "$CLAUDE_DIR/agents" -name "*.md" 2>/dev/null | wc -l)
    local skills_count=$(find "$CLAUDE_DIR/skills" -name "*.md" 2>/dev/null | wc -l)
    local hooks_count=$(find "$CLAUDE_DIR/hooks" -name "*.md" -o -name "*.sh" 2>/dev/null | wc -l)
    local commands_count=$(find "$CLAUDE_DIR/commands" -name "*.md" 2>/dev/null | wc -l)

    # Update stats section if exists
    if grep -q "## Stats" "$README_FILE"; then
        log_info "README stats: Agents=$agents_count, Skills=$skills_count, Hooks=$hooks_count, Commands=$commands_count"
    fi
}

# ============================================
# Main Hook Logic
# ============================================

# Handle git commit events
if [[ "$TOOL_NAME" == "Bash" ]] && [[ "$TOOL_INPUT" == *"git commit"* ]]; then
    # Check if commit was successful
    if [[ "$TOOL_OUTPUT" =~ \[.*[a-f0-9]{7,}\] ]]; then
        log_info "Git commit detected, syncing documentation..."

        # Get last commit message
        COMMIT_MSG=$(git log -1 --pretty=%B 2>/dev/null | head -1)

        if [[ -n "$COMMIT_MSG" ]]; then
            update_changelog "$COMMIT_MSG"
        fi

        update_readme_stats
        log_success "Documentation sync complete"
    fi
fi

# Handle file creation/modification in .claude directory
if [[ "$TOOL_NAME" == "Write" ]] || [[ "$TOOL_NAME" == "Edit" ]]; then
    if [[ "$TOOL_INPUT" == *".claude/"* ]]; then
        log_info "Claude config changed, consider running: /readme-sync"
        update_readme_stats
    fi
fi

exit 0
