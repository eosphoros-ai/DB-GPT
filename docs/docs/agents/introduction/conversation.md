# Multi-Agents Conversation

Here we will show you how to write a multi-agents conversation program.

## Two Agents Conversation

First, create common `LLMConfig` and `AgentMemory` for both agents.

```python
import os
from dbgpt.agent import AgentContext, AgentMemory
from dbgpt.model.proxy import OpenAILLMClient

llm_client = OpenAILLMClient(
    model_alias="gpt-4o",
    api_base=os.getenv("OPENAI_API_BASE"),
    api_key=os.getenv("OPENAI_API_KEY"),
)

context: AgentContext = AgentContext(
    conv_id="test123",
    language="en",
    temperature=0.9,
    max_new_tokens=2048,
    max_chat_round=4,
)
# Create an agent memory, default memory is ShortTermMemory
agent_memory: AgentMemory = AgentMemory()


system_prompt_template = """\
You are a {{ role }}, {% if name %}named {{ name }}, {% endif %}your goal is {{ goal }}.
*** IMPORTANT REMINDER ***
{% if language == 'zh' %}\
Please answer in simplified Chinese.
{% else %}\
Please answer in English.
{% endif %}\
"""  # noqa

user_prompt_template = """\
{% if most_recent_memories %}\
Most recent observations:
{{ most_recent_memories }}
{% endif %}\
{% if question %}\
user: {{ question }}
{% endif %}
"""
```

In above code, we set `max_chat_round=4` in `AgentContext`, which means the conversation 
will end after 4 rounds.

And here we set `system_prompt_template` and `user_prompt_template` for both agents for a simple conversation, we
will introduce it in profile module later.


Then, create two agents, `Bob` and `Alice`, and initiate a chat between them.

```python 

import asyncio
from dbgpt.agent import ConversableAgent, ProfileConfig, LLMConfig, BlankAction


async def main():
    bob_profile = ProfileConfig(
        name="Bob",
        role="Comedians",
        system_prompt_template=system_prompt_template,
        user_prompt_template=user_prompt_template,
    )
    bob = (
        await ConversableAgent(profile=bob_profile)
        .bind(context)
        .bind(LLMConfig(llm_client=llm_client))
        .bind(agent_memory)
        .bind(BlankAction)
        .build()
    )
    alice_profile = ProfileConfig(
        name="Alice",
        role="Comedians",
        system_prompt_template=system_prompt_template,
        user_prompt_template=user_prompt_template,
    )
    alice = (
        await ConversableAgent(profile=alice_profile)
        .bind(context)
        .bind(LLMConfig(llm_client=llm_client))
        .bind(agent_memory)
        .bind(BlankAction)
        .build()
    )

    await bob.initiate_chat(alice, message="Tell me a joke.")


if __name__ == "__main__":
    asyncio.run(main())
```

Run the code, you will see the conversation between `Bob` and `Alice`:

```bash
--------------------------------------------------------------------------------
Bob (to Alice)-[]:

"Tell me a joke."

--------------------------------------------------------------------------------
un_stream ai response: Why don't scientists trust atoms?

Because they make up everything!

--------------------------------------------------------------------------------
Alice (to Bob)-[gpt-4o]:

"Why don't scientists trust atoms?\n\nBecause they make up everything!"
>>>>>>>>Alice Review info: 
Pass(None)
>>>>>>>>Alice Action report: 
execution succeeded,
Why don't scientists trust atoms?

Because they make up everything!

--------------------------------------------------------------------------------
un_stream ai response: That's a classic! You know, it's always good to have a few science jokes in your toolbox—they have the potential energy to make everyone laugh, and they rarely get a negative reaction!

--------------------------------------------------------------------------------
Bob (to Alice)-[gpt-4o]:

"That's a classic! You know, it's always good to have a few science jokes in your toolbox—they have the potential energy to make everyone laugh, and they rarely get a negative reaction!"
>>>>>>>>Bob Review info: 
Pass(None)
>>>>>>>>Bob Action report: 
execution succeeded,
That's a classic! You know, it's always good to have a few science jokes in your toolbox—they have the potential energy to make everyone laugh, and they rarely get a negative reaction!

--------------------------------------------------------------------------------
un_stream ai response: Absolutely, science jokes have a universal appeal! Here's another one for your collection:

Why did the biologist go to the beach?

Because they wanted to study the current events!

--------------------------------------------------------------------------------
Alice (to Bob)-[gpt-4o]:

"Absolutely, science jokes have a universal appeal! Here's another one for your collection:\n\nWhy did the biologist go to the beach?\n\nBecause they wanted to study the current events!"
>>>>>>>>Alice Review info: 
Pass(None)
>>>>>>>>Alice Action report: 
execution succeeded,
Absolutely, science jokes have a universal appeal! Here's another one for your collection:

Why did the biologist go to the beach?

Because they wanted to study the current events!

--------------------------------------------------------------------------------
un_stream ai response: Haha, that's a good one! You know, biologists at the beach must have some serious kelp issues, too. They just can’t help but dive into their work—whether it's in the lab or lounging in the sand!

--------------------------------------------------------------------------------
Bob (to Alice)-[gpt-4o]:

"Haha, that's a good one! You know, biologists at the beach must have some serious kelp issues, too. They just can’t help but dive into their work—whether it's in the lab or lounging in the sand!"
>>>>>>>>Bob Review info: 
Pass(None)
>>>>>>>>Bob Action report: 
execution succeeded,
Haha, that's a good one! You know, biologists at the beach must have some serious kelp issues, too. They just can’t help but dive into their work—whether it's in the lab or lounging in the sand!

--------------------------------------------------------------------------------
```