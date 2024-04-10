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

from dbgpt.agent import (
    AgentContext,
    AgentResource,
    GptsMemory,
    LLMConfig,
    ResourceLoader,
    ResourceType,
    UserProxyAgent,
)
from dbgpt.agent.expand.plugin_assistant_agent import PluginAssistantAgent
from dbgpt.agent.resource import PluginFileLoadClient

current_dir = os.getcwd()
parent_dir = os.path.dirname(current_dir)
test_plugin_dir = os.path.join(parent_dir, "test_files/plugins")


async def main():
    from dbgpt.model.proxy import OpenAILLMClient

    llm_client = OpenAILLMClient(model_alias="gpt-3.5-turbo")
    context: AgentContext = AgentContext(conv_id="test456")

    default_memory: GptsMemory = GptsMemory()

    plugin_resource = AgentResource(
        type=ResourceType.Plugin,
        name="test",
        value=test_plugin_dir,
    )

    resource_loader = ResourceLoader()
    plugin_file_loader = PluginFileLoadClient()
    resource_loader.register_resource_api(plugin_file_loader)

    user_proxy = await UserProxyAgent().bind(default_memory).bind(context).build()

    tool_engineer = (
        await PluginAssistantAgent()
        .bind(context)
        .bind(LLMConfig(llm_client=llm_client))
        .bind(default_memory)
        .bind([plugin_resource])
        .bind(resource_loader)
        .build()
    )

    await user_proxy.initiate_chat(
        recipient=tool_engineer,
        reviewer=user_proxy,
        message="查询今天成都的天气",
    )

    ## dbgpt-vis message infos
    print(await default_memory.one_chat_completions("test456"))


if __name__ == "__main__":
    asyncio.run(main())
