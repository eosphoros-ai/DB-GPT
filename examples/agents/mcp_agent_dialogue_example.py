"""Agents: single agents about CodeAssistantAgent?

Examples:

    Execute the following command in the terminal:
    Set env params.
    .. code-block:: shell

        export SILICONFLOW_API_KEY=sk-xx
        export SILICONFLOW_API_BASE=https://xx:80/v1

    run example.
    ..code-block:: shell
        python examples/agents/plugin_agent_dialogue_example.py
"""

import asyncio
import os

from dbgpt.agent import AgentContext, AgentMemory, LLMConfig, UserProxyAgent
from dbgpt.agent.expand.tool_assistant_agent import ToolAssistantAgent
from dbgpt.agent.resource import AutoGPTPluginToolPack, MCPToolPack
from dbgpt.configs.model_config import ROOT_PATH
from dbgpt.model.proxy import SiliconFlowLLMClient

test_plugin_dir = os.path.join(ROOT_PATH, "examples/test_files/plugins")


async def main():
    ### Test method
    # 1.start mcp server as a sse server
    # Reference https://github.com/supercorp-ai/supergateway
    # npx -y supergateway --stdio "uvx mcp-server-fetch"
    # or
    # npx -y supergateway --stdio "npx -y @modelcontextprotocol/server-filesystem ./"
    ## ./ 可以替换为你需要代理的目录

    # 2.bind dbgpt resource MCPToolPack use mcp sse server lisk this：
    # MCPToolPack("http://127.0.0.1:8000/sse")

    llm_client = SiliconFlowLLMClient(
        model_alias=os.getenv(
            "SILICONFLOW_MODEL_VERSION", "Qwen/Qwen2.5-Coder-32B-Instruct"
        ),
    )

    agent_memory = AgentMemory()
    agent_memory.gpts_memory.init(conv_id="test456")

    context: AgentContext = AgentContext(
        conv_id="test456", gpts_app_name="MCP工具对话助手"
    )

    tools = MCPToolPack("http://127.0.0.1:8000/sse")

    user_proxy = await UserProxyAgent().bind(agent_memory).bind(context).build()

    tool_engineer = (
        await ToolAssistantAgent()
        .bind(context)
        .bind(LLMConfig(llm_client=llm_client))
        .bind(agent_memory)
        .bind(tools)
        .build()
    )

    await user_proxy.initiate_chat(
        recipient=tool_engineer,
        reviewer=user_proxy,
        message="看下这个页面: https://www.cnblogs.com/fnng/p/18744210",  ##配合 mcp-server-fetch 使用
        # message="有多少个文件", ## 配合server-filesystem 这个mcp使用
    )

    # dbgpt-vis message infos
    print(await agent_memory.gpts_memory.app_link_chat_message("test456"))


if __name__ == "__main__":
    asyncio.run(main())
