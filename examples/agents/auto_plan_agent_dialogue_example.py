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

from dbgpt.agent import (
    AgentContext,
    GptsMemory,
    LLMConfig,
    ResourceLoader,
    UserProxyAgent,
)
from dbgpt.agent.expand.code_assistant_agent import CodeAssistantAgent
from dbgpt.agent.plan import AutoPlanChatManager


async def main():
    from dbgpt.model.proxy import OpenAILLMClient

    llm_client = OpenAILLMClient(model_alias="gpt-4")
    context: AgentContext = AgentContext(conv_id="test456", gpts_app_name="代码分析助手")

    default_memory = GptsMemory()

    resource_loader = ResourceLoader()

    coder = (
        await CodeAssistantAgent()
        .bind(context)
        .bind(LLMConfig(llm_client=llm_client))
        .bind(default_memory)
        .bind(resource_loader)
        .build()
    )

    manager = (
        await AutoPlanChatManager()
        .bind(context)
        .bind(default_memory)
        .bind(LLMConfig(llm_client=llm_client))
        .build()
    )
    manager.hire([coder])

    user_proxy = await UserProxyAgent().bind(context).bind(default_memory).build()

    await user_proxy.initiate_chat(
        recipient=manager,
        reviewer=user_proxy,
        message="Obtain simple information about issues in the repository 'eosphoros-ai/DB-GPT' in the past three days and analyze the data. Create a Markdown table grouped by day and status.",
        # message="Find papers on gpt-4 in the past three weeks on arxiv, and organize their titles, authors, and links into a markdown table",
        # message="find papers on LLM applications from arxiv in the last month, create a markdown table of different domains.",
    )

    print(await default_memory.one_chat_completions("test456"))


if __name__ == "__main__":
    ## dbgpt-vis message infos
    asyncio.run(main())
