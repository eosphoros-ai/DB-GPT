"""Select an explicitly configured container runtime, or use local execution."""

import logging

from ..config import SANDBOX_RUNTIME
from .docker_runtime import DockerRuntime
from .local_runtime import LocalRuntime
from .nerdctl_runtime import NerdctlRuntime
from .podman_runtime import PodmanRuntime
from .utils import EnvironmentDetector

logger = logging.getLogger(__name__)


class RuntimeFactory:
    """Keep local execution available without requiring a container setup."""

    @staticmethod
    def create(runtime_preference: str = None):
        """Explicit argument > deployment config > local.

        Local execution is the default, not a fallback. An explicitly selected
        container backend must initialize successfully or raise an error.
        """
        preference = (runtime_preference or SANDBOX_RUNTIME or "local").strip().lower()
        if not preference or preference == "local":
            return LocalRuntime()
        if preference not in {"docker", "podman", "nerdctl"}:
            raise ValueError(f"Unknown sandbox runtime: {preference}")

        runtime = None
        try:
            if preference == "docker":
                runtime = DockerRuntime()
                if not runtime.docker_client.ping():
                    raise RuntimeError("Docker daemon did not respond to ping")
                return runtime
            if preference == "podman" and EnvironmentDetector.is_podman_available():
                return PodmanRuntime()
            if preference == "nerdctl" and EnvironmentDetector.is_nerdctl_available():
                return NerdctlRuntime()
            raise RuntimeError(f"{preference} is not installed")
        except Exception as exc:
            if runtime is not None:
                try:
                    runtime.docker_client.close()
                except Exception:
                    pass
            message = (
                f"Configured sandbox runtime {preference} is unavailable; "
                f"refusing local execution: {exc}"
            )
            logger.error("%s", message)
            raise RuntimeError(message) from exc
