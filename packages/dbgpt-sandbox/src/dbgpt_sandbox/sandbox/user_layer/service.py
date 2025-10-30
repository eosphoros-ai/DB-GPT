import logging
from typing import Any, Dict, List

from fastapi import APIRouter, FastAPI
from pydantic import BaseModel

from ..control_layer.control_layer import ControlLayer
from .schemas import TaskObject

logger = logging.getLogger(__name__)

# 创建全局路由器
router = APIRouter()

# 全局用户层实例
user_layer_instance = None


def get_user_layer() -> "UserLayer":
    """获取用户层实例"""
    global user_layer_instance
    if user_layer_instance is None:
        user_layer_instance = UserLayer()
    return user_layer_instance


class UserLayer:
    """用户层：处理用户请求和会话管理"""

    def __init__(self):
        self.control = ControlLayer()
        self.active_sessions: Dict[str, str] = {}  # session_id -> task_id

    async def connect(
        self, user_id: str, task_id: str, image_type: str
    ) -> Dict[str, Any]:
        session_id = f"{user_id}_{task_id}"
        task = TaskObject(
            task_type="connect",
            user_id=user_id,
            task_id=task_id,
            session_id=session_id,
            language=image_type,
        )
        result = await self.control.handle_task(task)
        self.active_sessions[session_id] = task_id
        return {
            "status": result.status,
            "output": getattr(result, "output", None),
            "error": getattr(result, "error", None),
        }

    async def configure_environment(
        self, user_id: str, task_id: str, config_info: Dict
    ) -> Dict[str, Any]:
        session_id = f"{user_id}_{task_id}"
        task = TaskObject(
            task_type="configure",
            user_id=user_id,
            task_id=task_id,
            session_id=session_id,
            language=config_info.get("language", "python"),
            config=config_info,
        )
        result = await self.control.handle_task(task)
        return {
            "status": result.status,
            "output": getattr(result, "output", None),
            "error": getattr(result, "error", None),
        }

    async def disconnect(self, user_id: str, task_id: str) -> Dict[str, Any]:
        session_id = f"{user_id}_{task_id}"
        task = TaskObject(
            task_type="disconnect",
            user_id=user_id,
            task_id=task_id,
            session_id=session_id,
            language="unknown",
        )
        result = await self.control.handle_task(task)
        self.active_sessions.pop(session_id, None)
        return {
            "status": result.status,
            "output": getattr(result, "output", None),
            "error": getattr(result, "error", None),
        }

    async def execute_code(
        self, session_id: str, code_type: str, code_content: str
    ) -> Dict[str, Any]:
        task_id = self.active_sessions.get(session_id, f"{session_id}_auto")
        task = TaskObject(
            task_type="execute",
            user_id="user",
            task_id=task_id,
            session_id=session_id,
            language=code_type,
            code_content=code_content,
        )
        result = await self.control.handle_task(task)
        return {
            "status": result.status,
            "output": getattr(result, "output", None),
            "error": getattr(result, "error", None),
        }

    async def get_file(self, session_id: str, filename: str) -> Dict[str, Any]:
        task_id = self.active_sessions.get(session_id, f"{session_id}_auto")
        task = TaskObject(
            task_type="get_file",
            user_id="user",
            task_id=task_id,
            session_id=session_id,
            language="python",
            file_name=filename,
        )
        result = await self.control.handle_task(task)
        return {
            "status": result.status,
            "output": getattr(result, "output", None),
            "error": getattr(result, "error", None),
        }

    async def manual_operation(self, session_id: str, action: str) -> Dict[str, Any]:
        task_id = self.active_sessions.get(session_id, f"{session_id}_auto")
        task = TaskObject(
            task_type="manual",
            user_id="user",
            task_id=task_id,
            session_id=session_id,
            language="python",
            manual_action=action,
        )
        result = await self.control.handle_task(task)
        return {
            "status": result.status,
            "output": getattr(result, "output", None),
            "error": getattr(result, "error", None),
        }

    async def get_execution_status(self, session_id: str) -> Dict[str, Any]:
        task_id = self.active_sessions.get(session_id, f"{session_id}_auto")
        task = TaskObject(
            task_type="status",
            user_id="user",
            task_id=task_id,
            session_id=session_id,
            language="python",
        )
        result = await self.control.handle_task(task)
        return {
            "status": result.status,
            "output": getattr(result, "output", None),
            "error": getattr(result, "error", None),
        }

    async def list_sessions(self) -> List[str]:
        return await self.control.runtime.list_sessions()

    def get_available_methods(self) -> List[Dict[str, str]]:
        return [
            {"path": "/api/connect", "method": "POST", "description": "建立沙箱会话"},
            {"path": "/api/configure", "method": "POST", "description": "配置沙箱环境"},
            {
                "path": "/api/disconnect",
                "method": "POST",
                "description": "断开并销毁沙箱会话",
            },
            {"path": "/api/execute", "method": "POST", "description": "执行代码"},
            {
                "path": "/api/manual",
                "method": "POST",
                "description": "进入手动操作模式",
            },
            {
                "path": "/api/status",
                "method": "POST",
                "description": "获取任务/会话状态",
            },
            {
                "path": "/api/sessions",
                "method": "GET",
                "description": "列出所有活跃会话",
            },
            {
                "path": "/api/get_file",
                "method": "POST",
                "description": "获取沙箱内指定文件内容",
            },
            {
                "path": "/api/methods",
                "method": "GET",
                "description": "获取所有可用接口和方法",
            },
        ]


