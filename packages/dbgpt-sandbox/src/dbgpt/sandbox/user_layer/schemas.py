from typing import Any, Dict, Optional

TASK_TYPES = [
    "connect",
    "configure",
    "execute",
    "manual",
    "disconnect",
    "status",
    "list",
    "get_file",
]


# -------------------- TaskObject 封装 --------------------
class TaskObject:
    """封装用户任务信息"""

    def __init__(
        self,
        task_type: str,
        user_id: str,
        task_id: str,
        session_id: str,
        language: str,
        code_content: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
        manual_action: Optional[str] = None,
        file_name: Optional[str] = None,
    ):
        self.task_type = task_type
        if task_type not in TASK_TYPES:
            raise ValueError(f"Invalid task_type: {task_type}")
        self.user_id = user_id
        self.task_id = task_id
        self.session_id = session_id
        self.language = language
        self.code_content = code_content
        self.config = config or {}
        self.manual_action = manual_action
        self.file_name = file_name

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "task_id": self.task_id,
            "session_id": self.session_id,
            "language": self.language,
            "code_content": self.code_content,
            "config": self.config,
            "manual_action": self.manual_action,
            "file_name": self.file_name,
        }

    def __repr__(self):
        return f"TaskObject(session_id={self.session_id}, \
            language={self.language}, action={self.manual_action}, \
            file_name={self.file_name})"
