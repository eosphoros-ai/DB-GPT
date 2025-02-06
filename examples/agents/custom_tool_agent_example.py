import asyncio
import logging
import os
import sys

from typing_extensions import Annotated, Doc

from dbgpt.agent import AgentContext, AgentMemory, LLMConfig, UserProxyAgent
from dbgpt.agent.expand.tool_assistant_agent import ToolAssistantAgent
from dbgpt.agent.resource import ToolPack, tool

logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)


@tool
def simple_calculator(first_number: int, second_number: int, operator: str) -> float:
    """Simple calculator tool. Just support +, -, *, /."""
    if isinstance(first_number, str):
        first_number = int(first_number)
    if isinstance(second_number, str):
        second_number = int(second_number)
    if operator == "+":
        return first_number + second_number
    elif operator == "-":
        return first_number - second_number
    elif operator == "*":
        return first_number * second_number
    elif operator == "/":
        return first_number / second_number
    else:
        raise ValueError(f"Invalid operator: {operator}")


@tool
def count_directory_files(path: Annotated[str, Doc("The directory path")]) -> int:
    """Count the number of files in a directory."""
    if not os.path.isdir(path):
        raise ValueError(f"Invalid directory path: {path}")
    return len(os.listdir(path))


async def main():
    from dbgpt.model.proxy.llms.siliconflow import SiliconFlowLLMClient

    llm_client = SiliconFlowLLMClient(
        model_alias=os.getenv(
            "SILICONFLOW_MODEL_VERSION", "Qwen/Qwen2.5-Coder-32B-Instruct"
        ),
    )
    agent_memory = AgentMemory()
    agent_memory.gpts_memory.init(conv_id="test456")

    context: AgentContext = AgentContext(conv_id="test456", gpts_app_name="工具助手")

    tools = ToolPack([simple_calculator, count_directory_files])

    user_proxy = await UserProxyAgent().bind(agent_memory).bind(context).build()

    tool_engineer = (
        await ToolAssistantAgent()
        .bind(context)
        .bind(LLMConfig(llm_client=llm_client))
        .bind(agent_memory)
        .bind(tools)
        .build()
    )

    await user_proxy.initiate_chat(
        recipient=tool_engineer,
        reviewer=user_proxy,
        message="Calculate the product of 10 and 99",
    )

    await user_proxy.initiate_chat(
        recipient=tool_engineer,
        reviewer=user_proxy,
        message="Count the number of files in /tmp",
    )

    # dbgpt-vis message infos
    print(await agent_memory.gpts_memory.app_link_chat_message("test456"))


if __name__ == "__main__":
    asyncio.run(main())
