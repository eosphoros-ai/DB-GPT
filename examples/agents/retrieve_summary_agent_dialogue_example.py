"""Agents: single agents about CodeAssistantAgent?

Examples:

    Execute the following command in the terminal:
    Set env params.
    .. code-block:: shell

        export SILICONFLOW_API_KEY=sk-xx
        export SILICONFLOW_API_BASE=https://xx:80/v1

    run example.
    ..code-block:: shell
        python examples/agents/retrieve_summary_agent_dialogue_example.py
"""

import asyncio
import os

from dbgpt.agent import AgentContext, AgentMemory, LLMConfig, UserProxyAgent
from dbgpt.agent.expand.summary_assistant_agent import SummaryAssistantAgent
from dbgpt.configs.model_config import ROOT_PATH


async def main():
    from dbgpt.model.proxy.llms.siliconflow import SiliconFlowLLMClient

    llm_client = SiliconFlowLLMClient(
        model_alias=os.getenv(
            "SILICONFLOW_MODEL_VERSION", "Qwen/Qwen2.5-Coder-32B-Instruct"
        ),
    )
    context: AgentContext = AgentContext(
        conv_id="retrieve_summarize", gpts_app_name="Summary Assistant"
    )

    agent_memory = AgentMemory()
    agent_memory.gpts_memory.init(conv_id="retrieve_summarize")

    summarizer = (
        await SummaryAssistantAgent()
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

    # TODO add a tool to load the pdf and internet files
    await user_proxy.initiate_chat(
        recipient=summarizer,
        reviewer=user_proxy,
        message=f"I want to summarize advantages of Nuclear Power. You can refer the "
        f"following file paths and URLs: {paths_urls}",
    )

    # dbgpt-vis message infos
    print(await agent_memory.gpts_memory.app_link_chat_message("retrieve_summarize"))


if __name__ == "__main__":
    asyncio.run(main())
