"""API endpoints for bundled example files.

Provides a single ``POST /v1/examples/use`` endpoint that copies a bundled
example file to the user's upload directory so it can be used in
conversations.

Example files are resolved in the following order:

1. ``docker/examples/`` under the source-code project root (dev mode).
2. ``dbgpt_app/_builtin_examples/`` inside the installed wheel (PyPI mode).
"""

import asyncio
import logging
import os
import shutil
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Optional

from fastapi import APIRouter, Body, Depends

from dbgpt._private.config import Config
from dbgpt_app.openapi.api_view_model import Result
from dbgpt_serve.utils.auth import UserRequest, get_user_from_headers

router = APIRouter()
CFG = Config()
logger = logging.getLogger(__name__)

# Map of example IDs to their file info.
# - ``source_path``: path relative to source-repo root.
# - ``builtin_path``: path relative to ``_builtin_examples/`` inside the wheel.
# - ``name``: the user-visible filename.
EXAMPLE_FILES = {
    "walmart_sales": {
        "source_path": "docker/examples/excel/Walmart_Sales.csv",
        "builtin_path": "excel/Walmart_Sales.csv",
        "name": "Walmart_Sales.csv",
    },
    "csv_visual_report": {
        "source_path": "docker/examples/excel/Walmart_Sales.csv",
        "builtin_path": "excel/Walmart_Sales.csv",
        "name": "Walmart_Sales.csv",
    },
    "fin_report": {
        "source_path": (
            "docker/examples/fin_report/pdf/"
            "2020-01-23__浙江海翔药业股份有限公司__002099__海翔药业__2019年__年度报告.pdf"
        ),
        "builtin_path": (
            "fin_report/pdf/"
            "2020-01-23__浙江海翔药业股份有限公司__002099__海翔药业__2019年__年度报告.pdf"
        ),
        "name": (
            "2020-01-23__浙江海翔药业股份有限公司__002099__海翔药业__2019年__年度报告.pdf"
        ),
    },
    "create_sql_skill": {
        "source_path": "docker/examples/txt/sql_skill.txt",
        "builtin_path": "txt/sql_skill.txt",
        "name": "sql_skill.txt",
    },
}

EXAMPLE_KNOWLEDGE = {
    "olist_ecommerce_report": {
        "source_path": "examples/olist/olist-analytics-metric-governance.md",
        "builtin_path": "knowledge/olist-analytics-metric-governance.md",
        "name": "Olist_Analytics_Governance",
    },
}
_knowledge_prepare_lock = asyncio.Lock()


@router.post("/v1/examples/prepare", response_model=Result[dict])
async def prepare_example_knowledge(
    example_id: str = Body(..., embed=True),
    user_token: UserRequest = Depends(get_user_from_headers),
):
    """Ensure bundled knowledge is indexed before sending an example turn."""
    from dbgpt.rag.embedding import EmbeddingFactory
    from dbgpt_app.knowledge.request.request import KnowledgeSpaceRequest
    from dbgpt_app.knowledge.service import KnowledgeService
    from dbgpt_ext.rag.chunk_manager import ChunkParameters
    from dbgpt_serve.rag.api.schemas import (
        DocumentServeRequest,
        KnowledgeSyncRequest,
    )
    from dbgpt_serve.rag.service.service import Service

    example = EXAMPLE_KNOWLEDGE.get(example_id)
    if example is None:
        return Result.failed(msg=f"Unknown knowledge example: {example_id}")
    try:
        async with _knowledge_prepare_lock:
            service = Service.get_instance(CFG.SYSTEM_APP)
            space = service.get({"name": example["name"]})
            if space is None:
                KnowledgeService().create_knowledge_space(
                    KnowledgeSpaceRequest(
                        name=example["name"],
                        vector_type="VectorStore",
                        domain_type="Normal",
                        owner=user_token.user_id,
                        desc="Olist 分析指标口径与数据治理",
                    )
                )
                space = service.get({"name": example["name"]})
            # Preserve an existing governing document; only seed an empty space.
            doc = service.get_document(
                {"space": space.name, "status": "FINISHED"}
            ) or service.get_document({"space": space.name})
            if doc is None:
                source = _resolve_example_source(example)
                if source is None:
                    return Result.failed(
                        msg="Bundled Olist knowledge document not found"
                    )
                doc_id = service.create_document(
                    DocumentServeRequest(
                        space_id=str(space.id),
                        doc_name="olist-analytics-metric-governance.md",
                        doc_type="TEXT",
                        content=Path(source).read_text(encoding="utf-8"),
                    )
                )
                doc = service.get_document({"id": int(doc_id)})
            if doc.status in {"TODO", "FAILED"}:
                # Worker registration can finish after HTTP startup. Check the
                # configured embedding service before queuing persistent work.
                embeddings = EmbeddingFactory.get_instance(CFG.SYSTEM_APP).create()
                if not await embeddings.aembed_query("Olist 指标口径"):
                    return Result.failed(msg="Embedding model is not ready")
                await service.sync_document(
                    [
                        KnowledgeSyncRequest(
                            space_id=str(space.id),
                            doc_id=doc.id,
                            chunk_parameters=ChunkParameters(
                                chunk_strategy="CHUNK_BY_SIZE"
                            ),
                        )
                    ]
                )
            # sync_document schedules indexing; do not mistake that for readiness.
            for _ in range(120):
                doc = service.get_document({"id": doc.id})
                if doc.status == "FINISHED" and doc.chunk_size:
                    indexed_chunks = len(
                        [value for value in (doc.vector_ids or "").split(",") if value]
                    )
                    if indexed_chunks != doc.chunk_size:
                        return Result.failed(
                            msg="Knowledge index is incomplete; resync the document "
                            "after the embedding model is ready"
                        )
                    return Result.succ({"id": space.id, "name": space.name})
                if doc.status != "RUNNING":
                    return Result.failed(msg=f"Knowledge indexing failed: {doc.result}")
                await asyncio.sleep(1)
            return Result.failed(
                msg="Knowledge indexing is still running; try again shortly"
            )
    except Exception:
        logger.exception("Failed to prepare example knowledge")
        return Result.failed(
            msg="Could not prepare example knowledge; check server logs"
        )


