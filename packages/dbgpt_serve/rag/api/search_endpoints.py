"""Search Tools API Endpoints.

Provides REST API for knowledge base search tools, enabling the frontend
search test panel and direct API access to kb_ls, kb_glob, kb_grep,
kb_cat, and kb_semantic_search.
"""

import logging
from typing import Optional

from fastapi import APIRouter

from dbgpt.component import SystemApp
from dbgpt_serve.core import Result

from ..api.schemas import KbSearchRequest
from ..config import SERVE_SERVICE_COMPONENT_NAME, ServeConfig

router = APIRouter()

global_system_app: Optional[SystemApp] = None


@router.post("/knowledge/{space_id}/tools/ls")
async def kb_ls_endpoint(
    space_id: str,
    request: KbSearchRequest,
) -> Result:
    """List files and directories in a knowledge space."""
    from ..tools.kb_file_tools import kb_ls

    result = await kb_ls(
        knowledge_id=space_id,
        path=request.path,
        offset=request.offset,
        limit=request.limit,
    )
    return Result.succ(result)


@router.post("/knowledge/{space_id}/tools/glob")
async def kb_glob_endpoint(
    space_id: str,
    request: KbSearchRequest,
) -> Result:
    """Search files by name pattern in a knowledge space."""
    from ..tools.kb_file_tools import kb_glob

    result = await kb_glob(
        knowledge_id=space_id,
        pattern=request.query,
        limit=request.limit,
        offset=request.offset,
    )
    return Result.succ(result)


@router.post("/knowledge/{space_id}/tools/grep")
async def kb_grep_endpoint(
    space_id: str,
    request: KbSearchRequest,
) -> Result:
    """Search file contents by keyword in a knowledge space."""
    from ..tools.kb_file_tools import kb_grep

    result = await kb_grep(
        knowledge_id=space_id,
        query=request.query,
        path=request.path,
        file_pattern=request.file_pattern,
        limit=request.limit,
        offset=request.offset,
    )
    return Result.succ(result)


@router.post("/knowledge/{space_id}/tools/cat")
async def kb_cat_endpoint(
    space_id: str,
    request: KbSearchRequest,
) -> Result:
    """Read file content from a knowledge space."""
    from ..tools.kb_file_tools import kb_cat

    result = await kb_cat(
        knowledge_id=space_id,
        path=request.path,
        start_line=request.start_line,
        end_line=request.end_line,
    )
    return Result.succ(result)


@router.post("/knowledge/{space_id}/tools/semantic_search")
async def kb_semantic_search_endpoint(
    space_id: str,
    request: KbSearchRequest,
) -> Result:
    """Perform semantic search in a knowledge space."""
    from ..tools.semantic_search_tool import kb_semantic_search

    result = await kb_semantic_search(
        knowledge_id=space_id,
        query=request.query,
        top_k=request.top_k,
        score_threshold=request.score_threshold,
    )
    return Result.succ(result)


def init_search_endpoints(system_app: SystemApp, config: ServeConfig) -> None:
    """Initialize the search tools endpoints."""
    global global_system_app
    global_system_app = system_app