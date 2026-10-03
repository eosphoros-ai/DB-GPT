"""Workspace provisioning module for dbgpt-app pip package users.

Copies pilot template files to the user's workspace directory on first startup.
"""

import logging
import os
import shutil

from .package_resources import bundled_resource_dir

logger = logging.getLogger(__name__)


def _ensure_pilot_workspace(dest_root: str) -> None:
    """Idempotently copy pilot workspace template files to dest_root.

    This function is safe to call multiple times — it will never overwrite
    existing files. On first run, it provisions the full pilot/ directory
    structure including alembic config and benchmark data.

    Args:
        dest_root (str): The destination root directory (parent of meta_data/).
            Example: ~/.dbgpt/workspace/pilot/
    """
    template_dir = bundled_resource_dir("pilot_template")
    if template_dir is None:
        logger.debug("Packaged pilot templates unavailable, skipping provisioning.")
        return
    for src_dir, dirs, files in os.walk(template_dir):
        # Committed migration revisions are production assets.  Only interpreter
        # caches are excluded; versions/ must be provisioned with the workspace.
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for filename in files:
            if filename in (".DS_Store",) or filename.endswith((".pyc",)):
                continue
            src_file = os.path.join(src_dir, filename)
            rel_path = os.path.relpath(src_file, template_dir)
            dest_file = os.path.join(dest_root, rel_path)
            if not os.path.exists(dest_file):
                os.makedirs(os.path.dirname(dest_file), exist_ok=True)
                shutil.copy2(src_file, dest_file)
                logger.info("Provisioned: %s", dest_file)
            else:
                logger.debug("Skipped (exists): %s", dest_file)
