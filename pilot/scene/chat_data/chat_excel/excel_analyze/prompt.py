import json
from pilot.prompts.prompt_new import PromptTemplate
from pilot.configs.config import Config
from pilot.scene.base import ChatScene
from pilot.scene.chat_data.chat_excel.excel_analyze.out_parser import ChatExcelOutputParser
from pilot.common.schema import SeparatorStyle

CFG = Config()

PROMPT_SCENE_DEFINE = "You are a data analysis expert. "

_DEFAULT_TEMPLATE = """
Please use the data structure information of the above historical dialogue, make sure not to use column names that are not in the data structure.
According to the user goal: {user_input}，give the correct duckdb SQL for data analysis.
Use the table name: {table_name}

According to the analysis SQL obtained by the user's goal, select the best one from the following display forms, if it cannot be determined, use Text  as the display.
Display type: 
    {disply_type}
    
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
    input_variables=["user_input", "table_name", "disply_type"],
    response_format=json.dumps(RESPONSE_FORMAT_SIMPLE, ensure_ascii=False, indent=4),
    template_define=PROMPT_SCENE_DEFINE,
    template=_DEFAULT_TEMPLATE,
    stream_out=PROMPT_NEED_NEED_STREAM_OUT,
    output_parser=ChatExcelOutputParser(
        sep=PROMPT_SEP, is_stream_out=PROMPT_NEED_NEED_STREAM_OUT
    ),
    need_historical_messages = True,
    # example_selector=sql_data_example,
    temperature=PROMPT_TEMPERATURE,
)
CFG.prompt_template_registry.register(prompt, is_default=True)

