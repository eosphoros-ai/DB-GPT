"""Locate assets for both normal wheels and editable workspace installs."""

from importlib.metadata import PackageNotFoundError, distribution
from pathlib import Path
from typing import Optional


def bundled_resource_dir(name: str) -> Optional[Path]:
    """Find an application asset directory without inspecting user workspaces.

    An editable wheel points Python modules at src/, while Hatch force-included
    assets remain in site-packages. Looking only beside __file__ misses those
    assets even though they were correctly installed.
    """
    local = Path(__file__).resolve().parent.parent / name
    if local.is_dir():
        return local
    try:
        installed = Path(distribution("dbgpt-app").locate_file(f"dbgpt_app/{name}"))
    except PackageNotFoundError:
        return None
    return installed if installed.is_dir() else None
