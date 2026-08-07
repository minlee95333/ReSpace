#!/bin/bash
#
# Notification Handler Hook
# Handles various notification events with appropriate responses
#
# Events: Notification
#

NOTIFICATION_TYPE="$1"
NOTIFICATION_MESSAGE="$2"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

# Notification handlers
handle_success() {
    echo -e "${GREEN}[Notify]${NC} $1"
}

handle_warning() {
    echo -e "${YELLOW}[Notify]${NC} $1"
}

handle_error() {
    echo -e "${RED}[Notify]${NC} $1"
}

handle_info() {
    echo -e "${BLUE}[Notify]${NC} $1"
}

# Parse notification type and respond
main() {
    case "$NOTIFICATION_TYPE" in
        "success"|"complete"|"done")
            handle_success "$NOTIFICATION_MESSAGE"
            ;;
        "warning"|"warn")
            handle_warning "$NOTIFICATION_MESSAGE"
            ;;
        "error"|"fail"|"failed")
            handle_error "$NOTIFICATION_MESSAGE"
            ;;
        "info"|"information")
            handle_info "$NOTIFICATION_MESSAGE"
            ;;
        "phase_complete")
            handle_success "Phase completed: $NOTIFICATION_MESSAGE"
            echo -e "${BLUE}[Notify]${NC} Consider starting the next phase"
            ;;
        "task_complete")
            handle_success "Task completed: $NOTIFICATION_MESSAGE"
            ;;
        "build_success")
            handle_success "Build successful"
            ;;
        "build_failed")
            handle_error "Build failed: $NOTIFICATION_MESSAGE"
            ;;
        "test_passed")
            handle_success "All tests passed"
            ;;
        "test_failed")
            handle_error "Tests failed: $NOTIFICATION_MESSAGE"
            ;;
        *)
            handle_info "$NOTIFICATION_TYPE: $NOTIFICATION_MESSAGE"
            ;;
    esac
}

main
exit 0
