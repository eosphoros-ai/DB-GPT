from dataclasses import dataclass, field
from typing import List, Optional

from dbgpt.core.awel.flow import (
    TAGS_ORDER_HIGH,
    ResourceCategory,
    auto_register_resource,
)
from dbgpt.core.interface.file import StorageBackendConfig
from dbgpt.util.i18n_utils import _
from dbgpt.util.module_utils import ScannerConfig
from dbgpt_serve.core import BaseServeConfig

APP_NAME = "file"
SERVE_APP_NAME = "dbgpt_serve_file"
SERVE_APP_NAME_HUMP = "dbgpt_serve_File"
SERVE_CONFIG_KEY_PREFIX = "dbgpt.serve.file."
SERVE_SERVICE_COMPONENT_NAME = f"{SERVE_APP_NAME}_service"
# Database table name
SERVER_APP_TABLE_NAME = "dbgpt_serve_file"


@auto_register_resource(
    label=_("File Serve Configurations"),
    category=ResourceCategory.COMMON,
    tags={"order": TAGS_ORDER_HIGH},
    description=_(
        "This configuration is for the file serve module. In DB-GPT, you can store your"
        "files in the file server."
    ),
    show_in_ui=False,
    skip_fields=["backends"],
)
@dataclass
class ServeConfig(BaseServeConfig):
    """Parameters for the serve command"""

    __type__ = APP_NAME

    __scan_config__ = ScannerConfig(
        module_path="dbgpt_ext.storage.file",
        base_class=StorageBackendConfig,
        recursive=True,
        specific_files=["config"],
    )

    check_hash: Optional[bool] = field(
        default=True,
        metadata={"help": _("Check the hash of the file when downloading")},
    )
    host: Optional[str] = field(
        default=None, metadata={"help": _("The host of the file server")}
    )
    port: Optional[int] = field(
        default=5670,
        metadata={"help": _("The port of the file server, default is 5670")},
    )
    download_chunk_size: Optional[int] = field(
        default=1024 * 1024,
        metadata={"help": _("The chunk size when downloading the file")},
    )
    save_chunk_size: Optional[int] = field(
        default=1024 * 1024, metadata={"help": _("The chunk size when saving the file")}
    )
    transfer_chunk_size: Optional[int] = field(
        default=1024 * 1024,
        metadata={"help": _("The chunk size when transferring the file")},
    )
    transfer_timeout: Optional[int] = field(
        default=360, metadata={"help": _("The timeout when transferring the file")}
    )
    local_storage_path: Optional[str] = field(
        default=None, metadata={"help": _("The local storage path")}
    )
    default_backend: Optional[str] = field(
        default=None,
        metadata={"help": _("The default storage backend")},
    )
    backends: List[StorageBackendConfig] = field(
        default_factory=list,
        metadata={"help": _("The storage backend configurations")},
    )

    def get_node_address(self) -> str:
        """Get the node address"""
        file_server_host = self.host
        if (
            not file_server_host
            or file_server_host == "0.0.0.0"
            or file_server_host == "127.0.0.1"
            or file_server_host == "localhost"
            or file_server_host == "::1"
            or file_server_host == "::"
        ):
            from dbgpt.util.net_utils import _get_ip_address

            file_server_host = _get_ip_address()
        file_server_port = self.port or 5670
        return f"{file_server_host}:{file_server_port}"

    def get_local_storage_path(self) -> str:
        """Get the local storage path"""
        local_storage_path = self.local_storage_path
        if not local_storage_path:
            from pathlib import Path

            base_path = Path.home() / ".cache" / "dbgpt" / "files"
            local_storage_path = str(base_path)
        return local_storage_path