# -------------------- API 请求模型 --------------------
class ConnectRequest(BaseModel):
    user_id: str
    task_id: str
    image_type: str


class ConfigureRequest(BaseModel):
    user_id: str
    task_id: str
    config_info: Dict


class DisconnectRequest(BaseModel):
    user_id: str
    task_id: str


class ExecuteRequest(BaseModel):
    session_id: str
    code_type: str
    code_content: str


class ManualOperationRequest(BaseModel):
    session_id: str
    action: str


class StatusRequest(BaseModel):
    session_id: str


class FileRequest(BaseModel):
    session_id: str
    file_name: str


# -------------------- API 路由 --------------------
@router.get("/health")
async def api_health_check():
    """健康检查 API"""
    return {"status": "ok"}


@router.post("/connect")
async def api_connect(req: ConnectRequest):
    """建立沙箱会话"""
    user_layer = get_user_layer()
    return await user_layer.connect(req.user_id, req.task_id, req.image_type)


@router.post("/configure")
async def api_configure(req: ConfigureRequest):
    """配置沙箱环境"""
    user_layer = get_user_layer()
    return await user_layer.configure_environment(
        req.user_id, req.task_id, req.config_info
    )


@router.post("/disconnect")
async def api_disconnect(req: DisconnectRequest):
    """断开并销毁沙箱会话"""
    user_layer = get_user_layer()
    return await user_layer.disconnect(req.user_id, req.task_id)


@router.post("/execute")
async def api_execute(req: ExecuteRequest):
    """执行代码"""
    user_layer = get_user_layer()
    return await user_layer.execute_code(
        req.session_id, req.code_type, req.code_content
    )


@router.post("/manual")
async def api_manual(req: ManualOperationRequest):
    """进入手动操作模式"""
    user_layer = get_user_layer()
    return await user_layer.manual_operation(req.session_id, req.action)


@router.post("/status")
async def api_status(req: StatusRequest):
    """获取任务/会话状态"""
    user_layer = get_user_layer()
    return await user_layer.get_execution_status(req.session_id)


@router.get("/sessions")
async def api_list_sessions():
    """列出所有活跃会话"""
    user_layer = get_user_layer()
    sessions = await user_layer.list_sessions()
    return {"sessions": sessions}


@router.post("/get_file")
async def api_get_file(req: FileRequest):
    """获取沙箱内指定文件内容"""
    user_layer = get_user_layer()
    return await user_layer.get_file(req.session_id, req.file_name)


@router.get("/methods")
async def api_methods():
    """获取所有可用接口和方法"""
    user_layer = get_user_layer()
    return {"methods": user_layer.get_available_methods()}


def initialize_sandbox(
    app: FastAPI = None,
    host: str = "0.0.0.0",
    port: int = 8000,
    log_level: str = "info",
):
    """初始化沙箱服务

    Args:
        app: FastAPI 应用实例，如果为 None 则创建新实例并运行服务器
        host: 主机地址
        port: 端口号
        log_level: 日志级别
    """
    if app:
        # 将路由注册到现有应用
        app.include_router(router, tags=["Sandbox"])
        logger.info("Sandbox routes registered to existing FastAPI app")
    else:
        # 创建新应用并运行服务器
        import uvicorn
        from fastapi import FastAPI

        app = FastAPI(
            title="DB-GPT Sandbox API",
            description="Secure sandbox execution environment for DB-GPT Agent",
            version="0.7.3",
        )

        # 包含路由
        app.include_router(router, prefix="/api", tags=["Sandbox"])

        # 添加根路径
        @app.get("/")
        async def root():
            return {"message": "DB-GPT Sandbox API is running"}

        logger.info(f"Starting DB-GPT Sandbox server on {host}:{port}")
        uvicorn.run(app, host=host, port=port, log_level=log_level)
