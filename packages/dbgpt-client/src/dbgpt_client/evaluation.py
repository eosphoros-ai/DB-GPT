"""Evaluation."""

from typing import List, Optional

from dbgpt._private.pydantic import BaseModel, Field
from dbgpt.core.interface.evaluation import EvaluationResult
from dbgpt.core.schema.api import Result

from .client import Client, ClientException


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
    """EvaluateServeResponse."""


async def run_evaluation(
    client: Client, request: EvaluateServeRequest
) -> List[EvaluationResult]:
    """Run evaluation.

    Args:
        client (Client): The dbgpt client.
        request (EvaluateServeRequest): The Evaluate Request.
    """
    try:
        res = await client.post("/evaluate/evaluation", request.dict())
        result: Result = res.json()
        if result["success"]:
            return list(result["data"])
        else:
            raise ClientException(status=result["err_code"], reason=result)
    except Exception as e:
        raise ClientException(f"Failed to run evaluation: {e}")
