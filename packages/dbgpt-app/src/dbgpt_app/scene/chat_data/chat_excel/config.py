from dataclasses import dataclass, field
from typing import List, Optional

from dbgpt.util.i18n_utils import _
from dbgpt_app.scene import ChatScene
from dbgpt_serve.core.config import (
    BaseGPTsAppMemoryConfig,
    BufferWindowGPTsAppMemoryConfig,
    GPTsAppCommonConfig,
)


@dataclass
class ChatExcelConfig(GPTsAppCommonConfig):
    """Chat Excel Configuration"""

    name = ChatScene.ChatExcel.value()
    duckdb_extensions_dir: List[str] = field(
        default_factory=list,
        metadata={
            "help": _(
                "The directory of the duckdb extensions."
                "Duckdb will download the extensions from the internet if not provided."
                "This configuration is used to tell duckdb where to find the extensions"
                " and avoid downloading. Note that the extensions are platform-specific"
                " and version-specific."
            )
        },
    )
    force_install: bool = field(
        default=False,
        metadata={
            "help": _(
                "Whether to force install the duckdb extensions. If True, the "
                "extensions will be installed even if they are already installed."
            )
        },
    )

    memory: Optional[BaseGPTsAppMemoryConfig] = field(
        default_factory=lambda: BufferWindowGPTsAppMemoryConfig(
            keep_start_rounds=0, keep_end_rounds=10
        ),
        metadata={"help": _("Memory configuration")},
    )
