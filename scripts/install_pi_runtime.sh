#!/usr/bin/env bash
# Install the pi harness runtime so DB-GPT's pi engine probe succeeds.
#
# The pi CLI is an out-of-band runtime: it is NOT part of DB-GPT's dependency
# manifests. This script ensures
#   1. a Node runtime >= 22.19 (DBGPT_HARNESS_PI_NODE > PATH > nvm installs,
#      installing Node 22 via nvm when nothing qualifies), and
#   2. @earendil-works/pi-coding-agent installed into one of the probe's known
#      locations (default ~/.dbgpt/pi-runtime).
#
# Idempotent, sudo-free. Overrides:
#   NPM_REGISTRY   npm registry used for the pi package
#                  (default https://registry.npmmirror.com; set
#                   https://registry.npmjs.org for the official source)
#   PI_PREFIX      install prefix (default ~/.dbgpt/pi-runtime)
#
# Verify afterwards (no server restart needed, probes run per request):
#   curl -s http://127.0.0.1:5670/api/v1/chat/harness/engines
set -euo pipefail

NPM_REGISTRY="${NPM_REGISTRY:-https://registry.npmmirror.com}"
PI_PREFIX="${PI_PREFIX:-$HOME/.dbgpt/pi-runtime}"
PI_PKG="@earendil-works/pi-coding-agent"
REQUIRED_MAJOR=22
REQUIRED_MINOR=19

log() { printf '\033[1;32m[pi-runtime]\033[0m %s\n' "$*"; }
err() { printf '\033[1;31m[pi-runtime]\033[0m %s\n' "$*" >&2; }

node_ver_ok() {  # $1 = node binary; succeeds when version >= 22.19
  local ver maj min
  ver="$("$1" -v 2>/dev/null | sed 's/^v//')" || return 1
  maj="${ver%%.*}"
  min="$(printf '%s' "$ver" | cut -d. -f2)"
  case "$maj" in (''|*[!0-9]*) return 1 ;; esac
  case "$min" in (''|*[!0-9]*) return 1 ;; esac
  if [ "$maj" -gt "$REQUIRED_MAJOR" ] || { [ "$maj" -eq "$REQUIRED_MAJOR" ] && [ "$min" -ge "$REQUIRED_MINOR" ]; }; then
    return 0
  fi
  return 1
}

find_node() {  # prints first qualifying node binary, else returns 1
  local list="" d cand
  if [ -n "${DBGPT_HARNESS_PI_NODE:-}" ]; then list="$DBGPT_HARNESS_PI_NODE"; fi
  if command -v node >/dev/null 2>&1; then list="$list $(command -v node)"; fi
  if [ -d "$HOME/.nvm/versions/node" ]; then
    for d in $(ls -d "$HOME"/.nvm/versions/node/v* 2>/dev/null | sort -Vr); do
      list="$list $d/bin/node"
    done
  fi
  for cand in $list; do
    if [ -x "$cand" ] && node_ver_ok "$cand"; then
      printf '%s' "$cand"
      return 0
    fi
  done
  return 1
}

NODE_BIN="$(find_node || true)"
if [ -z "$NODE_BIN" ]; then
  log "No Node >= ${REQUIRED_MAJOR}.${REQUIRED_MINOR} found; installing Node 22 via nvm ..."
  export NVM_DIR="${NVM_DIR:-$HOME/.nvm}"
  if [ ! -s "$NVM_DIR/nvm.sh" ]; then
    curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash
  fi
  # shellcheck disable=SC1091
  . "$NVM_DIR/nvm.sh"
  nvm install 22
  NODE_BIN="$(find_node || true)"
fi
if [ -z "$NODE_BIN" ]; then
  err "still no qualifying Node runtime; set DBGPT_HARNESS_PI_NODE explicitly"
  exit 1
fi
log "Using Node $("$NODE_BIN" -v) at $NODE_BIN"

NPM_BIN="$(dirname "$NODE_BIN")/npm"
if [ ! -x "$NPM_BIN" ]; then
  err "npm not found next to $NODE_BIN"
  exit 1
fi

CLI_JS="$PI_PREFIX/lib/node_modules/$PI_PKG/dist/cli.js"
if [ -f "$CLI_JS" ]; then
  log "pi CLI already installed: $CLI_JS"
else
  log "Installing $PI_PKG into $PI_PREFIX (registry: $NPM_REGISTRY) ..."
  "$NPM_BIN" install -g --prefix "$PI_PREFIX" "$PI_PKG" \
    --registry "$NPM_REGISTRY" --no-audit --no-fund
fi

log "pi CLI version: $("$NODE_BIN" "$CLI_JS" --version 2>&1 || echo unknown)"
log "Done. Availability is probed per request; verify with:"
log "  curl -s http://127.0.0.1:5670/api/v1/chat/harness/engines"
log "Note: a persisted server preference (harness_engine.json in the server working"
log "      directory) outranks the project default; if it pins dbgpt, re-select pi in"
log "      Setting or PUT /api/v1/chat/harness/engine {\"engine\":\"pi\"}."
