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
    LLMConfig,
    UserProxyAgent,
    WrappedAWELLayoutManager,
)
from dbgpt.agent.expand.resources.search_tool import baidu_search
from dbgpt.agent.expand.summary_assistant_agent import SummaryAssistantAgent
from dbgpt.agent.expand.tool_assistant_agent import ToolAssistantAgent
from dbgpt.agent.resource import ToolPack
from dbgpt.util.tracer import initialize_tracer

initialize_tracer("/tmp/agent_trace.jsonl", create_system_app=True)


async def main():
    from dbgpt.model.proxy import OpenAILLMClient

    agent_memory = AgentMemory()
    agent_memory.gpts_memory.init(conv_id="test456")
    try:
        from dbgpt.model.proxy.llms.tongyi import TongyiLLMClient

        llm_client = TongyiLLMClient(
            model_alias="qwen2-72b-instruct",
        )

        context: AgentContext = AgentContext(conv_id="test456", gpts_app_name="信息析助手")

        tools = ToolPack([baidu_search])
        tool_engineer = (
            await ToolAssistantAgent()
            .bind(context)
            .bind(LLMConfig(llm_client=llm_client))
            .bind(agent_memory)
            .bind(tools)
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
            message="查询北京今天天气",
            # message="查询今天的最新热点财经新闻",
            # message="Find papers on gpt-4 in the past three weeks on arxiv, and organize their titles, authors, and links into a markdown table",
            # message="find papers on LLM applications from arxiv in the last month, create a markdown table of different domains.",
        )

    finally:
        agent_memory.gpts_memory.clear(conv_id="test456")


if __name__ == "__main__":
    ## dbgpt-vis message infos
    asyncio.run(main())
