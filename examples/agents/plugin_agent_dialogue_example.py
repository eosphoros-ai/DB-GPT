"""Agents: single agents about CodeAssistantAgent?

    Examples:

        Execute the following command in the terminal:
        Set env params.
        .. code-block:: shell

            export OPENAI_API_KEY=sk-xx
            export OPENAI_API_BASE=https://xx:80/v1

        run example.
        ..code-block:: shell
            python examples/agents/single_agent_dialogue_example.py
"""

import asyncio
import os

from dbgpt.agent.agents.agent import AgentContext
from dbgpt.agent.agents.expand.plugin_assistant_agent import PluginAssistantAgent
from dbgpt.agent.agents.user_proxy_agent import UserProxyAgent
from dbgpt.agent.memory.gpts_memory import GptsMemory
from dbgpt.core.interface.llm import ModelMetadata

if __name__ == "__main__":
    from dbgpt.model import OpenAILLMClient

    llm_client = OpenAILLMClient()
    context: AgentContext = AgentContext(conv_id="test456", llm_provider=llm_client)
    context.llm_models = [ModelMetadata(model="gpt-3.5-turbo")]

    default_memory = GptsMemory()
    tool_enginer = PluginAssistantAgent(
        memory=default_memory,
        agent_context=context,
        plugin_path="/Users/tuyang.yhj/Code/python/DB-GPT/plugins",
    )

    user_proxy = UserProxyAgent(memory=default_memory, agent_context=context)

    asyncio.run(
        user_proxy.a_initiate_chat(
            recipient=tool_enginer,
            reviewer=user_proxy,
            message="查询今天成都的天气",
        )
    )

    ## dbgpt-vis message infos
    print(asyncio.run(default_memory.one_plan_chat_competions("test456")))
