import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from dbgpt.agent import AgentContext, AgentMemory, LLMConfig, UserProxyAgent
from dbgpt.agent.expand.actions.insert_action import Excel2TableAction
from dbgpt.agent.expand.data_scientist_agent import DataScientistAgent
from dbgpt.agent.expand.excel_table_agent import Excel2TableAgent
from dbgpt.agent.resource import RDBMSConnectorResource
from dbgpt.model.proxy import TongyiLLMClient
from dbgpt_ext.datasource.rdbms.conn_sqlite import SQLiteConnector

connector = SQLiteConnector.from_file_path(
    "../test_files/datamanus_test.db"
)
db_resource = RDBMSConnectorResource("user_manager", connector=connector)
api_base = "https://dashscope.aliyuncs.com/compatible-mode/v1"
api_key = "sk-xxx"
model = "qwen3-32b"

# 待分析的所有Excel文件所在目录
excel_path = "../test_files"

def find_excel_files(directory: str) -> list[str]:
        """
        查找指定目录下所有.csv和.xlsx文件，并返回它们的绝对路径
        
        参数:
            directory: 要搜索的目录路径
            
        返回:
            包含所有.csv和.xlsx文件绝对路径的列表，如果目录不存在则返回空列表
        """
        # 检查目录是否存在
        if not os.path.isdir(directory):
            print(f"错误: 目录 '{directory}' 不存在")
            return []
        
        # 存储结果的列表
        file_paths = []
        
        # 遍历目录及其子目录
        for root, dirs, files in os.walk(directory):
            for file in files:
                # 检查文件扩展名
                if file.lower().endswith(('.csv', '.xlsx')):
                    # 获取文件的绝对路径并添加到列表
                    absolute_path = os.path.abspath(os.path.join(root, file))
                    file_paths.append(absolute_path)
        
        return file_paths

def read_excel_headers_and_data(
    file_path: str,
) -> Tuple[List[str], List[Dict[str, Any]]]:
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
    excel_files = find_excel_files(excel_path)
    all_file_data = []
    # 读取Excel部分文件数据，可自行替换
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

    message_parts = ["我读取到以下Excel文件的数据："]
    for i, (filename, mdstr) in enumerate(all_file_data, 1):
        message_parts.append(f"\n文件 {i}: {filename}")
        message_parts.append(f"数据内容：\n{mdstr}")
    full_message = (
        "\n".join(message_parts)
        + "\n请帮我分析这些数据，为每个文件生成对应的建表语句和插入语句，并执行这些SQL语句创建数据表并插入数据。"
    )

    await user_proxy.initiate_chat(
        recipient=excel_boy,
        reviewer=user_proxy,
        message=full_message,
    )

    print(await agent_memory.gpts_memory.app_link_chat_message("test123"))


if __name__ == "__main__":
    asyncio.run(main())
