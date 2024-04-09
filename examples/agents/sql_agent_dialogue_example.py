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

from dbgpt.agent import (
    AgentContext,
    AgentResource,
    GptsMemory,
    LLMConfig,
    ResourceLoader,
    ResourceType,
    UserProxyAgent,
)
from dbgpt.agent.expand.data_scientist_agent import DataScientistAgent
from dbgpt.agent.resource import SqliteLoadClient

current_dir = os.getcwd()
parent_dir = os.path.dirname(current_dir)
test_plugin_dir = os.path.join(parent_dir, "test_files")


async def main():
    from dbgpt.model.proxy.llms.chatgpt import OpenAILLMClient

    llm_client = OpenAILLMClient(model_alias="gpt-3.5-turbo")
    context: AgentContext = AgentContext(conv_id="test456")

    default_memory: GptsMemory = GptsMemory()

    db_resource = AgentResource(
        type=ResourceType.DB,
        name="TestData",
        value=f"{test_plugin_dir}/dbgpt.db",
    )

    resource_loader = ResourceLoader()
    sqlite_file_loader = SqliteLoadClient()
    resource_loader.register_resource_api(sqlite_file_loader)

    user_proxy = await UserProxyAgent().bind(default_memory).bind(context).build()

    sql_boy = (
        await DataScientistAgent()
        .bind(context)
        .bind(LLMConfig(llm_client=llm_client))
        .bind(default_memory)
        .bind([db_resource])
        .bind(resource_loader)
        .build()
    )

    await user_proxy.initiate_chat(
        recipient=sql_boy,
        reviewer=user_proxy,
        message="当前库有那些表",
    )

    ## dbgpt-vis message infos
    print(await default_memory.one_chat_completions("test456"))


if __name__ == "__main__":
    asyncio.run(main())
