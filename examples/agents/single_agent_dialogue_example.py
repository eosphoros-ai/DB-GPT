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
from dbgpt.agent.agents.expand.code_assistant_agent import CodeAssistantAgent
from dbgpt.agent.agents.user_proxy_agent import UserProxyAgent
from dbgpt.agent.memory.gpts_memory import GptsMemory
from dbgpt.core.interface.llm import ModelMetadata

if __name__ == "__main__":
    from dbgpt.model.proxy import OpenAILLMClient

    llm_client = OpenAILLMClient()
    context: AgentContext = AgentContext(conv_id="test456", llm_provider=llm_client)
    context.llm_models = [ModelMetadata(model="gpt-3.5-turbo")]

    default_memory = GptsMemory()
    coder = CodeAssistantAgent(memory=default_memory, agent_context=context)

    user_proxy = UserProxyAgent(memory=default_memory, agent_context=context)

    asyncio.run(
        user_proxy.a_initiate_chat(
            recipient=coder,
            reviewer=user_proxy,
            message="式计算下321 * 123等于多少",  # 用python代码的方式计算下321 * 123等于多少
            # message="download data from https://raw.githubusercontent.com/uwdata/draco/master/data/cars.csv and plot a visualization that tells us about the relationship between weight and horsepower. Save the plot to a file. Print the fields in a dataset before visualizing it.",
        )
    )

    ## dbgpt-vis message infos
    print(asyncio.run(default_memory.one_plan_chat_competions("test456")))
