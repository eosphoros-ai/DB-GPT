"""Export an executed query artifact without rerunning SQL or invoking a shell."""

import csv
import io
import json
import os
import tempfile
from typing import Any, Dict

from dbgpt.agent.resource.tool.base import tool


def make_export_csv(react_state: Dict[str, Any]):
    @tool(
        description=(
            "将本会话已执行的查询结果保存为可下载的 UTF-8 BOM CSV 文件。"
            "不重新查询数据库，不执行脚本。使用 sql_query 返回的 artifact_id。"
            '参数: {"artifact_id":"sql-...", "filename":"result.csv"}。'
        )
    )
    def export_csv(artifact_id: str, filename: str = "query-result.csv") -> str:
        query = react_state.get("_query_artifacts", {}).get(artifact_id)
        if query is None or query.get("truncated"):
            return json.dumps(
                {
                    "success": False,
                    "error": "查询产物不存在或已截断，无法导出完整结果。",
                },
                ensure_ascii=False,
            )
        name = os.path.basename(filename.replace("\\", "/")) or "query-result.csv"
        if not name.lower().endswith(".csv"):
            name += ".csv"
        buffer = io.StringIO(newline="")
        writer = csv.writer(buffer)
        writer.writerow(query["columns"])
        writer.writerows(query["rows"])
        content = buffer.getvalue()
        directory = tempfile.mkdtemp(prefix="dbgpt-query-export-", dir="/tmp")
        path = os.path.join(directory, name)
        with open(path, "w", encoding="utf-8-sig", newline="") as output:
            output.write(content)
        return json.dumps(
            {
                "success": True,
                "artifact_id": artifact_id,
                "row_count": len(query["rows"]),
                "chunks": [
                    {
                        "output_type": "file",
                        "content": {
                            "name": name,
                            "file_path": path,
                            "size": os.path.getsize(path),
                            "content": content,
                        },
                    }
                ],
            },
            ensure_ascii=False,
        )

    return export_csv
