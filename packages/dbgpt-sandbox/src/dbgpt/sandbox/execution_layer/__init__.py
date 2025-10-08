"""
DB-GPT Sandbox Agent - 核心沙箱模块

提供统一的代码执行沙箱接口，支持 Docker、本地运行时与 Podman。
"""

from .base import ExecutionResult, SandboxRuntime, SandboxSession
from .docker_runtime import DockerRuntime
from .local_runtime import LocalRuntime
from .nerdctl_runtime import NerdctlRuntime
from .podman_runtime import PodmanRuntime
from .utils import EnvironmentDetector, ResourceLimits

__version__ = "0.1.0"
__author__ = "DB-GPT Team"

__all__ = [
    "SandboxRuntime",
    "SandboxSession",
    "ExecutionResult",
    "DockerRuntime",
    "LocalRuntime",
    "PodmanRuntime",
    "NerdctlRuntime",
    "ResourceLimits",
    "EnvironmentDetector",
]
