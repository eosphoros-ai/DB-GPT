"""Built-in file data sources registered by the local application."""

import os
from typing import List, Tuple


def default_file_datasources(
    root_path: str, pilot_path: str
) -> List[Tuple[str, List[str], str]]:
    """Return deterministic file data sources anchored to this checkout."""

    return [
        (
            "Walmart_Sales",
            [
                os.path.join(pilot_path, "examples", "Walmart_Sales.db"),
                os.path.join(
                    root_path, "docker", "examples", "dashboard", "Walmart_Sales.db"
                ),
            ],
            "Default Walmart Sales example database",
        ),
        (
            "olist_ecommerce_demo",
            [
                os.path.join(
                    root_path,
                    "examples",
                    "dashboard",
                    "olist",
                    "data",
                    "generated",
                    "olist.db",
                )
            ],
            "Olist 电商多表演示（完整八表 SQLite 数据集）",
        ),
    ]
