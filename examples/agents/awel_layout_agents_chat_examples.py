"""Agents: auto plan agents example?

    Examples:

        Execute the following command in the terminal:
        Set env params.
        .. code-block:: shell

            export OPENAI_API_KEY=sk-xx
            export OPENAI_API_BASE=https://xx:80/v1

        run example.
        ..code-block:: shell
            python examples/agents/auto_plan_agent_dialogue_example.py
"""

import asyncio
import os

from dbgpt.agent.agents.agent import AgentContext
from dbgpt.agent.agents.expand.plugin_assistant_agent import PluginAssistantAgent
from dbgpt.agent.agents.expand.summary_assistant_agent import SummaryAssistantAgent
from dbgpt.agent.agents.llm.llm import LLMConfig
from dbgpt.agent.agents.user_proxy_agent import UserProxyAgent
from dbgpt.agent.memory.gpts_memory import GptsMemory
from dbgpt.agent.resource.resource_api import AgentResource, ResourceType
from dbgpt.agent.resource.resource_loader import ResourceLoader
from dbgpt.agent.resource.resource_plugin_api import PluginFileLoadClient
from dbgpt.core.interface.llm import ModelMetadata
from dbgpt.serve.agent.team.layout.team_awel_layout import AwelLayoutChatManager

current_dir = os.getcwd()
parent_dir = os.path.dirname(current_dir)
test_plugin_dir = os.path.join(parent_dir, "test_files/plugins")


async def main():
    from dbgpt.model import OpenAILLMClient

    llm_client = OpenAILLMClient(model_alias="gpt-3.5-turbo")
    context: AgentContext = AgentContext(conv_id="test456", gpts_app_name="信息析助手")

    default_memory = GptsMemory()

    resource_loader = ResourceLoader()
    plugin_file_loader = PluginFileLoadClient()
    resource_loader.register_resesource_api(plugin_file_loader)

    plugin_resource = AgentResource(
        type=ResourceType.Plugin,
        name="test",
        value=test_plugin_dir,
    )

    tool_enginer = (
        await PluginAssistantAgent()
        .bind(context)
        .bind(LLMConfig(llm_client=llm_client))
        .bind(default_memory)
        .bind([plugin_resource])
        .bind(resource_loader)
        .build()
    )
    summarizer = (
        await SummaryAssistantAgent()
        .bind(context)
        .bind(default_memory)
        .bind(LLMConfig(llm_client=llm_client))
        .build()
    )

    manager = (
        await AwelLayoutChatManager()
        .bind(context)
        .bind(default_memory)
        .bind(LLMConfig(llm_client=llm_client))
        .build()
    )
    manager.hire([tool_enginer, summarizer])

    user_proxy = await UserProxyAgent().bind(context).bind(default_memory).build()

    await user_proxy.a_initiate_chat(
        recipient=manager,
        reviewer=user_proxy,
        message="查询成都今天天气",
        # message="查询今天的最新热点财经新闻",
        # message="Find papers on gpt-4 in the past three weeks on arxiv, and organize their titles, authors, and links into a markdown table",
        # message="find papers on LLM applications from arxiv in the last month, create a markdown table of different domains.",
    )

    print(await default_memory.one_chat_competions("test456"))


if __name__ == "__main__":
    ## dbgpt-vis message infos
    asyncio.run(main())
