# Calculator With Agents

In this example, we will show you how to use an agent as your calculator.

## Installations

Install the required packages by running the following command:

```bash
pip install "dbgpt[agent]>=0.5.6rc1" -U
pip install openai
```

## Code

Create a new Python file and add the following code:

```python
import asyncio

from dbgpt.agent import AgentContext, AgentMemory, LLMConfig, UserProxyAgent
from dbgpt.agent.expand.code_assistant_agent import CodeAssistantAgent
from dbgpt.model.proxy import OpenAILLMClient


async def main():
    llm_client = OpenAILLMClient(model_alias="gpt-3.5-turbo")
    context: AgentContext = AgentContext(conv_id="test123")
    # Create an agent memory, default memory is ShortTermMemory
    agent_memory: AgentMemory = AgentMemory()

    # Create a code assistant agent
    coder = (
        await CodeAssistantAgent()
        .bind(context)
        .bind(LLMConfig(llm_client=llm_client))
        .bind(agent_memory)
        .build()
    )

    # Create a user proxy agent
    user_proxy = await UserProxyAgent().bind(context).bind(agent_memory).build()

    # Initiate a chat with the user proxy agent
    await user_proxy.initiate_chat(
        recipient=coder,
        reviewer=user_proxy,
        message="calculate the result of 321 * 123",
    )
    # Obtain conversation history messages between agents
    print(await agent_memory.gpts_memory.one_chat_completions("test123"))


if __name__ == "__main__":
    asyncio.run(main())
```

You will see the following output:

````bash
Prompt manager is not available.
Prompt manager is not available.
Prompt manager is not available.
Prompt manager is not available.
Prompt manager is not available.

--------------------------------------------------------------------------------
User (to Turing)-[]:

"calculate the result of 321 * 123"

--------------------------------------------------------------------------------
un_stream ai response: ```python
# filename: calculate_multiplication.py

result = 321 * 123
print(result)
```

>>>>>>>> EXECUTING CODE BLOCK 0 (inferred language is python)...
execute_code was called without specifying a value for use_docker. Since the python docker package is not available, code will be run natively. Note: this fallback behavior is subject to change
un_stream ai response: True

--------------------------------------------------------------------------------
Turing (to User)-[gpt-3.5-turbo]:

"```python\n# filename: calculate_multiplication.py\n\nresult = 321 * 123\nprint(result)\n```"
>>>>>>>>Turing Review info: 
Pass(None)
>>>>>>>>Turing Action report: 
execution succeeded,

39483


--------------------------------------------------------------------------------
```agent-plans
[{"name": "calculate the result of 321 * 123", "num": 1, "status": "complete", "agent": "Human", "markdown": "```agent-messages\n[{\"sender\": \"CodeEngineer\", \"receiver\": \"Human\", \"model\": \"gpt-3.5-turbo\", \"markdown\": \"```vis-code\\n{\\\"exit_success\\\": true, \\\"language\\\": \\\"python\\\", \\\"code\\\": [[\\\"python\\\", \\\"# filename: calculate_multiplication.py\\\\n\\\\nresult = 321 * 123\\\\nprint(result)\\\"]], \\\"log\\\": \\\"\\\\n39483\\\\n\\\"}\\n```\"}]\n```"}]
```
````