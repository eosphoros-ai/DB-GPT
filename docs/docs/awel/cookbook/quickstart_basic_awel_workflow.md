# QuickStart Basic AWEL Workflow

## Install 

At first, install dbgpt, and necessary dependencies:

```shell
pip install dbgpt --upgrade
pip install openai
```

Create a python file `simple_sdk_llm_example_dag.py` and write the following content:

```python
import asyncio
from dbgpt.core.awel import DAG
from dbgpt.core.operators import (
    PromptBuilderOperator,
    RequestBuilderOperator,
)
from dbgpt.model.proxy import OpenAILLMClient
from dbgpt.model.operators import LLMOperator

with DAG("simple_sdk_llm_example_dag") as dag:
    prompt_task = PromptBuilderOperator(
        "Write a SQL of {dialect} to query all data of {table_name}."
    )
    model_pre_handle_task = RequestBuilderOperator(model="gpt-3.5-turbo")
    llm_task = LLMOperator(OpenAILLMClient())
    prompt_task >> model_pre_handle_task >> llm_task
    
output = asyncio.run(
    llm_task.call({
        "dialect": "MySQL", 
        "table_name": "users"
    }
))
print(output)
```

Configure the environment variables for OpenAI API:

```bash
export OPENAI_API_KEY=sk-xx
export OPENAI_API_BASE=https://xx:80/v1
```

Run the python file:

```bash
python simple_sdk_llm_example_dag.py
```

The output will like this:
```plaintext
ModelOutput(text='SELECT * FROM users;', error_code=0, model_context=None, finish_reason=None, usage={'completion_tokens': 5, 'prompt_tokens': 19, 'total_tokens': 24}, metrics=None)
```

Congratulations! You have already mastered the basic usage of AWEL. For more examples, 
please refer to the **[cookbook](/docs/awel/cookbook/)**.

And we suggest you to read the book **[AWEL Tutorial](/docs/awel/tutorial/)** to learn more about AWEL.
