"""
基于本地进程的代码执行环境，使用 subprocess 和资源限制。
"""

import asyncio
import os
import subprocess
import tempfile
import time
from typing import Any, Dict, List, Optional

import psutil

from .base import (
    ExecutionResult,
    ExecutionStatus,
    SandboxRuntime,
    SandboxSession,
    SessionConfig,
)
from .utils import PathUtils, ProcessManager, SecurityUtils


class LocalSandboxSession(SandboxSession):
    """本地沙箱会话实现"""

    def __init__(self, session_id: str, config: SessionConfig):
        super().__init__(session_id, config)
        self.work_dir = None
        self.process_pool = []
        self.path_utils = PathUtils()
        self.process_manager = ProcessManager()
        self.security_utils = SecurityUtils()

    async def start(self) -> bool:
        """启动本地沙箱会话"""
        try:
            # 创建工作目录
            self.work_dir = self.path_utils.create_temp_dir(
                f"sandbox_{self.session_id}_"
            )

            # 设置环境变量
            self._setup_environment()

            self._is_active = True
            return True

        except Exception as e:
            print(f"启动本地沙箱失败: {e}")
            return False

    def _setup_environment(self):
        """设置执行环境"""
        # 设置基本环境变量
        os.environ.update(self.config.environment_vars)

        # 创建必要的子目录
        os.makedirs(os.path.join(self.work_dir, "input"), exist_ok=True)
        os.makedirs(os.path.join(self.work_dir, "output"), exist_ok=True)

    async def stop(self) -> bool:
        """停止本地沙箱会话"""
        try:
            # 清理所有子进程
            for pid in self.process_pool:
                self.process_manager.kill_process_tree(pid)

            # 清理工作目录
            if self.work_dir and os.path.exists(self.work_dir):
                self.path_utils.cleanup_directory(self.work_dir)

            self._is_active = False
            return True

        except Exception as e:
            print(f"停止本地沙箱失败: {e}")
            return False

    async def execute(self, code: str) -> ExecutionResult:
        """在本地进程中执行代码"""
        if not self._is_active or not self.work_dir:
            return ExecutionResult(
                status=ExecutionStatus.ERROR, error="会话未启动或工作目录不存在"
            )

        self.update_last_accessed()

        # 安全检查
        warnings = self.security_utils.validate_code(code, self.config.language)
        if warnings and any("危险操作" in w for w in warnings):
            return ExecutionResult(
                status=ExecutionStatus.ERROR,
                error=f"代码安全检查失败: {'; '.join(warnings)}",
            )

        try:
            # 创建代码文件
            code_file = self._create_code_file(code)

            # 获取执行命令
            command = self._get_exec_command(code_file)

            # 执行代码
            start_time = time.time()
            result = await self._run_with_limits(command)
            execution_time = time.time() - start_time

            return ExecutionResult(
                status=ExecutionStatus.SUCCESS
                if result["returncode"] == 0
                else ExecutionStatus.ERROR,
                output=result["stdout"],
                error=result["stderr"],
                execution_time=execution_time,
                memory_usage=result.get("memory_usage", 0),
                exit_code=result["returncode"],
            )

        except asyncio.TimeoutError:
            return ExecutionResult(
                status=ExecutionStatus.TIMEOUT,
                error=f"执行超时 ({self.config.timeout}秒)",
            )
        except Exception as e:
            return ExecutionResult(
                status=ExecutionStatus.ERROR, error=f"执行失败: {str(e)}"
            )
        finally:
            if "code_file" in locals():
                os.unlink(code_file)

    def _create_code_file(self, code: str) -> str:
        """创建临时代码文件"""
        extensions = {
            "python": ".py",
            "javascript": ".js",
            "java": ".java",
            "cpp": ".cpp",
            "c": ".c",
            "go": ".go",
            "rust": ".rs",
            "bash": ".sh",
        }

        ext = extensions.get(self.config.language, ".txt")

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=ext, dir=self.work_dir, delete=False, encoding="utf-8"
        ) as f:
            f.write(code)
            return f.name

    def _get_exec_command(self, code_file: str) -> List[str]:
        """根据语言获取执行命令"""
        filename = os.path.basename(code_file)

        commands = {
            "python": ["python", code_file],
            "javascript": ["node", code_file],
            "java": [
                "sh",
                "-c",
                f"cd {os.path.dirname(code_file)} && \
                    javac {filename} && java {filename[:-5]}",
            ],
            "cpp": [
                "sh",
                "-c",
                f"cd {os.path.dirname(code_file)} && g++ -o program {filename} \
                      && ./program",
            ],
            "c": [
                "sh",
                "-c",
                f"cd {os.path.dirname(code_file)} && gcc -o program {filename} \
                      && ./program",
            ],
            "go": ["go", "run", code_file],
            "rust": [
                "sh",
                "-c",
                f"cd {os.path.dirname(code_file)} && rustc {filename} \
                  -o program && ./program",
            ],
            "bash": ["bash", code_file],
        }

        return commands.get(self.config.language, ["cat", code_file])

    async def _run_with_limits(self, command: List[str]) -> Dict[str, Any]:
        """在资源限制下运行命令"""
        process = None
        try:
            # 启动进程
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.work_dir,
                env=dict(os.environ, **self.config.environment_vars),
            )

            # 记录进程 PID
            if process.pid:
                self.process_pool.append(process.pid)

            # 设置资源监控
            memory_usage = 0
            if process.pid:
                try:
                    proc_info = psutil.Process(process.pid)
                    memory_usage = proc_info.memory_info().rss

                    # 检查内存限制
                    if memory_usage > self.config.max_memory:
                        process.terminate()
                        return {
                            "returncode": -1,
                            "stdout": "",
                            "stderr": "内存使用超出限制",
                            "memory_usage": memory_usage,
                        }
                except psutil.NoSuchProcess:
                    pass

            # 等待进程完成（带超时）
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=self.config.timeout
            )

            # 清理进程记录
            if process.pid in self.process_pool:
                self.process_pool.remove(process.pid)

            return {
                "returncode": process.returncode,
                "stdout": stdout.decode("utf-8", errors="replace"),
                "stderr": stderr.decode("utf-8", errors="replace"),
                "memory_usage": memory_usage,
            }

        except asyncio.TimeoutError:
            # 超时处理
            if process and process.pid:
                self.process_manager.kill_process_tree(process.pid)
                if process.pid in self.process_pool:
                    self.process_pool.remove(process.pid)
            raise
        except Exception as e:
            # 其他异常处理
            if process and process.pid:
                self.process_manager.kill_process_tree(process.pid)
                if process.pid in self.process_pool:
                    self.process_pool.remove(process.pid)
            raise e

    async def get_status(self) -> Dict[str, Any]:
        """获取会话状态"""
        if not self._is_active:
            return {"status": "stopped"}

        active_processes = []
        for pid in self.process_pool[:]:  # 复制列表避免修改时的问题
            try:
                proc = psutil.Process(pid)
                active_processes.append(
                    {
                        "pid": pid,
                        "status": proc.status(),
                        "memory": proc.memory_info().rss,
                        "cpu_percent": proc.cpu_percent(),
                    }
                )
            except psutil.NoSuchProcess:
                # 进程已结束，从池中移除
                self.process_pool.remove(pid)

        return {
            "status": "running",
            "work_dir": self.work_dir,
            "created_at": self.created_at,
            "last_accessed": self.last_accessed,
            "active_processes": active_processes,
            "process_count": len(active_processes),
        }


