"""Serve configuration for the finance research module."""

from dataclasses import dataclass, field

from dbgpt_serve.core import BaseServeConfig

APP_NAME = "finance"
SERVE_APP_NAME = "dbgpt_serve_finance"
SERVE_APP_NAME_HUMP = "dbgpt_serve_Finance"
SERVE_CONFIG_KEY_PREFIX = "dbgpt.serve.finance."
SERVE_SERVICE_COMPONENT_NAME = f"{SERVE_APP_NAME}_service"


@dataclass
class ServeConfig(BaseServeConfig):
    """Configuration for the finance serve module."""

    __type__ = APP_NAME

    search_provider: str = field(
        default="eastmoney",
        metadata={"help": "Search provider: eastmoney / baidu / mock / custom."},
    )
    db_path: str = field(
        default="finance_research.db",
        metadata={"help": "SQLite database path for provenance storage."},
    )
    max_results: int = field(
        default=10,
        metadata={"help": "Maximum number of search results per query."},
    )
