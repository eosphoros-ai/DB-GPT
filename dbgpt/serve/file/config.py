from dataclasses import dataclass, field
from typing import Optional

from dbgpt.serve.core import BaseServeConfig

APP_NAME = "file"
SERVE_APP_NAME = "dbgpt_serve_file"
SERVE_APP_NAME_HUMP = "dbgpt_serve_File"
SERVE_CONFIG_KEY_PREFIX = "dbgpt.serve.file."
SERVE_SERVICE_COMPONENT_NAME = f"{SERVE_APP_NAME}_service"
# Database table name
SERVER_APP_TABLE_NAME = "dbgpt_serve_file"


@dataclass
class ServeConfig(BaseServeConfig):
    """Parameters for the serve command"""

    # TODO: add your own parameters here
    api_keys: Optional[str] = field(
        default=None, metadata={"help": "API keys for the endpoint, if None, allow all"}
    )
    check_hash: Optional[bool] = field(
        default=True, metadata={"help": "Check the hash of the file when downloading"}
    )
    file_server_host: Optional[str] = field(
        default=None, metadata={"help": "The host of the file server"}
    )
    file_server_port: Optional[int] = field(
        default=5670, metadata={"help": "The port of the file server"}
    )
    file_server_download_chunk_size: Optional[int] = field(
        default=1024 * 1024,
        metadata={"help": "The chunk size when downloading the file"},
    )
    file_server_save_chunk_size: Optional[int] = field(
        default=1024 * 1024, metadata={"help": "The chunk size when saving the file"}
    )
    file_server_transfer_chunk_size: Optional[int] = field(
        default=1024 * 1024,
        metadata={"help": "The chunk size when transferring the file"},
    )
    file_server_transfer_timeout: Optional[int] = field(
        default=360, metadata={"help": "The timeout when transferring the file"}
    )
    local_storage_path: Optional[str] = field(
        default=None, metadata={"help": "The local storage path"}
    )

    def get_node_address(self) -> str:
        """Get the node address"""
        file_server_host = self.file_server_host
        if not file_server_host:
            from dbgpt.util.net_utils import _get_ip_address

            file_server_host = _get_ip_address()
        file_server_port = self.file_server_port or 5670
        return f"{file_server_host}:{file_server_port}"

    def get_local_storage_path(self) -> str:
        """Get the local storage path"""
        local_storage_path = self.local_storage_path
        if not local_storage_path:
            from pathlib import Path

            base_path = Path.home() / ".cache" / "dbgpt" / "files"
            local_storage_path = str(base_path)
        return local_storage_path
