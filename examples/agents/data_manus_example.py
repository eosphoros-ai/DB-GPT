import asyncio
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from dbgpt.agent import (
    AgentContext,
    AgentMemory,
    AutoPlanChatManager,
    LLMConfig,
    UserProxyAgent,
)
from dbgpt.agent.expand.actions.insert_action import Excel2TableAction
from dbgpt.agent.expand.data_scientist_agent import DataScientistAgent
from dbgpt.agent.expand.excel_table_agent import Excel2TableAgent, excel_files
from dbgpt.agent.expand.web_assistant_agent import WebSearchAgent
from dbgpt.agent.resource import RDBMSConnectorResource
from dbgpt.model.proxy import OpenAILLMClient, TongyiLLMClient
from dbgpt_ext.datasource.rdbms.conn_sqlite import SQLiteConnector

connector = SQLiteConnector.from_file_path("../test_files/datamanus_test.db")
db_resource = RDBMSConnectorResource("user_manager", connector=connector)
api_base = "https://dashscope.aliyuncs.com/compatible-mode/v1"
api_key = "sk-xxx"
model = "qwq-32b"


def read_excel_headers_and_data(
    file_path: str, read_rows: Optional[int] = 3
) -> Tuple[List[str], List[Dict[str, Any]]]:
    """
    读取Excel文件，返回表头信息和结构化数据（支持指定读取行数）

    参数:
        file_path: Excel文件路径（.xlsx格式）
        read_rows: 可选，指定读取的数据行数（不含表头）。
                   - 默认为5：仅读取前5行数据
                   - 设为None或0：读取全部数据
                   - 设为正整数N：读取前N行数据（若数据总行数不足N，则读取实际所有行）

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

    total_data_rows = len(df)
    if read_rows in (None, 0):
        target_rows = total_data_rows
    elif isinstance(read_rows, int) and read_rows > 0:
        target_rows = min(read_rows, total_data_rows)
    else:
        raise ValueError(f"参数read_rows无效：{read_rows}，仅支持正整数、None或0")

    df_target = df.head(target_rows)

    data = []
    for _, row in df_target.iterrows():
        row_data = {
            header: (row[header] if row[header] != "" else None) for header in headers
        }
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
    all_file_data = []
    # To read some data from Excel files, you can go to excel_table_agent.py
    # by yourself and replace the excel_file variable
    # as the default directory where the excel file is located
    for excel_file in excel_files:
        filename_with_ext = os.path.basename(excel_file)
        headers, table_data = read_excel_headers_and_data(excel_file)
        mdstr = data2md(headers, table_data)
        all_file_data.append((filename_with_ext, mdstr))

    llm_client = TongyiLLMClient(api_base=api_base, api_key=api_key, model=model)
    context: AgentContext = AgentContext(
        conv_id="test123", language="zh", temperature=0.5, max_new_tokens=2048
    )
    agent_memory = AgentMemory()
    agent_memory.gpts_memory.init(conv_id="test123")

    user_proxy = await UserProxyAgent().bind(agent_memory).bind(context).build()

    excel_boy = (
        await Excel2TableAgent()
        .bind(context)
        .bind(LLMConfig(llm_client=llm_client))
        .bind(db_resource)
        .bind(agent_memory)
        .build()
    )

    sql_boy = (
        await DataScientistAgent()
        .bind(context)
        .bind(LLMConfig(llm_client=llm_client))
        .bind(db_resource)
        .bind(agent_memory)
        .build()
    )

    web_boy = (
        await WebSearchAgent()
        .bind(context)
        .bind(LLMConfig(llm_client=llm_client))
        .bind(agent_memory)
        .build()
    )

    manager = (
        await AutoPlanChatManager()
        .bind(context)
        .bind(agent_memory)
        .bind(LLMConfig(llm_client=llm_client))
        .build()
    )
    manager.hire([sql_boy])
    manager.hire([excel_boy])
    manager.hire([web_boy])

    message_parts = ["我读取到以下Excel文件的数据："]
    for i, (filename, mdstr) in enumerate(all_file_data, 1):
        message_parts.append(f"\n文件 {i}: {filename}")
        message_parts.append(f"数据内容：\n{mdstr}")
    full_message = (
        "\n".join(message_parts) + "\n\n\n截止今年中秋节之前哪些员工还有项目没有结项？"
    )
    print("完整消息内容：" + full_message)
    await user_proxy.initiate_chat(
        recipient=manager,
        reviewer=user_proxy,
        message=full_message,
    )

    print(await agent_memory.gpts_memory.app_link_chat_message("test123"))


if __name__ == "__main__":
    asyncio.run(main())
