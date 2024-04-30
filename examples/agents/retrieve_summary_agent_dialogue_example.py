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

from dbgpt.agent import AgentContext, AgentMemory, LLMConfig, UserProxyAgent
from dbgpt.agent.expand.retrieve_summary_assistant_agent import (
    RetrieveSummaryAssistantAgent,
)
from dbgpt.configs.model_config import ROOT_PATH


async def summary_example_with_success():
    from dbgpt.model.proxy import OpenAILLMClient

    llm_client = OpenAILLMClient(model_alias="gpt-3.5-turbo-16k")
    context: AgentContext = AgentContext(conv_id="retrieve_summarize")
    agent_memory = AgentMemory()
    summarizer = (
        await RetrieveSummaryAssistantAgent()
        .bind(context)
        .bind(LLMConfig(llm_client=llm_client))
        .bind(agent_memory)
        .build()
    )

    user_proxy = UserProxyAgent(memory=agent_memory, agent_context=context)

    paths_urls = [
        os.path.join(ROOT_PATH, "examples/agents/example_files/Nuclear_power.pdf"),
        os.path.join(ROOT_PATH, "examples/agents/example_files/Taylor_Swift.pdf"),
        "https://en.wikipedia.org/wiki/Modern_Family",
        "https://en.wikipedia.org/wiki/Chernobyl_disaster",
    ]

    await user_proxy.initiate_chat(
        recipient=summarizer,
        reviewer=user_proxy,
        message=f"I want to summarize advantages of Nuclear Power. You can refer the "
        f"following file paths and URLs: {paths_urls}",
    )

    # dbgpt-vis message infos
    print(await agent_memory.gpts_memory.one_chat_completions("retrieve_summarize"))


if __name__ == "__main__":
    asyncio.run(summary_example_with_success())
    print(
        "\033[92m=======================The Summary Assistant with Successful Results Ended==================\n\n\033[91m"
    )
