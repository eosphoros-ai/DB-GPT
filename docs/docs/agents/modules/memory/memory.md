# Memory Introduction

> The memory module plays a very important role in the agent architecture design. It 
> stores information perceived from the environment and leverages the recorded memories 
> to facilitate future actions. The memory module can help the agent to accumulate 
> experiences, self-evolve, and behave in a more consistent, reasonable, and effective manner.

## Memory Module Overview

### Memory Operations

In DB-GPT agents, there are three main memory operations:

1. **Memory reading**: The objective of memory reading is to extract meaningful 
information from memory to enhance the agent’s actions.
2. **Memory writing**: The purpose of memory writing is to store information about the 
perceived environment in memory. Storing valuable information in memory provides a 
foundation for retrieving informative memories in the future, enabling the agent to act 
more efficiently and rationally.
3. **Memory reflection**: Memory reflection emulates humans’ ability to witness and 
evaluate their own cognitive, emotional, and behavioral processes. When adapted to agents, 
the objective is to provide agents with the capability to independently summarize and 
infer more abstract, complex and high-level information.

### Memory Structure

In DB-GPT agents, there are four main memory structures:
1. **Sensory memory**: Like human sensory memory, the sensory memory is registers 
perceptual inputs, and it will receive the observations from the environment, some of sensory
memory will be transferred to short-term memory.
2. **Short-term memory**: Short-term memory temporarily buffers recent perceptions, it will receive
some of the sensory memory, and it can be enhanced by other observations or retrieved memories to enter the long-term memory.
3. **Long-term memory**: Long-term memory stores the agent’s experiences and knowledge, it can receive
information from short-term memory, and it will consolidates important information over time.
4. **Hybrid memory**: Hybrid memory is a combination of sensory memory, short-term memory, and long-term memory.

## Memory In DB-GPT Agents

### Some Concepts Of Memory

- `Memory`: The memory is a class that stores all the memories, it can be `SensorMemory`, 
`ShortTermMemory`, `EnhancedShortTermMemory`, `LongTermMemory` and `HybridMemory` now.
- `MemoryFragment`: The `MemoryFragment` is an abstract class that stores the memory information,  
The `AgentMemoryFragment` is a class that inherits from `MemoryFragment`,  it contains 
the memory content, memory id, memory importance, last access time, etc. 
- `GptsMemory`: The `GptsMemory` is used to store the conversation and plan information, not a part of the memory structure.
- `AgentMemory`: The `AgentMemory` is a class that contains the `Memory` and `GptsMemory`.

### Create Memory

As mentioned in previous sections, the memory are include in `AgentMemory` class, here is an example:
```python
from dbgpt.agent import AgentMemory, ShortTermMemory

# Create an agent memory, default memory is ShortTermMemory
memory = ShortTermMemory(buffer_size=5)
agent_memory = AgentMemory(memory=memory)
```

By the way, in `AgentMemory` class, you can pass a `GptsMemory`, in the conventional sense, 
`GptsMemory` is not included in the memory structure, it is used to store the conversation and plan information.

A example of `GptsMemory`:
```python
from dbgpt.agent import AgentMemory, ShortTermMemory, GptsMemory

# Create an agent memory, default memory is ShortTermMemory
memory = ShortTermMemory(buffer_size=5)
# Store the conversation and plan information
gpts_memory = GptsMemory()
agent_memory = AgentMemory(memory=memory, gpts_memory=gpts_memory)
```

### Read And Write Memory In Agent

The agent will call the `read_memories` method to read the memory fragments from the memory, 
and call the `write_memories` method to write the memory fragments to the memory.

When agent call the LLM, the memories will write to the LLM prompt, after the LLM return the response,
the agent will write the query and response to the memory.

As we mentioned in [Profile To Prompt](../profile/profile_to_prompt), there are a 
template variables named `most_recent_memories` in prompt template, it will be replaced by the
most recent memories.

#### Read Memories To Build Prompt

