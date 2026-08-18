#!/usr/bin/env bash
#
# Garmin Connect for Claude -- installer
#
# Sets up an isolated Python environment, installs the server, signs you in to
# Garmin and configures Claude Desktop. Safe to run again to update.
#
#   curl -fsSL https://raw.githubusercontent.com/jharkebusch/garmin-connect-mcp/main/install.sh | bash

set -euo pipefail

REPO_URL="https://github.com/jharkebusch/garmin-connect-mcp"
APP_DIR="${HOME}/.garmin-mcp"
BIN_DIR="${HOME}/.local/bin"
PYTHON_VERSION="3.12"

say()  { printf '%s\n' "$*"; }
step() { printf '\n==> %s\n' "$*"; }
fail() { printf '\nError: %s\n' "$*" >&2; exit 1; }

say ""
say "----------------------------------------------------"
say "  Garmin Connect for Claude -- installer"
say "----------------------------------------------------"

case "$(uname -s)" in
    Darwin) ;;
    Linux)  say "Note: Linux detected. This is built for macOS but should work." ;;
    *)      fail "This installer supports macOS. Please see ${REPO_URL} for other systems." ;;
esac

# --- 1. uv, which brings its own Python so the system one is left alone ------
step "Checking for the uv package manager"
UV_BIN=""
for candidate in "$(command -v uv 2>/dev/null || true)" "${HOME}/.local/bin/uv" "${HOME}/.cargo/bin/uv"; do
    if [ -n "${candidate}" ] && [ -x "${candidate}" ]; then UV_BIN="${candidate}"; break; fi
done

if [ -z "${UV_BIN}" ]; then
    say "    Not found. Installing uv (this is a small, standard tool)..."
    curl -LsSf https://astral.sh/uv/install.sh | sh >/dev/null 2>&1 \
        || fail "Could not install uv. Check your internet connection and try again."
    for candidate in "${HOME}/.local/bin/uv" "${HOME}/.cargo/bin/uv"; do
        if [ -x "${candidate}" ]; then UV_BIN="${candidate}"; break; fi
    done
    [ -n "${UV_BIN}" ] || fail "uv installed but could not be found. Please restart your Terminal and try again."
    say "    Installed uv."
else
    say "    Found uv at ${UV_BIN}"
fi

# --- 2. Isolated environment -------------------------------------------------
step "Setting up a private Python environment in ${APP_DIR}"
"${UV_BIN}" venv --python "${PYTHON_VERSION}" "${APP_DIR}" >/dev/null 2>&1 \
    || fail "Could not create the Python environment. Try running: ${UV_BIN} python install ${PYTHON_VERSION}"
say "    Ready."

step "Installing the Garmin server (this can take a minute)"
VIRTUAL_ENV="${APP_DIR}" "${UV_BIN}" pip install --upgrade "git+${REPO_URL}.git" >/dev/null \
    || fail "Could not install the server. Check your internet connection and try again."
say "    Installed."

# --- 3. Make the setup command easy to run again -----------------------------
mkdir -p "${BIN_DIR}"
ln -sf "${APP_DIR}/bin/garmin-mcp-setup" "${BIN_DIR}/garmin-mcp-setup"

# Put ~/.local/bin on PATH for future Terminal sessions if it is not already.
if ! printf '%s' ":${PATH}:" | grep -q ":${BIN_DIR}:"; then
    for profile in "${HOME}/.zprofile" "${HOME}/.bash_profile"; do
        if [ -f "${profile}" ] || [ "${profile}" = "${HOME}/.zprofile" ]; then
            if ! grep -qs '\.local/bin' "${profile}"; then
                printf '\nexport PATH="$HOME/.local/bin:$PATH"\n' >> "${profile}"
            fi
        fi
    done
    export PATH="${BIN_DIR}:${PATH}"
fi

# --- 4. Sign in and configure Claude ----------------------------------------
step "Connecting your Garmin account"

# When this script is piped from curl, stdin is the script itself, so the
# interactive prompts must read from the terminal directly.
if [ -r /dev/tty ]; then
    "${APP_DIR}/bin/garmin-mcp-setup" < /dev/tty
else
    say ""
    say "Almost done. Finish by running this command in your Terminal:"
    say ""
    say "    ${APP_DIR}/bin/garmin-mcp-setup"
    say ""
    exit 0
fi
