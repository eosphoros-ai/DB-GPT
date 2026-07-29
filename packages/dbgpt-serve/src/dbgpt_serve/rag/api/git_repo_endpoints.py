"""Git Repository API Endpoints.

Provides REST API for syncing git repositories into knowledge spaces
and checking sync status.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from dbgpt.component import SystemApp
from dbgpt_serve.core import Result

from ..api.schemas import (
    GitRepoIncrementalSyncRequest,
    GitRepoSyncRequest,
    GitRepoSyncStatusResponse,
)
from ..config import SERVE_SERVICE_COMPONENT_NAME, ServeConfig
from ..service.service import Service
from .endpoints import check_api_key

router = APIRouter()

global_system_app: Optional[SystemApp] = None


def get_service() -> Service:
    """Get the service instance."""
    return global_system_app.get_component(SERVE_SERVICE_COMPONENT_NAME, Service)


def get_git_sync_service():
    """Get or create a GitRepoSyncService instance."""
    from ..service.git_repo_sync_service import GitRepoSyncService

    service = get_service()
    return GitRepoSyncService(service)


@router.post("/{space_id}/git/sync", dependencies=[Depends(check_api_key)])
async def sync_git_repo(
    space_id: str,
    request: GitRepoSyncRequest,
) -> Result:
    """Sync a git repository into a knowledge space.

    Starts the sync in the background and returns immediately.
    Poll GET /{space_id}/git/sync-status for progress.
    """
    try:
        sync_service = get_git_sync_service()
        result = await sync_service.sync_repo(
            knowledge_id=space_id,
            repo_url=request.repo_url,
            branch=request.branch,
            exclude_dirs=request.exclude_dirs,
            exclude_extensions=request.exclude_extensions,
            include_dirs=request.include_dirs,
            build_graph=request.build_graph,
        )
        return Result.succ(result)
    except ValueError as e:
        # Concurrent sync or space not found
        error_msg = str(e)
        if "already in progress" in error_msg:
            raise HTTPException(status_code=409, detail=error_msg)
        raise HTTPException(status_code=400, detail=error_msg)
    except Exception as e:
        logging.exception(f"Git repo sync failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{space_id}/git/incremental-sync", dependencies=[Depends(check_api_key)])
async def incremental_sync_git_repo(
    space_id: str,
    request: GitRepoIncrementalSyncRequest,
) -> Result:
    """Incrementally sync a git repository.

    Starts the incremental sync in the background and returns immediately.
    Poll GET /{space_id}/git/sync-status for progress.
    """
    try:
        sync_service = get_git_sync_service()
        result = await sync_service.incremental_sync(
            knowledge_id=space_id,
            repo_url=request.repo_url,
            branch=request.branch,
            last_commit=request.last_commit,
        )
        return Result.succ(result)
    except ValueError as e:
        error_msg = str(e)
        if "already in progress" in error_msg:
            raise HTTPException(status_code=409, detail=error_msg)
        raise HTTPException(status_code=400, detail=error_msg)
    except Exception as e:
        logging.exception(f"Git repo incremental sync failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/{space_id}/git/sync-status",
    response_model=Result[GitRepoSyncStatusResponse],
)
async def get_git_sync_status(
    space_id: str,
) -> Result[GitRepoSyncStatusResponse]:
    """Get the sync status of a git repo knowledge space."""
    try:
        sync_service = get_git_sync_service()
        result = sync_service.get_index_status(knowledge_id=space_id)
        return Result.succ(GitRepoSyncStatusResponse(**result))
    except Exception as e:
        logging.exception(f"Failed to get git sync status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{space_id}/build-graph", dependencies=[Depends(check_api_key)])
async def build_knowledge_graph(space_id: str) -> Result:
    """Build a structural graph from the indexed documents of a knowledge space.

    Works for both GIT_REPO spaces (code structure graph) and DOCUMENT spaces
    (markdown heading hierarchy graph). Reconstructs file contents from the
    stored chunks and builds the graph via RepoGraphBuilder.

    Returns:
        Dict with vertex/edge counts and status, or an error message if no
        documents were found to build a graph from.
    """
    try:
        from ..service.codegraph_build_service import (
            build_code_graph_from_knowledge_space,
        )

        result = await build_code_graph_from_knowledge_space(space_id)
        if result:
            return Result.succ(result)
        return Result.fail(
            "No documents found to build a graph from. Index some documents first."
        )
    except Exception as e:
        logging.exception(f"Failed to build knowledge graph: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def init_git_repo_endpoints(system_app: SystemApp, config: ServeConfig) -> None:
    """Initialize the git repo endpoints."""
    global global_system_app
    global_system_app = system_app
