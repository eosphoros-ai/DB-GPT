# Calculator With Agents

In this example, we will show you how to use an agent as your calculator.

## Installations

Install the required packages by running the following command:

```bash
pip install "dbgpt[agent]>=0.5.4rc0" -U
pip install openai
```

## Code

Create a new Python file and add the following code:

```python
import asyncio

from dbgpt.agent import AgentContext, GptsMemory, LLMConfig, UserProxyAgent
from dbgpt.agent.expand.code_assistant_agent import CodeAssistantAgent
from dbgpt.model.proxy import OpenAILLMClient

async def main():
    llm_client = OpenAILLMClient(model_alias="gpt-3.5-turbo")
    context: AgentContext = AgentContext(conv_id="test123")
    default_memory: GptsMemory = GptsMemory()

    # Create a code assistant agent
    coder = (
        await CodeAssistantAgent()
        .bind(context)
        .bind(LLMConfig(llm_client=llm_client))
        .bind(default_memory)
        .build()
    )

    # Create a user proxy agent
    user_proxy = await UserProxyAgent().bind(context).bind(default_memory).build()

    # Initiate a chat with the user proxy agent
    await user_proxy.initiate_chat(
        recipient=coder,
        reviewer=user_proxy,
        message="calculate the result of 321 * 123"  
    )
    # Obtain conversation history messages between agents
    print(await default_memory.one_chat_completions("test123"))
    
if __name__ == "__main__":
    asyncio.run(main())
```

You will see the following output:

````bash
--------------------------------------------------------------------------------
User (to Turing)-[]:

"calculate the result of 321 * 123"

--------------------------------------------------------------------------------
un_stream ai response: ```python
# Calculate the result of 321 * 123
result = 321 * 123
print(result)
```

>>>>>>>> EXECUTING CODE BLOCK 0 (inferred language is python)...
execute_code was called without specifying a value for use_docker. Since the python docker package is not available, code will be run natively. Note: this fallback behavior is subject to change
un_stream ai response: True

--------------------------------------------------------------------------------
Turing (to User)-[gpt-3.5-turbo]:

"```python\n# Calculate the result of 321 * 123\nresult = 321 * 123\nprint(result)\n```"
>>>>>>>>Turing Review info: 
Pass(None)
>>>>>>>>Turing Action report: 
execution succeeded,

39483


--------------------------------------------------------------------------------
```agent-plans
[{"name": "calculate the result of 321 * 123", "num": 1, "status": "complete", "agent": "Human", "markdown": "```agent-messages\n[{\"sender\": \"CodeEngineer\", \"receiver\": \"Human\", \"model\": \"gpt-3.5-turbo\", \"markdown\": \"```vis-code\\n{\\\"exit_success\\\": true, \\\"language\\\": \\\"python\\\", \\\"code\\\": [[\\\"python\\\", \\\"# Calculate the result of 321 * 123\\\\nresult = 321 * 123\\\\nprint(result)\\\"]], \\\"log\\\": \\\"\\\\n39483\\\\n\\\"}\\n```\"}]\n```"}]
```
(dbgpt-agents-py3.11) (base) ➜  dbgpt-agents
````