Here is an example to read memories from memory and build the prompt:
```python
import os
import asyncio
from dbgpt.agent import (
    AgentContext,
    ShortTermMemory,
    AgentMemory,
    ConversableAgent,
    ProfileConfig,
    LLMConfig,
    BlankAction,
    UserProxyAgent,
)
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
    verbose=True,  # Add verbose=True to print out the conversation history
)

# Create an agent memory, which contains a short-term memory
memory = ShortTermMemory(buffer_size=2)
agent_memory: AgentMemory = AgentMemory(memory=memory)

# Custom user prompt template, which includes most recent memories and question
user_prompt_template = """\
{% if most_recent_memories %}\
Most recent observations:
{{ most_recent_memories }}
{% endif %}\

{% if question %}\
Question: {{ question }}
{% endif %}
"""

# Custom write memory template, which includes question and thought
write_memory_template = """\
{% if question %}user: {{ question }} {% endif %}
{% if thought %}assistant: {{ thought }} {% endif %}\
"""


async def main():
    # Create a profile with a custom user prompt template
    joy_profile = ProfileConfig(
        name="Joy",
        role="Comedians",
        user_prompt_template=user_prompt_template,
        write_memory_template=write_memory_template,
    )
    joy = (
        await ConversableAgent(profile=joy_profile)
        .bind(context)
        .bind(LLMConfig(llm_client=llm_client))
        .bind(agent_memory)
        .bind(BlankAction)
        .build()
    )
    user_proxy = await UserProxyAgent().bind(agent_memory).bind(context).build()
    await user_proxy.initiate_chat(
        recipient=joy,
        reviewer=user_proxy,
        message="My name is bob, please tell me a joke",
    )
    await user_proxy.initiate_chat(
        recipient=joy,
        reviewer=user_proxy,
        message="What's my name?",
    )


if __name__ == "__main__":
    asyncio.run(main())
```
In the above example, we set `verbose=True` in `AgentContext`, to print out the conversation history.

The output will be like this:

``````shell
--------------------------------------------------------------------------------
User (to Joy)-[]:

"My name is bob, please tell me a joke"

--------------------------------------------------------------------------------
un_stream ai response: Sure thing, Bob! Here's one for you:

Why don’t scientists trust atoms?

Because they make up everything!

--------------------------------------------------------------------------------
String Prompt[verbose]: 
system: You are a Comedians, named Joy, your goal is None.
Please think step by step to achieve the goal. You can use the resources given below. 
At the same time, please strictly abide by the constraints and specifications in IMPORTANT REMINDER.

*** IMPORTANT REMINDER ***
Please answer in English.




human: 
Question: My name is bob, please tell me a joke

LLM Output[verbose]: 
Sure thing, Bob! Here's one for you:

Why don’t scientists trust atoms?

Because they make up everything!
--------------------------------------------------------------------------------


--------------------------------------------------------------------------------
Joy (to User)-[gpt-4o]:

"Sure thing, Bob! Here's one for you:\n\nWhy don’t scientists trust atoms?\n\nBecause they make up everything!"
>>>>>>>>Joy Review info: 
Pass(None)
>>>>>>>>Joy Action report: 
execution succeeded,
Sure thing, Bob! Here's one for you:

Why don’t scientists trust atoms?

Because they make up everything!

--------------------------------------------------------------------------------

--------------------------------------------------------------------------------
User (to Joy)-[]:

"What's my name?"

--------------------------------------------------------------------------------
un_stream ai response: Your name is Bob! 

And here's another quick joke for you:

Why don't skeletons fight each other?

They don't have the guts!

--------------------------------------------------------------------------------
String Prompt[verbose]: 
system: You are a Comedians, named Joy, your goal is None.
Please think step by step to achieve the goal. You can use the resources given below. 
At the same time, please strictly abide by the constraints and specifications in IMPORTANT REMINDER.

*** IMPORTANT REMINDER ***
Please answer in English.




human: Most recent observations:
user: My name is bob, please tell me a joke 
assistant: Sure thing, Bob! Here's one for you:

Why don’t scientists trust atoms?

Because they make up everything! 

Question: What's my name?

LLM Output[verbose]: 
Your name is Bob! 

And here's another quick joke for you:

Why don't skeletons fight each other?

They don't have the guts!
--------------------------------------------------------------------------------


--------------------------------------------------------------------------------
Joy (to User)-[gpt-4o]:

