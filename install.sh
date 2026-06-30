#!/bin/bash
# ============================================================================
# Local LLM Setup Installer
# ============================================================================
# One-line install for Linux and macOS (Hermes-style bootstrap).
#
#   curl -fsSL https://raw.githubusercontent.com/PerasutRu/Local_LLM_setup/main/install.sh | bash
#
# Options (pass after bash -s --):
#   --dir PATH          Install directory (default: ~/.local-llm-setup/app)
#   --branch NAME       Git branch (default: main)
#   --no-venv           Skip virtualenv (install into active Python)
#   --skip-doctor       Skip post-install dependency check
#   -h, --help          Show help
# ============================================================================

set -e

if [ -n "${PYTHONPATH:-}" ]; then
    echo "⚠ Ignoring inherited PYTHONPATH during install"
    unset PYTHONPATH
fi
if [ -n "${PYTHONHOME:-}" ]; then
    echo "⚠ Ignoring inherited PYTHONHOME during install"
    unset PYTHONHOME
fi

export UV_NO_CONFIG=1

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
NC='\033[0m'
BOLD='\033[1m'

REPO_URL_HTTPS="https://github.com/PerasutRu/Local_LLM_setup.git"
REPO_URL_SSH="git@github.com:PerasutRu/Local_LLM_setup.git"
LLS_HOME="${LOCAL_LLM_SETUP_HOME:-$HOME/.local-llm-setup}"
PYTHON_VERSION="3.11"
BRANCH="main"
USE_VENV=true
RUN_DOCTOR=true
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
        --branch|-Branch)
            BRANCH="$2"
            shift 2
            ;;
        --no-venv)
            USE_VENV=false
            shift
            ;;
        --skip-doctor)
            RUN_DOCTOR=false
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

print_banner() {
    echo ""
    echo -e "${BOLD}"
    echo "┌─────────────────────────────────────────────────────────┐"
    echo "│  Local LLM Setup Installer                              │"
    echo "├─────────────────────────────────────────────────────────┤"
    echo "│  TUI wizard for Ollama, vLLM, llama.cpp, and SGLang     │"
    echo "└─────────────────────────────────────────────────────────┘"
    echo -e "${NC}"
}

detect_os() {
    case "$(uname -s)" in
        Linux*)
            OS="linux"
            if [ -f /etc/os-release ]; then
                # shellcheck disable=SC1091
                . /etc/os-release
                DISTRO="${ID:-unknown}"
            else
                DISTRO="unknown"
            fi
            ;;
        Darwin*)
            OS="macos"
            DISTRO="macos"
            ;;
        CYGWIN*|MINGW*|MSYS*)
            log_error "Windows detected. Use WSL2 or install manually with pip."
            exit 1
            ;;
        *)
            OS="unknown"
            DISTRO="unknown"
            log_warn "Unknown operating system"
            ;;
    esac
    log_success "Detected: $OS ($DISTRO)"
}

resolve_install_layout() {
    if [ "$INSTALL_DIR_EXPLICIT" = true ]; then
        log_info "Install directory: $INSTALL_DIR (explicit)"
        return 0
    fi

    if [ "$OS" = "linux" ] && [ "$(id -u)" -eq 0 ]; then
        if [ -d "$LLS_HOME/app/.git" ]; then
            INSTALL_DIR="$LLS_HOME/app"
            log_info "Existing install at $INSTALL_DIR — keeping user layout"
            return 0
        fi
        INSTALL_DIR="/usr/local/lib/local-llm-setup"
        ROOT_FHS_LAYOUT=true
        export UV_PYTHON_INSTALL_DIR="${UV_PYTHON_INSTALL_DIR:-/usr/local/share/uv/python}"
        export UV_PYTHON_BIN_DIR="${UV_PYTHON_BIN_DIR:-/usr/local/share/uv/bin}"
        log_info "Root install — code: $INSTALL_DIR, command: /usr/local/bin/local-llm-setup"
        return 0
    fi

    INSTALL_DIR="$LLS_HOME/app"
}

