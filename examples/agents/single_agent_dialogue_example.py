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

from dbgpt.agent import AgentContext, AgentMemory, LLMConfig, UserProxyAgent
from dbgpt.agent.expand.code_assistant_agent import CodeAssistantAgent


async def main():
    from dbgpt.model.proxy.llms.siliconflow import SiliconFlowLLMClient

    llm_client = SiliconFlowLLMClient(
        model_alias=os.getenv(
            "SILICONFLOW_MODEL_VERSION", "Qwen/Qwen2.5-Coder-32B-Instruct"
        ),
    )

    context: AgentContext = AgentContext(conv_id="test123", gpts_app_name="代码助手")

    agent_memory = AgentMemory()
    agent_memory.gpts_memory.init(conv_id="test123")
    try:
        coder = (
            await CodeAssistantAgent()
            .bind(context)
            .bind(LLMConfig(llm_client=llm_client))
            .bind(agent_memory)
            .build()
        )

        user_proxy = await UserProxyAgent().bind(context).bind(agent_memory).build()

        await user_proxy.initiate_chat(
            recipient=coder,
            reviewer=user_proxy,
            message="计算下321 * 123等于多少",  # 用python代码的方式计算下321 * 123等于多少
            # message="download data from https://raw.githubusercontent.com/uwdata/draco/master/data/cars.csv and plot a visualization that tells us about the relationship between weight and horsepower. Save the plot to a file. Print the fields in a dataset before visualizing it.",
        )
    finally:
        agent_memory.gpts_memory.clear(conv_id="test123")


if __name__ == "__main__":
    asyncio.run(main())
