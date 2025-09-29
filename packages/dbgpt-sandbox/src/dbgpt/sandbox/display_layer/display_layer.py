"""
显示层，封装并管理 Docker 执行结果
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class DisplayResult:
    status: str  # "success" / "error"
    output: str
    error: str
    execution_time: float
    exit_code: int
    files: List[str] = field(default_factory=list)
    logs: List[str] = field(default_factory=list)
    gui_frame: Optional[Any] = None  # 可选 GUI 内容
    gui_url: Optional[str] = None
    screenshots: List[str] = field(default_factory=list)


class DisplayLayer:
    """显示层，封装并管理 Docker 执行结果"""

    def __init__(self):
        self.history: Dict[str, DisplayResult] = {}  # session_id -> last result

    def add_result(self, session_id: str, result: DisplayResult):
        """保存执行结果"""
        self.history[session_id] = result

    def get_result(self, session_id: str) -> Optional[DisplayResult]:
        """获取某会话最新执行结果"""
        return self.history.get(session_id)

    def list_history(self) -> Dict[str, DisplayResult]:
        """返回所有会话的最新执行结果"""
        return self.history
