---
id: runtime
title: Sandbox Runtime Configuration
sidebar_position: 1
description: Configure LocalRuntime and container-backed runtimes for DB-GPT agent execution.
---

# Sandbox Runtime Configuration

This page documents the runtime selection used by DB-GPT's application-side
Python and Shell agent tools. The implementation is shared by the main agent and
sub-agents through:

- packages/dbgpt-app/src/dbgpt_app/openapi/api_v1/tools/_execution.py
- packages/dbgpt-sandbox/src/dbgpt_sandbox/sandbox/execution_layer/runtime_factory.py

## Runtime selection

The selection order is:

1. An explicit runtime argument, when a caller provides one.
2. The SANDBOX_RUNTIME environment variable.
3. LocalRuntime.

| Configuration | Runtime |
| --- | --- |
| Unset, empty, or local | LocalRuntime |
| SANDBOX_RUNTIME=docker and Docker is reachable | DockerRuntime |
| SANDBOX_RUNTIME=podman and Podman is available | PodmanRuntime |
| SANDBOX_RUNTIME=nerdctl and Nerdctl is available | NerdctlRuntime |
| Configured container backend or session cannot be initialized | Error; no local execution |
| Unknown runtime name | Configuration error |

Installing Docker does not enable Docker execution. Docker is opt-in:

~~~bash
export SANDBOX_RUNTIME=docker
~~~

If the variable is not set, DB-GPT uses the current application environment and
does not need a Docker image.

LocalRuntime is the default, not a fallback. Explicitly selecting docker, podman,
or nerdctl requires that backend to work. Initialization, image pull, container
creation, or input-file transfer failures return an error instead of running the
code on the host. This policy does not require an additional flag.

## LocalRuntime

LocalRuntime is the default because it lets DB-GPT work immediately after the
application starts.

In local mode:

- Python runs with the application Python interpreter.
- Installed application dependencies, such as pandas and numpy, are available.
- Shell commands run on the service host.
- No container image is required.
- Local execution does not provide container isolation; deploy the service with
  the appropriate operating-system permissions and network controls.

To select it explicitly:

~~~bash
export SANDBOX_RUNTIME=local
~~~

## DockerRuntime

Docker execution requires both a reachable Docker daemon and an image. The
application-side agent executor uses SANDBOX_AGENT_IMAGE, whose default is:

~~~text
dbgpt-sandbox-agent:latest
~~~

The repository includes a Dockerfile for an agent image with the common data
analysis dependencies used by code_interpreter:

~~~bash
cd /path/to/DB-GPT
docker build -f packages/dbgpt-sandbox/src/docker_images/Dockerfile.agent -t dbgpt-sandbox-agent:latest packages/dbgpt-sandbox/src/docker_images
~~~

Use a different image when the deployment has its own image registry or extra
system dependencies:

~~~bash
export SANDBOX_RUNTIME=docker
export SANDBOX_AGENT_IMAGE=registry.example.com/dbgpt/agent:2026-09
~~~

The custom image is recommended for full Python data-analysis compatibility.
Minimal images such as python:3.11-slim can run basic Python and Shell code,
but do not include pandas, numpy, matplotlib, Excel libraries, or arbitrary
system commands required by every agent workflow.

## Execution lifecycle

The current application-side Agent integration uses a short-lived execution
session for each Python or Shell tool call:

1. Select a runtime.
2. Create a session and, for Docker, start a container.
3. Transfer the working directory and explicit input files when needed.
4. Execute the code or Shell command.
5. Copy ordinary output files and generated artifacts back to the host.
6. Destroy the session and remove the container.

The container is therefore expected to disappear after the tool call. Files in
the host working directory can remain available to later calls, but packages
installed inside a short-lived container do not persist between calls. Put
long-lived dependencies in the agent image instead.

The actual runtime is logged at INFO level after a session is successfully
created, immediately before code execution:

~~~text
Sandbox execution: runtime=docker language=python session_id=agent_...
~~~

This is a per-tool-call log, not an application startup log. It is not emitted
when runtime or session initialization fails.

If the configured container runtime, image pull, session initialization, or
input-file transfer fails, the tool returns an error without executing user code
locally. An error, timeout, cancellation, or artifact-collection failure after
execution starts is also not replayed on another runtime.

## Files and workspaces

The application executor keeps the host conversation work directory under the
configured DB-GPT temporary path. In Docker mode it transfers the workspace and
explicit input files into the container, then collects ordinary files back.

The following values are passed to the child execution environment when present:

- PLOT_DIR
- FILE_PATH
- FILES_JSON

The container is not given the host's entire filesystem. Files must be provided
through the supported workspace or input-file path flow.

## Verification

Run the runtime and application tests without Docker:

~~~bash
.venv/bin/python -m pytest packages/dbgpt-sandbox/tests packages/dbgpt-app/src/dbgpt_app/openapi/api_v1/tools/tests packages/dbgpt-app/src/dbgpt_app/openapi/api_v1/subagent/tests -q
~~~

After building the agent image, run the live Docker tests:

~~~bash
DBGPT_TEST_DOCKER_IMAGE=dbgpt-sandbox-agent:latest .venv/bin/python -m pytest packages/dbgpt-app/src/dbgpt_app/openapi/api_v1/tools/tests/test_execution_docker_integration.py -q
~~~

## Troubleshooting

### pull access denied for dbgpt-sandbox-agent

The configured image is not present in the Docker daemon and is not available
from the registry. Build the repository image or set SANDBOX_AGENT_IMAGE to an
image that the daemon can access.

### Configured container runtime is unavailable

Check the selected backend, daemon connection, image, and reported input-file
error. The tool deliberately stops rather than silently switching to host
execution. If local execution is intended, explicitly set SANDBOX_RUNTIME=local
and restart DB-GPT; local mode does not provide container isolation.

### No container appears in docker ps

This is normal after a successful Agent tool call because the container is
removed during cleanup. To observe its short lifetime, run:

~~~bash
docker events --filter type=container --format '{{.Time}} {{.Status}} {{.Actor.Attributes.name}}'
~~~

Then trigger a longer-running tool call.

### Docker is installed but local execution is used

Check that SANDBOX_RUNTIME=docker is exported in the same environment that
starts DB-GPT, and restart the service after changing it. Then trigger a Python
or Shell tool call and check its INFO runtime log; this line is not printed at
application startup.
