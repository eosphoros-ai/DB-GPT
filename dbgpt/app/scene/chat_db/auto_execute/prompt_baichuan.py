#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
from dbgpt.core.interface.prompt import PromptTemplate
from dbgpt._private.config import Config
from dbgpt.app.scene import ChatScene
from dbgpt.app.scene.chat_db.auto_execute.out_parser import DbChatOutputParser

CFG = Config()

PROMPT_SCENE_DEFINE = None

_DEFAULT_TEMPLATE = """
你是一个 SQL 专家，给你一个用户的问题，你会生成一条对应的 {dialect} 语法的 SQL 语句。

如果用户没有在问题中指定 sql 返回多少条数据，那么你生成的 sql 最多返回 {top_k} 条数据。 
你应该尽可能少地使用表。

已知表结构信息如下：
{table_info}

注意：
1. 只能使用表结构信息中提供的表来生成 sql，如果无法根据提供的表结构中生成 sql ，请说：“提供的表结构信息不足以生成 sql 查询。” 禁止随意捏造信息。
2. 不要查询不存在的列，注意哪一列位于哪张表中。
3. 使用 json 格式回答，确保你的回答是必须是正确的 json 格式，并且能被 python 语言的 `json.loads` 库解析, 格式如下：
{response}
"""

RESPONSE_FORMAT_SIMPLE = {
    "thoughts": "对用户说的想法摘要",
    "sql": "生成的将被执行的 SQL",
}


PROMPT_NEED_STREAM_OUT = False

# Temperature is a configuration hyperparameter that controls the randomness of language model output.
# A high temperature produces more unpredictable and creative results, while a low temperature produces more common and conservative output.
# For example, if you adjust the temperature to 0.5, the model will usually generate text that is more predictable and less creative than if you set the temperature to 1.0.
PROMPT_TEMPERATURE = 0.5

prompt = PromptTemplate(
    template_scene=ChatScene.ChatWithDbExecute.value(),
    input_variables=["input", "table_info", "dialect", "top_k", "response"],
    response_format=json.dumps(RESPONSE_FORMAT_SIMPLE, ensure_ascii=False, indent=4),
    template_is_strict=False,
    template_define=PROMPT_SCENE_DEFINE,
    template=_DEFAULT_TEMPLATE,
    stream_out=PROMPT_NEED_STREAM_OUT,
    output_parser=DbChatOutputParser(is_stream_out=PROMPT_NEED_STREAM_OUT),
    # example_selector=sql_data_example,
    temperature=PROMPT_TEMPERATURE,
)

CFG.prompt_template_registry.register(
    prompt,
    language=CFG.LANGUAGE,
    is_default=False,
    model_names=["baichuan-13b", "baichuan-7b"],
)
