# QuickStart Basic AWEL Workflow

## Install 

At first, install dbgpt, and necessary dependencies:

```python
pip install dbgpt --upgrade
pip install openai
```

Create a python file `simple_sdk_llm_example_dag.py` and write the following content:

```python
from dbgpt.core import BaseOutputParser
from dbgpt.core.awel import DAG
from dbgpt.core.operator import (
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
    out_parse_task = BaseOutputParser()
    prompt_task >> model_pre_handle_task >> llm_task >> out_parse_task
```

Support OpenAI key and address:

```bash
export OPENAI_API_KEY=sk-xx
export OPENAI_API_BASE=https://xx:80/v1
```

Run this python script for test

```bash
python simple_sdk_llm_example_dag.py
```

Ok, You have already mastered the basic usage of AWEL. For more examples, please refer to the **[cookbook](/docs/awel/cookbook/)**
