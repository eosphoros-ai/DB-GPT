# DB-GPT Docker release build log

Images: `golliaph/dbgpt-openai` (linux/amd64 only)

| Field | Value |
|-------|-------|
| Script | `scripts/build_docker_release.sh` |
| Tags per build | `latest` + `{app_version}-b{N}` (e.g. `0.8.1-b1`) |
| Machine log | [builds.json](builds.json) |
| Skill | [skills/dbgpt-docker-release](../../skills/dbgpt-docker-release/SKILL.md) |

---

## Historical (before release script)

### 0.8.1-b1 — 2026-06-19 (manual)

- **Git:** `main` @ `abd04909`
- **Platform:** linux/amd64 (arm64 local only for dev)
- **Tags:** `golliaph/dbgpt-openai:latest` (not version-tagged yet)
- **Changes:**
  - Remove Chinese locale; translate frontend and skills to English-only

### 0.8.1-b2 — 2026-06-19 (manual)

- **Git:** `main` @ `e41d2548`
- **Platform:** linux/amd64
- **Changes:**
  - Rebuild static web assets (`build_web_static.sh`)

### 0.8.1-b3 — 2026-06-19 (manual)

- **Git:** `main` @ `256ca5fa`
- **Platform:** linux/amd64
- **Tags:** `golliaph/dbgpt-openai:latest`, `golliaph/dbgpt-openai:0.8.1-b3`
- **Digest:** `sha256:77540eca6219fab0f056d7aec96e8b983ee5693618cb9bf65507561bc99838b5`
- **Pushed:** yes
- **Changes:**
  - Translate `agentic_data_api` user-facing strings to English
  - amd64 image build and push to Docker Hub

---

<!-- New entries below are appended by scripts/build_docker_release.sh -->

## 0.8.1-b4 — 2026-06-19T10:59:16Z

- **Git:** `style/modernize-html-reports` @ [`a5dfd8e8`](https://github.com/golliaph/dbgpt/commit/a5dfd8e8)
- **Platform:** linux/amd64
- **Tags:** `golliaph/dbgpt-openai:latest`, `golliaph/dbgpt-openai:0.8.1-b4`
- **Digest:** `golliaph/dbgpt-openai@sha256:16031f4b8c8c582eda4589d580d71ce539319e7dea0f9a91ce7b717db3d1378c`
- **Frontend rebuild:** no
- **Pushed:** no
- **Changes:**
  - Modern Slate & Indigo style for HTML reports and templates
