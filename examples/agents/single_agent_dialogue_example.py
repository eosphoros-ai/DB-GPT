from dbgpt.agent.agents.expand.code_assistant_agent import CodeAssistantAgent
from dbgpt.agent.agents.user_proxy_agent import UserProxyAgent
from dbgpt.agent.memory.gpts_memory import GptsMemory
from dbgpt.agent.agents.agent import AgentContext
import asyncio

if __name__ == "__main__":

    context: AgentContext = AgentContext(conv_id="test456", gpts_name="测试助手2")
    context.llm_models = ["chatgpt_proxyllm"]

    default_memory = GptsMemory()
    coder = CodeAssistantAgent(
        memory=default_memory,
        agent_context=context
    )

    user_proxy = UserProxyAgent(
        memory=default_memory,
        agent_context=context
    )
    asyncio.run(user_proxy.a_initiate_chat(
        recipient =coder,
        reviewer = user_proxy,
        message="用python代码的方式计算下321 * 123等于多少",
        memory=common_memory,
    ))