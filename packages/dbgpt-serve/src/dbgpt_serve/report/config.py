"""Configuration for the report persistence serve."""

from dataclasses import dataclass

from dbgpt_serve.core import BaseServeConfig

APP_NAME = "report"
SERVE_APP_NAME = "dbgpt_serve_report"
SERVE_APP_NAME_HUMP = "dbgpt_serve_Report"
SERVE_CONFIG_KEY_PREFIX = "dbgpt.serve.report."


@dataclass
class ServeConfig(BaseServeConfig):
    """Report persistence configuration."""

    __type__ = APP_NAME
    SERVE_APP_NAME = APP_NAME
    SERVE_APP_NAME_HUMP = "Report"
