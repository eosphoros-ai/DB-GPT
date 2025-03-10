import json
import logging
import os
from typing import Dict

from dbgpt.core.awel.flow.compat import FlowCompatMetadata, _register_flow_compat

logger = logging.getLogger(__name__)


def _version_sort_functon(version: str):
    versions = [int(v) for v in version.split(".")]
    num = versions[0] * 10000 + versions[1] * 100 + versions[2]
    return num


def read_compat_json_from_file() -> Dict:
    # List files in current directory
    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    compat_dir = os.path.join(parent_dir, "compat")
    if not os.path.exists(compat_dir):
        logger.warning(f"Directory not found: {compat_dir}")
        return {}
    # List files in compat directory
    compat_files = os.listdir(compat_dir)
    if not compat_files:
        logger.warning(f"No files found in {compat_dir}")

    compat_data = []
    for file in compat_files:
        if file.endswith("_compat_flow.json"):
            file_path = os.path.join(compat_dir, file)
            version = file.split("_")[0]
            try:
                with open(file_path, "r") as f:
                    data = json.load(f)
                    compat_data.append((version, data))
            except Exception as e:
                logger.warning(f"Error reading file {file_path}: {str(e)}")

    # sort by version
    compat_data.sort(key=lambda x: _version_sort_functon(x[0]))
    latest_compat = compat_data[-1]
    for version, data in compat_data:
        logger.info(f"Found compat file: {version}, use latest: {latest_compat[0]}")
    return latest_compat[1]


def register_compat_flow():
    """Register flow compat data from json files."""
    compat_data = read_compat_json_from_file()
    last_support_version = compat_data["last_support_version"]
    curr_version = compat_data["curr_version"]
    for data in compat_data["compat"]:
        metadata = FlowCompatMetadata(**data)
        _register_flow_compat(curr_version, last_support_version, metadata)
