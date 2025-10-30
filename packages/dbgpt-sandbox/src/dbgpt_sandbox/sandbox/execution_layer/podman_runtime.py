"""
基于 Podman 容器的代码执行环境，支持多语言和状态保持
"""

import asyncio
import contextlib
import os
import tempfile
import time
from typing import Any, Dict, List, Optional, Tuple

from ..display_layer.display_layer import DisplayResult
from ..utils_function.logger import print_log
from .base import (
    ExecutionResult,
    ExecutionStatus,
    SandboxRuntime,
    SandboxSession,
    SessionConfig,
)


async def _run_cmd(
    cmd: List[str], timeout: Optional[int] = None, cwd: Optional[str] = None
) -> Tuple[int, str, str]:
    """以异步方式运行命令并返回 (code, stdout, stderr)"""
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=cwd,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        with contextlib.suppress(ProcessLookupError):
            proc.kill()
        raise
    return (
        proc.returncode,
        stdout.decode(errors="replace"),
        stderr.decode(errors="replace"),
    )


class PodmanSandboxSession(SandboxSession):
    """异步 Podman 沙箱会话实现"""

    def __init__(self, session_id: str, config: SessionConfig):
        super().__init__(session_id, config)
        self.container_name = f"sandbox_{self.session_id}"
        self.image_name = self._get_image_name(config.language)

    def _get_image_name(self, language: str) -> str:
        language_images = {
            "python": "docker.io/library/python:3.11-slim",
            "python-vnc": "vnc-gui-browser:latest",
            "javascript": "docker.io/library/node:18-slim",
            "java": "docker.io/library/openjdk:11-jre-slim",
            "cpp": "docker.io/library/gcc:latest",
            "go": "docker.io/library/golang:1.21-alpine",
            "rust": "docker.io/library/rust:1.75-slim",
        }
        return language_images.get(language, "docker.io/library/python:3.11-slim")

    async def start(self) -> bool:
        """启动 Podman 容器"""
        try:
            args = [
                "podman",
                "run",
                "-d",
                "--name",
                self.container_name,
                "--memory",
                str(self.config.max_memory),
            ]

            # CPU 限制
            if getattr(self.config, "max_cpus", None):
                args += ["--cpus", str(self.config.max_cpus)]

            # 网络
            if getattr(self.config, "network_disabled", False):
                args += ["--network", "none"]

            # 工作目录
            if getattr(self.config, "working_dir", None):
                args += ["-w", self.config.working_dir]

            # 环境变量
            for k, v in (self.config.environment_vars or {}).items():
                args += ["-e", f"{k}={v}"]

            # 挂载临时目录
            args += ["-v", f"{tempfile.gettempdir()}:/tmp:rw"]

            # VNC GUI 容器端口映射
            is_vnc = str(self.config.language).endswith("-vnc")
            if is_vnc:
                # 简化处理：固定映射 5900, 6080 端口。若端口占用将启动失败。
                args += ["-p", "5900:5900", "-p", "6080:6080"]

            # 镜像和命令
            if is_vnc:
                args += [self.image_name, "sh", "-lc", "/startup.sh"]
            else:
                args += [self.image_name, "sh", "-lc", "tail -f /dev/null"]

            code, out, err = await _run_cmd(args, timeout=60)
            if code != 0:
                print_log("ERROR", f"Podman 启动失败: {err.strip()}")
                return False

            self._is_active = True
            # 拉起后创建工作目录，以防镜像中不存在
            if getattr(self.config, "working_dir", None):
                await _run_cmd(
                    [
                        "podman",
                        "exec",
                        "-w",
                        "/",
                        self.container_name,
                        "sh",
                        "-lc",
                        f"mkdir -p {self.config.working_dir}",
                    ],
                    timeout=30,
                )
            return True
        except Exception as e:
            print_log("ERROR", f"启动 Podman 容器失败: {e}")
            return False

    async def stop(self) -> bool:
        try:
            await _run_cmd(["podman", "stop", self.container_name], timeout=30)
            await _run_cmd(["podman", "rm", self.container_name], timeout=30)
            self._is_active = False
            return True
        except Exception as e:
            print_log("ERROR", f"停止 Podman 容器失败: {e}")
            return False

    def _create_code_file(self, code: str) -> str:
        extensions = {
            "python": ".py",
            "python-vnc": ".py",
            "javascript": ".js",
            "java": ".java",
            "cpp": ".cpp",
            "go": ".go",
            "rust": ".rs",
            "bash": ".sh",
        }
        ext = extensions.get(self.config.language, ".txt")
        filename = f"{self.session_id}_{int(time.time() * 1000)}{ext}"
        path = os.path.join(tempfile.gettempdir(), filename)
        with open(path, "w", encoding="utf-8") as f:
            f.write(code)
        return path

    def _get_exec_command(self, filename: str) -> str:
        cmds = {
            "python-vnc": f"python3 {filename}",
            "python": f"python {filename}",
            "javascript": f"node {filename}",
            "java": f"javac {filename} && java {filename[:-5]}",
            "cpp": f"g++ -o program {filename} && ./program",
            "go": f"go run {filename}",
            "rust": f"rustc {filename} -o program && ./program",
            "bash": f"sh {filename}",
        }
        return cmds.get(self.config.language, f"cat {filename}")

    async def install_dependencies(self, dependencies: List[str]) -> ExecutionResult:
        """通过 podman exec 安装 pip/npm 依赖。"""
        if not self._is_active:
            return ExecutionResult(
                status=ExecutionStatus.ERROR, error="容器未启动", exit_code=-1
            )
        if not dependencies:
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS, output="无依赖需要安装", exit_code=0
            )

        try:
            outputs: List[str] = []
            errors: List[str] = []
            exit_code = 0
            workdir = self.config.working_dir or "/workspace"

            if self.config.language.startswith("python"):
                for dep in dependencies:
                    code, out, err = await _run_cmd(
                        [
                            "podman",
                            "exec",
                            self.container_name,
                            "sh",
                            "-lc",
                            f"pip install --no-input --disable-pip-version-check {dep}",
                        ],
                        timeout=300,
                    )
                    exit_code = code
                    if code != 0:
                        errors.append(f"pip install {dep} 失败: {err.strip()}")
                        break
                    outputs.append(f"installed: {dep}")
            elif self.config.language == "javascript":
                # 确保初始化
                await _run_cmd(
                    [
                        "podman",
                        "exec",
                        "-w",
                        workdir,
                        self.container_name,
                        "sh",
                        "-lc",
                        "npm init -y",
                    ],
                    timeout=120,
                )
                dep_str = " ".join(dependencies)
                code, out, err = await _run_cmd(
                    [
                        "podman",
                        "exec",
                        "-w",
                        workdir,
                        self.container_name,
                        "sh",
                        "-lc",
                        f"npm install {dep_str}",
                    ],
                    timeout=600,
                )
                exit_code = code
                if code != 0:
                    errors.append(f"npm install 失败: {err.strip()}")
                else:
                    outputs.append(f"installed: {dep_str}")
            else:
                return ExecutionResult(
                    status=ExecutionStatus.ERROR,
                    error=f"不支持的依赖安装语言: {self.config.language}",
                    exit_code=1,
                )

            if errors:
                return ExecutionResult(
                    status=ExecutionStatus.ERROR,
                    output="\n".join(outputs),
                    error="\n".join(errors),
                    exit_code=exit_code,
                )
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                output="\n".join(outputs) or "安装完成",
                exit_code=0,
            )
        except Exception as e:
            return ExecutionResult(
                status=ExecutionStatus.ERROR, error=f"依赖安装异常: {e}", exit_code=1
            )

    async def execute(self, code: str) -> DisplayResult:
        if not self._is_active:
            return DisplayResult(
                status="error",
                output="",
                error="容器未启动",
                execution_time=0,
                exit_code=-1,
            )

        # GUI 容器：直接提示已启动并返回访问 URL
        if str(self.config.language).endswith("-vnc"):
            return DisplayResult(
                status="success",
                output="GUI容器已启动",
                error="",
                execution_time=0,
                exit_code=0,
                files=[],
                gui_url="http://localhost:6080/vnc.html",
            )

        self.update_last_accessed()
        code_file = self._create_code_file(code)
        try:
            # 拷贝代码到容器
            workdir = self.config.working_dir or "/workspace"
            code_basename = os.path.basename(code_file)
            code_in_container = f"{workdir}/{code_basename}"

            cp_code, _, cp_err = await _run_cmd(
                [
                    "podman",
                    "cp",
                    code_file,
                    f"{self.container_name}:{code_in_container}",
                ],
                timeout=30,
            )
            if cp_code != 0:
                return DisplayResult(
                    status="error",
                    output="",
                    error=f"拷贝文件失败: {cp_err}",
                    execution_time=0,
                    exit_code=-1,
                )

            # 执行命令
            exec_cmd = self._get_exec_command(code_basename)
            start = time.time()
            code, out, err = await _run_cmd(
                [
                    "podman",
                    "exec",
                    "-w",
                    workdir,
                    self.container_name,
                    "sh",
                    "-lc",
                    exec_cmd,
                ],
                timeout=self.config.timeout,
            )
            duration = time.time() - start

            return DisplayResult(
                status="success" if code == 0 else "error",
                output=out,
                error=err,
                execution_time=duration,
                exit_code=code,
                files=[code_basename],
            )
        except asyncio.TimeoutError:
            return DisplayResult(
                status="error",
                output="",
                error=f"执行超时({self.config.timeout}s)",
                execution_time=self.config.timeout,
                exit_code=124,
            )
        except Exception as e:
            return DisplayResult(
                status="error",
                output="",
                error=f"执行失败: {e}",
                execution_time=0,
                exit_code=-1,
            )
        finally:
            with contextlib.suppress(Exception):
                os.unlink(code_file)

    async def get_status(self) -> Dict[str, Any]:
        if not self._is_active:
            return {"status": "stopped"}
        try:
            # podman inspect 读取状态
            code, out, err = await _run_cmd(
                ["podman", "inspect", self.container_name, "--format", "json"],
                timeout=15,
            )
            if code != 0:
                return {"status": "error", "error": err.strip()}
            return {
                "status": "running",
                "raw": out,
                "created_at": self.created_at,
                "last_accessed": self.last_accessed,
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}


