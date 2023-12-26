from dbgpt.agent.agents.planner_agent import PlannerAgent
from dbgpt.agent.agents.user_proxy_agent import UserProxyAgent
from dbgpt.agent.agents.plan_group_chat import PlanChat, PlanChatManager

from dbgpt.agent.agents.expand.code_assistant_agent import CodeAssistantAgent
from dbgpt.agent.agents.expand.plugin_assistant_agent import PluginAgent
from dbgpt.agent.agents.agents_mange import agent_mange

from dbgpt.agent.agents.agent import AgentContext
from dbgpt.agent.memory.gpts_memory import GptsMemory

import asyncio
import os

if __name__ == "__main__":
    from dbgpt.model import OpenAILLMClient

    llm_client = OpenAILLMClient()
    context: AgentContext = AgentContext(conv_id="test456", llm_provider=llm_client)
    context.llm_models = ["gpt-3.5-turbo"]

    default_memory = GptsMemory()
    coder = CodeAssistantAgent(memory=default_memory, agent_context=context)
    ## TODO  add other agent

    groupchat = PlanChat(agents=[coder], messages=[], max_round=50)
    planner = PlannerAgent(
        agent_context=context,
        memory=default_memory,
        plan_chat=groupchat,
    )

    manager = PlanChatManager(
        plan_chat=groupchat,
        planner=planner,
        agent_context=context,
        memory=default_memory,
    )

    user_proxy = UserProxyAgent(memory=default_memory, agent_context=context)

    os.environ["OPENAI_API_KEY"] = "sk-xx"
    os.environ["OPENAI_API_BASE"] = "https://xx:80/v1"

    asyncio.run(
        user_proxy.a_initiate_chat(
            recipient=manager,
            reviewer=user_proxy,
            message="download data from https://raw.githubusercontent.com/uwdata/draco/master/data/cars.csv and plot a visualization that tells us about the relationship between weight and horsepower. Save the plot to a file. Print the fields in a dataset before visualizing it.",
            # message="find papers on LLM applications from arxiv in the last week, create a markdown table of different domains.",
        )
    )

    ## dbgpt-vis message infos
    print(asyncio.run(default_memory.one_plan_chat_competions("test123")))