get_command_link_dir() {
    if [ "$ROOT_FHS_LAYOUT" = true ]; then
        echo "/usr/local/bin"
    else
        echo "$HOME/.local/bin"
    fi
}

install_uv() {
    local managed_uv="$LLS_HOME/bin/uv"
    if [ -x "$managed_uv" ]; then
        UV_CMD="$managed_uv"
        log_success "Managed uv found ($("$UV_CMD" --version 2>/dev/null))"
        return 0
    fi

    log_info "Installing uv into $LLS_HOME/bin ..."
    mkdir -p "$LLS_HOME/bin"

    local uv_installer uv_log
    uv_installer="$(mktemp 2>/dev/null || echo "/tmp/lls-uv-installer.$$.sh")"
    uv_log="$(mktemp 2>/dev/null || echo "/tmp/lls-uv-install.$$.log")"

    if ! curl -LsSf https://astral.sh/uv/install.sh -o "$uv_installer" 2>"$uv_log"; then
        log_error "Failed to download uv installer"
        sed 's/^/  /' "$uv_log" >&2
        rm -f "$uv_installer" "$uv_log"
        exit 1
    fi

    if UV_UNMANAGED_INSTALL="$LLS_HOME/bin" sh "$uv_installer" >>"$uv_log" 2>&1; then
        rm -f "$uv_installer"
        if [ ! -x "$managed_uv" ]; then
            log_error "uv installer succeeded but binary missing at $managed_uv"
            sed 's/^/  /' "$uv_log" >&2
            rm -f "$uv_log"
            exit 1
        fi
        UV_CMD="$managed_uv"
        rm -f "$uv_log"
        log_success "uv installed ($("$UV_CMD" --version 2>/dev/null))"
    else
        log_error "Failed to install uv"
        sed 's/^/  /' "$uv_log" >&2
        rm -f "$uv_installer" "$uv_log"
        exit 1
    fi
}

check_python() {
    log_info "Checking Python $PYTHON_VERSION ..."
    if PYTHON_PATH="$("$UV_CMD" python find "$PYTHON_VERSION" 2>/dev/null)"; then
        log_success "Python found ($("$PYTHON_PATH" --version 2>/dev/null))"
        return 0
    fi

    log_info "Installing Python $PYTHON_VERSION via uv ..."
    if "$UV_CMD" python install "$PYTHON_VERSION"; then
        PYTHON_PATH="$("$UV_CMD" python find "$PYTHON_VERSION")"
        log_success "Python installed ($("$PYTHON_PATH" --version 2>/dev/null))"
    else
        log_error "Failed to install Python $PYTHON_VERSION"
        exit 1
    fi
}

attempt_install_git() {
    local sudo_cmd=""
    [ "$(id -u 2>/dev/null || echo 1000)" -ne 0 ] && command -v sudo >/dev/null 2>&1 && sudo_cmd="sudo"

    case "$OS" in
        macos)
            if command -v brew >/dev/null 2>&1; then
                log_info "Installing Git via Homebrew ..."
                brew install git >/dev/null 2>&1 || true
                command -v git >/dev/null 2>&1 && return 0
            fi
            if command -v xcode-select >/dev/null 2>&1; then
                log_info "Requesting Apple Command Line Tools (provides git) ..."
                xcode-select --install >/dev/null 2>&1 || true
            fi
            return 1
            ;;
        linux)
            case "$DISTRO" in
                ubuntu|debian)
                    log_info "Installing Git via apt ..."
                    $sudo_cmd env DEBIAN_FRONTEND=noninteractive apt-get update -qq >/dev/null 2>&1 || true
                    $sudo_cmd env DEBIAN_FRONTEND=noninteractive apt-get install -y -qq git >/dev/null 2>&1 || true
                    ;;
                fedora)
                    log_info "Installing Git via dnf ..."
                    $sudo_cmd dnf install -y git >/dev/null 2>&1 || true
                    ;;
                arch)
                    log_info "Installing Git via pacman ..."
                    $sudo_cmd pacman -S --noconfirm git >/dev/null 2>&1 || true
                    ;;
                *)
                    return 1
                    ;;
            esac
            command -v git >/dev/null 2>&1 && return 0
            return 1
            ;;
    esac
    return 1
}

