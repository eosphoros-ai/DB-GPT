"""Agents: single agents about CodeAssistantAgent?

    Examples:

        Execute the following command in the terminal:
        Set env params.
        .. code-block:: shell

            export OPENAI_API_KEY=sk-xx
            export OPENAI_API_BASE=https://xx:80/v1

        run example.
        ..code-block:: shell
            python examples/agents/plugin_agent_dialogue_example.py
"""

import asyncio
import os

from dbgpt.agent import AgentContext, AgentMemory, LLMConfig, UserProxyAgent
from dbgpt.agent.expand.tool_assistant_agent import ToolAssistantAgent
from dbgpt.agent.resource import AutoGPTPluginToolPack

current_dir = os.getcwd()
parent_dir = os.path.dirname(current_dir)
test_plugin_dir = os.path.join(parent_dir, "test_files/plugins")


async def main():
    from dbgpt.model.proxy import OpenAILLMClient

    llm_client = OpenAILLMClient(model_alias="gpt-3.5-turbo")
    context: AgentContext = AgentContext(conv_id="test456")

    agent_memory = AgentMemory()

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
    print(await agent_memory.gpts_memory.one_chat_completions("test456"))


if __name__ == "__main__":
    asyncio.run(main())
