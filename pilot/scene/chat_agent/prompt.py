import json
from pilot.prompts.prompt_new import PromptTemplate
from pilot.configs.config import Config
from pilot.scene.base import ChatScene
from pilot.common.schema import SeparatorStyle, ExampleType

from pilot.scene.chat_execution.out_parser import PluginChatOutputParser
from pilot.scene.chat_execution.example import plugin_example

CFG = Config()

_PROMPT_SCENE_DEFINE_EN = "You are a universal AI assistant."

_DEFAULT_TEMPLATE_EN = """
You need to analyze the user goals and, under the given constraints, prioritize using one of the following tools to solve the user goals.
Tool list:
    {tool_list}
Constraint:
	1. After selecting an available tool, please ensure that the output results include the following parts to use the tool: 
	<api-call><name>Selected Tool name</name><args><name>value</name></args></api-call>
	2. If you cannot analyze the exact tool for the problem, you can consider using the search engine tool among the tools first.
	3. Parameter content may need to be inferred based on the user's goals, not just extracted from text
	4. If you cannot find a suitable tool, please answer Unable to complete the goal.
    {expand_constraints}
User goals:
    {user_goal}
"""

_PROMPT_SCENE_DEFINE_ZH = "你是一个通用AI助手！"

_DEFAULT_TEMPLATE_ZH = """
根据用户目标，请一步步思考，如何在满足下面约束条件的前提下，优先使用给出工具回答或者完成用户目标。

约束条件:
	1.从下面给定工具列表找到可用的工具后，请确保输出结果包含以下内容用来使用工具:
	<api-call><name>Selected Tool name</name><args><arg1>value</arg1><arg2>value</arg2></args></api-call>
    2.请根据工具列表对应工具的定义来生成上述调用文本, 参考案例如下: 
        工具作用介绍: "工具名称", args: "参数1": "<参数1取值描述>","参数2": "<参数2取值描述>" 对应调用文本:<api-call><name>工具名称</name><args><参数1>value</参数1><参数2>value</参数2></args></api-call>
    3.根据上面约束的方式生成每个工具的调用，对于工具使用的提示文本，需要在工具使用前生成
    4.如果用户目标无法理解和意图不明确，优先使用搜索引擎工具
    5.参数内容可能需要根据用户的目标推理得到，不仅仅是从文本提取
    6.约束条件和工具信息作为推理过程的辅助信息，不要表达在给用户的输出内容中
    {expand_constraints}

工具列表:
    {tool_list}   

用户目标:
    {user_goal}
"""

_DEFAULT_TEMPLATE = (
    _DEFAULT_TEMPLATE_EN if CFG.LANGUAGE == "en" else _DEFAULT_TEMPLATE_ZH
)


_PROMPT_SCENE_DEFINE=(
    _PROMPT_SCENE_DEFINE_EN if CFG.LANGUAGE == "en" else _PROMPT_SCENE_DEFINE_ZH
)

RESPONSE_FORMAT = None


EXAMPLE_TYPE = ExampleType.ONE_SHOT
PROMPT_SEP = SeparatorStyle.SINGLE.value
### Whether the model service is streaming output
PROMPT_NEED_STREAM_OUT = True

prompt = PromptTemplate(
    template_scene=ChatScene.ChatAgent.value(),
    input_variables=["tool_list", "expand_constraints", "user_goal"],
    response_format=None,
    template_define=_PROMPT_SCENE_DEFINE,
    template=_DEFAULT_TEMPLATE,
    stream_out=PROMPT_NEED_STREAM_OUT,
    output_parser=PluginChatOutputParser(
        sep=PROMPT_SEP, is_stream_out=PROMPT_NEED_STREAM_OUT
    ),
    temperature = 1
    # example_selector=plugin_example,
)

CFG.prompt_template_registry.register(prompt, is_default=True)
