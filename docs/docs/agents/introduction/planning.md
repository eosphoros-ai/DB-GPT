# Agents Planning

When faced with a complex task, humans tend to deconstruct it into
simpler subtasks and solve them individually. The planning module aims to empower the
agents with such human capability, which is expected to make the agent behave more
reasonably, powerfully, and reliably

## Introduction

Here is a simple architecture diagram of the planning module:

<p align="left">
  <img src={'/img/agents/introduction/agents_planning.png'} width="720px" />
</p>

In the above diagram, the planning module will receive the task from the user, then it will 
decompose the task into subtasks and assign them to the corresponding agents(Agent1, Agent2,...).

## Analysis Your Database With Agents

In the following example, we will show you how to use the planning module to analyze your database.

To run this example, please install the dependencies according to [previous instructions](./database#installation).

### Prepare The Database

For simplicity, we will use a temporary SQLite database to store the data. The database 
will be created in the temporary directory and will be deleted after the program exits.

Fist, create a temporary SQLite database and create some tables and insert some data:

```python
from dbgpt.datasource.rdbms.conn_sqlite import SQLiteTempConnector

connector = SQLiteTempConnector.create_temporary_db()
connector.create_temp_tables(
    {
        "students": {
            "columns": {
                "student_id": "INTEGER PRIMARY KEY",
                "student_name": "TEXT",
                "major": "TEXT",
                "year_of_enrollment": "INTEGER",
                "student_age": "INTEGER",
            },
            "data": [
                (1, "Zhang San", "Computer Science", 2020, 20),
                (2, "Li Si", "Computer Science", 2021, 19),
                (3, "Wang Wu", "Physics", 2020, 21),
                (4, "Zhao Liu", "Mathematics", 2021, 19),
                (5, "Zhou Qi", "Computer Science", 2022, 18),
                (6, "Wu Ba", "Physics", 2020, 21),
                (7, "Zheng Jiu", "Mathematics", 2021, 19),
                (8, "Sun Shi", "Computer Science", 2022, 18),
                (9, "Liu Shiyi", "Physics", 2020, 21),
                (10, "Chen Shier", "Mathematics", 2021, 19),
            ],
        },
        "courses": {
            "columns": {
                "course_id": "INTEGER PRIMARY KEY",
                "course_name": "TEXT",
                "credit": "REAL",
            },
            "data": [
                (1, "Introduction to Computer Science", 3),
                (2, "Data Structures", 4),
                (3, "Advanced Physics", 3),
                (4, "Linear Algebra", 4),
                (5, "Calculus", 5),
                (6, "Programming Languages", 4),
                (7, "Quantum Mechanics", 3),
                (8, "Probability Theory", 4),
                (9, "Database Systems", 4),
                (10, "Computer Networks", 4),
            ],
        },
        "scores": {
            "columns": {
                "student_id": "INTEGER",
                "course_id": "INTEGER",
                "score": "INTEGER",
                "semester": "TEXT",
            },
            "data": [
                (1, 1, 90, "Fall 2020"),
                (1, 2, 85, "Spring 2021"),
                (2, 1, 88, "Fall 2021"),
                (2, 2, 90, "Spring 2022"),
                (3, 3, 92, "Fall 2020"),
                (3, 4, 85, "Spring 2021"),
                (4, 3, 88, "Fall 2021"),
                (4, 4, 86, "Spring 2022"),
                (5, 1, 90, "Fall 2022"),
                (5, 2, 87, "Spring 2023"),
            ],
        },
    }
)
```

### Create A Database Resource

```python
from dbgpt.agent.resource import RDBMSConnectorResource

db_resource = RDBMSConnectorResource("student_manager", connector=connector)
```

### Analyze The Database Automatically Plan

To create a plan to analyze the database, here we introduce a new agent `AutoPlanChatManager`,
which can automatically plan the task and assign the subtasks to the corresponding agents.

`AutoPlanChatManager` is a special agent, the creation of the agent is similar to other agents,
but it has a special method `hire` to hire other agents.

```python

import asyncio
import os

from dbgpt.agent import (
    AgentContext,
    AgentMemory,
    AutoPlanChatManager,
    LLMConfig,
    UserProxyAgent,
)
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
    manager = (
        await AutoPlanChatManager()
        .bind(context)
        .bind(agent_memory)
        .bind(LLMConfig(llm_client=llm_client))
        .build()
    )
    manager.hire([sql_boy])

    await user_proxy.initiate_chat(
        recipient=manager,
        reviewer=user_proxy,
        message="Analyze student scores from at least three dimensions",
    )

    # dbgpt-vis message infos
    print(await agent_memory.gpts_memory.one_chat_completions("test123"))


if __name__ == "__main__":
    asyncio.run(main())
```

The output will be like this:

``````bash
--------------------------------------------------------------------------------
User (to AutoPlanChatManager)-[]:

"Analyze student scores from at least three dimensions"

--------------------------------------------------------------------------------
un_stream ai response: [
    {
        "serial_number": "1",
        "agent": "DataScientist",
        "content": "Retrieve student scores data from the database including scores for each subject, overall performance, and attendance records.",
        "rely": ""
    },
    {
        "serial_number": "2",
        "agent": "DataScientist",
        "content": "Analyze student scores data to identify trends and patterns in academic performance, subject-wise scores, and attendance correlation.",
        "rely": "1"
    },
    {
        "serialjson_number": "3",
        "agent": "DataScientist",
        "content": "Visualize the analyzed data using appropriate graphs and charts to represent the student scores from different dimensions effectively.",
        "rely": "2"
    }
]

--------------------------------------------------------------------------------
Planner (to AutoPlanChatManager)-[gpt-3.5-turbo]:

"[\n    {\n        \"serial_number\": \"1\",\n        \"agent\": \"DataScientist\",\n        \"content\": \"Retrieve student scores data from the database including scores for each subject, overall performance, and attendance records.\",\n        \"rely\": \"\"\n    },\n    {\n        \"serial_number\": \"2\",\n        \"agent\": \"DataScientist\",\n        \"content\": \"Analyze student scores data to identify trends and patterns in academic performance, subject-wise scores, and attendance correlation.\",\n        \"rely\": \"1\"\n    },\n    {\n        \"serialjson_number\": \"3\",\n        \"agent\": \"DataScientist\",\n        \"content\": \"Visualize the analyzed data using appropriate graphs and charts to represent the student scores from different dimensions effectively.\",\n        \"rely\": \"2\"\n    }\n]"
>>>>>>>>Planner Review info: 
Pass(None)
>>>>>>>>Planner Action report: 
execution succeeded,
[
    {
        "serial_number": "1",
        "agent": "DataScientist",
        "content": "Retrieve student scores data from the database including scores for each subject, overall performance, and attendance records.",
        "rely": ""
    },
    {
        "serial_number": "2",
        "agent": "DataScientist",
        "content": "Analyze student scores data to identify trends and patterns in academic performance, subject-wise scores, and attendance correlation.",
        "rely": "1"
    },
    {
        "serialjson_number": "3",
        "agent": "DataScientist",
        "content": "Visualize the analyzed data using appropriate graphs and charts to represent the student scores from different dimensions effectively.",
        "rely": "2"
    }
]

--------------------------------------------------------------------------------
GroupChat select_speaker failed to resolve the next speaker's name. This is because the speaker selection OAI call returned:
DataScientist

--------------------------------------------------------------------------------
AutoPlanChatManager (to Edgar)-[]:

"Retrieve student scores data from the database including scores for each subject, overall performance, and attendance records."

--------------------------------------------------------------------------------
un_stream ai response: {
  "display_type": "response_table",
  "sql": "SELECT s.student_id, s.student_name, s.major, s.year_of_enrollment, s.student_age, c.course_name, c.credit, sc.score, sc.semester FROM students s JOIN scores sc ON s.student_id = sc.student_id JOIN courses c ON sc.course_id = c.course_id",
  "thought": "I have crafted a SQL query that retrieves student scores data including scores for each subject, overall performance, and attendance records by joining the 'students', 'scores', and 'courses' tables on their respective keys."
}

--------------------------------------------------------------------------------
Edgar (to AutoPlanChatManager)-[gpt-3.5-turbo]:

"{\n  \"display_type\": \"response_table\",\n  \"sql\": \"SELECT s.student_id, s.student_name, s.major, s.year_of_enrollment, s.student_age, c.course_name, c.credit, sc.score, sc.semester FROM students s JOIN scores sc ON s.student_id = sc.student_id JOIN courses c ON sc.course_id = c.course_id\",\n  \"thought\": \"I have crafted a SQL query that retrieves student scores data including scores for each subject, overall performance, and attendance records by joining the 'students', 'scores', and 'courses' tables on their respective keys.\"\n}"
>>>>>>>>Edgar Review info: 
Pass(None)
>>>>>>>>Edgar Action report: 
execution succeeded,
{"display_type":"response_table","sql":"SELECT s.student_id, s.student_name, s.major, s.year_of_enrollment, s.student_age, c.course_name, c.credit, sc.score, sc.semester FROM students s JOIN scores sc ON s.student_id = sc.student_id JOIN courses c ON sc.course_id = c.course_id","thought":"I have crafted a SQL query that retrieves student scores data including scores for each subject, overall performance, and attendance records by joining the 'students', 'scores', and 'courses' tables on their respective keys."}

--------------------------------------------------------------------------------
GroupChat select_speaker failed to resolve the next speaker's name. This is because the speaker selection OAI call returned:
DataScientist

--------------------------------------------------------------------------------
AutoPlanChatManager (to Edgar)-[]:

"Read the result data of the dependent steps in the above historical message to complete the current goal:Analyze student scores data to identify trends and patterns in academic performance, subject-wise scores, and attendance correlation."

--------------------------------------------------------------------------------
un_stream ai response: {
  "display_type": "response_table",
  "sql": "SELECT student_id, student_name, course_name, credit, AVG(score) AS average_score, COUNT(score) AS total_scores, MAX(score) AS highest_score, MIN(score) AS lowest_score, SUM(score) AS total_score, AVG(semester) AS average_semester FROM (SELECT s.student_id, s.student_name, c.course_name, c.credit, sc.score, sc.semester FROM students s JOIN scores sc ON s.student_id = sc.student_id JOIN courses c ON sc.course_id = c.course_id) GROUP BY student_id, course_name",
  "thought": "I have created a SQL query that analyzes student scores data to identify trends and patterns in academic performance, subject-wise scores, and attendance correlation. The query calculates average score, total scores, highest score, lowest score, total score, and average semester for each student in each course."
}

--------------------------------------------------------------------------------
Edgar (to AutoPlanChatManager)-[gpt-3.5-turbo]:

"{\n  \"display_type\": \"response_table\",\n  \"sql\": \"SELECT student_id, student_name, course_name, credit, AVG(score) AS average_score, COUNT(score) AS total_scores, MAX(score) AS highest_score, MIN(score) AS lowest_score, SUM(score) AS total_score, AVG(semester) AS average_semester FROM (SELECT s.student_id, s.student_name, c.course_name, c.credit, sc.score, sc.semester FROM students s JOIN scores sc ON s.student_id = sc.student_id JOIN courses c ON sc.course_id = c.course_id) GROUP BY student_id, course_name\",\n  \"thought\": \"I have created a SQL query that analyzes student scores data to identify trends and patterns in academic performance, subject-wise scores, and attendance correlation. The query calculates average score, total scores, highest score, lowest score, total score, and average semester for each student in each course.\"\n}"
>>>>>>>>Edgar Review info: 
Pass(None)
>>>>>>>>Edgar Action report: 
execution succeeded,
{"display_type":"response_table","sql":"SELECT student_id, student_name, course_name, credit, AVG(score) AS average_score, COUNT(score) AS total_scores, MAX(score) AS highest_score, MIN(score) AS lowest_score, SUM(score) AS total_score, AVG(semester) AS average_semester FROM (SELECT s.student_id, s.student_name, c.course_name, c.credit, sc.score, sc.semester FROM students s JOIN scores sc ON s.student_id = sc.student_id JOIN courses c ON sc.course_id = c.course_id) GROUP BY student_id, course_name","thought":"I have created a SQL query that analyzes student scores data to identify trends and patterns in academic performance, subject-wise scores, and attendance correlation. The query calculates average score, total scores, highest score, lowest score, total score, and average semester for each student in each course."}

--------------------------------------------------------------------------------
GroupChat select_speaker failed to resolve the next speaker's name. This is because the speaker selection OAI call returned:
DataScientist

--------------------------------------------------------------------------------
AutoPlanChatManager (to Edgar)-[]:

"Read the result data of the dependent steps in the above historical message to complete the current goal:Visualize the analyzed data using appropriate graphs and charts to represent the student scores from different dimensions effectively."

--------------------------------------------------------------------------------
un_stream ai response: {
  "display_type": "response_table",
  "sql": "SELECT student_id, student_name, course_name, credit, AVG(score) AS average_score, COUNT(score) AS total_scores, MAX(score) AS highest_score, MIN(score) AS lowest_score, SUM(score) AS total_score, AVG(semester) AS average_semester FROM (SELECT s.student_id, s.student_name, c.course_name, c.credit, sc.score, sc.semester FROM students s JOIN scores sc ON s.student_id = sc.student_id JOIN courses c ON sc.course_id = c.course_id) GROUP BY student_id, course_name",
  "thought": "The SQL query provided will generate a table with the analyzed data including average score, total scores, highest score, lowest score, total score, and average semester for each student in each course. This table can be further used for visualization purposes to represent student scores from different dimensions effectively."
}

--------------------------------------------------------------------------------
Edgar (to AutoPlanChatManager)-[gpt-3.5-turbo]:

"{\n  \"display_type\": \"response_table\",\n  \"sql\": \"SELECT student_id, student_name, course_name, credit, AVG(score) AS average_score, COUNT(score) AS total_scores, MAX(score) AS highest_score, MIN(score) AS lowest_score, SUM(score) AS total_score, AVG(semester) AS average_semester FROM (SELECT s.student_id, s.student_name, c.course_name, c.credit, sc.score, sc.semester FROM students s JOIN scores sc ON s.student_id = sc.student_id JOIN courses c ON sc.course_id = c.course_id) GROUP BY student_id, course_name\",\n  \"thought\": \"The SQL query provided will generate a table with the analyzed data including average score, total scores, highest score, lowest score, total score, and average semester for each student in each course. This table can be further used for visualization purposes to represent student scores from different dimensions effectively.\"\n}"
>>>>>>>>Edgar Review info: 
Pass(None)
>>>>>>>>Edgar Action report: 
execution succeeded,
{"display_type":"response_table","sql":"SELECT student_id, student_name, course_name, credit, AVG(score) AS average_score, COUNT(score) AS total_scores, MAX(score) AS highest_score, MIN(score) AS lowest_score, SUM(score) AS total_score, AVG(semester) AS average_semester FROM (SELECT s.student_id, s.student_name, c.course_name, c.credit, sc.score, sc.semester FROM students s JOIN scores sc ON s.student_id = sc.student_id JOIN courses c ON sc.course_id = c.course_id) GROUP BY student_id, course_name","thought":"The SQL query provided will generate a table with the analyzed data including average score, total scores, highest score, lowest score, total score, and average semester for each student in each course. This table can be further used for visualization purposes to represent student scores from different dimensions effectively."}

--------------------------------------------------------------------------------

--------------------------------------------------------------------------------
AutoPlanChatManager (to User)-[]:

"Analyze student scores from at least three dimensions"
>>>>>>>>AutoPlanChatManager Review info: 
Pass(None)
>>>>>>>>AutoPlanChatManager Action report: 
execution succeeded,
```vis-chart
{"sql": "SELECT student_id, student_name, course_name, credit, AVG(score) AS average_score, COUNT(score) AS total_scores, MAX(score) AS highest_score, MIN(score) AS lowest_score, SUM(score) AS total_score, AVG(semester) AS average_semester FROM (SELECT s.student_id, s.student_name, c.course_name, c.credit, sc.score, sc.semester FROM students s JOIN scores sc ON s.student_id = sc.student_id JOIN courses c ON sc.course_id = c.course_id) GROUP BY student_id, course_name", "type": "response_table", "title": "", "describe": "The SQL query provided will generate a table with the analyzed data including average score, total scores, highest score, lowest score, total score, and average semester for each student in each course. This table can be further used for visualization purposes to represent student scores from different dimensions effectively.", "data": [{"student_id": 1, "student_name": "Zhang San", "course_name": "Data Structures", "credit": 4.0, "average_score": 85.0, "total_scores": 1, "highest_score": 85, "lowest_score": 85, "total_score": 85, "average_semester": 0.0}, {"student_id": 1, "student_name": "Zhang San", "course_name": "Introduction to Computer Science", "credit": 3.0, "average_score": 90.0, "total_scores": 1, "highest_score": 90, "lowest_score": 90, "total_score": 90, "average_semester": 0.0}, {"student_id": 2, "student_name": "Li Si", "course_name": "Data Structures", "credit": 4.0, "average_score": 90.0, "total_scores": 1, "highest_score": 90, "lowest_score": 90, "total_score": 90, "average_semester": 0.0}, {"student_id": 2, "student_name": "Li Si", "course_name": "Introduction to Computer Science", "credit": 3.0, "average_score": 88.0, "total_scores": 1, "highest_score": 88, "lowest_score": 88, "total_score": 88, "average_semester": 0.0}, {"student_id": 3, "student_name": "Wang Wu", "course_name": "Advanced Physics", "credit": 3.0, "average_score": 92.0, "total_scores": 1, "highest_score": 92, "lowest_score": 92, "total_score": 92, "average_semester": 0.0}, {"student_id": 3, "student_name": "Wang Wu", "course_name": "Linear Algebra", "credit": 4.0, "average_score": 85.0, "total_scores": 1, "highest_score": 85, "lowest_score": 85, "total_score": 85, "average_semester": 0.0}, {"student_id": 4, "student_name": "Zhao Liu", "course_name": "Advanced Physics", "credit": 3.0, "average_score": 88.0, "total_scores": 1, "highest_score": 88, "lowest_score": 88, "total_score": 88, "average_semester": 0.0}, {"student_id": 4, "student_name": "Zhao Liu", "course_name": "Linear Algebra", "credit": 4.0, "average_score": 86.0, "total_scores": 1, "highest_score": 86, "lowest_score": 86, "total_score": 86, "average_semester": 0.0}, {"student_id": 5, "student_name": "Zhou Qi", "course_name": "Data Structures", "credit": 4.0, "average_score": 87.0, "total_scores": 1, "highest_score": 87, "lowest_score": 87, "total_score": 87, "average_semester": 0.0}, {"student_id": 5, "student_name": "Zhou Qi", "course_name": "Introduction to Computer Science", "credit": 3.0, "average_score": 90.0, "total_scores": 1, "highest_score": 90, "lowest_score": 90, "total_score": 90, "average_semester": 0.0}]}
```

--------------------------------------------------------------------------------
``````

The output is [GPT-Vis](https://github.com/eosphoros-ai/GPT-Vis) protocol, we can parse some
useful results.

**1. Plans**
```json
[
    {
        "serial_number": "1",
        "agent": "DataScientist",
        "content": "Retrieve student scores data from the database including scores for each subject, overall performance, and attendance records.",
        "rely": ""
    },
    {
        "serial_number": "2",
        "agent": "DataScientist",
        "content": "Analyze student scores data to identify trends and patterns in academic performance, subject-wise scores, and attendance correlation.",
        "rely": "1"
    },
    {
        "serialjson_number": "3",
        "agent": "DataScientist",
        "content": "Visualize the analyzed data using appropriate graphs and charts to represent the student scores from different dimensions effectively.",
        "rely": "2"
    }
]
```

**2. LLM output of first task**
```json
{
  "display_type": "response_table",
  "sql": "SELECT s.student_id, s.student_name, s.major, s.year_of_enrollment, s.student_age, c.course_name, c.credit, sc.score, sc.semester FROM students s JOIN scores sc ON s.student_id = sc.student_id JOIN courses c ON sc.course_id = c.course_id",
  "thought": "I have crafted a SQL query that retrieves student scores data including scores for each subject, overall performance, and attendance records by joining the 'students', 'scores', and 'courses' tables on their respective keys."
}
```

**3. LLM output of second task**
```json
{
  "display_type": "response_table",
  "sql": "SELECT student_id, student_name, course_name, credit, AVG(score) AS average_score, COUNT(score) AS total_scores, MAX(score) AS highest_score, MIN(score) AS lowest_score, SUM(score) AS total_score, AVG(semester) AS average_semester FROM (SELECT s.student_id, s.student_name, c.course_name, c.credit, sc.score, sc.semester FROM students s JOIN scores sc ON s.student_id = sc.student_id JOIN courses c ON sc.course_id = c.course_id) GROUP BY student_id, course_name",
  "thought": "I have created a SQL query that analyzes student scores data to identify trends and patterns in academic performance, subject-wise scores, and attendance correlation. The query calculates average score, total scores, highest score, lowest score, total score, and average semester for each student in each course."
}
```

**4. LLM output of third task**
```json
{
  "display_type": "response_table",
  "sql": "SELECT student_id, student_name, course_name, credit, AVG(score) AS average_score, COUNT(score) AS total_scores, MAX(score) AS highest_score, MIN(score) AS lowest_score, SUM(score) AS total_score, AVG(semester) AS average_semester FROM (SELECT s.student_id, s.student_name, c.course_name, c.credit, sc.score, sc.semester FROM students s JOIN scores sc ON s.student_id = sc.student_id JOIN courses c ON sc.course_id = c.course_id) GROUP BY student_id, course_name",
  "thought": "The SQL query provided will generate a table with the analyzed data including average score, total scores, highest score, lowest score, total score, and average semester for each student in each course. This table can be further used for visualization purposes to represent student scores from different dimensions effectively."
}
```

Of course, it will include the data after the execution of the SQL query if you run 
above code, here we not show the data because it is too long.