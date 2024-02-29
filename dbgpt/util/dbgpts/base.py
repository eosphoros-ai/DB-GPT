import hashlib
import logging
import os
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

_ABS_ROOT_PATH = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)
DEFAULT_DBGPTS_DIR = Path.home() / ".dbgpts"
DBGPTS_HOME = os.getenv("DBGPTS_HOME", str(DEFAULT_DBGPTS_DIR))
DBGPTS_REPO_HOME = os.getenv("DBGPTS_REPO_HOME", str(DEFAULT_DBGPTS_DIR / "repos"))

DEFAULT_REPO_MAP = {
    "eosphoros/dbgpts": "https://github.com/eosphoros-ai/dbgpts.git",
    "fangyinc/dbgpts": "https://github.com/fangyinc/dbgpts.git",
}

DEFAULT_PACKAGES = ["agents", "apps", "operators", "workflow"]
DEFAULT_PACKAGE_TYPES = ["agent", "app", "operator", "flow"]
INSTALL_METADATA_FILE = "install_metadata.toml"
DBGPTS_METADATA_FILE = "dbgpts.toml"

TYPE_TO_PACKAGE = {
    "agent": "agents",
    "app": "apps",
    "operator": "operators",
    "flow": "workflow",
}


def _get_env_sig() -> str:
    """Get a unique signature for the current Python environment."""
    py_path = os.path.join(os.path.dirname(sys.executable), "python")
    env_path = f"{_ABS_ROOT_PATH}_{py_path}"
    md5_hash = hashlib.md5()
    md5_hash.update(env_path.encode("utf-8"))
    return md5_hash.hexdigest()


def _print_path(path: str | Path) -> str:
    str_path = str(path)
    if str_path.startswith(str(Path.home())):
        str_path = str_path.replace(str(Path.home()), "~")
    return str_path


def get_repo_path(repo: str) -> str:
    """Get the path of the repo

    Args:
        repo (str): The name of the repo

    Returns:
        str: The path of the repo
    """
    repo_group, repo_name = repo.split("/")
    return str(Path(DBGPTS_REPO_HOME) / repo_group / repo_name)


ENV_SIG = _get_env_sig()
# The directory where the dbgpts package is installed
INSTALL_DIR = Path(DBGPTS_HOME) / "packages" / ENV_SIG


os.makedirs(DBGPTS_REPO_HOME, exist_ok=True)
os.makedirs(INSTALL_DIR, exist_ok=True)
