#!/usr/bin/env bash
# Checkout i18n branch and overlay OpenRouter files from a separate fork branch (no merge).
set -euo pipefail

SRC="${SRC:-/home/algerd/dbgpt-src}"
REPO="${REPO:-https://github.com/algerdby/DB-GPT.git}"
I18N_BRANCH="${I18N_BRANCH:-feature/i18n-ru-locale}"
OR_BRANCH="${OR_BRANCH:-feature/openrouter-multi-llm}"

if [ ! -d "$SRC/.git" ]; then
  git clone --branch "$I18N_BRANCH" --depth 1 "$REPO" "$SRC"
fi

cd "$SRC"
git remote add fork "$REPO" 2>/dev/null || true
git fetch fork "$I18N_BRANCH" "$OR_BRANCH" 2>/dev/null \
  || git fetch origin "$I18N_BRANCH" "$OR_BRANCH" 2>/dev/null \
  || true

git checkout "$I18N_BRANCH" 2>/dev/null || git checkout -B "$I18N_BRANCH"
git pull --ff-only fork "$I18N_BRANCH" 2>/dev/null \
  || git pull --ff-only origin "$I18N_BRANCH" 2>/dev/null \
  || true

REF="fork/$OR_BRANCH"
git show-ref --verify --quiet "refs/remotes/$REF" 2>/dev/null \
  || REF="origin/$OR_BRANCH"
if ! git show-ref --verify --quiet "refs/remotes/$REF" 2>/dev/null; then
  echo "prepare_dbgpt_src: remote ref $OR_BRANCH not found; skip OpenRouter overlay"
  exit 0
fi

git checkout "$REF" -- \
  packages/dbgpt-core/src/dbgpt/model/proxy/llms/chatgpt.py \
  configs/dbgpt-openrouter.toml

echo "prepare_dbgpt_src: overlay from $REF onto $I18N_BRANCH in $SRC"
grep -q DBGPT_OPENROUTER_NATIVE \
  packages/dbgpt-core/src/dbgpt/model/proxy/llms/chatgpt.py \
  && echo "prepare_dbgpt_src: chatgpt.py has native OpenRouter support"
