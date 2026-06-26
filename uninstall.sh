#!/bin/bash
# ============================================================================
# Local LLM Setup Uninstaller
# ============================================================================
# Removes a curl-install deployment of local-llm-setup.
#
#   curl -fsSL https://raw.githubusercontent.com/PerasutRu/Local_LLM_setup/main/uninstall.sh | bash
#
# Options (pass after bash -s --):
#   --dir PATH       App directory (default: auto-detect)
#   --keep-data      Keep ~/.local-llm-setup/llm_local (output and profiles)
#   --keep-uv        Keep managed uv in ~/.local-llm-setup/bin
#   --yes, -y        Skip confirmation prompt
#   -h, --help       Show help
# ============================================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
NC='\033[0m'
BOLD='\033[1m'

LLS_HOME="${LOCAL_LLM_SETUP_HOME:-$HOME/.local-llm-setup}"
KEEP_DATA=false
KEEP_UV=false
ASSUME_YES=false
ROOT_FHS_LAYOUT=false

if [ -n "${LOCAL_LLM_SETUP_INSTALL_DIR:-}" ]; then
    INSTALL_DIR="$LOCAL_LLM_SETUP_INSTALL_DIR"
    INSTALL_DIR_EXPLICIT=true
else
    INSTALL_DIR=""
    INSTALL_DIR_EXPLICIT=false
fi

if [ -t 0 ]; then
    IS_INTERACTIVE=true
else
    IS_INTERACTIVE=false
fi

while [[ $# -gt 0 ]]; do
    case $1 in
        --dir)
            INSTALL_DIR="$2"
            INSTALL_DIR_EXPLICIT=true
            shift 2
            ;;
        --keep-data)
            KEEP_DATA=true
            shift
            ;;
        --keep-uv)
            KEEP_UV=true
            shift
            ;;
        --yes|-y)
            ASSUME_YES=true
            shift
            ;;
        -h|--help)
            sed -n '2,14p' "$0" | sed 's/^# \{0,1\}//'
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

log_info() { echo -e "${CYAN}→${NC} $1"; }
log_success() { echo -e "${GREEN}✓${NC} $1"; }
log_warn() { echo -e "${YELLOW}⚠${NC} $1"; }
log_error() { echo -e "${RED}✗${NC} $1"; }

detect_os() {
    case "$(uname -s)" in
        Linux*) OS="linux" ;;
        Darwin*) OS="macos" ;;
        *) OS="unknown" ;;
    esac
}

resolve_install_layout() {
    if [ "$INSTALL_DIR_EXPLICIT" = true ]; then
        return 0
    fi

    if [ -d "$LLS_HOME/app/.git" ] || [ -f "$LLS_HOME/app/.install_method" ]; then
        INSTALL_DIR="$LLS_HOME/app"
        return 0
    fi

    if [ "$OS" = "linux" ] && [ -d "/usr/local/lib/local-llm-setup/.git" ]; then
        INSTALL_DIR="/usr/local/lib/local-llm-setup"
        ROOT_FHS_LAYOUT=true
        return 0
    fi

    if [ -d "$LLS_HOME/app" ]; then
        INSTALL_DIR="$LLS_HOME/app"
        return 0
    fi

    INSTALL_DIR="$LLS_HOME/app"
}

get_command_paths() {
    if [ "$ROOT_FHS_LAYOUT" = true ]; then
        echo "/usr/local/bin/local-llm-setup"
    else
        echo "$HOME/.local/bin/local-llm-setup"
    fi
}

maybe_stop_stack() {
    local cmd
    cmd="$(get_command_paths | head -1)"
    if [ ! -x "$cmd" ]; then
        return 0
    fi

    log_info "Stopping Docker stack (if running) ..."
    if "$cmd" stop 2>/dev/null; then
        log_success "Stack stopped"
    else
        log_warn "Could not stop stack (may not be running)"
    fi
}

