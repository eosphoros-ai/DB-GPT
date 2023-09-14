import json
import time
from fastapi import (
    APIRouter,
    Body,
)

from typing import List
from pilot.configs.model_config import LOGDIR
from pilot.utils import build_logger

from pilot.openapi.api_view_model import (
    Result,
)



router = APIRouter()
logger = build_logger("agent_mange", LOGDIR + "agent_mange.log")


@router.get("/v1/mange/agent/list", response_model=Result[str])
async def get_agent_list():
    logger.info(f"get_agent_list!")

    return Result.succ(None)
