# Agents With Database

Most of the time, we want the agent to answer questions based on the data in the database,
or make decisions based on the data in the database. In this case, we need to connect 
the agent to the database.

## Installation

To use the database in the agent, you need to install the dependencies with the following command:

```bash
pip install "dbgpt[simple_framework]>=0.5.9rc0"
```

## Create A Database Connector

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

<Tabs
  defaultValue="sqlite_temp"
  values={[
    {label: 'SQLite(Temporary)', value: 'sqlite_temp'},
    {label: 'SQLite', value: 'sqlite'},
    {label: 'MySQL', value: 'mysql'},
  ]}>

<TabItem value="sqlite_temp" label="sqlite_temp">

:::tip NOTE
We provide a temporary SQLite database for testing. The temporary database will be 
created in temporary directory and will be deleted after the program exits.
:::

```python
from dbgpt.datasource.rdbms.conn_sqlite import SQLiteTempConnector

connector = SQLiteTempConnector.create_temporary_db()
connector.create_temp_tables(
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

```
</TabItem>

<TabItem value="sqlite" label="sqlite">

:::tip NOTE
We connect to the SQLite database by giving the database file path, please make sure the file path is correct.
:::

```python
from dbgpt.datasource.rdbms.conn_sqlite import SQLiteConnector

connector = SQLiteConnector.from_file_path("path/to/your/database.db")
```

</TabItem>

<TabItem value="mysql" label="MySQL">

:::tip NOTE

We connect to the MySQL database by giving the database connection information, please 
make sure the connection information is correct.
:::

```python
from dbgpt.datasource.rdbms.conn_mysql import MySQLConnector

connector = MySQLConnector.from_uri_db(
    host="localhost",
    port=3307,
    user="root",
    pwd="********",
    db_name="user_manager",
    engine_args={"connect_args": {"charset": "utf8mb4"}},
)
```
 
</TabItem>

</Tabs>


## Create A Database Resource

```python
from dbgpt.agent.resource import RDBMSConnectorResource

db_resource = RDBMSConnectorResource("user_manager", connector=connector)
```

As previously mentioned, the **Database** is a kind of resource, we can use most database
which supported in DB-GPT(like SQLite, MySQL, ClickHouse, ApacheDoris, DuckDB, Hive, 
MSSQL, OceanBase, PostgreSQL, StarRocks, Vertica, etc.) as the resource.

## Use Database In Your Agent

```python
import asyncio
import os
from dbgpt.agent import AgentContext, AgentMemory, LLMConfig, UserProxyAgent
from dbgpt.agent.expand.data_scientist_agent import DataScientistAgent
from dbgpt.model.proxy import OpenAILLMClient

async def main():

    llm_client = OpenAILLMClient(
        model_alias="gpt-3.5-turbo",  # or other models, eg. "gpt-4o"
        api_base=os.getenv("OPENAI_API_BASE"),
        api_key=os.getenv("OPENAI_API_KEY"),
    )
    context: AgentContext = AgentContext(
        conv_id="test123", language="en", temperature=0.5, max_new_tokens=2048
    )
    agent_memory = AgentMemory()

    user_proxy = await UserProxyAgent().bind(agent_memory).bind(context).build()

    sql_boy = (
        await DataScientistAgent()
        .bind(context)
        .bind(LLMConfig(llm_client=llm_client))
        .bind(db_resource)
        .bind(agent_memory)
        .build()
    )

    await user_proxy.initiate_chat(
        recipient=sql_boy,
        reviewer=user_proxy,
        message="What is the name and age of the user with age less than 18",
    )

    ## dbgpt-vis message infos
    print(await agent_memory.gpts_memory.one_chat_completions("test123"))


if __name__ == "__main__":
    asyncio.run(main())

```

The output will be like this:

``````bash
--------------------------------------------------------------------------------
User (to Edgar)-[]:

"What is the name and age of the user with age less than 18"

--------------------------------------------------------------------------------
un_stream ai response: {
  "display_type": "response_table",
  "sql": "SELECT name, age FROM user WHERE age < 18",
  "thought": "I have selected a response_table to display the names and ages of users with an age less than 18. The SQL query retrieves the name and age columns from the user table where the age is less than 18."
}

--------------------------------------------------------------------------------
Edgar (to User)-[gpt-3.5-turbo]:

"{\n  \"display_type\": \"response_table\",\n  \"sql\": \"SELECT name, age FROM user WHERE age < 18\",\n  \"thought\": \"I have selected a response_table to display the names and ages of users with an age less than 18. The SQL query retrieves the name and age columns from the user table where the age is less than 18.\"\n}"
>>>>>>>>Edgar Review info: 
Pass(None)
>>>>>>>>Edgar Action report: 
execution succeeded,
{"display_type":"response_table","sql":"SELECT name, age FROM user WHERE age < 18","thought":"I have selected a response_table to display the names and ages of users with an age less than 18. The SQL query retrieves the name and age columns from the user table where the age is less than 18."}

--------------------------------------------------------------------------------
```agent-plans
[{"name": "What is the name and age of the user with age less than 18", "num": 1, "status": "complete", "agent": "Human", "markdown": "```agent-messages\n[{\"sender\": \"DataScientist\", \"receiver\": \"Human\", \"model\": \"gpt-3.5-turbo\", \"markdown\": \"```vis-chart\\n{\\\"sql\\\": \\\"SELECT name, age FROM user WHERE age < 18\\\", \\\"type\\\": \\\"response_table\\\", \\\"title\\\": \\\"\\\", \\\"describe\\\": \\\"I have selected a response_table to display the names and ages of users with an age less than 18. The SQL query retrieves the name and age columns from the user table where the age is less than 18.\\\", \\\"data\\\": [{\\\"name\\\": \\\"Tom\\\", \\\"age\\\": 10}, {\\\"name\\\": \\\"Jerry\\\", \\\"age\\\": 16}]}\\n```\"}]\n```"}]
```
``````

Let's parse the result from above output, we just focus on the last part
(output with [GPT-Vis](https://github.com/eosphoros-ai/GPT-Vis) protocol):
```json
[
    {
        "name": "What is the name and age of the user with age less than 18",
        "num": 1,
        "status": "complete",
        "agent": "Human",
        "markdown": "```agent-messages\n[{\"sender\": \"DataScientist\", \"receiver\": \"Human\", \"model\": \"gpt-3.5-turbo\", \"markdown\": \"```vis-chart\\n{\\\"sql\\\": \\\"SELECT name, age FROM user WHERE age < 18\\\", \\\"type\\\": \\\"response_table\\\", \\\"title\\\": \\\"\\\", \\\"describe\\\": \\\"I have selected a response_table to display the names and ages of users with an age less than 18. The SQL query retrieves the name and age columns from the user table where the age is less than 18.\\\", \\\"data\\\": [{\\\"name\\\": \\\"Tom\\\", \\\"age\\\": 10}, {\\\"name\\\": \\\"Jerry\\\", \\\"age\\\": 16}]}\\n```\"}]\n```"
    }
]
```
What is GPT-Vis? GPT-Vis is a collection components for GPTs, generative AI, and LLM projects. 
It provides a protocol(a custom code syntax in markdown) to describe the output of the AI model, 
and be able to render the output in rich UI components. 

Here, the output is a table, which contains the name and age of the users with age less than 18.