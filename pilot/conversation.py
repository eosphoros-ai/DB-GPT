#!/usr/bin/env python3
# -*- coding:utf-8 -*-

import dataclasses
import uuid
from enum import auto, Enum
from typing import List, Any
from pilot.language.translation_handler import get_lang_text

from pilot.configs.config import Config

CFG = Config()

DB_SETTINGS = {
    "user": CFG.LOCAL_DB_USER,
    "password": CFG.LOCAL_DB_PASSWORD,
    "host": CFG.LOCAL_DB_HOST,
    "port": CFG.LOCAL_DB_PORT,
}

ROLE_USER = "USER"
ROLE_ASSISTANT = "Assistant"


class SeparatorStyle(Enum):
    SINGLE = auto()
    TWO = auto()
    THREE = auto()
    FOUR = auto()


@dataclasses.dataclass
class Conversation:
    """This class keeps all conversation history."""

    system: str
    roles: List[str]
    messages: List[List[str]]
    offset: int
    sep_style: SeparatorStyle = SeparatorStyle.SINGLE
    sep: str = "###"
    sep2: str = None

    # Used for gradio server
    skip_next: bool = False
    conv_id: Any = None
    last_user_input: Any = None

    def get_prompt(self):
        if self.sep_style == SeparatorStyle.SINGLE:
            ret = self.system + self.sep
            for role, message in self.messages:
                if message:
                    ret += role + ": " + message + self.sep
                else:
                    ret += role + ":"
            return ret

        elif self.sep_style == SeparatorStyle.TWO:
            seps = [self.sep, self.sep2]
            ret = self.system + seps[0]
            for i, (role, message) in enumerate(self.messages):
                if message:
                    ret += role + ":" + message + seps[i % 2]
                else:
                    ret += role + ":"
            return ret
        else:
            raise ValueError(f"Invalid style: {self.sep_style}")

    def append_message(self, role, message):
        self.messages.append([role, message])

    def to_gradio_chatbot(self):
        ret = []
        for i, (role, msg) in enumerate(self.messages[self.offset :]):
            if i % 2 == 0:
                ret.append([msg, None])
            else:
                ret[-1][-1] = msg

        return ret

    def copy(self):
        return Conversation(
            system=self.system,
            roles=self.roles,
            messages=[[x, y] for x, y in self.messages],
            offset=self.offset,
            sep_style=self.sep_style,
            sep=self.sep,
            sep2=self.sep2,
            conv_id=self.conv_id,
        )

    def dict(self):
        return {
            "system": self.system,
            "roles": self.roles,
            "messages": self.messages,
            "offset": self.offset,
            "sep": self.sep,
            "sep2": self.sep2,
            "conv_id": self.conv_id,
        }


conv_default = Conversation(
    system=None,
    roles=("human", "ai"),
    messages=[],
    offset=0,
    sep_style=SeparatorStyle.SINGLE,
    sep="###",
)

#
# conv_one_shot = Conversation(
#     system="A chat between a curious user and an artificial intelligence assistant, who very familiar with database related knowledge. "
#     "The assistant gives helpful, detailed, professional and polite answers to the user's questions. ",
#     roles=("USER", "Assistant"),
#     messages=(
#         (
#             "USER",
#             "What are the key differences between mysql and postgres?",
#         ),
#         (
#             "Assistant",
#             "MySQL and PostgreSQL are both popular open-source relational database management systems (RDBMS) "
#             "that have many similarities but also some differences. Here are some key differences: \n"
#             "1. Data Types: PostgreSQL has a more extensive set of data types, "
#             "including support for array, hstore, JSON, and XML, whereas MySQL has a more limited set.\n"
#             "2. ACID compliance: Both MySQL and PostgreSQL support ACID compliance (Atomicity, Consistency, Isolation, Durability), "
#             "but PostgreSQL is generally considered to be more strict in enforcing it.\n"
#             "3. Replication: MySQL has a built-in replication feature, which allows you to replicate data across multiple servers,"
#             "whereas PostgreSQL has a similar feature, but it is not as mature as MySQL's.\n"
#             "4. Performance: MySQL is generally considered to be faster and more efficient in handling large datasets, "
#             "whereas PostgreSQL is known for its robustness and reliability.\n"
#             "5. Licensing: MySQL is licensed under the GPL (General Public License), which means that it is free and open-source software, "
#             "whereas PostgreSQL is licensed under the PostgreSQL License, which is also free and open-source but with different terms.\n"
#             "Ultimately, the choice between MySQL and PostgreSQL depends on the specific needs and requirements of your application. "
#             "Both are excellent database management systems, and choosing the right one "
#             "for your project requires careful consideration of your application's requirements, performance needs, and scalability.",
#         ),
#     ),
#     offset=2,
#     sep_style=SeparatorStyle.SINGLE,
#     sep="###",
# )


