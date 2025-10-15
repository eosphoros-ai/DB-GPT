from enum import Enum
from typing import List, Optional

from dbgpt._private.pydantic import BaseModel, Field

from ..config import SERVE_APP_NAME_HUMP


class EvaluationScene(Enum):
    RECALL = "recall"
    APP = "app"
    DATASET = "dataset"


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


class BuildDemoRequest(BaseModel):
    round_id: int = Field(..., description="benchmark round id")
    input_file_path: str = Field(..., description="path to input jsonl")
    left_output_file_path: str = Field(
        ..., description="path to left llm outputs jsonl"
    )
    right_output_file_path: str = Field(
        ..., description="path to right llm outputs jsonl"
    )
    compare_config: Optional[dict] = Field(
        None, description="compare config, e.g. {'check': 'FULL_TEXT'}"
    )


class ExecuteDemoRequest(BaseModel):
    round_id: int = Field(..., description="benchmark round id")
    input_file_path: str = Field(..., description="path to input jsonl")
    right_output_file_path: str = Field(
        ..., description="path to right llm outputs jsonl"
    )
    standard_file_path: str = Field(..., description="path to standard answers excel")
    compare_config: Optional[dict] = Field(
        None, description="optional compare config for json compare"
    )


class BenchmarkServeRequest(BaseModel):
    evaluate_code: Optional[str] = Field(None, description="evaluation code")
    scene_key: Optional[str] = Field(None, description="evaluation scene key")
    scene_value: Optional[str] = Field(None, description="evaluation scene value")
    input_file_path: Optional[str] = Field(
        None, description="input benchmark file path"
    )
    output_file_path: Optional[str] = Field(None, description="output result file path")
    model_list: Optional[List[str]] = Field(
        None, description="execute benchmark model name list"
    )
    user_name: Optional[str] = Field(None, description="user name")
    user_id: Optional[str] = Field(None, description="user id")
    sys_code: Optional[str] = Field(None, description="system code")
    parallel_num: Optional[int] = Field(None, description="system code")
    state: Optional[str] = Field(None, description="evaluation state")
    temperature: Optional[str] = Field(None, description="evaluation state")
    max_tokens: Optional[str] = Field(None, description="evaluation state")
    gmt_create: Optional[str] = Field(None, description="create time")
    gmt_modified: Optional[str] = Field(None, description="create time")


class StorageType(Enum):
    FILE = "FILE"
    OSS = "OSS"
    YU_QUE = "YU_QUE"
