"""
基于 Docker 容器的代码执行环境，支持多语言和状态保持，所有 Docker 操作均异步化。
"""

import asyncio
import base64
import io
import os
import tarfile
import tempfile
import time
from typing import Any, Dict, List, Optional

try:
    import docker
except ImportError:
    docker = None

from ..config import LANGUAGE_IMAGES, get_command_by_language
from ..display_layer.display_layer import DisplayResult
from ..utils_function.logger import print_log
from .base import (
    ExecutionResult,
    ExecutionStatus,
    SandboxRuntime,
    SandboxSession,
    SessionConfig,
)


class DockerSandboxSession(SandboxSession):
    """异步 Docker 沙箱会话实现"""

    def __init__(self, session_id: str, config: SessionConfig, docker_client):
        super().__init__(session_id, config)
        self.docker_client = docker_client
        self.container = None
        self.image_name = self._get_image_name(config.language)

    def _get_image_name(self, language: str) -> str:
        return LANGUAGE_IMAGES.get(language, "python:3.11-slim")

    async def start(self) -> bool:
        """启动 Docker 容器"""
        try:
            container_config = {
                "image": self.image_name,
                "command": "tail -f /dev/null",
                "detach": True,
                "mem_limit": self.config.max_memory,
                "cpuset_cpus": str(self.config.max_cpus),
                "working_dir": self.config.working_dir,
                "environment": self.config.environment_vars,
                "network_disabled": self.config.network_disabled,
                "volumes": {tempfile.gettempdir(): {"bind": "/tmp", "mode": "rw"}},
                "name": f"sandbox_{self.session_id}",
            }

            if self.config.language.endswith("-vnc"):
                container_config["ports"] = {"5900/tcp": None, "6080/tcp": None}
                container_config["command"] = "/startup.sh"
                print_log("INFO", f"使用 VNC/noVNC 容器: {self.image_name}")

            self.container = await asyncio.to_thread(
                self.docker_client.containers.run, **container_config
            )
            self._is_active = True

            # ✅ 确认 startup.sh 存在并有执行权限
            check = self.container.exec_run("ls -l /startup.sh")
            print_log("DEBUG", f"startup.sh 状态: {check.output}")

            # ✅ 查看容器启动日志
            logs = self.container.logs(stdout=True, stderr=True, tail=50)
            print_log("DEBUG", f"容器日志: {logs.decode('utf-8', errors='ignore')}")

            await self._setup_environment()
            return True
        except Exception as e:
            print(f"启动 Docker 容器失败: {e}")
            return False

    async def _setup_environment(self):
        """设置执行环境"""
        if not self.container:
            return

        await asyncio.to_thread(
            self.container.exec_run, f"mkdir -p {self.config.working_dir}"
        )

        if self.config.language.startswith("python"):
            await asyncio.to_thread(
                self.container.exec_run,
                "pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple",
            )
        elif self.config.language.startswith("javascript"):
            await asyncio.to_thread(
                self.container.exec_run, "npm init -y", workdir=self.config.working_dir
            )

    async def stop(self) -> bool:
        """停止并删除容器"""
        try:
            if self.container:
                await asyncio.to_thread(self.container.stop)
                await asyncio.to_thread(self.container.remove)
                self.container = None
            self._is_active = False
            return True
        except Exception as e:
            print(f"停止 Docker 容器失败: {e}")
            return False

    async def install_dependencies(self, dependencies: List[str]) -> ExecutionResult:
        """在容器内安装依赖，支持 python/npm。"""
        if not self.container or not self._is_active:
            return ExecutionResult(
                status=ExecutionStatus.ERROR, error="容器未启动或已停止", exit_code=-1
            )
        if not dependencies:
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS, output="无依赖需要安装", exit_code=0
            )

        try:
            outputs = []
            errors = []
            exit_code = 0

            if self.config.language.startswith("python"):
                for dep in dependencies:
                    res = await asyncio.to_thread(
                        self.container.exec_run,
                        f"pip install --no-input --disable-pip-version-check {dep}",
                    )
                    exit_code = res.exit_code
                    if res.exit_code != 0:
                        errors.append(f"pip install {dep} 失败")
                        break
                    else:
                        outputs.append(f"installed: {dep}")
            elif self.config.language.startswith("javascript"):
                await asyncio.to_thread(
                    self.container.exec_run,
                    "npm init -y",
                    workdir=self.config.working_dir,
                )
                dep_str = " ".join(dependencies)
                res = await asyncio.to_thread(
                    self.container.exec_run,
                    f"npm install {dep_str}",
                    workdir=self.config.working_dir,
                )
                exit_code = res.exit_code
                if res.exit_code != 0:
                    errors.append("npm install 失败")
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

    async def execute(self, code: str, shell=False) -> DisplayResult:
        """在容器中执行代码，并封装 DisplayResult"""
        if not self.container or not self._is_active:
            return DisplayResult(
                status="error",
                output="",
                error="容器未启动或已停止",
                execution_time=0,
                exit_code=-1,
            )

        if shell:
            try:
                self.update_last_accessed()
                start_time = time.time()
                result = self.container.exec_run(
                    code, workdir=self.config.working_dir, demux=True
                )
                execution_time = time.time() - start_time

                stdout, stderr = result.output
                output_text = stdout.decode("utf-8") if stdout else ""
                error_text = stderr.decode("utf-8") if stderr else ""

                return DisplayResult(
                    status="success" if result.exit_code == 0 else "error",
                    output=output_text,
                    error=error_text,
                    execution_time=execution_time,
                    exit_code=result.exit_code,
                    files=[],
                )
            except Exception as e:
                return DisplayResult(
                    status="error",
                    output="",
                    error=f"执行失败: {str(e)}",
                    execution_time=0,
                    exit_code=-1,
                )

        self.update_last_accessed()
        code_file = self._create_code_file(code)
        tar_data = self._create_tar_from_file(code_file)

        self.container.put_archive(self.config.working_dir, tar_data)

        try:
            exec_command = self._get_exec_command(os.path.basename(code_file))
            start_time = time.time()
            result = self.container.exec_run(
                exec_command, workdir=self.config.working_dir, demux=True
            )

            execution_time = time.time() - start_time

            stdout, stderr = result.output
            output_text = stdout.decode("utf-8") if stdout else ""
            error_text = stderr.decode("utf-8") if stderr else ""

            return DisplayResult(
                status="success" if result.exit_code == 0 else "error",
                output=output_text,
                error=error_text,
                execution_time=execution_time,
                exit_code=result.exit_code,
                files=[os.path.basename(code_file)],
            )
        except Exception as e:
            return DisplayResult(
                status="error",
                output="",
                error=f"执行失败: {str(e)}",
                execution_time=0,
                exit_code=-1,
            )
        finally:
            if "code_file" in locals():
                os.unlink(code_file)

    async def get_file_content(self, filename: str) -> Optional[DisplayResult]:
        """从容器内获取文件内容"""
        if not self.container or not self._is_active:
            return None

        file_path = os.path.join(self.config.working_dir, filename)

        check = self.container.exec_run(f"test -f {file_path}")
        if check.exit_code != 0:
            return DisplayResult(
                status="error",
                output="",
                error=f"文件不存在: {filename}",
                execution_time=0,
                exit_code=-1,
            )

        try:
            bits, stat = self.container.get_archive(file_path)
            file_data = io.BytesIO()
            for chunk in bits:
                file_data.write(chunk)
            file_data.seek(0)

            with tarfile.open(fileobj=file_data) as tar:
                basename = os.path.basename(filename)

                member = next((m for m in tar.getmembers() if m.name == basename), None)

                if not member:
                    member = next(
                        (m for m in tar.getmembers() if m.name.endswith(basename)), None
                    )

                if not member:
                    raise FileNotFoundError(
                        f"{filename} 不在中: {[m.name for m in tar.getmembers()]}"
                    )

                extracted = tar.extractfile(member)
                content_bytes = extracted.read()
                # 统一转成 base64 字符串
                file_content = base64.b64encode(content_bytes).decode("utf-8")

            return DisplayResult(
                status="success",
                output=file_content,
                error="",
                execution_time=0,
                exit_code=0,
                files=[filename],
            )

        except Exception as e:
            return DisplayResult(
                status="error",
                output="",
                error=f"获取文件失败: {str(e)}",
                execution_time=0,
                exit_code=-1,
            )

    def _create_tar_from_file(self, filepath: str) -> bytes:
        tar_stream = io.BytesIO()
        filename = os.path.basename(filepath)

        with tarfile.open(fileobj=tar_stream, mode="w") as tar:
            with open(filepath, "rb") as f:
                file_data = f.read()
                tarinfo = tarfile.TarInfo(name=filename)
                tarinfo.size = len(file_data)
                tar.addfile(tarinfo=tarinfo, fileobj=io.BytesIO(file_data))

        tar_stream.seek(0)
        return tar_stream.read()

    def _create_code_file(self, code: str) -> str:
        extensions = {
            "python": ".py",
            "javascript": ".js",
            "java": ".java",
            "cpp": ".cpp",
            "go": ".go",
            "rust": ".rs",
            "python-vnc": ".py",
        }
        ext = extensions.get(self.config.language, ".txt")
        timestamp = int(time.time() * 1000)
        filename = f"{self.session_id}_{timestamp}{ext}"
        file_path = os.path.join(tempfile.gettempdir(), filename)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(code)
        return file_path

    def _get_exec_command(self, filename: str) -> str:
        return get_command_by_language(self.config.language, filename)

    async def get_status(self) -> Dict[str, Any]:
        """获取容器状态"""
        if not self.container:
            return {"status": "stopped"}

        try:
            await asyncio.to_thread(self.container.reload)
            stats = await asyncio.to_thread(self.container.stats, stream=False)
            return {
                "status": self.container.status,
                "created_at": self.created_at,
                "last_accessed": self.last_accessed,
                "memory_usage": stats.get("memory", {}).get("usage", 0),
                "cpu_usage": stats.get("cpu_stats", {})
                .get("cpu_usage", {})
                .get("total_usage", 0),
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}


