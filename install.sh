#!/bin/sh
# Open Agent Kit (OAK) installer
# Usage: curl -fsSL https://raw.githubusercontent.com/goondocks-co/open-agent-kit/main/install.sh | sh
#
# Detects available Python package managers and installs oak-ci from PyPI.
# Prefers: pipx > uv > pip (--user)
# Requires: Python 3.12-3.13
#
# Environment variables:
#   OAK_INSTALL_METHOD  - Force a specific method: pipx, uv, or pip
#   OAK_VERSION         - Install a specific version (e.g., "0.2.0")

set -e

PACKAGE="oak-ci"
MIN_PYTHON_MAJOR=3
MIN_PYTHON_MINOR=12
MAX_PYTHON_MINOR=13

# --- Colors (disabled for non-TTY) ---

if [ -t 1 ]; then
    RED='\033[0;31m'
    GREEN='\033[0;32m'
    YELLOW='\033[0;33m'
    BLUE='\033[0;34m'
    BOLD='\033[1m'
    RESET='\033[0m'
else
    RED=''
    GREEN=''
    YELLOW=''
    BLUE=''
    BOLD=''
    RESET=''
fi

info()  { printf "${BLUE}==>${RESET} %s\n" "$1"; }
ok()    { printf "${GREEN}==>${RESET} %s\n" "$1"; }
warn()  { printf "${YELLOW}warning:${RESET} %s\n" "$1"; }
error() { printf "${RED}error:${RESET} %s\n" "$1" >&2; }
bold()  { printf "${BOLD}%s${RESET}" "$1"; }

# --- Python detection ---

find_python() {
    # Try versioned binaries first (highest supported → lowest), then generic
    for cmd in python3.13 python3.12 python3 python; do
        if command -v "$cmd" >/dev/null 2>&1; then
            if check_python_version "$cmd" >/dev/null 2>&1; then
                echo "$cmd"
                return 0
            fi
        fi
    done
    return 1
}

check_python_version() {
    python_cmd="$1"
    version_output=$("$python_cmd" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null) || return 1
    major=$(echo "$version_output" | cut -d. -f1)
    minor=$(echo "$version_output" | cut -d. -f2)

    if [ "$major" -lt "$MIN_PYTHON_MAJOR" ] || { [ "$major" -eq "$MIN_PYTHON_MAJOR" ] && [ "$minor" -lt "$MIN_PYTHON_MINOR" ]; }; then
        return 1
    fi
    if [ "$major" -gt "$MIN_PYTHON_MAJOR" ] || { [ "$major" -eq "$MIN_PYTHON_MAJOR" ] && [ "$minor" -gt "$MAX_PYTHON_MINOR" ]; }; then
        return 1
    fi
    echo "$version_output"
    return 0
}

# --- Installer methods ---

install_with_pipx() {
    version_spec="$1"
    python_cmd="$2"
    info "Installing with pipx (python: $python_cmd)..."
    if [ -n "$version_spec" ]; then
        pipx install --force --python "$python_cmd" "${PACKAGE}==${version_spec}"
    else
        pipx install --force --python "$python_cmd" "$PACKAGE"
    fi
}

install_with_uv() {
    version_spec="$1"
    python_cmd="$2"
    info "Installing with uv (python: $python_cmd)..."
    if [ -n "$version_spec" ]; then
        uv tool install --force --python "$python_cmd" "${PACKAGE}==${version_spec}"
    else
        uv tool install --force --python "$python_cmd" "$PACKAGE"
    fi
}

install_with_pip() {
    python_cmd="$1"
    version_spec="$2"
    info "Installing with pip (--user)..."
    if [ -n "$version_spec" ]; then
        "$python_cmd" -m pip install --user --upgrade "${PACKAGE}==${version_spec}"
    else
        "$python_cmd" -m pip install --user --upgrade "$PACKAGE"
    fi
}

version_matches() {
    actual="$1"
    expected="$2"
    if [ -z "$expected" ]; then
        return 0
    fi

    case "$actual" in
        *"$expected"*) return 0 ;;
        *) return 1 ;;
    esac
}

verify_pipx_install() {
    version_spec="$1"
    line=$(pipx list --short 2>/dev/null | awk -v pkg="$PACKAGE" '$1 == pkg {print $0; exit}')
    [ -n "$line" ] || return 1
    version_matches "$line" "$version_spec"
}

verify_uv_install() {
    version_spec="$1"
    line=$(uv tool list 2>/dev/null | awk -v pkg="$PACKAGE" '$1 == pkg {print $0; exit}')
    [ -n "$line" ] || return 1
    version_matches "$line" "$version_spec"
}

verify_pip_install() {
    python_cmd="$1"
    version_spec="$2"
    installed_version=$("$python_cmd" -m pip show "$PACKAGE" 2>/dev/null | awk -F': ' '/^Version: / {print $2; exit}')
    [ -n "$installed_version" ] || return 1
    if [ -z "$version_spec" ]; then
        return 0
    fi
    [ "$installed_version" = "$version_spec" ]
}

verify_install() {
    method="$1"
    python_cmd="$2"
    version_spec="$3"

    case "$method" in
        pipx) verify_pipx_install "$version_spec" ;;
        uv) verify_uv_install "$version_spec" ;;
        pip) verify_pip_install "$python_cmd" "$version_spec" ;;
        *) return 1 ;;
    esac
}

# --- Main ---

