#!/usr/bin/env bash
# Auto Skill Finder — Universal Installer
# Supports: macOS, Linux, WSL, Git Bash
#
# Remote install (one-liner):
#   curl -fsSL https://raw.githubusercontent.com/prantikmedhi/auto-skill-finder/main/install.sh | bash
#
# Local install (already cloned):
#   bash install.sh
#
# Options (set as env vars):
#   AUTO_SKILL_DIR   Override install directory (default: ~/.auto-skill-finder)
#   AUTO_SKILL_ONLY  Install for one agent only (e.g. AUTO_SKILL_ONLY=claude)
#   AUTO_SKILL_UPDATE=1  Force re-clone even if already installed

set -euo pipefail

REPO="https://github.com/prantikmedhi/auto-skill-finder.git"
INSTALL_DIR="${AUTO_SKILL_DIR:-$HOME/.auto-skill-finder}"
ONLY="${AUTO_SKILL_ONLY:-}"
UPDATE="${AUTO_SKILL_UPDATE:-0}"

# ── Colors ────────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BOLD='\033[1m'; RESET='\033[0m'

info()    { echo -e "${BOLD}[auto-skill-finder]${RESET} $*"; }
success() { echo -e "${GREEN}✓${RESET} $*"; }
warn()    { echo -e "${YELLOW}⚠${RESET}  $*"; }
error()   { echo -e "${RED}✗${RESET}  $*" >&2; }
die()     { error "$*"; exit 1; }

# ── Dependency checks ─────────────────────────────────────────────────────────

check_node() {
  if ! command -v node &>/dev/null; then
    die "Node.js not found. Install from https://nodejs.org (v18+) and re-run."
  fi
  local ver
  ver=$(node -e "process.stdout.write(process.versions.node.split('.')[0])")
  if [ "$ver" -lt 18 ]; then
    die "Node.js v$ver found but v18+ required. Upgrade and re-run."
  fi
  success "Node.js $(node --version)"
}

check_git() {
  if ! command -v git &>/dev/null; then
    die "git not found. Install git and re-run."
  fi
  success "git $(git --version | awk '{print $3}')"
}

# ── Detect if running from remote pipe (curl | bash) ─────────────────────────

SCRIPT_DIR=""
if [ -n "${BASH_SOURCE[0]+x}" ] && [ "${BASH_SOURCE[0]}" != "bash" ] && [ -f "${BASH_SOURCE[0]}" ]; then
  SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
fi

# ── Clone or use existing ─────────────────────────────────────────────────────

get_skill_dir() {
  # If running from inside a clone, use that directly (avoid redundant clone)
  if [ -n "$SCRIPT_DIR" ] && [ -f "$SCRIPT_DIR/bin/install.js" ]; then
    echo "$SCRIPT_DIR"
    return
  fi

  # Already installed — update or reuse
  if [ -d "$INSTALL_DIR/.git" ]; then
    if [ "$UPDATE" = "1" ]; then
      info "Updating existing install at $INSTALL_DIR..."
      git -C "$INSTALL_DIR" pull --ff-only --quiet
      success "Updated"
    else
      info "Found existing install at $INSTALL_DIR (set AUTO_SKILL_UPDATE=1 to update)"
    fi
    echo "$INSTALL_DIR"
    return
  fi

  # Fresh clone
  info "Cloning to $INSTALL_DIR..."
  git clone --depth 1 --quiet "$REPO" "$INSTALL_DIR"
  success "Cloned to $INSTALL_DIR"
  echo "$INSTALL_DIR"
}

# ── Main ──────────────────────────────────────────────────────────────────────

echo ""
echo -e "${BOLD}╔══════════════════════════════════════╗${RESET}"
echo -e "${BOLD}║     Auto Skill Finder Installer      ║${RESET}"
echo -e "${BOLD}╚══════════════════════════════════════╝${RESET}"
echo ""

info "Checking dependencies..."
check_git
check_node
echo ""

SKILL_DIR="$(get_skill_dir)"
echo ""

info "Running installer..."
NODE_ARGS=()
if [ -n "$ONLY" ]; then
  NODE_ARGS+=("--only" "$ONLY")
fi

node "$SKILL_DIR/bin/install.js" "${NODE_ARGS[@]}"

echo ""
echo -e "${GREEN}${BOLD}Auto Skill Finder installed successfully.${RESET}"
echo ""
echo -e "  Skill dir : ${BOLD}$SKILL_DIR${RESET}"
echo -e "  Docs      : ${BOLD}https://github.com/prantikmedhi/auto-skill-finder${RESET}"
echo ""
echo -e "  Restart your AI agent session to activate."
echo ""
