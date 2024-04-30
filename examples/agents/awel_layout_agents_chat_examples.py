"""Agents: auto plan agents example?

    Examples:

        Execute the following command in the terminal:
        Set env params.
        .. code-block:: shell

            export OPENAI_API_KEY=sk-xx
            export OPENAI_API_BASE=https://xx:80/v1

        run example.
        ..code-block:: shell
            python examples/agents/awel_layout_agents_chat_examples.py
"""

import asyncio
import os

from dbgpt.agent import (
    AgentContext,
    AgentMemory,
    AgentResource,
    LLMConfig,
    ResourceLoader,
    ResourceType,
    UserProxyAgent,
    WrappedAWELLayoutManager,
)
from dbgpt.agent.expand.plugin_assistant_agent import PluginAssistantAgent
from dbgpt.agent.expand.summary_assistant_agent import SummaryAssistantAgent
from dbgpt.agent.resource import PluginFileLoadClient
from dbgpt.configs.model_config import ROOT_PATH
from dbgpt.util.tracer import initialize_tracer

test_plugin_dir = os.path.join(ROOT_PATH, "examples/test_files/plugins")

initialize_tracer("/tmp/agent_trace.jsonl", create_system_app=True)


async def main():
    from dbgpt.model.proxy import OpenAILLMClient

    llm_client = OpenAILLMClient(model_alias="gpt-3.5-turbo")
    context: AgentContext = AgentContext(conv_id="test456", gpts_app_name="信息析助手")

    agent_memory = AgentMemory()
    resource_loader = ResourceLoader()
    plugin_file_loader = PluginFileLoadClient()
    resource_loader.register_resource_api(plugin_file_loader)

    plugin_resource = AgentResource(
        type=ResourceType.Plugin,
        name="test",
        value=test_plugin_dir,
    )

    tool_engineer = (
        await PluginAssistantAgent()
        .bind(context)
        .bind(LLMConfig(llm_client=llm_client))
        .bind(agent_memory)
        .bind([plugin_resource])
        .bind(resource_loader)
        .build()
    )
    summarizer = (
        await SummaryAssistantAgent()
        .bind(context)
        .bind(agent_memory)
        .bind(LLMConfig(llm_client=llm_client))
        .build()
    )

    manager = (
        await WrappedAWELLayoutManager()
        .bind(context)
        .bind(agent_memory)
        .bind(LLMConfig(llm_client=llm_client))
        .build()
    )
    manager.hire([tool_engineer, summarizer])

    user_proxy = await UserProxyAgent().bind(context).bind(agent_memory).build()

    await user_proxy.initiate_chat(
        recipient=manager,
        reviewer=user_proxy,
        message="查询成都今天天气",
        # message="查询今天的最新热点财经新闻",
        # message="Find papers on gpt-4 in the past three weeks on arxiv, and organize their titles, authors, and links into a markdown table",
        # message="find papers on LLM applications from arxiv in the last month, create a markdown table of different domains.",
    )

    print(await agent_memory.gpts_memory.one_chat_completions("test456"))


if __name__ == "__main__":
    ## dbgpt-vis message infos
    asyncio.run(main())
