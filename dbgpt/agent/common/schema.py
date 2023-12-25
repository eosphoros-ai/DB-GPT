from enum import Enum


class PluginStorageType(Enum):
    Git = "git"
    Oss = "oss"


class ApiTagType(Enum):
    API_VIEW = "dbgpt_view"
    API_CALL = "dbgpt_call"


class Status(Enum):
    TODO = "todo"
    RUNNING = "running"
    WAITING = "waiting"
    RETRYING = "retrying"
    FAILED = "failed"
    COMPLETE = "complete"