class PodmanRuntime(SandboxRuntime):
    """异步 Podman 沙箱运行时管理"""

    def __init__(self, runtime_id: str = "podman"):
        super().__init__(runtime_id)
        self.supported_languages = [
            "python",
            "python-vnc",
            "javascript",
            "java",
            "cpp",
            "go",
            "rust",
            "bash",
        ]

    async def create_session(
        self, session_id: str, config: SessionConfig
    ) -> SandboxSession:
        if session_id in self.sessions:
            raise ValueError(f"会话 {session_id} 已存在")
        sess = PodmanSandboxSession(session_id, config)
        ok = await sess.start()
        if not ok:
            raise RuntimeError(f"启动会话 {session_id} 失败")
        self.sessions[session_id] = sess
        return sess

    async def destroy_session(self, session_id: str) -> bool:
        sess = self.sessions.get(session_id)
        if not sess:
            return False
        asyncio.create_task(sess.stop())
        del self.sessions[session_id]
        return True

    async def list_sessions(self) -> List[str]:
        return list(self.sessions.keys())

    async def get_session(self, session_id: str) -> Optional[SandboxSession]:
        return self.sessions.get(session_id)

    async def cleanup_expired_sessions(self, max_idle_time: int = 3600) -> int:
        now = time.time()
        expired = [
            sid
            for sid, s in self.sessions.items()
            if now - s.last_accessed > max_idle_time
        ]
        for sid in expired:
            await self.destroy_session(sid)
        return len(expired)

    async def health_check(self) -> Dict[str, Any]:
        try:
            code, out, err = await _run_cmd(["podman", "version"], timeout=10)
            if code == 0:
                return {"status": "healthy", "version": out}
            return {"status": "unhealthy", "error": err}
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}

    def supports_language(self, language: str) -> bool:
        return language.lower() in self.supported_languages
