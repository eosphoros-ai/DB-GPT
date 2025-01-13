"""Module to define the data source connectors."""

from typing import Any

from dbgpt.datasource.base import BaseConnector  # noqa: F401


def __getattr__(name: str) -> Any:
    if name == "RDBMSConnector":
        from dbgpt.datasource.rdbms.base import RDBMSConnector  # noqa: F401

        return RDBMSConnector
    else:
        raise AttributeError(f"Could not find: {name} in datasource")


__ALL__ = ["BaseConnector", "RDBMSConnector"]
