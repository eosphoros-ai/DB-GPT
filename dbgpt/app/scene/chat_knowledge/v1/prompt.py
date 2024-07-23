from dbgpt._private.config import Config
from dbgpt.app.scene import AppScenePromptTemplateAdapter, ChatScene
from dbgpt.app.scene.chat_normal.out_parser import NormalChatOutputParser
from dbgpt.core import (
    ChatPromptTemplate,
    HumanPromptTemplate,
    MessagesPlaceholder,
    SystemPromptTemplate,
)

CFG = Config()

PROMPT_SCENE_DEFINE = """A chat between a curious user and an artificial intelligence assistant, who very familiar with database related knowledge. 
The assistant gives helpful, detailed, professional and polite answers to the user's questions. """


_DEFAULT_TEMPLATE_ZH = """ 基于以下给出的已知信息, 准守规范约束，专业、简要回答用户的问题.
规范约束:
     1.如果已知信息包含的图片、链接、表格、代码块等特殊markdown标签格式的信息，确保在答案中包含原文这些图片、链接、表格和代码标签，不要丢弃不要修改，如:图片格式：![image.png](xxx), 链接格式:[xxx](xxx), 表格格式:|xxx|xxx|xxx|, 代码格式:```xxx```.
     2.如果无法从提供的内容中获取答案, 请说: "知识库中提供的内容不足以回答此问题" 禁止胡乱编造.
     3.回答的时候最好按照1.2.3.点进行总结, 并以markdwon格式显示.
            已知内容: 
            {context}
            问题:
            {question},请使用和用户相同的语言进行回答.
"""
_DEFAULT_TEMPLATE_EN = """ Based on the known information below, provide users with professional and concise answers to their questions.
constraints:
    1.Ensure to include original markdown formatting elements such as images, links, tables, or code blocks without alteration in the response if they are present in the provided information.
        For example, image format should be ![image.png](xxx), link format [xxx](xxx), table format should be represented with |xxx|xxx|xxx|, and code format with xxx.
    2.If the information available in the knowledge base is insufficient to answer the question, state clearly: "The content provided in the knowledge base is not enough to answer this question," and avoid making up answers.
    3.When responding, it is best to summarize the points in the order of 1, 2, 3, And displayed in markdwon format.
            known information: 
            {context}
            question:
            {question},when answering, use the same language as the "user".
"""

_DEFAULT_TEMPLATE = (
    _DEFAULT_TEMPLATE_EN if CFG.LANGUAGE == "en" else _DEFAULT_TEMPLATE_ZH
)

PROMPT_NEED_STREAM_OUT = True
prompt = ChatPromptTemplate(
    messages=[
        SystemPromptTemplate.from_template(_DEFAULT_TEMPLATE),
        MessagesPlaceholder(variable_name="chat_history"),
        HumanPromptTemplate.from_template("{question}"),
    ]
)

prompt_adapter = AppScenePromptTemplateAdapter(
    prompt=prompt,
    template_scene=ChatScene.ChatKnowledge.value(),
    stream_out=PROMPT_NEED_STREAM_OUT,
    output_parser=NormalChatOutputParser(is_stream_out=PROMPT_NEED_STREAM_OUT),
    need_historical_messages=False,
)

CFG.prompt_template_registry.register(
    prompt_adapter, language=CFG.LANGUAGE, is_default=True
)
