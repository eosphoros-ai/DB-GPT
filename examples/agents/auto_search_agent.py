import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from dbgpt.agent import AgentContext, AgentMemory, LLMConfig, UserProxyAgent
from dbgpt.agent.expand.data_scientist_agent import DataScientistAgent
from dbgpt.agent.expand.web_assistant_agent import WebSearchAgent
from dbgpt.agent.resource import RDBMSConnectorResource
from dbgpt.model.proxy import TongyiLLMClient
from dbgpt_ext.datasource.rdbms.conn_sqlite import SQLiteConnector

api_base = "https://dashscope.aliyuncs.com/compatible-mode/v1"
api_key = "sk-xxx"
model = "qwen3-32b"


def read_excel_headers_and_data(
    file_path: str,
) -> Tuple[List[str], List[Dict[str, Any]]]:
    """
    读取Excel文件，返回表头信息和结构化数据

    参数:
        file_path: Excel文件路径（.xlsx格式）

    返回:
        Tuple[表头列表, 数据列表]
        - 表头列表: 从Excel第一行读取的列名
        - 数据列表: 每个元素是一个字典，键为表头，值为对应单元格数据（空单元格转为None）
    """
    if not Path(file_path).exists():
        raise FileNotFoundError(f"文件不存在: {file_path}")

    if Path(file_path).suffix.lower() != ".xlsx":
        raise ValueError(f"不支持的文件格式: {Path(file_path).suffix}，仅支持.xlsx")

    try:
        df = pd.read_excel(
            file_path, sheet_name=0, engine="openpyxl", keep_default_na=False
        )
    except Exception as e:
        raise RuntimeError(f"读取Excel失败: {str(e)}")

    headers = list(df.columns)
    if not headers:
        raise ValueError("Excel文件没有表头信息（第一行为空）")

    data = []
    for _, row in df.iterrows():
        row_data = {}
        for header in headers:
            value = row[header]
            row_data[header] = value if value != "" else None
        data.append(row_data)

    return headers, data


def data2md(headers, table_data):
    md_lines = []

    md_lines.append("| " + " | ".join(headers) + " |")
    md_lines.append("| " + " | ".join(["---"] * len(headers)) + " |")

    for row in table_data:
        values = []
        for h in headers:
            val = row.get(h, "")
            if hasattr(val, "strftime"):
                values.append(val.strftime("%Y-%m-%d"))
            else:
                values.append(str(val))
        md_lines.append("| " + " | ".join(values) + " |")

    markdown_table = "\n".join(md_lines)
    return markdown_table


async def main():
    llm_client = TongyiLLMClient(api_base=api_base, api_key=api_key, model=model)
    context: AgentContext = AgentContext(
        conv_id="test123", language="zh", temperature=0.5, max_new_tokens=2048
    )
    agent_memory = AgentMemory()
    agent_memory.gpts_memory.init(conv_id="test123")

    user_proxy = await UserProxyAgent().bind(agent_memory).bind(context).build()

    sql_boy = (
        await WebSearchAgent()
        .bind(context)
        .bind(LLMConfig(llm_client=llm_client))
        .bind(agent_memory)
        .build()
    )

    await user_proxy.initiate_chat(
        recipient=sql_boy, reviewer=user_proxy, message=f"今年的中秋节是多久？"
    )
    print(await agent_memory.gpts_memory.app_link_chat_message("test123"))


if __name__ == "__main__":
    asyncio.run(main())
