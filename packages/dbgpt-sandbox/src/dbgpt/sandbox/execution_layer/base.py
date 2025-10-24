"""
沙箱运行时基础抽象类

定义了统一的沙箱接口，包括会话管理、代码执行等核心功能。
"""

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional


class ExecutionStatus(Enum):
    """执行状态枚举"""

    SUCCESS = "success"
    ERROR = "error"
    TIMEOUT = "timeout"
    RESOURCE_LIMIT = "resource_limit"


@dataclass
class ExecutionResult:
    """代码执行结果"""

    status: ExecutionStatus
    output: str = ""
    error: str = ""
    execution_time: float = 0.0
    memory_usage: int = 0  # bytes
    exit_code: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "status": self.status.value,
            "output": self.output,
            "error": self.error,
            "execution_time": self.execution_time,
            "memory_usage": self.memory_usage,
            "exit_code": self.exit_code,
        }


@dataclass
class SessionConfig:
    """会话配置"""

    language: str = "python"
    timeout: int = 30  # seconds
    max_memory: int = 256 * 1024 * 1024  # 256MB
    # max_cpu_percent: float = 50.0
    max_cpus: int = 1
    working_dir: str = "/workspace"
    environment_vars: Dict[str, str] = None
    network_disabled: bool = False  # 是否禁用网络

    def __post_init__(self):
        if self.environment_vars is None:
            self.environment_vars = {}


class SandboxSession(ABC):
    """沙箱会话抽象类"""

    def __init__(self, session_id: str, config: SessionConfig):
        self.session_id = session_id
        self.config = config
        self.created_at = time.time()
        self.last_accessed = time.time()
        self._is_active = False

    @property
    def is_active(self) -> bool:
        """检查会话是否活跃"""
        return self._is_active

    @abstractmethod
    async def start(self) -> bool:
        """启动会话"""
        pass

    @abstractmethod
    async def stop(self) -> bool:
        """停止会话"""
        pass

    @abstractmethod
    async def execute(self, code: str) -> ExecutionResult:
        """执行代码"""
        pass

    @abstractmethod
    async def get_status(self) -> Dict[str, Any]:
        """获取会话状态"""
        pass

    async def install_dependencies(self, dependencies: List[str]) -> ExecutionResult:
        """安装依赖（可选）。默认未实现，由具体运行时覆盖。
        返回 ExecutionResult，status 为 ERROR 表示未实现或失败。
        """
        if not dependencies:
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS, output="无依赖需要安装", exit_code=0
            )
        return ExecutionResult(
            status=ExecutionStatus.ERROR, error="依赖安装未实现", exit_code=1
        )

    def update_last_accessed(self):
        """更新最后访问时间"""
        self.last_accessed = time.time()


class SandboxRuntime(ABC):
    """沙箱运行时抽象类"""

    def __init__(self, runtime_id: str):
        self.runtime_id = runtime_id
        self.sessions: Dict[str, SandboxSession] = {}

    @abstractmethod
    async def create_session(
        self, session_id: str, config: SessionConfig
    ) -> SandboxSession:
        """创建新的沙箱会话"""
        pass

    @abstractmethod
    async def destroy_session(self, session_id: str) -> bool:
        """销毁沙箱会话"""
        pass

    @abstractmethod
    async def list_sessions(self) -> List[str]:
        """列出所有活跃会话"""
        pass

    @abstractmethod
    async def get_session(self, session_id: str) -> Optional[SandboxSession]:
        """获取指定会话"""
        pass

    @abstractmethod
    async def cleanup_expired_sessions(self, max_idle_time: int = 3600) -> int:
        """清理过期会话，返回清理的会话数量"""
        pass

    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        pass

    @abstractmethod
    def supports_language(self, language: str) -> bool:
        """检查是否支持指定编程语言"""
        pass
