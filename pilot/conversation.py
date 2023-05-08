#!/usr/bin/env python3
# -*- coding:utf-8 -*-

import dataclasses
from enum import auto, Enum
from typing import List, Any
from pilot.configs.model_config import DB_SETTINGS

class SeparatorStyle(Enum):
    
    SINGLE = auto()
    TWO = auto()

@dataclasses.dataclass
class Conversation:
    """This class keeps all conversation history. """

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
        for i, (role, msg) in enumerate(self.messages[self.offset:]):
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
            "conv_id": self.conv_id
        }


def gen_sqlgen_conversation(dbname):
    from pilot.connections.mysql import MySQLOperator
    mo = MySQLOperator(
        **DB_SETTINGS
    )

    message = ""

    schemas = mo.get_schema(dbname)
    for s in schemas:
        message += s["schema_info"] + ";"
    return f"数据库{dbname}的Schema信息如下: {message}\n"

conv_one_shot = Conversation(
    system="A chat between a curious human and an artificial intelligence assistant, who very familiar with database related knowledge. "
    "The assistant gives helpful, detailed, professional and polite answers to the human's questions. ",
    roles=("Human", "Assistant"),
    messages=(
        (
            "Human",
            "What are the key differences between mysql and postgres?",
        ),
        (
            "Assistant",
            "MySQL and PostgreSQL are both popular open-source relational database management systems (RDBMS) "
            "that have many similarities but also some differences. Here are some key differences: \n"
            "1. Data Types: PostgreSQL has a more extensive set of data types, "
            "including support for array, hstore, JSON, and XML, whereas MySQL has a more limited set.\n"
            "2. ACID compliance: Both MySQL and PostgreSQL support ACID compliance (Atomicity, Consistency, Isolation, Durability), "
            "but PostgreSQL is generally considered to be more strict in enforcing it.\n"
            "3. Replication: MySQL has a built-in replication feature, which allows you to replicate data across multiple servers,"
            "whereas PostgreSQL has a similar feature, but it is not as mature as MySQL's.\n"
            "4. Performance: MySQL is generally considered to be faster and more efficient in handling large datasets, "
            "whereas PostgreSQL is known for its robustness and reliability.\n"
            "5. Licensing: MySQL is licensed under the GPL (General Public License), which means that it is free and open-source software, "
            "whereas PostgreSQL is licensed under the PostgreSQL License, which is also free and open-source but with different terms.\n"

            "Ultimately, the choice between MySQL and PostgreSQL depends on the specific needs and requirements of your application. "
            "Both are excellent database management systems, and choosing the right one "
            "for your project requires careful consideration of your application's requirements, performance needs, and scalability."
        ),
    ),
    offset=2,
    sep_style=SeparatorStyle.SINGLE,
    sep="###"
)
    
conv_vicuna_v1 = Conversation(
    system = "A chat between a curious user and an artificial intelligence assistant. who very familiar with database related knowledge. "
    "The assistant gives helpful, detailed, professional and polite answers to the user's questions. ",
    roles=("USER", "ASSISTANT"),
    messages=(),
    offset=0,
    sep_style=SeparatorStyle.TWO,
    sep=" ",
    sep2="</s>",
)


conv_qa_prompt_template = """ 基于以下已知的信息, 专业、详细的回答用户的问题。
            如果无法从提供的恶内容中获取答案, 请说: "知识库中提供的内容不足以回答此问题", 但是你可以给出一些与问题相关答案的建议:   
            
            已知内容: 
            {context}
            问题:
            {question}
"""

default_conversation = conv_one_shot

conversation_types = {
    "native": "LLM原生对话",
    "default_knownledge": "默认知识库对话",
    "custome":  "新增知识库对话",
}

conv_templates = {
    "conv_one_shot": conv_one_shot,
    "vicuna_v1": conv_vicuna_v1,
}


if __name__ == "__main__":
    message = gen_sqlgen_conversation("dbgpt")
    print(message)