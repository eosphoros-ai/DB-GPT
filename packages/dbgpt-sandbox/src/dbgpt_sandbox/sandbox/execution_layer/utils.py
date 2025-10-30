"""
提供资源限制、路径处理、环境检测等工具功能。
"""

import os
import platform
import shutil
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import psutil

from ..config import (
    MAX_CPU_PERCENT,
    MAX_EXECUTION_TIME,
    MAX_FILE_SIZE,
    MAX_MEMORY,
    MAX_PROCESSES,
)


@dataclass
class ResourceLimits:
    """资源限制配置"""

    max_memory: int = MAX_MEMORY
    max_cpu_percent: float = MAX_CPU_PERCENT
    max_execution_time: int = MAX_EXECUTION_TIME  # seconds
    max_file_size: int = MAX_FILE_SIZE  # 10MB
    max_processes: int = MAX_PROCESSES


class EnvironmentDetector:
    """环境检测工具"""

    @staticmethod
    def is_docker_available() -> bool:
        """检查 Docker CLI 是否可用"""
        return shutil.which("docker") is not None

    @staticmethod
    def is_docker_sdk_available() -> bool:
        """检查 Docker Python SDK 是否可用"""
        try:
            return True
        except Exception:
            return False

    @staticmethod
    def is_podman_available() -> bool:
        """检查 Podman 是否可用"""
        return shutil.which("podman") is not None

    @staticmethod
    def is_nerdctl_available() -> bool:
        """检查 Nerdctl 是否可用"""
        return shutil.which("nerdctl") is not None

    @staticmethod
    def get_system_info() -> Dict[str, Any]:
        """获取系统信息"""
        return {
            "platform": platform.platform(),
            "python_version": platform.python_version(),
            "cpu_count": psutil.cpu_count(),
            "memory_total": psutil.virtual_memory().total,
            "memory_available": psutil.virtual_memory().available,
            "disk_usage": psutil.disk_usage("/").percent
            if os.name != "nt"
            else psutil.disk_usage("C:").percent,
        }

    @staticmethod
    def check_resource_availability(limits: ResourceLimits) -> Dict[str, bool]:
        """检查资源是否满足限制要求"""
        memory = psutil.virtual_memory()

        return {
            "memory_ok": memory.available >= limits.max_memory,
            "cpu_ok": psutil.cpu_count() >= 1,
            "disk_ok": True,
        }


class PathUtils:
    """路径处理工具"""

    @staticmethod
    def ensure_safe_path(path: str, base_dir: str) -> str:
        """确保路径安全，防止路径遍历攻击"""
        normalized_path = os.path.normpath(path)
        normalized_base = os.path.normpath(base_dir)

        if not normalized_path.startswith(normalized_base):
            raise ValueError(f"不安全的路径: {path}")

        return normalized_path

    @staticmethod
    def create_temp_dir(prefix: str = "sandbox_") -> str:
        """创建临时目录"""
        import tempfile

        return tempfile.mkdtemp(prefix=prefix)

    @staticmethod
    def cleanup_directory(directory: str) -> bool:
        """清理目录"""
        try:
            if os.path.exists(directory):
                shutil.rmtree(directory)
            return True
        except Exception as e:
            print(f"清理目录失败: {e}")
            return False


class ProcessManager:
    """进程管理工具"""

    @staticmethod
    def kill_process_tree(pid: int) -> bool:
        """终止进程树"""
        try:
            parent = psutil.Process(pid)
            children = parent.children(recursive=True)

            for child in children:
                try:
                    child.terminate()
                except psutil.NoSuchProcess:
                    pass

            gone, alive = psutil.wait_procs(children, timeout=3)

            for p in alive:
                try:
                    p.kill()
                except psutil.NoSuchProcess:
                    pass

            try:
                parent.terminate()
                parent.wait(timeout=3)
            except (psutil.NoSuchProcess, psutil.TimeoutExpired):
                try:
                    parent.kill()
                except psutil.NoSuchProcess:
                    pass

            return True
        except Exception as e:
            print(f"终止进程树失败: {e}")
            return False

    @staticmethod
    def get_process_stats(pid: int) -> Optional[Dict[str, Any]]:
        """获取进程统计信息"""
        try:
            process = psutil.Process(pid)
            return {
                "cpu_percent": process.cpu_percent(),
                "memory_info": process.memory_info()._asdict(),
                "status": process.status(),
                "create_time": process.create_time(),
            }
        except psutil.NoSuchProcess:
            return None


class SecurityUtils:
    """安全工具"""

    @staticmethod
    def validate_code(code: str, language: str) -> List[str]:
        """验证代码安全性，返回警告列表"""
        warnings = []

        dangerous_patterns = [
            "import os",
            "import subprocess",
            "import sys",
            "__import__",
            "eval(",
            "exec(",
            "open(",
            "file(",
            "input(",
            "raw_input(",
            "socket",
            "urllib",
            "requests",
            "rmdir",
            "remove",
            "unlink",
            "delete",
        ]

        code_lower = code.lower()
        for pattern in dangerous_patterns:
            if pattern in code_lower:
                warnings.append(f"检测到潜在危险操作: {pattern}")

        if language == "python":
            if "pickle" in code_lower:
                warnings.append("检测到 pickle 模块使用，可能存在安全风险")

        return warnings


path_utils = PathUtils()
resource_limits = ResourceLimits()
environment_detector = EnvironmentDetector()
process_manager = ProcessManager()
security_utils = SecurityUtils()
