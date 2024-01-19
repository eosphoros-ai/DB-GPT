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
from dbgpt.agent.agents.agents_mange import agent_mange
from dbgpt.agent.agents.expand.code_assistant_agent import CodeAssistantAgent
from dbgpt.agent.agents.planner_agent import PlannerAgent
from dbgpt.agent.agents.user_proxy_agent import UserProxyAgent
from dbgpt.agent.memory.gpts_memory import GptsMemory
from dbgpt.core.interface.llm import ModelMetadata
from dbgpt.serve.agent.team.plan.team_auto_plan import AutoPlanChatManager

if __name__ == "__main__":
    from dbgpt.model.proxy import OpenAILLMClient

    llm_client = OpenAILLMClient()
    context: AgentContext = AgentContext(conv_id="test456", llm_provider=llm_client)
    context.llm_models = [ModelMetadata(model="gpt-3.5-turbo")]
    # context.llm_models = [ModelMetadata(model="gpt-4-vision-preview")]
    context.gpts_name = "代码分析助手"

    default_memory = GptsMemory()
    coder = CodeAssistantAgent(memory=default_memory, agent_context=context)
    ## TODO  add other agent

    manager = AutoPlanChatManager(
        agent_context=context,
        memory=default_memory,
    )
    manager.hire([coder])

    user_proxy = UserProxyAgent(memory=default_memory, agent_context=context)

    asyncio.run(
        user_proxy.a_initiate_chat(
            recipient=manager,
            reviewer=user_proxy,
            message="Obtain simple information about issues in the repository 'eosphoros-ai/DB-GPT' in the past three days and analyze the data. Create a Markdown table grouped by day and status.",
            # message="Find papers on gpt-4 in the past three weeks on arxiv, and organize their titles, authors, and links into a markdown table",
            # message="find papers on LLM applications from arxiv in the last month, create a markdown table of different domains.",
        )
    )

    ## dbgpt-vis message infos
    print(asyncio.run(default_memory.one_plan_chat_competions("test456")))
