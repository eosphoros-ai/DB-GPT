"""Tools for server-authorized persisted tabular upload datasets."""

import json
from typing import Any, Dict, List

from dbgpt.agent.resource.tool.base import tool


def make_load_file_for_dataset(react_state: Dict[str, Any]):
    @tool(description="Load uploaded file-group information if provided.")
    def load_file() -> str:
        uploaded_files = react_state.get("uploaded_files") or []
        file_paths = react_state.get("file_paths") or (
            [react_state["file_path"]] if react_state.get("file_path") else []
        )
        if not file_paths:
            return json.dumps(
                {"chunks": [{"output_type": "text", "content": "No file uploaded"}]},
                ensure_ascii=False,
            )
        return json.dumps(
            {
                "chunks": [
                    {
                        "output_type": "json",
                        "content": {
                            "dataset_id": react_state.get("dataset_id"),
                            "files": uploaded_files
                            or [
                                {
                                    "name": str(path)
                                    .replace("\\", "/")
                                    .rsplit("/", 1)[-1]
                                }
                                for path in file_paths
                            ],
                        },
                    },
                    {
                        "output_type": "text",
                        "content": (
                            "Files belong to one upload group. Inspect every table "
                            "and validate keys/cardinality before combining them."
                        ),
                    },
                ]
            },
            ensure_ascii=False,
        )

    return load_file


def make_execute_analysis_for_dataset(react_state: Dict[str, Any]):
    @tool(description="Execute quick analysis on uploaded Excel/CSV file.")
    async def execute_analysis() -> str:
        from dbgpt._private.config import Config
        from dbgpt.util.code.server import get_code_server

        CFG = Config()

        def _is_excel_skill(meta) -> bool:
            name = (meta.name or "").lower()
            desc = (meta.description or "").lower()
            tags = [tag.lower() for tag in (meta.tags or [])]
            return any(
                token in name or token in desc or token in tags
                for token in ["excel", "xlsx", "xls", "spreadsheet"]
            )

        matched = react_state.get("matched")
        file_paths = react_state.get("file_paths") or (
            [react_state["file_path"]] if react_state.get("file_path") else []
        )
        if not file_paths:
            return json.dumps(
                {"chunks": [{"output_type": "text", "content": "No file to analyze"}]},
                ensure_ascii=False,
            )
        matched_name = (
            (matched.metadata.name or "").casefold() if matched is not None else ""
        )
        if (
            matched
            and not _is_excel_skill(matched.metadata)
            and matched_name != "dashboard-builder"
        ):
            return json.dumps(
                {
                    "chunks": [
                        {
                            "output_type": "text",
                            "content": "Selected skill is not for Excel analysis",
                        }
                    ]
                },
                ensure_ascii=False,
            )
        code_server = await get_code_server(CFG.SYSTEM_APP)
        analysis_code = """
import json
from pathlib import Path
import pandas as pd

file_paths = json.loads({file_paths_json})
summaries = []
for file_path in file_paths:
    path = Path(file_path)
    if path.suffix.lower() in (".xls", ".xlsx"):
        frames = pd.read_excel(path, sheet_name=None)
    else:
        separator = "\\t" if path.suffix.lower() == ".tsv" else ","
        frames = {{"": pd.read_csv(path, sep=separator)}}
    for sheet_name, df in frames.items():
        summaries.append({{
            "file_name": path.name,
            "sheet_name": sheet_name or None,
            "shape": list(df.shape),
            "columns": [str(column) for column in df.columns],
            "dtypes": {{str(col): str(dtype) for col, dtype in df.dtypes.items()}},
            "head": df.head(5).to_dict(orient="records"),
        }})
summary = {{"files": summaries}}
print(json.dumps(summary, ensure_ascii=False))
""".format(file_paths_json=repr(json.dumps(file_paths, ensure_ascii=False)))
        result = await code_server.exec(analysis_code, "python")
        output_text = (
            result.output.decode("utf-8") if isinstance(result.output, bytes) else ""
        )
        # Do not return the executable source: it contains server-local paths.
        # The deterministic JSON/table/chart results are sufficient evidence
        # for the user and remain safe to include in a shared conversation.
        chunks: List[Dict[str, Any]] = [
            {
                "output_type": "text",
                "content": "Inspected every authorized file in the upload dataset.",
            }
        ]
        if output_text:
            try:
                summary = json.loads(output_text)
                chunks.append({"output_type": "json", "content": summary})
                first_summary = (summary.get("files") or [{}])[0]
                head_rows = first_summary.get("head")
                columns = first_summary.get("columns")
                if isinstance(head_rows, list) and isinstance(columns, list):
                    chunks.append(
                        {
                            "output_type": "table",
                            "content": {
                                "columns": [
                                    {"title": col, "dataIndex": col, "key": col}
                                    for col in columns
                                ],
                                "rows": head_rows,
                            },
                        }
                    )
                numeric_columns = [
                    col
                    for col, dtype in (first_summary.get("dtypes") or {}).items()
                    if "int" in dtype or "float" in dtype
                ]
                if numeric_columns and isinstance(head_rows, list):
                    series_col = numeric_columns[0]
                    data = [
                        {"x": idx + 1, "y": row.get(series_col)}
                        for idx, row in enumerate(head_rows)
                        if row.get(series_col) is not None
                    ]
                    if data:
                        chunks.append(
                            {
                                "output_type": "chart",
                                "content": {
                                    "data": data,
                                    "xField": "x",
                                    "yField": "y",
                                },
                            }
                        )
            except Exception:
                chunks.append({"output_type": "text", "content": output_text})
        return json.dumps({"chunks": chunks}, ensure_ascii=False)

    return execute_analysis