confirm_uninstall() {
    if [ "$ASSUME_YES" = true ] || [ "$IS_INTERACTIVE" = false ]; then
        return 0
    fi

    echo ""
    echo -e "${BOLD}This will remove:${NC}"
    echo "  - Command: $(get_command_paths)"
    echo "  - App:     $INSTALL_DIR"
    if [ "$KEEP_DATA" = false ]; then
        echo "  - Data:    $LLS_HOME/llm_local"
    else
        echo "  - Data:    kept ($LLS_HOME/llm_local)"
    fi
    if [ "$KEEP_UV" = false ]; then
        echo "  - uv:      $LLS_HOME/bin/uv (if present)"
    fi
    echo ""
    printf "Continue? [y/N] "
    read -r answer || answer=""
    case "$answer" in
        y|Y|yes|YES) return 0 ;;
        *) log_info "Cancelled"; exit 0 ;;
    esac
}

remove_command_shim() {
    local path removed=false
    for path in $(get_command_paths); do
        if [ -f "$path" ]; then
            rm -f "$path"
            log_success "Removed $path"
            removed=true
        fi
    done
    if [ "$removed" = false ]; then
        log_warn "Command shim not found"
    fi
}

remove_app_dir() {
    if [ -d "$INSTALL_DIR" ]; then
        rm -rf "$INSTALL_DIR"
        log_success "Removed $INSTALL_DIR"
    else
        log_warn "App directory not found: $INSTALL_DIR"
    fi
}

remove_data_dir() {
    if [ "$KEEP_DATA" = true ]; then
        log_info "Keeping data in $LLS_HOME"
        return 0
    fi

    if [ -d "$LLS_HOME/llm_local" ]; then
        rm -rf "$LLS_HOME/llm_local"
        log_success "Removed $LLS_HOME/llm_local"
    fi

    # Legacy layout (pre-llm_local)
    for sub in output profiles; do
        if [ -d "$LLS_HOME/$sub" ]; then
            rm -rf "$LLS_HOME/$sub"
            log_success "Removed $LLS_HOME/$sub"
        fi
    done

    if [ -d "$LLS_HOME" ] && [ -z "$(ls -A "$LLS_HOME" 2>/dev/null)" ]; then
        rmdir "$LLS_HOME" 2>/dev/null && log_success "Removed $LLS_HOME" || true
    elif [ "$KEEP_UV" = true ] && [ -d "$LLS_HOME/bin" ]; then
        log_info "Left $LLS_HOME (contains uv)"
    fi
}

remove_managed_uv() {
    if [ "$KEEP_UV" = true ]; then
        log_info "Keeping managed uv"
        return 0
    fi

    if [ -x "$LLS_HOME/bin/uv" ]; then
        rm -f "$LLS_HOME/bin/uv" "$LLS_HOME/bin/uvx" 2>/dev/null || true
        log_success "Removed managed uv from $LLS_HOME/bin"
    fi

    if [ -d "$LLS_HOME/bin" ] && [ -z "$(ls -A "$LLS_HOME/bin" 2>/dev/null)" ]; then
        rmdir "$LLS_HOME/bin" 2>/dev/null || true
    fi
}

print_done() {
    echo ""
    echo -e "${GREEN}${BOLD}Uninstall complete.${NC}"
    echo ""
    log_info "Docker images/volumes from deployed stacks are not removed automatically."
    log_info "To remove containers and volumes: local-llm-setup stop --volumes (before uninstall)"
    log_info "Or manually: docker compose -f <output>/docker-compose.yaml down -v"
    echo ""
    log_info "PATH lines added to ~/.bashrc or ~/.zshrc were not changed."
    log_info "Remove the \"Local LLM Setup\" block manually if you no longer need ~/.local/bin on PATH."
}

main() {
    echo ""
    echo -e "${BOLD}Local LLM Setup Uninstaller${NC}"
    echo ""

    detect_os
    resolve_install_layout
    maybe_stop_stack
    confirm_uninstall
    remove_command_shim
    remove_app_dir
    remove_data_dir
    remove_managed_uv
    print_done
}

main "$@"