main() {
    printf "\n"
    printf "${BOLD}  Open Agent Kit (OAK) Installer${RESET}\n"
    printf "  The Intelligence Layer for AI Agents\n"
    printf "\n"

    # Detect OS
    os="$(uname -s)"
    case "$os" in
        Linux*)  os_name="Linux" ;;
        Darwin*) os_name="macOS" ;;
        *)
            error "This script requires macOS or Linux."
            printf "\n"
            info "On Windows, use PowerShell instead:"
            printf "  irm https://raw.githubusercontent.com/goondocks-co/open-agent-kit/main/install.ps1 | iex\n"
            printf "\n"
            info "Or install directly:"
            printf "  pip install %s\n" "$PACKAGE"
            exit 1
            ;;
    esac
    info "Detected OS: $os_name"

    # Find Python
    # Use if-statement (not cmd || handler) to avoid set -e + command substitution
    # portability issues — macOS /bin/sh (zsh POSIX mode) exits silently otherwise.
    python_cmd=""
    if ! python_cmd=$(find_python); then
        error "Python ${MIN_PYTHON_MAJOR}.${MIN_PYTHON_MINOR}-${MIN_PYTHON_MAJOR}.${MAX_PYTHON_MINOR} not found."
        printf "\n"
        case "$os_name" in
            macOS)  info "Install via: brew install python@3.13" ;;
            Linux)  info "Install via: sudo apt install python3.13  (or your distro's package manager)" ;;
        esac
        exit 1
    fi

    # Check Python version
    python_version=""
    if ! python_version=$(check_python_version "$python_cmd"); then
        actual=$("$python_cmd" --version 2>&1 || echo "unknown")
        error "Python ${MIN_PYTHON_MAJOR}.${MIN_PYTHON_MINOR}-${MIN_PYTHON_MAJOR}.${MAX_PYTHON_MINOR} required, found: $actual"
        exit 1
    fi
    info "Found Python $python_version ($python_cmd)"

    # Determine version spec
    version_spec="${OAK_VERSION:-}"
    if [ -n "$version_spec" ]; then
        info "Installing version: $version_spec"
    fi

    # Choose install method
    method="${OAK_INSTALL_METHOD:-}"
    actual_method=""

    if [ -n "$method" ]; then
        info "Using requested method: $method"
        case "$method" in
            pipx)
                command -v pipx >/dev/null 2>&1 || { error "pipx not found"; exit 1; }
                install_with_pipx "$version_spec" "$python_cmd"
                actual_method="pipx"
                ;;
            uv)
                command -v uv >/dev/null 2>&1 || { error "uv not found"; exit 1; }
                install_with_uv "$version_spec" "$python_cmd"
                actual_method="uv"
                ;;
            pip)
                install_with_pip "$python_cmd" "$version_spec"
                actual_method="pip"
                ;;
            *)
                error "Unknown method: $method (use: pipx, uv, or pip)"
                exit 1
                ;;
        esac
    elif command -v pipx >/dev/null 2>&1; then
        install_with_pipx "$version_spec" "$python_cmd"
        actual_method="pipx"
    elif command -v uv >/dev/null 2>&1; then
        install_with_uv "$version_spec" "$python_cmd"
        actual_method="uv"
    else
        warn "Neither pipx nor uv found, falling back to pip --user"
        install_with_pip "$python_cmd" "$version_spec"
        actual_method="pip"
    fi

    if ! verify_install "$actual_method" "$python_cmd" "$version_spec"; then
        error "Installation verification failed for method: $actual_method"
        info "Try setting OAK_INSTALL_METHOD=pipx|uv|pip and rerun installer"
        exit 1
    fi

    # Verify installation
    printf "\n"
    if command -v oak >/dev/null 2>&1; then
        installed_version=$(oak --version 2>/dev/null || echo "unknown")
        if ! version_matches "$installed_version" "$version_spec"; then
            error "Detected oak command does not match requested version ($version_spec)"
            info "Run 'hash -r' or restart your shell, then verify with: oak --version"
            exit 1
        fi
        ok "OAK installed successfully! (${installed_version})"
        printf "\n"
        info "Get started:"
        printf "  cd /path/to/your/project\n"
        printf "  oak init\n"
        printf "  oak ci start\n"
        printf "\n"
    else
        warn "oak command not found in PATH"

        # Detect the scripts directory where oak was installed
        scripts_dir=""
        if [ "$actual_method" = "pip" ]; then
            scripts_dir=$("$python_cmd" -c "import sysconfig; print(sysconfig.get_path('scripts', 'posix_user'))" 2>/dev/null || true)
        fi

        if [ -n "$scripts_dir" ] && [ -d "$scripts_dir" ]; then
            printf "\n"
            info "oak was installed to: $scripts_dir"
            printf "\n"
            info "Add it to your PATH (this session):"
            printf "  ${BOLD}export PATH=\"%s:\$PATH\"${RESET}\n" "$scripts_dir"
            printf "\n"
            info "Add it permanently (add to ~/.bashrc or ~/.zshrc):"
            printf "  ${BOLD}echo 'export PATH=\"%s:\$PATH\"' >> ~/.%src${RESET}\n" "$scripts_dir" "$(basename "${SHELL:-bash}")"
        else
            printf "\n"
            info "Restart your shell or add the Python scripts directory to PATH:"
            printf "  export PATH=\"\$HOME/.local/bin:\$PATH\"\n"
        fi

        printf "\n"
        info "Then verify with: oak --version"
    fi
}

main
