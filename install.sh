#!/usr/bin/env bash
# Auto Skill Finder — installer shim
# Delegates to bin/install.js for all logic.
#
# Usage:
#   bash install.sh                  # install for all detected agents
#   bash install.sh --only claude    # Claude Code only
#   bash install.sh --uninstall      # remove
#   bash install.sh --list           # list detected agents

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if ! command -v node &>/dev/null; then
  echo "Error: node not found. Install Node.js >= 18 first." >&2
  exit 1
fi

exec node "$SCRIPT_DIR/bin/install.js" "$@"
