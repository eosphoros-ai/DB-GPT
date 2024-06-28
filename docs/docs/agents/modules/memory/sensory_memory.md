# Sensory Memory

Like human sensory memory, the sensory memory is registers perceptual inputs, and it 
will receive the observations from the environment, some of sensory memory will be 
transferred to short-term memory.

:::tip NOTE
You should not use the `SensoryMemory` directly in most cases, it is designed to receive
the observations from the environment, only a part of sensory memory will be transferred to short-term memory.
:::

## Simple Example of Sensory Memory

First, you need to create an instance of `SensoryMemory` and then you can use it to store the observations.

```python
from dbgpt.agent import AgentMemory, SensoryMemory

# Create an agent memory, which contains a sensory memory
memory = SensoryMemory(buffer_size=2)
agent_memory: AgentMemory = AgentMemory(memory=memory)
```

Then, let's create some user messages for testing.

```python
import os
from dbgpt.agent import AgentContext
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
)

messages = [
    "When I was 4 years old, I went to primary school for the first time, please tell me a joke",
    "When I was 10 years old, I went to middle school for the first time, please tell me a joke",
    "When I was 16 years old, I went to high school for the first time, please tell me a joke",
    "When I was 18 years old, I went to college for the first time, please tell me a joke",
]
```

### Verifying Remember

```python
import asyncio
from dbgpt.agent import (
    ConversableAgent,
    ProfileConfig,
    LLMConfig,
    BlankAction,
    UserProxyAgent,
)

async def verify_remember():
    joy = (
        await ConversableAgent(profile=ProfileConfig(name="Joy", role="Comedians"))
        .bind(context)
        .bind(LLMConfig(llm_client=llm_client))
        .bind(agent_memory)
        .bind(BlankAction)
        .build()
    )
    user_proxy = await UserProxyAgent().bind(agent_memory).bind(context).build()
    # The turns not more than 2, make sure the agent remembers the previous conversation
    for message in messages[:2]:
        await user_proxy.initiate_chat(
            recipient=joy,
            reviewer=user_proxy,
            message=message,
        )
    await user_proxy.initiate_chat(
        recipient=joy,
        reviewer=user_proxy,
        message="How old was I when I went to primary school?"
    )

if __name__ == "__main__":
    asyncio.run(verify_remember())

```

The output will like this:

```
--------------------------------------------------------------------------------
User (to Joy)-[]:

"When I was 4 years old, I went to primary school for the first time, please tell me a joke"

--------------------------------------------------------------------------------
un_stream ai response: Sure, here's a fun joke for you:

Why did the kid bring a ladder to school?

Because he wanted to go to high school!

--------------------------------------------------------------------------------
Joy (to User)-[gpt-4o]:

"Sure, here's a fun joke for you:\n\nWhy did the kid bring a ladder to school?\n\nBecause he wanted to go to high school!"
>>>>>>>>Joy Review info: 
Pass(None)
>>>>>>>>Joy Action report: 
execution succeeded,
Sure, here's a fun joke for you:

Why did the kid bring a ladder to school?

Because he wanted to go to high school!

--------------------------------------------------------------------------------

--------------------------------------------------------------------------------
User (to Joy)-[]:

"When I was 10 years old, I went to middle school for the first time, please tell me a joke"

--------------------------------------------------------------------------------
un_stream ai response: Sure, here's a joke for you:

Why did the student eat his homework?

Because the teacher said it was a piece of cake!

--------------------------------------------------------------------------------
Joy (to User)-[gpt-4o]:

"Sure, here's a joke for you:\n\nWhy did the student eat his homework?\n\nBecause the teacher said it was a piece of cake!"
>>>>>>>>Joy Review info: 
Pass(None)
>>>>>>>>Joy Action report: 
execution succeeded,
Sure, here's a joke for you:

Why did the student eat his homework?

Because the teacher said it was a piece of cake!

--------------------------------------------------------------------------------

--------------------------------------------------------------------------------
User (to Joy)-[]:

"How old was I when I went to primary school?"

--------------------------------------------------------------------------------
un_stream ai response: Based on your previous statements, you went to primary school for the first time when you were 4 years old.

--------------------------------------------------------------------------------
Joy (to User)-[gpt-4o]:

"Based on your previous statements, you went to primary school for the first time when you were 4 years old."
>>>>>>>>Joy Review info: 
Pass(None)
>>>>>>>>Joy Action report: 
execution succeeded,
Based on your previous statements, you went to primary school for the first time when you were 4 years old.
```

In the above example, the agent remembers the previous conversation and can answer the 
question based on the previous conversation, it is because the `buffer_size=2` in the 
`SensoryMemory` and the agent can remember the previous two conversations.

### Verifying Forget

