import json
import logging
import uuid
from abc import ABC
from collections import defaultdict
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body
from fastapi.responses import StreamingResponse

from dbgpt._private.config import Config

CFG = Config()

router = APIRouter()
logger = logging.getLogger(__name__)
