#!/bin/bash
# Build golliaph/dbgpt-openai for linux/amd64 with local versioning and build log.
#
# Tags: latest + {app_version}-b{N}  (e.g. 0.8.1-b3)
#
# Usage:
#   bash scripts/build_docker_release.sh --notes "English UI + backend strings"
#   bash scripts/build_docker_release.sh --push --notes "Release notes here"
#   bash scripts/build_docker_release.sh --skip-frontend --notes "Backend only"
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
RELEASE_DIR="$REPO_ROOT/docker/release"
COUNTER_FILE="$RELEASE_DIR/.build-counter"
BUILD_LOG="$RELEASE_DIR/BUILD_LOG.md"
BUILDS_JSON="$RELEASE_DIR/builds.json"
DOCKERFILE_DIR="$REPO_ROOT/docker/base"

IMAGE_REPO="${IMAGE_REPO:-golliaph/dbgpt-openai}"
SKIP_FRONTEND=0
DO_PUSH=0
NOTES=""

usage() {
  cat <<EOF
Usage: $(basename "$0") [options]

Options:
  --notes TEXT        What changed in this build (required for log)
  --push              Push both tags to Docker Hub after build
  --skip-frontend     Skip scripts/build_web_static.sh
  --image REPO        Image repository (default: golliaph/dbgpt-openai)
  -h, --help          Show this help

Tags produced:
  \${IMAGE_REPO}:latest
  \${IMAGE_REPO}:\${app_version}-b{N}
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --notes)
      NOTES="${2:-}"
      shift 2
      ;;
    --push)
      DO_PUSH=1
      shift
      ;;
    --skip-frontend)
      SKIP_FRONTEND=1
      shift
      ;;
    --image)
      IMAGE_REPO="${2:-}"
      shift 2
      ;;
    -h | --help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

if [[ -z "$NOTES" ]]; then
  echo "Error: --notes is required (short description for BUILD_LOG.md)" >&2
  exit 1
fi

if [[ ! -f "$COUNTER_FILE" ]]; then
  echo "0" >"$COUNTER_FILE"
fi

APP_VERSION="$(grep -E '^version = ' "$REPO_ROOT/pyproject.toml" | head -1 | sed 's/.*"\(.*\)".*/\1/')"
BUILD_NUM="$(($(cat "$COUNTER_FILE") + 1))"
echo "$BUILD_NUM" >"$COUNTER_FILE"

IMAGE_VERSION="${APP_VERSION}-b${BUILD_NUM}"
GIT_SHA="$(git -C "$REPO_ROOT" rev-parse --short HEAD 2>/dev/null || echo unknown)"
GIT_BRANCH="$(git -C "$REPO_ROOT" rev-parse --abbrev-ref HEAD 2>/dev/null || echo unknown)"
BUILD_DATE="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"

echo "==> DB-GPT Docker release build"
echo "    App version:  $APP_VERSION"
echo "    Build tag:    $IMAGE_VERSION"
echo "    Image:        $IMAGE_REPO"
echo "    Platform:     linux/amd64"
echo "    Git:          $GIT_BRANCH @ $GIT_SHA"
echo "    Notes:        $NOTES"
echo

if [[ "$SKIP_FRONTEND" -eq 0 ]]; then
  echo "==> Building static frontend..."
  bash "$REPO_ROOT/scripts/build_web_static.sh"
else
  echo "==> Skipping frontend build (--skip-frontend)"
fi

echo "==> Building Docker image (amd64)..."
docker buildx build --platform linux/amd64 \
  --build-arg USE_TSINGHUA_UBUNTU=true \
  --build-arg BASE_IMAGE=ubuntu:22.04 \
  --build-arg PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple \
  --build-arg LANGUAGE=en \
  --build-arg LOAD_EXAMPLES=true \
  --build-arg EXTRAS=base,proxy_openai,rag,graph_rag,storage_chromadb,dbgpts,proxy_ollama,proxy_zhipuai,proxy_anthropic,proxy_qianfan,proxy_tongyi \
  --build-arg PYTHON_VERSION=3.11 \
  -f "$DOCKERFILE_DIR/Dockerfile" \
  -t "${IMAGE_REPO}:latest" \
  -t "${IMAGE_REPO}:${IMAGE_VERSION}" \
  --load \
  "$REPO_ROOT"

DIGEST="$(docker inspect "${IMAGE_REPO}:${IMAGE_VERSION}" --format '{{index .RepoDigests 0}}' 2>/dev/null || true)"
if [[ -z "$DIGEST" || "$DIGEST" == "<no value>" ]]; then
  DIGEST="$(docker inspect "${IMAGE_REPO}:${IMAGE_VERSION}" --format '{{.Id}}')"
fi

if [[ "$DO_PUSH" -eq 1 ]]; then
  echo "==> Pushing tags to Docker Hub..."
  docker push "${IMAGE_REPO}:latest"
  docker push "${IMAGE_REPO}:${IMAGE_VERSION}"
fi

# --- Append BUILD_LOG.md ---
{
  echo ""
  echo "## ${IMAGE_VERSION} — ${BUILD_DATE}"
  echo ""
  echo "- **Git:** \`${GIT_BRANCH}\` @ [\`${GIT_SHA}\`](https://github.com/golliaph/dbgpt/commit/${GIT_SHA})"
  echo "- **Platform:** linux/amd64"
  echo "- **Tags:** \`${IMAGE_REPO}:latest\`, \`${IMAGE_REPO}:${IMAGE_VERSION}\`"
  echo "- **Digest:** \`${DIGEST}\`"
  echo "- **Frontend rebuild:** $([[ "$SKIP_FRONTEND" -eq 0 ]] && echo yes || echo no)"
  echo "- **Pushed:** $([[ "$DO_PUSH" -eq 1 ]] && echo yes || echo no)"
  echo "- **Changes:**"
  echo "  - ${NOTES}"
} >>"$BUILD_LOG"

# --- Update builds.json (requires python3) ---
python3 - "$BUILDS_JSON" "$IMAGE_REPO" "$IMAGE_VERSION" "$BUILD_DATE" "$GIT_SHA" "$GIT_BRANCH" "$DIGEST" "$NOTES" "$SKIP_FRONTEND" "$DO_PUSH" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
data = json.loads(path.read_text()) if path.exists() else {
    "image": sys.argv[2],
    "platform": "linux/amd64",
    "builds": [],
}
entry = {
    "version": sys.argv[3],
    "built_at": sys.argv[4],
    "git_sha": sys.argv[5],
    "git_branch": sys.argv[6],
    "digest": sys.argv[7],
    "notes": sys.argv[8],
    "frontend_rebuild": sys.argv[9] == "0",
    "pushed": sys.argv[10] == "1",
    "tags": [f"{sys.argv[2]}:latest", f"{sys.argv[2]}:{sys.argv[3]}"],
}
data.setdefault("builds", []).append(entry)
path.write_text(json.dumps(data, indent=2) + "\n")
PY

echo
echo "==> Done"
echo "    Tags:  ${IMAGE_REPO}:latest"
echo "           ${IMAGE_REPO}:${IMAGE_VERSION}"
echo "    Log:   $BUILD_LOG"
echo "    JSON:  $BUILDS_JSON"
if [[ "$DO_PUSH" -eq 0 ]]; then
  echo
  echo "    Push:  docker push ${IMAGE_REPO}:latest && docker push ${IMAGE_REPO}:${IMAGE_VERSION}"
fi