check_git() {
    log_info "Checking Git ..."
    if command -v git >/dev/null 2>&1 && git --version >/dev/null 2>&1; then
        log_success "Git $(git --version | awk '{print $3}')"
        return 0
    fi

    log_info "Git not found — attempting install ..."
    if attempt_install_git; then
        log_success "Git $(git --version | awk '{print $3}')"
        return 0
    fi

    log_error "Git is required. Install git and re-run this script."
    exit 1
}

clone_repo() {
    log_info "Installing to $INSTALL_DIR ..."

    if [ -d "$INSTALL_DIR/.git" ] && ! git -C "$INSTALL_DIR" rev-parse --verify HEAD >/dev/null 2>&1; then
        backup_dir="${INSTALL_DIR}.broken-$(date -u +%Y%m%d-%H%M%S)"
        log_warn "Interrupted clone detected — moving aside to $backup_dir"
        mv "$INSTALL_DIR" "$backup_dir"
    fi

    if [ -d "$INSTALL_DIR" ]; then
        if [ -d "$INSTALL_DIR/.git" ]; then
            log_info "Updating existing installation ..."
            cd "$INSTALL_DIR"
            git remote set-branches origin "$BRANCH" 2>/dev/null || true
            git fetch origin "$BRANCH"
            git checkout "$BRANCH"
            git pull --ff-only origin "$BRANCH"
        else
            log_error "Directory exists but is not a git repo: $INSTALL_DIR"
            exit 1
        fi
    else
        log_info "Cloning repository ..."
        if GIT_SSH_COMMAND="ssh -o BatchMode=yes -o ConnectTimeout=5" \
            git clone --depth 1 --branch "$BRANCH" "$REPO_URL_SSH" "$INSTALL_DIR" 2>/dev/null; then
            log_success "Cloned via SSH"
        else
            rm -rf "$INSTALL_DIR" 2>/dev/null || true
            if git clone --depth 1 --branch "$BRANCH" "$REPO_URL_HTTPS" "$INSTALL_DIR"; then
                log_success "Cloned via HTTPS"
            else
                log_error "Failed to clone repository"
                exit 1
            fi
        fi
    fi

    cd "$INSTALL_DIR"
    log_success "Repository ready"
}

setup_venv() {
    if [ "$USE_VENV" = false ]; then
        log_info "Skipping virtual environment (--no-venv)"
        return 0
    fi

    log_info "Creating virtual environment ..."
    if [ -d "venv" ]; then
        rm -rf venv
    fi
    "$UV_CMD" venv venv --python "$PYTHON_VERSION"
    if [ -x "$INSTALL_DIR/venv/bin/python" ]; then
        export UV_PYTHON="$INSTALL_DIR/venv/bin/python"
    fi
    log_success "Virtual environment ready"
}

install_deps() {
    log_info "Installing local-llm-setup ..."
    if [ -x "$INSTALL_DIR/venv/bin/python" ]; then
        export UV_PYTHON="$INSTALL_DIR/venv/bin/python"
    fi

    if [ "$USE_VENV" = true ]; then
        "$UV_CMD" pip install -e .
    else
        "$UV_CMD" pip install -e . --system
    fi
    log_success "Package installed"
}

