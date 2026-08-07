#!/bin/bash
#
# Pre-Tool-Use Safety Hook
# Blocks dangerous operations before execution
#
# Events: PreToolUse (Bash, Write, Edit)
#

TOOL_NAME="$1"
TOOL_INPUT="$2"

# Colors
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_block() {
    echo -e "${RED}[Safety]${NC} BLOCKED: $1"
}

log_warning() {
    echo -e "${YELLOW}[Safety]${NC} WARNING: $1"
}

# Dangerous bash commands
DANGEROUS_BASH_PATTERNS=(
    "rm -rf /"
    "rm -rf ~"
    "rm -rf \*"
    "> /dev/sda"
    "mkfs\."
    "dd if="
    ":(){:|:&};:"
    "chmod -R 777 /"
    "chown -R"
    "curl.*\| ?sh"
    "wget.*\| ?sh"
    "git push.*--force.*main"
    "git push.*--force.*master"
    "git reset --hard.*origin"
    "DROP DATABASE"
    "DROP TABLE"
    "TRUNCATE"
    "DELETE FROM.*WHERE 1"
)

# Protected file patterns
PROTECTED_FILES=(
    ".env"
    ".env.local"
    ".env.production"
    "credentials"
    "secrets"
    "private_key"
    "id_rsa"
    ".pem"
    "password"
)

# Check for dangerous bash commands
check_dangerous_bash() {
    local input="$1"

    for pattern in "${DANGEROUS_BASH_PATTERNS[@]}"; do
        if echo "$input" | grep -qiE "$pattern"; then
            log_block "Dangerous command detected: $pattern"
            exit 1
        fi
    done
}

# Check for protected file access
check_protected_files() {
    local input="$1"

    for pattern in "${PROTECTED_FILES[@]}"; do
        if echo "$input" | grep -qi "$pattern"; then
            log_warning "Accessing potentially sensitive file: $pattern"
            # Warning only, not blocking
        fi
    done
}

# Check for destructive git operations
check_git_safety() {
    local input="$1"

    # Block force push to main/master
    if echo "$input" | grep -qE "git push.*--force.*(main|master)"; then
        log_block "Force push to main/master branch is not allowed"
        exit 1
    fi

    # Warn on destructive operations
    if echo "$input" | grep -qE "git reset --hard|git clean -fd"; then
        log_warning "Destructive git operation detected"
    fi
}

# Main logic
main() {
    case "$TOOL_NAME" in
        "Bash")
            check_dangerous_bash "$TOOL_INPUT"
            check_git_safety "$TOOL_INPUT"
            ;;
        "Write"|"Edit")
            check_protected_files "$TOOL_INPUT"
            ;;
    esac
}

main
exit 0
