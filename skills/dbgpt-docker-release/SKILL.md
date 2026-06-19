---
name: dbgpt-docker-release
description: Build and publish golliaph/dbgpt-openai Docker images (linux/amd64 only) with local versioning, latest + version tags, and a build log. Use when releasing DB-GPT to Docker Hub or rebuilding the stack after frontend/backend changes.
---

# DB-GPT Docker release

Build the **proxy/openai** DB-GPT image for **linux/amd64** only. Each run produces two tags and appends a row to the release log.

## Image tags

| Tag | Example | Purpose |
|-----|---------|---------|
| `latest` | `golliaph/dbgpt-openai:latest` | Always points to the most recent successful build |
| Versioned | `golliaph/dbgpt-openai:0.8.1-b3` | `{pyproject version}-b{build_number}` — unique, rollback-friendly |

Build counter lives in [docker/release/.build-counter](../../docker/release/.build-counter).

## Quick start

```bash
# Full release: frontend static + amd64 image + log entry
bash scripts/build_docker_release.sh \
  --notes "English-only UI, agentic_data_api strings, static web rebuild"

# Build and push to Docker Hub
bash scripts/build_docker_release.sh \
  --push \
  --notes "Production release 0.8.1-b4"

# Backend-only (skip yarn compile)
bash scripts/build_docker_release.sh \
  --skip-frontend \
  --notes "agentic_data_api translation only"
```

## What the script does

1. Reads app version from [pyproject.toml](../../pyproject.toml) (`0.8.1`)
2. Increments local build counter → `0.8.1-b{N}`
3. Runs [scripts/build_web_static.sh](../../scripts/build_web_static.sh) unless `--skip-frontend`
4. `docker buildx build --platform linux/amd64` → tags `latest` + version
5. Appends entry to [docker/release/BUILD_LOG.md](../../docker/release/BUILD_LOG.md)
6. Appends JSON record to [docker/release/builds.json](../../docker/release/builds.json)
7. Optionally `--push` both tags to Docker Hub

## Logs

- **Human:** [docker/release/BUILD_LOG.md](../../docker/release/BUILD_LOG.md) — markdown changelog per build
- **Machine:** [docker/release/builds.json](../../docker/release/builds.json) — structured history

Commit these files after each release so the team shares the same build history.

## Deploy on amd64 server

```bash
docker pull golliaph/dbgpt-openai:0.8.1-b3   # pinned
# or
docker pull golliaph/dbgpt-openai:latest
```

In `docker-compose.yml`:

```yaml
webserver:
  image: golliaph/dbgpt-openai:0.8.1-b3
```

## Prerequisites

- Docker with `buildx` (QEMU for amd64 on Apple Silicon)
- `yarn` (for frontend build; install via `npm install -g yarn`)
- `docker login` for `--push`

## Options reference

| Flag | Description |
|------|-------------|
| `--notes TEXT` | **Required.** Short description stored in the build log |
| `--push` | Push `latest` and version tag to Docker Hub |
| `--skip-frontend` | Skip `build_web_static.sh` |
| `--image REPO` | Override image name (default `golliaph/dbgpt-openai`) |
