# Multi-Round Chat with LLMs

In this example, we will show how to use the AWEL library to create a multi-round chat 
with a LLM. 

Create a python file `multi_round_chat_with_llm.py` and write the following content:

```python
import asyncio
from dbgpt.core.awel import DAG, MapOperator, BaseOperator
from dbgpt.core import (
    ChatPromptTemplate,
    HumanPromptTemplate,
    InMemoryStorage,
    MessagesPlaceholder,
    ModelRequestContext,
    SystemPromptTemplate,
)
from dbgpt.core.operators import (
    ChatComposerInput,
    ChatHistoryPromptComposerOperator,
)
from dbgpt.model.proxy import OpenAILLMClient
from dbgpt.model.operators import LLMOperator

with DAG("multi_round_chat_with_lll_dag") as dag:
    prompt = ChatPromptTemplate(
        messages=[
            SystemPromptTemplate.from_template("You are a helpful chatbot."),
            MessagesPlaceholder(variable_name="chat_history"),
            HumanPromptTemplate.from_template("{user_input}"),
        ]
    )

    composer_operator = ChatHistoryPromptComposerOperator(
        prompt_template=prompt,
        keep_end_rounds=5,
        storage=InMemoryStorage(),
        message_storage=InMemoryStorage(),
    )
    
    input_task = MapOperator(
        lambda req: ChatComposerInput(
            context=ModelRequestContext(conv_uid=req["conv_uid"]),
            prompt_dict={"user_input": req["user_input"]},
            model_dict={"model": "gpt-3.5-turbo"},
        )
    )

    # Use LLMOperator to generate response.
    llm_task = LLMOperator(task_name="llm_task", llm_client=OpenAILLMClient())
    out_parse_task = MapOperator(lambda out: out.text)
    
    input_task >> composer_operator >> llm_task >> out_parse_task


async def main(task: BaseOperator):
    conv_uid = "conv_1234"
    first_user_input = "Who is elon musk?"
    second_user_input = "Is he rich?"
    
    print(f"First round\nUser: {first_user_input}")
    first_ai_response = await task.call({"conv_uid": conv_uid, "user_input": first_user_input})
    print(f"AI: {first_ai_response}")
    
    print(f"\nSecond round\nUser: {second_user_input}")
    second_ai_response = await task.call({"conv_uid": conv_uid, "user_input": second_user_input})
    print(f"AI: {second_ai_response}")

asyncio.run(main(out_parse_task))
```

Then run the file with the following command:

```bash
python multi_round_chat_with_llm.py
```

And you will see the following output:

```plaintext
First round
User: Who is elon musk?
AI: Elon Musk is a well-known entrepreneur and business magnate. He is the CEO and founder of SpaceX, Tesla Inc., Neuralink, and The Boring Company. Musk is known for his work in the technology and space industries, and he is also involved in the development of electric vehicles, renewable energy, and artificial intelligence.

Second round
User: Is he rich?
AI: Yes, Elon Musk is one of the richest people in the world. As the CEO and founder of multiple successful companies, including SpaceX and Tesla, his net worth fluctuates but is consistently in the billions of dollars.
```