conv_one_shot = Conversation(
    system="You are a DB-GPT. Please provide me with user input and all table information known in the database, so I can accurately query tables are involved in the user input. If there are multiple tables involved, I will separate them by comma. Here is an example:",
    roles=("USER", "ASSISTANT"),
    messages=(
        (
            "USER",
            "please query there are how many orders?"
            "Querying the table involved in the user input？"
            "database schema:"
            "database name:db_test, database type:MYSQL, table infos:table name:carts,table description:购物车表;table name:categories,table description:商品分类表;table name:chat_groups,table description:群组表;table name:chat_users,table description:聊天用户表;table name:friends,table description:好友表;table name:messages,table description:消息表;table name:orders,table description:订单表;table name:products,table description:商品表;table name:table_test,table description:;table name:users,table description:用户表，"
            "You should only respond in JSON format as described below and ensure the response can be parsed by Python json.loads"
            """Response Format: 
            {
                "table": ["orders", "products"]
            }
            """,
        ),
        (
            "Assistant",
            """
            {
                "table": ["orders", "products"]
            }
            """,
        ),
    ),
    offset=2,
    sep_style=SeparatorStyle.SINGLE,
    sep="###",
)

conv_vicuna_v1 = Conversation(
    system="A chat between a curious user and an artificial intelligence assistant. who very familiar with database related knowledge. "
    "The assistant gives helpful, detailed, professional and polite answers to the user's questions. ",
    roles=("USER", "ASSISTANT"),
    messages=(),
    offset=0,
    sep_style=SeparatorStyle.TWO,
    sep=" ",
    sep2="</s>",
)

auto_dbgpt_one_shot = Conversation(
    system="You are DB-GPT, an AI designed to answer questions about HackerNews by query `hackerbews` database in MySQL. "
    "Your decisions must always be made independently without seeking user assistance. Play to your strengths as an LLM and pursue simple strategies with no legal complications.",
    roles=("USER", "ASSISTANT"),
    messages=(
        (
            "USER",
            """ Answer how many users does app_users have by query ob database
              Constraints:
              1. If you are unsure how you previously did something or want to recall past events, thinking about similar events will help you remember.
              2. No user assistance
              3. Exclusively use the commands listed in double quotes e.g. "command name"


              Schema:
              Database gpt-user Schema information as follows: users(city,create_time,email,last_login_time,phone,user_name);


              Commands:
              1. analyze_code: Analyze Code, args: "code": "<full_code_string>"
              2. execute_python_file: Execute Python File, args: "filename": "<filename>"
              3. append_to_file: Append to file, args: "filename": "<filename>", "text": "<text>"
              4. delete_file: Delete file, args: "filename": "<filename>"
              5. list_files: List Files in Directory, args: "directory": "<directory>"
              6. read_file: Read file, args: "filename": "<filename>"
              7. write_to_file: Write to file, args: "filename": "<filename>", "text": "<text>"
              8. db_sql_executor: "Execute SQL in Database.", args: "sql": "<sql>"

              You should only respond in JSON format as described below and ensure the response can be parsed by Python json.loads
              Response Format: 
              {
                  "thoughts": {
                      "text": "thought",
                      "reasoning": "reasoning",
                      "plan": "- short bulleted\n- list that conveys\n- long-term plan",
                      "criticism": "constructive self-criticism",
                      "speak": "thoughts summary to say to user"
                  },
                  "command": {
                      "name": "command name",
                      "args": {
                          "arg name": "value"
                      }
                  }
              } 
            """,
        ),
        (
            "ASSISTANT",
            """
            {
                "thoughts": {
                    "text": "To answer how many users  by query  database we need to write SQL query to get the count of the distinct users from the database. We can use db_sql_executor command to execute the SQL query in  database.",
                    "reasoning": "We can use the sql_executor command to execute the SQL query for getting count of distinct users from the users database. We can select the count of the distinct users from the users table.",
                    "plan": "- Write SQL query to get count of distinct users from users database\n- Use db_sql_executor to execute the SQL query in OB database\n- Parse the SQL result to get the count\n- Respond with the count as the answer",
                    "criticism": "None",
                    "speak": "To get the number of users in users, I will execute an SQL query in OB database using the db_sql_executor command and respond with the count."
                },
                "command": {
                    "name": "db_sql_executor",
                    "args": {
                        "sql": "SELECT COUNT(DISTINCT(user_name)) FROM users ;"
                    }
                }
            } 
            """,
        ),
    ),
    offset=0,
    sep_style=SeparatorStyle.SINGLE,
    sep="###",
)

