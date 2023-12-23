from dbgpt.agent.agents.expand.code_assistant_agent import CodeAssistantAgent
from dbgpt.agent.agents.user_proxy_agent import UserProxyAgent
from dbgpt.agent.memory.gpts_memory import GptsMemory
from dbgpt.agent.agents.agent import AgentContext
import asyncio
import os

if __name__ == "__main__":

    context: AgentContext = AgentContext(conv_id="test456", gpts_name="测试助手2")
    context.llm_models = ["gpt-3.5-turbo"]

    default_memory = GptsMemory()
    coder = CodeAssistantAgent(
        memory=default_memory,
        agent_context=context
    )

    user_proxy = UserProxyAgent(
        memory=default_memory,
        agent_context=context
    )




    os.environ["OPENAI_API_KEY"] = "xxx"
    os.environ["OPENAI_API_BASE"] = "http://xxx:3000/api/openai/v1"

    asyncio.run(user_proxy.a_initiate_chat(
        recipient =coder,
        reviewer = user_proxy,
        message="用python代码的方式计算下321 * 123等于多少",
    ))