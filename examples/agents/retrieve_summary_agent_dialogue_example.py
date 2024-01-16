"""Agents: single agents about CodeAssistantAgent?

    Examples:
     
        Execute the following command in the terminal:
        Set env params.
        .. code-block:: shell

            export OPENAI_API_KEY=sk-xx
            export OPENAI_API_BASE=https://xx:80/v1

        run example.
        ..code-block:: shell
            python examples/agents/retrieve_summary_agent_dialogue_example.py
"""

import asyncio
import os

from dbgpt.agent.agents.agent import AgentContext
from dbgpt.agent.agents.expand.retrieve_summary_assistant_agent import (
    RetrieveSummaryAssistantAgent,
)
from dbgpt.agent.agents.user_proxy_agent import UserProxyAgent
from dbgpt.agent.memory.gpts_memory import GptsMemory
from dbgpt.core.interface.llm import ModelMetadata


def summary_example_with_success():
    from dbgpt.model import OpenAILLMClient

    llm_client = OpenAILLMClient()
    context: AgentContext = AgentContext(
        conv_id="retrieve_summarize", llm_provider=llm_client
    )
    context.llm_models = [ModelMetadata(model="gpt-3.5-turbo-16k")]

    default_memory = GptsMemory()
    summarizer = RetrieveSummaryAssistantAgent(
        memory=default_memory, agent_context=context
    )

    user_proxy = UserProxyAgent(memory=default_memory, agent_context=context)

    asyncio.run(
        user_proxy.a_initiate_chat(
            recipient=summarizer,
            reviewer=user_proxy,
            message="""I want to summarize advantages of Nuclear Power. 
            You can refer the following file pathes and URLs: ['/home/ubuntu/DB-GPT/examples/Nuclear_power.pdf', 'https://en.wikipedia.org/wiki/Modern_Family', '/home/ubuntu/DB-GPT/examples/Taylor_Swift.pdf', 'https://en.wikipedia.org/wiki/Chernobyl_disaster']
            """,
        )
    )

    ## dbgpt-vis message infos
    print(asyncio.run(default_memory.one_plan_chat_competions("retrieve_summarize")))


if __name__ == "__main__":
    print(
        "\033[92m=======================Start The Summary Assistant with Successful Results==================\033[0m"
    )
    summary_example_with_success()
    print(
        "\033[92m=======================The Summary Assistant with Successful Results Ended==================\n\n\033[91m"
    )