class LocalRuntime(SandboxRuntime):
    """本地沙箱运行时"""

    def __init__(self, runtime_id: str = "local"):
        super().__init__(runtime_id)
        self.supported_languages = self._detect_supported_languages()

    def _detect_supported_languages(self) -> List[str]:
        """检测系统支持的编程语言"""
        languages = []

        # 检查常见编程语言的可用性
        language_commands = {
            "python": ["python", "--version"],
            "javascript": ["node", "--version"],
            "java": ["java", "-version"],
            "cpp": ["g++", "--version"],
            "c": ["gcc", "--version"],
            "go": ["go", "version"],
            "rust": ["rustc", "--version"],
            "bash": ["bash", "--version"],
        }

        for lang, cmd in language_commands.items():
            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    timeout=2,  # 减少超时时间
                    shell=True,  # 在Windows上使用shell
                )
                if result.returncode == 0:
                    languages.append(lang)
            except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
                # 如果命令不可用，跳过
                pass

        # 确保至少支持Python（假设在Python环境中运行）
        if "python" not in languages:
            languages.append("python")

        return languages

    async def create_session(
        self, session_id: str, config: SessionConfig
    ) -> SandboxSession:
        """创建新的本地沙箱会话"""
        if session_id in self.sessions:
            raise ValueError(f"会话 {session_id} 已存在")

        session = LocalSandboxSession(session_id, config)

        if await session.start():
            self.sessions[session_id] = session
            return session
        else:
            raise RuntimeError(f"启动会话 {session_id} 失败")

    async def destroy_session(self, session_id: str) -> bool:
        """销毁本地沙箱会话"""
        if session_id not in self.sessions:
            return False

        session = self.sessions[session_id]
        success = await session.stop()

        if success:
            del self.sessions[session_id]

        return success

    async def list_sessions(self) -> List[str]:
        """列出所有活跃会话"""
        return list(self.sessions.keys())

    async def get_session(self, session_id: str) -> Optional[SandboxSession]:
        """获取指定会话"""
        return self.sessions.get(session_id)

    async def cleanup_expired_sessions(self, max_idle_time: int = 3600) -> int:
        """清理过期会话"""
        current_time = time.time()
        expired_sessions = []

        for session_id, session in self.sessions.items():
            if current_time - session.last_accessed > max_idle_time:
                expired_sessions.append(session_id)

        cleanup_count = 0
        for session_id in expired_sessions:
            if await self.destroy_session(session_id):
                cleanup_count += 1

        return cleanup_count

    async def health_check(self) -> Dict[str, Any]:
        """本地运行时健康检查"""
        try:
            import psutil

            return {
                "status": "healthy",
                "system_info": {
                    "cpu_count": psutil.cpu_count(),
                    "memory_total": psutil.virtual_memory().total,
                    "memory_available": psutil.virtual_memory().available,
                    "disk_usage": psutil.disk_usage("/").percent
                    if os.name != "nt"
                    else psutil.disk_usage("C:").percent,
                },
                "active_sessions": len(self.sessions),
                "supported_languages": self.supported_languages,
            }
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}

    def supports_language(self, language: str) -> bool:
        """检查是否支持指定编程语言"""
        return language.lower() in self.supported_languages
