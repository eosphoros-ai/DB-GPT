import asyncio
from typing import Dict, List
import json
from dbgpt.core.awel import (
    DAG,
    InputOperator,
    SimpleCallDataInputSource,
    JoinOperator,
    MapOperator,
)
from dbgpt.core import SQLOutputParser, OpenAILLM, RequestBuildOperator, PromptTemplate
from dbgpt.datasource.rdbms.conn_sqlite import SQLiteTempConnect
from dbgpt.datasource.operator.datasource_operator import DatasourceOperator
from dbgpt.rag.operator.datasource import DatasourceRetrieverOperator


def _create_temporary_connection():
    """Create a temporary database connection for testing."""
    connect = SQLiteTempConnect.create_temporary_db()
    connect.create_temp_tables(
        {
            "user": {
                "columns": {
                    "id": "INTEGER PRIMARY KEY",
                    "name": "TEXT",
                    "age": "INTEGER",
                },
                "data": [
                    (1, "Tom", 10),
                    (2, "Jerry", 16),
                    (3, "Jack", 18),
                    (4, "Alice", 20),
                    (5, "Bob", 22),
                ],
            }
        }
    )
    return connect


def _sql_prompt() -> str:
    """This is a prompt template for SQL generation.

    Format of arguments:
        {db_name}: database name
        {table_info}: table structure information
        {dialect}: database dialect
        {top_k}: maximum number of results
        {user_input}: user question
        {response}: response format

    Returns:
        str: prompt template
    """
    return """Please answer the user's question based on the database selected by the user and some of the available table structure definitions of the database. 
Database name: 
    {db_name} 
    
Table structure definition: 
    {table_info}

Constraint:
    1.Please understand the user's intention based on the user's question, and use the given table structure definition to create a grammatically correct {dialect} sql. If sql is not required, answer the user's question directly.. 
    2.Always limit the query to a maximum of {top_k} results unless the user specifies in the question the specific number of rows of data he wishes to obtain.
    3.You can only use the tables provided in the table structure information to generate sql. If you cannot generate sql based on the provided table structure, please say: "The table structure information provided is not enough to generate sql queries." It is prohibited to fabricate information at will.
    4.Please be careful not to mistake the relationship between tables and columns when generating SQL.
    5.Please check the correctness of the SQL and ensure that the query performance is optimized under correct conditions.

User Question:
    {user_input}
Please think step by step and respond according to the following JSON format:
    {response}
Ensure the response is correct json and can be parsed by Python json.loads.
"""


def _join_func(query_dict: Dict, db_summary: List[str]):
    """Join function for JoinOperator.

    Build the format arguments for the prompt template.

    Args:
        query_dict (Dict): The query dict from DAG input.
        db_summary (List[str]): The table structure information from DatasourceRetrieverOperator.

    Returns:
        Dict: The query dict with the format arguments.
    """
    default_response = {
        "thoughts": "thoughts summary to say to user",
        "sql": "SQL Query to run",
    }
    response = json.dumps(default_response, ensure_ascii=False, indent=4)
    query_dict["table_info"] = db_summary
    query_dict["response"] = response
    return query_dict


class SQLResultOperator(JoinOperator[Dict]):
    """Merge the SQL result and the model result."""

    def __init__(self, **kwargs):
        super().__init__(combine_function=self._combine_result, **kwargs)

    def _combine_result(self, sql_result_df, model_result: Dict) -> Dict:
        model_result["data_df"] = sql_result_df
        return model_result


with DAG("simple_sdk_llm_sql_example") as dag:
    db_connection = _create_temporary_connection()
    input_task = InputOperator(input_source=SimpleCallDataInputSource())
    retriever_task = DatasourceRetrieverOperator(connection=db_connection)
    # Merge the input data and the table structure information.
    prompt_input_task = JoinOperator(combine_function=_join_func)
    prompt_task = PromptTemplate.from_template(_sql_prompt())
    model_pre_handle_task = RequestBuildOperator(model="gpt-3.5-turbo")
    llm_task = OpenAILLM()
    out_parse_task = SQLOutputParser()
    sql_parse_task = MapOperator(map_function=lambda x: x["sql"])
    db_query_task = DatasourceOperator(connection=db_connection)
    sql_result_task = SQLResultOperator()
    input_task >> prompt_input_task
    input_task >> retriever_task >> prompt_input_task
    (
        prompt_input_task
        >> prompt_task
        >> model_pre_handle_task
        >> llm_task
        >> out_parse_task
        >> sql_parse_task
        >> db_query_task
        >> sql_result_task
    )
    out_parse_task >> sql_result_task


if __name__ == "__main__":
    input_data = {
        "data": {
            "db_name": "test_db",
            "dialect": "sqlite",
            "top_k": 5,
            "user_input": "What is the name and age of the user with age less than 18",
        }
    }
    output = asyncio.run(sql_result_task.call(call_data=input_data))
    print(f"\nthoughts: {output.get('thoughts')}\n")
    print(f"sql: {output.get('sql')}\n")
    print(f"result data:\n{output.get('data_df')}")
