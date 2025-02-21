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
from dbgpt.agent.resource import AutoGPTPluginToolPack
from dbgpt.configs.model_config import ROOT_PATH

test_plugin_dir = os.path.join(ROOT_PATH, "examples/test_files/plugins")


async def main():
    from dbgpt.model.proxy.llms.siliconflow import SiliconFlowLLMClient

    llm_client = SiliconFlowLLMClient(
        model_alias=os.getenv(
            "SILICONFLOW_MODEL_VERSION", "Qwen/Qwen2.5-Coder-32B-Instruct"
        ),
    )

    agent_memory = AgentMemory()
    agent_memory.gpts_memory.init(conv_id="test456")

    context: AgentContext = AgentContext(
        conv_id="test456", gpts_app_name="插件对话助手"
    )

    tools = AutoGPTPluginToolPack(test_plugin_dir)

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
        message="查询今天成都的天气",
    )

    # dbgpt-vis message infos
    print(await agent_memory.gpts_memory.app_link_chat_message("test456"))


if __name__ == "__main__":
    asyncio.run(main())