auto_dbgpt_without_shot = Conversation(
    system="You are DB-GPT, an AI designed to answer questions about users by query `users` database in MySQL. "
    "Your decisions must always be made independently without seeking user assistance. Play to your strengths as an LLM and pursue simple strategies with no legal complications.",
    roles=("USER", "ASSISTANT"),
    messages=(),
    offset=0,
    sep_style=SeparatorStyle.SINGLE,
    sep=" ",
    sep2="</s>",
)

conv_qa_prompt_template = """ 基于以下已知的信息, 专业、简要的回答用户的问题,
            如果无法从提供的内容中获取答案, 请说: "知识库中提供的内容不足以回答此问题" 禁止胡乱编造。 
            已知内容: 
            {context}
            问题:
            {question}
            
"""

# conv_qa_prompt_template = """ Please provide the known information so that I can professionally and briefly answer the user's question. If the answer cannot be obtained from the provided content,
#             please say: "The information provided in the knowledge base is insufficient to answer this question." Fabrication is prohibited.。
#             known information:
#             {context}
#             question:
#             {question}
# """
default_conversation = conv_default


chat_mode_title = {
    "sql_generate_diagnostics": get_lang_text("sql_generate_diagnostics"),
    "chat_use_plugin": get_lang_text("chat_use_plugin"),
    "knowledge_qa": get_lang_text("knowledge_qa"),
}

conversation_sql_mode = {
    "auto_execute_ai_response": get_lang_text("sql_generate_mode_direct"),
    "dont_execute_ai_response": get_lang_text("sql_generate_mode_none"),
}

conversation_types = {
    "native": get_lang_text("knowledge_qa_type_llm_native_dialogue"),
    "default_knownledge": get_lang_text(
        "knowledge_qa_type_default_knowledge_base_dialogue"
    ),
    "custome": get_lang_text("knowledge_qa_type_add_knowledge_base_dialogue"),
    "url": get_lang_text("knowledge_qa_type_url_knowledge_dialogue"),
}

conv_templates = {
    "conv_one_shot": conv_one_shot,
    "vicuna_v1": conv_vicuna_v1,
    "auto_dbgpt_one_shot": auto_dbgpt_one_shot,
}

conv_db_summary_templates = """
Based on the following known database information?, answer which tables are involved in the user input.
Known database information:{db_profile_summary}
Input:{db_input}
You should only respond in JSON format as described below and ensure the response can be parsed by Python json.loads
The response format must be JSON, and the key of JSON must be "table".

"""

if __name__ == "__main__":
    message = gen_sqlgen_conversation("dbgpt")
    print(message)
