# Tool Use

While LLMs can complete a wide range of tasks, they may not work well for the domains 
which need comprehensive expert knowledge. In addition, LLMs may also encounter 
hallucination problems, which are hard to be resolved by themselves.

So, we need to use some tools to help LLMs to complete the tasks.

:::note
In DB-GPT agents, most LLMs support tool calls as long as their own capabilities are not too weak.
(Such as `glm-4-9b-chat`, `Yi-1.5-34B-Chat`, `Qwen2-72B-Instruct`, etc.)
:::

## Writing Tools

Sometimes, LLMs may not be able to complete the calculation tasks directly, so we can 
write a simple calculator tool to help them.
```python
from dbgpt.agent.resource import tool

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
```

To test multiple tools,  let's write another tool to help LLMs to count the number of files in a directory.

```python
import os
from typing_extensions import Annotated, Doc

@tool
def count_directory_files(path: Annotated[str, Doc("The directory path")]) -> int:
    """Count the number of files in a directory."""
    if not os.path.isdir(path):
        raise ValueError(f"Invalid directory path: {path}")
    return len(os.listdir(path))
```
## Wrap Your Tools To `ToolPack`

Most of the time, you may have multiple tools, so you can wrap them to a `ToolPack`.
`ToolPack` is a collection of tools, you can use it to manage your tools, and the agent 
can select the appropriate tool from the `ToolPack` according to the task requirements.

```python
from dbgpt.agent.resource import ToolPack

tools = ToolPack([simple_calculator, count_directory_files])
```

## Use Tools In Your Agent

```python
import asyncio
import os
from dbgpt.agent import AgentContext, AgentMemory, LLMConfig, UserProxyAgent
from dbgpt.agent.expand.tool_assistant_agent import ToolAssistantAgent
from dbgpt.model.proxy import OpenAILLMClient

async def main():

    llm_client = OpenAILLMClient(
        model_alias="gpt-3.5-turbo",  # or other models, eg. "gpt-4o"
        api_base=os.getenv("OPENAI_API_BASE"),
        api_key=os.getenv("OPENAI_API_KEY"),
    )
    context: AgentContext = AgentContext(
        conv_id="test123", language="en", temperature=0.5, max_new_tokens=2048
    )
    agent_memory = AgentMemory()

    user_proxy = await UserProxyAgent().bind(agent_memory).bind(context).build()

    tool_man = (
        await ToolAssistantAgent()
        .bind(context)
        .bind(LLMConfig(llm_client=llm_client))
        .bind(agent_memory)
        .bind(tools)
        .build()
    )

    await user_proxy.initiate_chat(
        recipient=tool_man,
        reviewer=user_proxy,
        message="Calculate the product of 10 and 99",
    )

    await user_proxy.initiate_chat(
        recipient=tool_man,
        reviewer=user_proxy,
        message="Count the number of files in /tmp",
    )

    # dbgpt-vis message infos
    print(await agent_memory.gpts_memory.one_chat_completions("test123"))
    
if __name__ == "__main__":
    asyncio.run(main())

```
The output will be like this:
``````bash
--------------------------------------------------------------------------------
User (to LuBan)-[]:

"Calculate the product of 10 and 99"

--------------------------------------------------------------------------------
un_stream ai response: {
  "thought": "To calculate the product of 10 and 99, we need to use a tool that can perform multiplication operation.",
  "tool_name": "simple_calculator",
  "args": {
    "first_number": 10,
    "second_number": 99,
    "operator": "*"
  }
}

--------------------------------------------------------------------------------
LuBan (to User)-[gpt-3.5-turbo]:

"{\n  \"thought\": \"To calculate the product of 10 and 99, we need to use a tool that can perform multiplication operation.\",\n  \"tool_name\": \"simple_calculator\",\n  \"args\": {\n    \"first_number\": 10,\n    \"second_number\": 99,\n    \"operator\": \"*\"\n  }\n}"
>>>>>>>>LuBan Review info: 
Pass(None)
>>>>>>>>LuBan Action report: 
execution succeeded,
990

--------------------------------------------------------------------------------

--------------------------------------------------------------------------------
User (to LuBan)-[]:

"Count the number of files in /tmp"

--------------------------------------------------------------------------------
un_stream ai response: {
  "thought": "To count the number of files in /tmp directory, we should use a tool that can perform this operation.",
  "tool_name": "count_directory_files",
  "args": {
    "path": "/tmp"
  }
}

--------------------------------------------------------------------------------
LuBan (to User)-[gpt-3.5-turbo]:

"{\n  \"thought\": \"To count the number of files in /tmp directory, we should use a tool that can perform this operation.\",\n  \"tool_name\": \"count_directory_files\",\n  \"args\": {\n    \"path\": \"/tmp\"\n  }\n}"
>>>>>>>>LuBan Review info: 
Pass(None)
>>>>>>>>LuBan Action report: 
execution succeeded,
19

--------------------------------------------------------------------------------
``````


In the above code, we use the `ToolAssistantAgent` to select and call the appropriate tool.

## More Details?

In the above code, we use the `tool` decorator to define the tool function. It will wrap the function to a 
`FunctionTool` object. And `FunctionTool` is a subclass of `BaseTool`, which is a base class of all tools.

Actually, **tool** is a special **resource** in the `DB-GPT` agent. You will see more details in the [Resource](../modules/resource/resource.md) section.