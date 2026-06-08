"""Pydantic schemas for the scheduled task REST API."""

from typing import Any, Dict, Optional

from dbgpt._private.pydantic import BaseModel, ConfigDict, Field


class ChatReplayPayload(BaseModel):
    """冻结的对话快照,定时执行时用于回放对话。"""

    model_config = ConfigDict(protected_namespaces=())

    version: int = Field(default=1, description="Payload schema version")
    user_input: str = Field(..., description="用户原始问题")
    chat_mode: str = Field(default="chat_react_agent", description="对话模式")
    model_name: Optional[str] = Field(default=None, description="LLM 模型名")
    select_param: Optional[str] = Field(default="", description="场景选择参数")
    temperature: Optional[float] = Field(default=None)
    max_new_tokens: Optional[int] = Field(default=None)
    ext_info: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="扩展信息,含 skill_id / connector_ids / mcp_ids 等",
    )


class CreateTaskRequest(BaseModel):
    """创建定时任务请求。"""

    task_name: str = Field(..., description="任务名称")
    description: Optional[str] = Field(default=None, description="任务描述")
    cron_expression: str = Field(..., description="cron 表达式")
    payload: ChatReplayPayload = Field(..., description="对话快照")
    creator_name: Optional[str] = Field(
        default=None, description="创建人显示名称(优先于鉴权 user_id)"
    )


class UpdateTaskRequest(BaseModel):
    """更新定时任务请求(部分字段可选)。"""

    # protected_namespaces=() — silence pydantic v2's warning about the
    # ``model_name`` field colliding with the protected ``model_`` prefix.
    model_config = ConfigDict(protected_namespaces=())

    task_name: Optional[str] = Field(default=None)
    description: Optional[str] = Field(default=None)
    cron_expression: Optional[str] = Field(default=None)
    # payload-level fields — merged into the frozen ChatReplayPayload on update
    # (only these two are user-editable post-creation; other payload fields are
    # preserved as-is). See ScheduledTaskService.update_task.
    user_input: Optional[str] = Field(default=None, description="原始问题")
    model_name: Optional[str] = Field(default=None, description="执行模型")


class ToggleTaskRequest(BaseModel):
    """启用/暂停任务请求。"""

    enabled: bool = Field(..., description="是否启用")


class TaskResponse(BaseModel):
    """定时任务响应。"""

    model_config = ConfigDict(protected_namespaces=())

    task_id: str
    task_name: str
    description: Optional[str] = None
    task_type: str = "chat_replay"
    cron_expression: str
    payload: Optional[ChatReplayPayload] = None
    enabled: bool = True
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    user_name: Optional[str] = None
    sys_code: Optional[str] = None
    next_run_time: Optional[str] = None


class RunResponse(BaseModel):
    """单次执行历史响应。"""

    run_id: str
    task_id: str
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    status: str
    result_summary: Optional[str] = None
    error_message: Optional[str] = None
    output_conv_uid: Optional[str] = None
