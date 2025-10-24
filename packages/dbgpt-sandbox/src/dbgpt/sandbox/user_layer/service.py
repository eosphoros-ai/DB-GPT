from typing import Any, Dict, List

from control_layer.control_layer import ControlLayer
from fastapi import FastAPI
from pydantic import BaseModel
from user_layer.schemas import TaskObject


# -------------------- 用户层 --------------------
class UserLayer:
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
            {"path": "/connect", "method": "POST", "description": "建立沙箱会话"},
            {"path": "/configure", "method": "POST", "description": "配置沙箱环境"},
            {
                "path": "/disconnect",
                "method": "POST",
                "description": "断开并销毁沙箱会话",
            },
            {"path": "/execute", "method": "POST", "description": "执行代码"},
            {"path": "/manual", "method": "POST", "description": "进入手动操作模式"},
            {"path": "/status", "method": "POST", "description": "获取任务/会话状态"},
            {"path": "/sessions", "method": "GET", "description": "列出所有活跃会话"},
            {
                "path": "/get_file",
                "method": "POST",
                "description": "获取沙箱内指定文件内容",
            },
            {
                "path": "/methods",
                "method": "GET",
                "description": "获取所有可用接口和方法",
            },
        ]


app = FastAPI(title="Sandbox User API, by dbgpt")
user_layer = UserLayer()


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
@app.post("/connect")
async def api_connect(req: ConnectRequest):
    return await user_layer.connect(req.user_id, req.task_id, req.image_type)


@app.post("/configure")
async def api_configure(req: ConfigureRequest):
    return await user_layer.configure_environment(
        req.user_id, req.task_id, req.config_info
    )


@app.post("/disconnect")
async def api_disconnect(req: DisconnectRequest):
    return await user_layer.disconnect(req.user_id, req.task_id)


@app.post("/execute")
async def api_execute(req: ExecuteRequest):
    return await user_layer.execute_code(
        req.session_id, req.code_type, req.code_content
    )


@app.post("/manual")
async def api_manual(req: ManualOperationRequest):
    return await user_layer.manual_operation(req.session_id, req.action)


@app.post("/status")
async def api_status(req: StatusRequest):
    return await user_layer.get_execution_status(req.session_id)


@app.get("/sessions")
async def api_list_sessions():
    sessions = await user_layer.list_sessions()
    return {"sessions": sessions}


@app.post("/get_file")
async def api_get_file(req: FileRequest):
    return await user_layer.get_file(req.session_id, req.file_name)


@app.get("/methods")
async def api_methods():
    routes = []
    for route in app.routes:
        if hasattr(route, "methods"):
            methods = ",".join(route.methods)
            routes.append({"path": route.path, "methods": methods})
    return {"available_endpoints": routes}
