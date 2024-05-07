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
    AgentMemory,
    AgentResource,
    LLMConfig,
    ResourceLoader,
    ResourceType,
    UserProxyAgent,
)
from dbgpt.agent.expand.data_scientist_agent import DataScientistAgent
from dbgpt.agent.resource import SqliteLoadClient
from dbgpt.util.tracer import initialize_tracer

current_dir = os.getcwd()
parent_dir = os.path.dirname(current_dir)
test_plugin_dir = os.path.join(parent_dir, "test_files")

initialize_tracer("/tmp/agent_trace.jsonl", create_system_app=True)


async def main():
    from dbgpt.model.proxy.llms.chatgpt import OpenAILLMClient

    agent_memory = AgentMemory()

    llm_client = OpenAILLMClient(model_alias="gpt-3.5-turbo")
    context: AgentContext = AgentContext(conv_id="test456")

    db_resource = AgentResource(
        type=ResourceType.DB,
        name="TestData",
        value=f"{test_plugin_dir}/dbgpt.db",
    )

    resource_loader = ResourceLoader()
    sqlite_file_loader = SqliteLoadClient()
    resource_loader.register_resource_api(sqlite_file_loader)

    user_proxy = await UserProxyAgent().bind(agent_memory).bind(context).build()

    sql_boy = (
        await DataScientistAgent()
        .bind(context)
        .bind(LLMConfig(llm_client=llm_client))
        .bind([db_resource])
        .bind(resource_loader)
        .bind(agent_memory)
        .build()
    )

    await user_proxy.initiate_chat(
        recipient=sql_boy,
        reviewer=user_proxy,
        message="当前库有那些表",
    )

    ## dbgpt-vis message infos
    print(await agent_memory.gpts_memory.one_chat_completions("test456"))


if __name__ == "__main__":
    asyncio.run(main())
