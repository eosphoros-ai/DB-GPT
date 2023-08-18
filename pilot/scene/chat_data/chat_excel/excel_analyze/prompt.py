import json
from pilot.prompts.prompt_new import PromptTemplate
from pilot.configs.config import Config
from pilot.scene.base import ChatScene
from pilot.scene.chat_db.auto_execute.out_parser import DbChatOutputParser, SqlAction
from pilot.common.schema import SeparatorStyle

CFG = Config()

PROMPT_SCENE_DEFINE = "You are a data analysis expert. "

_DEFAULT_TEMPLATE = """
Please give data analysis SQL based on the following user goals: {user_input}
Display type: 
    {disply_type}

According to the analysis SQL obtained by the user's goal, select the best one from the following display forms, if it cannot be determined, use Text  as the display.
Respond in the following json format:
    {response}
Ensure the response is correct json and can be parsed by Python json.loads

"""

RESPONSE_FORMAT_SIMPLE = {
	"sql": "analysis SQL",
	"thoughts": "Current thinking and value of data analysis",
	"display": "display type name"
}


PROMPT_SEP = SeparatorStyle.SINGLE.value

PROMPT_NEED_NEED_STREAM_OUT = False

# Temperature is a configuration hyperparameter that controls the randomness of language model output.
# A high temperature produces more unpredictable and creative results, while a low temperature produces more common and conservative output.
# For example, if you adjust the temperature to 0.5, the model will usually generate text that is more predictable and less creative than if you set the temperature to 1.0.
PROMPT_TEMPERATURE = 0.8

prompt = PromptTemplate(
    template_scene=ChatScene.ChatExcel.value(),
    input_variables=["user_input", "disply_type"],
    response_format=json.dumps(RESPONSE_FORMAT_SIMPLE, ensure_ascii=False, indent=4),
    template_define=PROMPT_SCENE_DEFINE,
    template=_DEFAULT_TEMPLATE,
    stream_out=PROMPT_NEED_NEED_STREAM_OUT,
    output_parser=DbChatOutputParser(
        sep=PROMPT_SEP, is_stream_out=PROMPT_NEED_NEED_STREAM_OUT
    ),
    # example_selector=sql_data_example,
    temperature=PROMPT_TEMPERATURE,
)
CFG.prompt_template_registry.register(prompt, is_default=True)