class DockerRuntime(SandboxRuntime):
    """异步 Docker 沙箱运行时管理"""

    def __init__(self, runtime_id: str = "docker"):
        super().__init__(runtime_id)
        self.docker_client = docker.from_env()
        self.supported_languages = list(LANGUAGE_IMAGES.keys())

    async def create_session(
        self, session_id: str, config: SessionConfig
    ) -> SandboxSession:
        if session_id in self.sessions:
            raise ValueError(f"会话 {session_id} 已存在")

        session = DockerSandboxSession(session_id, config, self.docker_client)

        if await session.start():
            self.sessions[session_id] = session
            return session
        else:
            raise RuntimeError(f"启动会话 {session_id} 失败")

    async def destroy_session(self, session_id: str) -> bool:
        if session_id not in self.sessions:
            return False

        session = self.sessions[session_id]
        asyncio.create_task(session.stop())
        del self.sessions[session_id]
        success = True

        return success

    async def list_sessions(self) -> List[str]:
        return list(self.sessions.keys())

    async def get_session(self, session_id: str) -> Optional[SandboxSession]:
        return self.sessions.get(session_id)

    async def cleanup_expired_sessions(self, max_idle_time: int = 3600) -> int:
        current_time = time.time()
        expired_sessions = [
            sid
            for sid, sess in self.sessions.items()
            if current_time - sess.last_accessed > max_idle_time
        ]

        cleanup_count = 0
        for sid in expired_sessions:
            if await self.destroy_session(sid):
                cleanup_count += 1
        return cleanup_count

    async def health_check(self) -> Dict[str, Any]:
        try:
            info = await asyncio.to_thread(self.docker_client.info)
            return {
                "status": "healthy",
                "docker_version": info.get("ServerVersion", "unknown"),
                "containers_running": info.get("ContainersRunning", 0),
                "active_sessions": len(self.sessions),
                "supported_languages": self.supported_languages,
            }
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}

    async def get_vnc_info(self) -> Dict[str, Any]:
        if not self.container:
            return {}
        await asyncio.to_thread(self.container.reload)
        ports = self.container.attrs["NetworkSettings"]["Ports"]
        return {
            "vnc_port": ports.get("5900/tcp", [{"HostPort": "5900"}])[0]["HostPort"],
            "novnc_port": ports.get("6080/tcp", [{"HostPort": "6080"}])[0]["HostPort"],
        }

    def supports_language(self, language: str) -> bool:
        return language.lower() in self.supported_languages
