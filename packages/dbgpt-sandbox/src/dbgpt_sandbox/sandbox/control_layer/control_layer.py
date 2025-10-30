"""
控制层：管理任务生命周期和执行，支持 TaskObject 的多类型任务
"""

import asyncio
import uuid
from typing import Any, Dict

from ..config import WORKING_DIR
from ..execution_layer.base import ExecutionResult, ExecutionStatus, SessionConfig
from ..execution_layer.runtime_factory import RuntimeFactory
from ..user_layer.schemas import TASK_TYPES, TaskObject


class ControlLayer:
    """控制层：管理任务生命周期和执行"""

    def __init__(self):
        self.runtime = RuntimeFactory.create()
        self.tasks: Dict[str, Dict[str, Any]] = {}
        self.task_locks: Dict[str, asyncio.Lock] = {}

    async def handle_task(self, task: TaskObject) -> ExecutionResult:
        """根据 TaskObject 的 task_type 分发处理"""
        if task.task_type not in TASK_TYPES:
            return ExecutionResult(
                status=ExecutionStatus.ERROR, error=f"未知任务类型: {task.task_type}"
            )

        handler_map = {
            "connect": self._handle_connect,
            "configure": self._handle_configure,
            "execute": self._handle_execute,
            "manual": self._handle_manual,
            "disconnect": self._handle_disconnect,
            "status": self._handle_status,
            "list": self._handle_list,
            "get_file": self._handle_get_file,
        }

        handler = handler_map[task.task_type]

        lock = self.task_locks.setdefault(task.task_id, asyncio.Lock())
        async with lock:
            return await handler(task)

    async def _handle_connect(self, task: TaskObject) -> ExecutionResult:
        """创建新的沙箱会话"""
        session_id = task.session_id or str(uuid.uuid4())
        config = SessionConfig(
            language=task.language,
            working_dir=WORKING_DIR,
            max_memory=512 * 1024 * 1024,  # 512MB in bytes
            max_cpus=task.config.get("max_cpus", 1),
            environment_vars=task.config.get("env", {}),
            network_disabled=task.config.get("network_disabled", False),
        )

        try:
            session = await self.runtime.create_session(session_id, config)
            self.tasks[task.task_id] = {
                "task": task,
                "session_id": session.session_id,
                "status": "connected",
            }
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                output=f"session {session.session_id} connected",
            )
        except Exception as e:
            return ExecutionResult(status=ExecutionStatus.ERROR, error=f"连接失败: {e}")

    async def _handle_configure(self, task: TaskObject) -> ExecutionResult:
        """配置沙箱环境，例如安装依赖"""
        if task.task_id not in self.tasks:
            return ExecutionResult(status=ExecutionStatus.ERROR, error="任务不存在")

        session_id = self.tasks[task.task_id]["session_id"]
        session = await self.runtime.get_session(session_id)
        if not session:
            return ExecutionResult(status=ExecutionStatus.ERROR, error="会话不存在")

        deps = task.config.get("dependencies", [])
        try:
            if not deps:
                self.tasks[task.task_id]["status"] = "configured"
                return ExecutionResult(
                    status=ExecutionStatus.SUCCESS, output="无依赖需要安装"
                )
            result = await session.install_dependencies(deps)
            self.tasks[task.task_id]["status"] = (
                "configured" if result.status == ExecutionStatus.SUCCESS else "failed"
            )
            return result
        except Exception as e:
            return ExecutionResult(status=ExecutionStatus.ERROR, error=f"配置失败: {e}")

    async def _handle_execute(self, task: TaskObject) -> ExecutionResult:
        """在沙箱中执行代码"""
        if task.task_id not in self.tasks:
            return ExecutionResult(status=ExecutionStatus.ERROR, error="任务不存在")

        session_id = self.tasks[task.task_id]["session_id"]
        session = await self.runtime.get_session(session_id)
        if not session:
            return ExecutionResult(status=ExecutionStatus.ERROR, error="会话不存在")

        try:
            if task.language == "shell":
                result = await session.execute(task.code_content or "", shell=True)
            else:
                result = await session.execute(task.code_content or "")
            self.tasks[task.task_id]["status"] = (
                "finished" if result.status == ExecutionStatus.SUCCESS else "failed"
            )
            self.tasks[task.task_id]["result"] = result
            return result
        except Exception as e:
            return ExecutionResult(status=ExecutionStatus.ERROR, error=f"执行失败: {e}")

    async def _handle_manual(self, task: TaskObject) -> ExecutionResult:
        """进入手动操作模式（返回可连接的 URL 或 token）"""
        if task.task_id not in self.tasks:
            return ExecutionResult(status=ExecutionStatus.ERROR, error="任务不存在")
        session_id = self.tasks[task.task_id]["session_id"]
        manual_url = f"http://sandbox-gui/{session_id}"
        self.tasks[task.task_id]["status"] = "manual"
        return ExecutionResult(status=ExecutionStatus.SUCCESS, output=manual_url)

    async def _handle_disconnect(self, task: TaskObject) -> ExecutionResult:
        """停止并销毁沙箱会话"""
        if task.task_id not in self.tasks:
            return ExecutionResult(status=ExecutionStatus.ERROR, error="任务不存在")

        session_id = self.tasks[task.task_id]["session_id"]
        success = await self.runtime.destroy_session(session_id)
        self.tasks[task.task_id]["status"] = "stopped" if success else "error"
        return ExecutionResult(
            status=ExecutionStatus.SUCCESS if success else ExecutionStatus.ERROR,
            output="会话已销毁" if success else "会话销毁失败",
        )

    async def _handle_status(self, task: TaskObject) -> ExecutionResult:
        """获取任务/会话状态"""
        if task.task_id not in self.tasks:
            return ExecutionResult(status=ExecutionStatus.ERROR, error="任务不存在")

        session_id = self.tasks[task.task_id]["session_id"]
        session = await self.runtime.get_session(session_id)
        if not session:
            return ExecutionResult(status=ExecutionStatus.ERROR, error="会话不存在")

        status = await session.get_status()
        return ExecutionResult(status=ExecutionStatus.SUCCESS, output=str(status))

    async def _handle_list(self, task: TaskObject) -> ExecutionResult:
        """列出所有活跃会话"""
        sessions = await self.runtime.list_sessions()
        return ExecutionResult(status=ExecutionStatus.SUCCESS, output=str(sessions))

    async def _handle_get_file(self, task: TaskObject) -> ExecutionResult:
        """获取沙箱内指定文件内容"""
        if task.task_id not in self.tasks:
            return ExecutionResult(status=ExecutionStatus.ERROR, error="任务不存在")

        session_id = self.tasks[task.task_id]["session_id"]
        session = await self.runtime.get_session(session_id)
        if not session:
            return ExecutionResult(status=ExecutionStatus.ERROR, error="会话不存在")

        filename = task.file_name

        if not filename:
            return ExecutionResult(status=ExecutionStatus.ERROR, error="未指定文件名")

        try:
            content = await session.get_file_content(filename)
            return ExecutionResult(status=ExecutionStatus.SUCCESS, output=content)
        except Exception as e:
            return ExecutionResult(
                status=ExecutionStatus.ERROR, error=f"获取文件失败: {e}"
            )
