import asyncio
from dbgpt.core.awel import DAG
from dbgpt.core import BaseOutputParser, OpenAILLM, RequestBuildOperator, PromptTemplate

with DAG("simple_sdk_llm_example_dag") as dag:
    prompt = PromptTemplate.from_template(
        "Write a SQL of {dialect} to query all data of {table_name}."
    )
    req_builder = RequestBuildOperator(model="gpt-3.5-turbo")
    llm = OpenAILLM()
    out_parser = BaseOutputParser()
    prompt >> req_builder >> llm >> out_parser

if __name__ == "__main__":
    output = asyncio.run(
        out_parser.call(call_data={"data": {"dialect": "mysql", "table_name": "user"}})
    )
    print(f"output: \n\n{output}")
