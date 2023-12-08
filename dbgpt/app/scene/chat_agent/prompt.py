from dbgpt.core.interface.prompt import PromptTemplate
from dbgpt._private.config import Config
from dbgpt.app.scene import ChatScene

from dbgpt.app.scene.chat_execution.out_parser import PluginChatOutputParser

CFG = Config()

_PROMPT_SCENE_DEFINE_EN = "You are a universal AI assistant."

_DEFAULT_TEMPLATE_EN = """
You need to analyze the user goals and, under the given constraints, prioritize using one of the following tools to solve the user goals.
Tool list:
    {tool_list}
Constraint:
    1. After finding the available tools from the tool list given below, please output the following content to use the tool. Please make sure that the following content only appears once in the output result:
        <api-call><name>Selected Tool name</name><args><arg1>value</arg1><arg2>value</arg2></args></api-call>
    2. Please generate the above call text according to the definition of the corresponding tool in the tool list. The reference case is as follows:
        Introduction to tool function: "Tool name", args: "Parameter 1": "<Parameter 1 value description>", "Parameter 2": "<Parameter 2 value description>" Corresponding call text: <api-call>< name>Tool name</name><args><parameter 1>value</parameter 1><parameter 2>value</parameter 2></args></api-call>
    3. Generate the call of each tool according to the above constraints. The prompt text for tool use needs to be generated before the tool is used.
    4. If the user goals cannot be understood and the intention is unclear, give priority to using search engine tools
    5. Parameter content may need to be inferred based on the user's goals, not just extracted from text
    6. Constraint conditions and tool information are used as auxiliary information for the reasoning process and should not be expressed in the output content to the user. 
    {expand_constraints}
User goals:
    {user_goal}
"""

_PROMPT_SCENE_DEFINE_ZH = "你是一个通用AI助手！"

_DEFAULT_TEMPLATE_ZH = """
根据用户目标，请一步步思考，如何在满足下面约束条件的前提下，优先使用给出工具回答或者完成用户目标。

约束条件:
	1.从下面给定工具列表找到可用的工具后，请输出以下内容用来使用工具, 注意要确保下面内容在输出结果中只出现一次:
	<api-call><name>Selected Tool name</name><args><arg1>value</arg1><arg2>value</arg2></args></api-call>
    2.请根据工具列表对应工具的定义来生成上述调用文本, 参考案例如下: 
        工具作用介绍: "工具名称", args: "参数1": "<参数1取值描述>","参数2": "<参数2取值描述>" 对应调用文本:<api-call><name>工具名称</name><args><参数1>value</参数1><参数2>value</参数2></args></api-call>
    3.根据上面约束的方式生成每个工具的调用，对于工具使用的提示文本，需要在工具使用前生成
    4.如果用户目标无法理解和意图不明确，优先使用搜索引擎工具
    5.参数内容可能需要根据用户的目标推理得到，不仅仅是从文本提取
    6.约束条件和工具信息作为推理过程的辅助信息，对应内容不要表达在给用户的输出内容中
    7.不要把<api-call></api-call>部分内容放在markdown标签里
    {expand_constraints}

工具列表:
    {tool_list}   

用户目标:
    {user_goal}
"""

_DEFAULT_TEMPLATE = (
    _DEFAULT_TEMPLATE_EN if CFG.LANGUAGE == "en" else _DEFAULT_TEMPLATE_ZH
)


_PROMPT_SCENE_DEFINE = (
    _PROMPT_SCENE_DEFINE_EN if CFG.LANGUAGE == "en" else _PROMPT_SCENE_DEFINE_ZH
)

RESPONSE_FORMAT = None


### Whether the model service is streaming output
PROMPT_NEED_STREAM_OUT = True

prompt = PromptTemplate(
    template_scene=ChatScene.ChatAgent.value(),
    input_variables=["tool_list", "expand_constraints", "user_goal"],
    response_format=None,
    template_define=_PROMPT_SCENE_DEFINE,
    template=_DEFAULT_TEMPLATE,
    stream_out=PROMPT_NEED_STREAM_OUT,
    output_parser=PluginChatOutputParser(is_stream_out=PROMPT_NEED_STREAM_OUT),
    temperature=1
    # example_selector=plugin_example,
)

CFG.prompt_template_registry.register(prompt, is_default=True)