def _validate_example_filename(filename: str) -> str:
    if "\x00" in filename:
        raise ValueError("example filename must not contain null bytes")

    posix_path = PurePosixPath(filename)
    windows_path = PureWindowsPath(filename)
    if (
        posix_path.is_absolute()
        or windows_path.is_absolute()
        or len(posix_path.parts) != 1
        or len(windows_path.parts) != 1
        or filename in {"", ".", ".."}
    ):
        raise ValueError("example filename must be a plain file name")
    return filename


def _resolve_example_source(example: dict) -> Optional[str]:
    """Return the absolute path to an example file, or *None* if not found.

    Resolution order:
    1. Source-repo path under ``SYSTEM_APP.work_dir`` or cwd (source-code
       development mode).
    2. ``_builtin_examples/…`` inside the installed ``dbgpt_app`` package
       (PyPI install mode).
    """
    # --- 1. Source-code / work_dir mode ---
    base_dir = os.getcwd()
    if (
        CFG.SYSTEM_APP
        and hasattr(CFG.SYSTEM_APP, "work_dir")
        and CFG.SYSTEM_APP.work_dir
    ):
        base_dir = CFG.SYSTEM_APP.work_dir

    candidate = os.path.join(base_dir, example["source_path"])
    if os.path.isfile(candidate):
        return candidate

    # --- 2. Builtin examples bundled in the wheel ---
    try:
        import dbgpt_app._builtin_examples as _be

        builtin_root = os.path.dirname(_be.__file__)
        candidate = os.path.join(builtin_root, example["builtin_path"])
        if os.path.isfile(candidate):
            return candidate
    except (ImportError, AttributeError):
        pass

    return None


@router.post("/v1/examples/use", response_model=Result[str])
async def use_example_file(
    example_id: str = Body(..., embed=True),
    user_token: UserRequest = Depends(get_user_from_headers),
):
    """Copy an example file to user's upload directory and return its path."""
    try:
        if example_id not in EXAMPLE_FILES:
            return Result.failed(msg=f"Unknown example: {example_id}")

        example = EXAMPLE_FILES[example_id]
        from dbgpt_app.openapi.api_v1.python_upload_api import (
            _resolve_upload_dir,
            _resolve_upload_path,
            _resolve_user_id,
        )

        user_id = _resolve_user_id(user_token.user_id)

        source_path = _resolve_example_source(example)
        if source_path is None:
            return Result.failed(msg=f"Example file not found: {example['name']}")

        # Determine upload base directory (same convention as python_upload_api)
        base_dir = os.getcwd()
        if (
            CFG.SYSTEM_APP
            and hasattr(CFG.SYSTEM_APP, "work_dir")
            and CFG.SYSTEM_APP.work_dir
        ):
            base_dir = CFG.SYSTEM_APP.work_dir

        upload_dir = _resolve_upload_dir(base_dir, user_id)
        os.makedirs(upload_dir, exist_ok=True)

        try:
            target_name = _validate_example_filename(example["name"])
        except ValueError as exc:
            return Result.failed(msg=str(exc))

        target_path = _resolve_upload_path(upload_dir, target_name)
        shutil.copy2(source_path, target_path)

        # ``file_path`` is consumed by the React attachment adapter, whose
        # transport contract intentionally rejects backslashes (they are
        # ambiguous with escaping and traversal on Windows).  Return a
        # platform-neutral absolute path so bundled examples work on Windows
        # exactly like user-uploaded session files.
        abs_path = os.path.abspath(target_path).replace("\\", "/")
        logger.info(f"Example file copied: {abs_path}")
        return Result.succ(abs_path)
    except Exception as e:
        logger.exception(f"Failed to use example file: {e}")
        return Result.failed(msg=f"Error: {str(e)}")