setup_path() {
    log_info "Installing local-llm-setup command ..."

    if [ "$USE_VENV" = true ]; then
        CLI_BIN="$INSTALL_DIR/venv/bin/local-llm-setup"
    else
        CLI_BIN="$(command -v local-llm-setup 2>/dev/null || true)"
    fi

    if [ ! -x "$CLI_BIN" ]; then
        log_warn "Entry point not found at ${CLI_BIN:-<unknown>}"
        return 0
    fi

    local link_dir
    link_dir="$(get_command_link_dir)"
    mkdir -p "$link_dir"
    rm -f "$link_dir/local-llm-setup"

    cat >"$link_dir/local-llm-setup" <<EOF
#!/usr/bin/env bash
unset PYTHONPATH PYTHONHOME
exec "$CLI_BIN" "\$@"
EOF
    chmod +x "$link_dir/local-llm-setup"

    if [ "$ROOT_FHS_LAYOUT" = false ]; then
        ensure_local_bin_on_path
    fi

    export PATH="$link_dir:$PATH"
    log_success "Command ready: $link_dir/local-llm-setup"
}

ensure_local_bin_on_path() {
    local path_line='export PATH="$HOME/.local/bin:$PATH"'
    local shell_configs=()

    case "${SHELL:-}" in
        */zsh) shell_configs+=("$HOME/.zshrc") ;;
        */bash)
            shell_configs+=("$HOME/.bashrc")
            shell_configs+=("$HOME/.bash_profile")
            ;;
        *) shell_configs+=("$HOME/.profile") ;;
    esac

    for cfg in "${shell_configs[@]}"; do
        if [ ! -f "$cfg" ]; then
            touch "$cfg"
        fi
        if ! grep -qE 'PATH=.*\.local/bin' "$cfg" 2>/dev/null; then
            {
                echo ""
                echo "# Local LLM Setup — ensure ~/.local/bin is on PATH"
                echo "$path_line"
            } >>"$cfg"
            log_success "Added ~/.local/bin to PATH in $cfg"
        fi
    done
}

prepare_data_dir() {
    mkdir -p "$LLS_HOME/llm_local"/{output,profiles}
    if [ ! -f "$LLS_HOME/llm_local/profiles/default.yaml" ] && [ -f "$INSTALL_DIR/llm_local/profiles/sample.yaml" ]; then
        cp "$INSTALL_DIR/llm_local/profiles/sample.yaml" "$LLS_HOME/llm_local/profiles/default.yaml"
        log_success "Copied sample profile to $LLS_HOME/llm_local/profiles/default.yaml"
    fi
}

maybe_run_doctor() {
    if [ "$RUN_DOCTOR" = false ]; then
        return 0
    fi

    local cmd
    cmd="$(get_command_link_dir)/local-llm-setup"
    if [ ! -x "$cmd" ]; then
        return 0
    fi

    log_info "Checking host dependencies (Docker, GPU, nginx) ..."
    if "$cmd" doctor; then
        log_success "Doctor checks passed"
    else
        log_warn "Some checks failed — install Docker/GPU drivers if you plan to deploy models"
        log_info "See: https://docs.docker.com/engine/install/"
    fi
}

print_success() {
    echo ""
    echo -e "${GREEN}${BOLD}Installation complete!${NC}"
    echo ""
    echo -e "${BOLD}Next steps:${NC}"
    echo ""
    echo -e "  ${GREEN}local-llm-setup tui${NC}       Launch the setup wizard"
    echo -e "  ${GREEN}local-llm-setup doctor${NC}    Check Docker / GPU / nginx"
    echo ""
    echo -e "  Code:  $INSTALL_DIR"
    echo -e "  Data:  $LLS_HOME"
    echo ""

    if [ "$ROOT_FHS_LAYOUT" = true ]; then
        echo -e "${YELLOW}Command installed to /usr/local/bin/local-llm-setup${NC}"
    else
        echo -e "${YELLOW}Run this in your current shell (or open a new terminal):${NC}"
        echo ""
        echo '  export PATH="$HOME/.local/bin:$PATH"'
        echo ""
    fi
}

main() {
    print_banner
    detect_os
    resolve_install_layout
    install_uv
    check_python
    check_git
    clone_repo
    setup_venv
    install_deps
    setup_path
    prepare_data_dir
    maybe_run_doctor
    print_success
    echo "git" >"$INSTALL_DIR/.install_method"
}

main "$@"