"Your name is Bob! \n\nAnd here's another quick joke for you:\n\nWhy don't skeletons fight each other?\n\nThey don't have the guts!"
>>>>>>>>Joy Review info: 
Pass(None)
>>>>>>>>Joy Action report: 
execution succeeded,
Your name is Bob! 

And here's another quick joke for you:

Why don't skeletons fight each other?

They don't have the guts!

--------------------------------------------------------------------------------
``````

In the second conversation, you can see the `Most recent observations` in the user prompt,
``````
--------------------------------------------------------------------------------
String Prompt[verbose]: 
system: You are a Comedians, named Joy, your goal is None.
Please think step by step to achieve the goal. You can use the resources given below. 
At the same time, please strictly abide by the constraints and specifications in IMPORTANT REMINDER.

*** IMPORTANT REMINDER ***
Please answer in English.




human: Most recent observations:
user: My name is bob, please tell me a joke 
assistant: Sure thing, Bob! Here's one for you:

Why don’t scientists trust atoms?

Because they make up everything! 

Question: What's my name?

LLM Output[verbose]: 
Your name is Bob! 

And here's another quick joke for you:

Why don't skeletons fight each other?

They don't have the guts!
--------------------------------------------------------------------------------
``````

#### Write Memories

When the agent receives the response from the LLM, it will write the query and response to the memory.
In memory fragment, the `content` is string, so you should decide how to store the information in the content.

In above example, the `write_memory_template` is:
```python
write_memory_template = """\
{% if question %}user: {{ question }} {% endif %}
{% if thought %}assistant: {{ thought }} {% endif %}\
"""
```
The `question` is the user query, and the `thought` is the LLM response, we will introduce more in next section.


## Custom Memory Reading And Writing

We can customize the memory reading and writing by inheriting the `ConversableAgent` class 
and override the `read_memories` and `write_memories` methods.

```python
from typing import Optional
from dbgpt.agent import (
    ConversableAgent,
    AgentMemoryFragment,
    ProfileConfig,
    BlankAction,
    ActionOutput,
)

write_memory_template = """\
{% if question %}user: {{ question }} {% endif %}
{% if thought %}assistant: {{ thought }} {% endif %}\
"""


class JoyAgent(ConversableAgent):
    profile: ProfileConfig = ProfileConfig(
        name="Joy",
        role="Comedians",
        write_memory_template=write_memory_template,
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._init_actions([BlankAction])

    async def read_memories(
        self,
        question: str,
    ) -> str:
        """Read the memories from the memory."""
        memories = await self.memory.read(observation=question)
        recent_messages = [m.raw_observation for m in memories]
        # Merge the recent messages.
        return "".join(recent_messages)

    async def write_memories(
        self,
        question: str,
        ai_message: str,
        action_output: Optional[ActionOutput] = None,
        check_pass: bool = True,
        check_fail_reason: Optional[str] = None,
    ) -> None:
        """Write the memories to the memory.

        We suggest you to override this method to save the conversation to memory
        according to your needs.

        Args:
            question(str): The question received.
            ai_message(str): The AI message, LLM output.
            action_output(ActionOutput): The action output.
            check_pass(bool): Whether the check pass.
            check_fail_reason(str): The check fail reason.
        """
        if not action_output:
            raise ValueError("Action output is required to save to memory.")

        mem_thoughts = action_output.thoughts or ai_message
        memory_map = {
            "question": question,
            "thought": mem_thoughts,
        }
        # This is the template to write the memory.
        # It configured in the agent's profile.
        write_memory_template = self.write_memory_template
        memory_content: str = self._render_template(write_memory_template, **memory_map)
        fragment = AgentMemoryFragment(memory_content)
        await self.memory.write(fragment)
```

In the above example, we override the `read_memories` to read the memories from the memory, in DB-GPT,
the most recent memories will form the `most_recent_memories` in the prompt template, 
And override the `write_memories` to write the memories to the memory.

**So, you can customize the memory reading and writing according to your needs.**

## Summary

In this document, we introduced the memory module in DB-GPT agents, and how to use the memory in agents.
In following sections, we will introduce how to use each memory structure in DB-GPT agents.