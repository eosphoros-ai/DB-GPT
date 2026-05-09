"""API endpoints for bundled example files.

Provides a single ``POST /v1/examples/use`` endpoint that copies a bundled
example file to the user's upload directory so it can be used in
conversations.

Example files are resolved in the following order:

1. ``docker/examples/`` under the source-code project root (dev mode).
2. ``dbgpt_app/_builtin_examples/`` inside the installed wheel (PyPI mode).
"""

import logging
import os
import shutil
from typing import Optional

from fastapi import APIRouter, Body, Depends

from dbgpt._private.config import Config
from dbgpt_app.openapi.api_view_model import Result
from dbgpt_serve.utils.auth import UserRequest, get_user_from_headers

router = APIRouter()
CFG = Config()
logger = logging.getLogger(__name__)

# Map of example IDs to their file info.
# - ``source_path``: path relative to source-repo root (``docker/examples/…``).
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


def _resolve_example_source(example: dict) -> Optional[str]:
    """Return the absolute path to an example file, or *None* if not found.

    Resolution order:
    1. ``docker/examples/…`` under ``SYSTEM_APP.work_dir`` or cwd (source-code
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
        user_id = user_token.user_id or "default"

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

        upload_dir = os.path.join(base_dir, "python_uploads", user_id)
        os.makedirs(upload_dir, exist_ok=True)

        target_path = os.path.join(upload_dir, example["name"])
        shutil.copy2(source_path, target_path)

        abs_path = os.path.abspath(target_path)
        logger.info(f"Example file copied: {abs_path}")
        return Result.succ(abs_path)
    except Exception as e:
        logger.exception(f"Failed to use example file: {e}")
        return Result.failed(msg=f"Error: {str(e)}")