```python
async def verify_forget():
    joy = (
        await ConversableAgent(profile=ProfileConfig(name="Joy", role="Comedians"))
        .bind(context)
        .bind(LLMConfig(llm_client=llm_client))
        .bind(agent_memory)
        .bind(BlankAction)
        .build()
    )
    user_proxy = await UserProxyAgent().bind(agent_memory).bind(context).build()
    for message in messages:
        await user_proxy.initiate_chat(
            recipient=joy,
            reviewer=user_proxy,
            message=message,
        )
    await user_proxy.initiate_chat(
        recipient=joy,
        reviewer=user_proxy,
        message="How old was I when I went to primary school?",
    )


if __name__ == "__main__":
    asyncio.run(verify_forget())
```

The output will like this:

```
--------------------------------------------------------------------------------
User (to Joy)-[]:

"When I was 4 years old, I went to primary school for the first time, please tell me a joke"

--------------------------------------------------------------------------------
un_stream ai response: Sure, here's a joke for you:

Why did the scarecrow become a successful student?

Because he was outstanding in his field!

--------------------------------------------------------------------------------
Joy (to User)-[gpt-4o]:

"Sure, here's a joke for you:\n\nWhy did the scarecrow become a successful student?\n\nBecause he was outstanding in his field!"
>>>>>>>>Joy Review info: 
Pass(None)
>>>>>>>>Joy Action report: 
execution succeeded,
Sure, here's a joke for you:

Why did the scarecrow become a successful student?

Because he was outstanding in his field!

--------------------------------------------------------------------------------

--------------------------------------------------------------------------------
User (to Joy)-[]:

"When I was 10 years old, I went to middle school for the first time, please tell me a joke"

--------------------------------------------------------------------------------
un_stream ai response: Of course! Here's a joke for you:

Why was the math book sad when it started middle school?

Because it had too many problems!

--------------------------------------------------------------------------------
Joy (to User)-[gpt-4o]:

"Of course! Here's a joke for you:\n\nWhy was the math book sad when it started middle school?\n\nBecause it had too many problems!"
>>>>>>>>Joy Review info: 
Pass(None)
>>>>>>>>Joy Action report: 
execution succeeded,
Of course! Here's a joke for you:

Why was the math book sad when it started middle school?

Because it had too many problems!

--------------------------------------------------------------------------------

--------------------------------------------------------------------------------
User (to Joy)-[]:

"When I was 16 years old, I went to high school for the first time, please tell me a joke"

--------------------------------------------------------------------------------
un_stream ai response: Sure, here's a joke for you:

Why did the geometry teacher go to the beach?

Because she needed to find a new angle!

--------------------------------------------------------------------------------
Joy (to User)-[gpt-4o]:

"Sure, here's a joke for you:\n\nWhy did the geometry teacher go to the beach?\n\nBecause she needed to find a new angle!"
>>>>>>>>Joy Review info: 
Pass(None)
>>>>>>>>Joy Action report: 
execution succeeded,
Sure, here's a joke for you:

Why did the geometry teacher go to the beach?

Because she needed to find a new angle!

--------------------------------------------------------------------------------

--------------------------------------------------------------------------------
User (to Joy)-[]:

"When I was 18 years old, I went to college for the first time, please tell me a joke"

--------------------------------------------------------------------------------
un_stream ai response: Sure, here’s a college-themed joke for you:

Why did the scarecrow become a successful college student?

Because he was outstanding in his field! 🌾🎓😄

--------------------------------------------------------------------------------
Joy (to User)-[gpt-4o]:

"Sure, here’s a college-themed joke for you:\n\nWhy did the scarecrow become a successful college student?\n\nBecause he was outstanding in his field! 🌾🎓😄"
>>>>>>>>Joy Review info: 
Pass(None)
>>>>>>>>Joy Action report: 
execution succeeded,
Sure, here’s a college-themed joke for you:

Why did the scarecrow become a successful college student?

Because he was outstanding in his field! 🌾🎓😄

--------------------------------------------------------------------------------

--------------------------------------------------------------------------------
User (to Joy)-[]:

"How old was I when I went to primary school?"

--------------------------------------------------------------------------------
un_stream ai response: Most people typically start primary school around 5 or 6 years old. But if you'd like a joke on that topic, here it goes:

Why did the math book look so sad on its first day of primary school?

Because it had too many problems! 📚😄

--------------------------------------------------------------------------------
Joy (to User)-[gpt-4o]:

"Most people typically start primary school around 5 or 6 years old. But if you'd like a joke on that topic, here it goes:\n\nWhy did the math book look so sad on its first day of primary school?\n\nBecause it had too many problems! 📚😄"
>>>>>>>>Joy Review info: 
Pass(None)
>>>>>>>>Joy Action report: 
execution succeeded,
Most people typically start primary school around 5 or 6 years old. But if you'd like a joke on that topic, here it goes:

Why did the math book look so sad on its first day of primary school?

Because it had too many problems! 📚😄
```

In the above example, the agent forgets the previous conversation and can't answer the 
question based on the previous conversation, it is because the `buffer_size=2` in this memory,
**it will discard all the existing memories when the buffer is full**, this is a special 
feature of the `SensoryMemory` that not like the common buffered memory(FIFO, keep the 
latest buffer_size memories).

