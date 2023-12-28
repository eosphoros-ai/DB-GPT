import asyncio

from dbgpt.core import BaseOutputParser, PromptTemplate
from dbgpt.core.awel import DAG
from dbgpt.core.operator import LLMOperator, RequestBuildOperator
from dbgpt.model import OpenAILLMClient

with DAG("simple_sdk_llm_example_dag") as dag:
    prompt_task = PromptTemplate.from_template(
        "Write a SQL of {dialect} to query all data of {table_name}."
    )
    model_pre_handle_task = RequestBuildOperator(model="gpt-3.5-turbo")
    llm_task = LLMOperator(OpenAILLMClient())
    out_parse_task = BaseOutputParser()
    prompt_task >> model_pre_handle_task >> llm_task >> out_parse_task

if __name__ == "__main__":
    output = asyncio.run(
        out_parse_task.call(
            call_data={"data": {"dialect": "mysql", "table_name": "user"}}
        )
    )
    print(f"output: \n\n{output}")
