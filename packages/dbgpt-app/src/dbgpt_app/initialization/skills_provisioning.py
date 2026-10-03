"""Skills provisioning module for dbgpt-app pip package users.

Copies builtin skill templates from the installed package to the user's
skills directory on first startup.  Existing skills are never overwritten.
"""

import logging
import os
import shutil

from .package_resources import bundled_resource_dir

logger = logging.getLogger(__name__)


def ensure_builtin_skills(skills_dir: str) -> None:
    """Idempotently seed builtin skills into *skills_dir*.

    On first run after ``pip install dbgpt-app``, the builtin skill
    templates bundled inside the wheel (``dbgpt_app/_builtin_skills/``)
    are copied to *skills_dir*.  Skills that already exist in the
    destination are **never** overwritten so that user modifications are
    preserved.

    Assets are located in the package or the installed editable wheel.
    If no bundled directory is available, provisioning is a no-op.

    Args:
        skills_dir: Absolute path to the target skills directory,
            e.g. ``~/.dbgpt/skills/``.
    """
    builtin_root = bundled_resource_dir("_builtin_skills")
    if builtin_root is None:
        logger.debug("dbgpt_app._builtin_skills not available, skipping seed.")
        return

    if not os.path.isdir(builtin_root):
        return

    os.makedirs(skills_dir, exist_ok=True)

    for entry in os.listdir(builtin_root):
        # Skip Python artifacts and hidden files
        if entry.startswith(("_", ".")) or entry == "__pycache__":
            continue

        src = os.path.join(builtin_root, entry)
        dst = os.path.join(skills_dir, entry)

        # Never overwrite existing skills (user may have modified them)
        if os.path.exists(dst):
            logger.debug("Builtin skill already exists, skipping: %s", dst)
            continue

        if os.path.isdir(src):
            shutil.copytree(src, dst)
            logger.info("Provisioned builtin skill: %s", entry)
        else:
            shutil.copy2(src, dst)
            logger.info("Provisioned builtin skill file: %s", entry)

    # Ensure user/ subdirectory exists for uploaded/imported skills
    user_dir = os.path.join(skills_dir, "user")
    os.makedirs(user_dir, exist_ok=True)
