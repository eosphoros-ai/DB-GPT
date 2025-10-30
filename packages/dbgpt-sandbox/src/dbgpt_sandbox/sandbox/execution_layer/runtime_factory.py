"""
自动沙箱运行时工厂

根据本机环境优先级自动选择 Docker/Podman/Nerdctl/Local 运行时。
"""

from ..config import SANDBOX_RUNTIME
from .docker_runtime import DockerRuntime
from .local_runtime import LocalRuntime
from .nerdctl_runtime import NerdctlRuntime
from .podman_runtime import PodmanRuntime
from .utils import EnvironmentDetector


class RuntimeFactory:
    """自动选择最佳沙箱运行时"""

    @staticmethod
    def create(runtime_preference: str = None):
        """
        创建最佳可用运行时。
        """
        env_choice = SANDBOX_RUNTIME
        if env_choice:
            runtime_preference = env_choice.lower()

        if runtime_preference:
            runtime_preference = runtime_preference.lower()
            if (
                runtime_preference == "docker"
                and EnvironmentDetector.is_docker_sdk_available()
            ):
                return DockerRuntime()
            if (
                runtime_preference == "podman"
                and EnvironmentDetector.is_podman_available()
            ):
                return PodmanRuntime()
            if (
                runtime_preference == "nerdctl"
                and EnvironmentDetector.is_nerdctl_available()
            ):
                return NerdctlRuntime()
            if runtime_preference == "local":
                return LocalRuntime()
            raise RuntimeError(f"指定的运行时不可用: {runtime_preference}")

        if EnvironmentDetector.is_docker_sdk_available():
            try:
                print("检测到 Docker SDK 可用")
                import docker

                client = docker.from_env()
                client.info()
                return DockerRuntime()
            except Exception:
                pass
        if EnvironmentDetector.is_podman_available():
            return PodmanRuntime()
        if EnvironmentDetector.is_nerdctl_available():
            return NerdctlRuntime()
        return LocalRuntime()
