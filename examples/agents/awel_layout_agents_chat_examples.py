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
from dbgpt.agent.agents.user_proxy_agent import UserProxyAgent
from dbgpt.agent.memory.gpts_memory import GptsMemory
from dbgpt.core.interface.llm import ModelMetadata
from dbgpt.serve.agent.team.layout.team_awel_layout import AwelLayoutChatManger

current_dir = os.getcwd()
parent_dir = os.path.dirname(current_dir)
test_plugin_dir = os.path.join(parent_dir, "test_files")

if __name__ == "__main__":
    from dbgpt.model import OpenAILLMClient

    llm_client = OpenAILLMClient()
    context: AgentContext = AgentContext(conv_id="test456", llm_provider=llm_client)
    context.llm_models = [ModelMetadata(model="gpt-3.5-turbo")]
    context.gpts_name = "信息析助手"

    default_memory = GptsMemory()
    manager = AwelLayoutChatManger(
        agent_context=context,
        memory=default_memory,
    )

    ### agents
    tool_enginer = PluginAssistantAgent(
        agent_context=context,
        memory=default_memory,
        plugin_path=test_plugin_dir,
    )
    summarizer = SummaryAssistantAgent(
        agent_context=context,
        memory=default_memory,
    )

    manager.hire([tool_enginer, summarizer])

    user_proxy = UserProxyAgent(memory=default_memory, agent_context=context)

    asyncio.run(
        user_proxy.a_initiate_chat(
            recipient=manager,
            reviewer=user_proxy,
            message="查询成都今天天气",
            # message="查询今天的最新热点财经新闻",
            # message="Find papers on gpt-4 in the past three weeks on arxiv, and organize their titles, authors, and links into a markdown table",
            # message="find papers on LLM applications from arxiv in the last month, create a markdown table of different domains.",
        )
    )

    ## dbgpt-vis message infos
    print(asyncio.run(default_memory.one_plan_chat_competions("test456")))
