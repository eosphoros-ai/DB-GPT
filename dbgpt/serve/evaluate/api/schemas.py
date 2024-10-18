from enum import Enum
from typing import Any, Dict, List, Optional

from dbgpt._private.pydantic import BaseModel, Field

from ..config import SERVE_APP_NAME_HUMP


class EvaluationScene(Enum):
    RECALL = "recall"
    APP = "app"


class DatasetStorageType(Enum):
    OSS = "oss"
    DB = "db"


class EvaluateServeRequest(BaseModel):
    evaluate_code: Optional[str] = Field(None, description="evaluation code")
    scene_key: Optional[str] = Field(None, description="evaluation scene key")
    scene_value: Optional[str] = Field(None, description="evaluation scene value")
    datasets_name: Optional[str] = Field(None, description="evaluation datasets name")
    datasets: Optional[List[dict]] = Field(None, description="datasets")
    evaluate_metrics: Optional[List[str]] = Field(
        None, description="evaluation metrics"
    )
    context: Optional[dict] = Field(None, description="The context of the evaluate")
    user_name: Optional[str] = Field(None, description="user name")
    user_id: Optional[str] = Field(None, description="user id")
    sys_code: Optional[str] = Field(None, description="system code")
    parallel_num: Optional[int] = Field(None, description="system code")
    state: Optional[str] = Field(None, description="evaluation state")
    result: Optional[str] = Field(None, description="evaluation result")
    storage_type: Optional[str] = Field(None, comment="datasets storage type")
    average_score: Optional[str] = Field(None, description="evaluation average score")
    log_info: Optional[str] = Field(None, description="evaluation log_info")
    gmt_create: Optional[str] = Field(None, description="create time")
    gmt_modified: Optional[str] = Field(None, description="create time")


class EvaluateServeResponse(EvaluateServeRequest):
    class Config:
        title = f"EvaluateServeResponse for {SERVE_APP_NAME_HUMP}"


class DatasetServeRequest(BaseModel):
    code: Optional[str] = Field(None, description="dataset code")
    name: Optional[str] = Field(None, description="dataset name")
    file_type: Optional[str] = Field(None, description="dataset file type")
    storage_type: Optional[str] = Field(None, comment="datasets storage type")
    storage_position: Optional[str] = Field(None, comment="datasets storage position")
    datasets_count: Optional[int] = Field(None, comment="datasets row count")
    have_answer: Optional[bool] = Field(None, comment="datasets have answer")
    members: Optional[str] = Field(None, comment="datasets manager members")
    user_name: Optional[str] = Field(None, description="user name")
    user_id: Optional[str] = Field(None, description="user id")
    sys_code: Optional[str] = Field(None, description="system code")


class DatasetServeResponse(DatasetServeRequest):
    gmt_create: Optional[str] = Field(None, description="create time")
    gmt_modified: Optional[str] = Field(None, description="create time")
