import json
from typing import Any, Dict

from dbgpt import SystemApp
from dbgpt.core.interface.message import ModelMessageRoleType
from dbgpt.util.executor_utils import blocking_func_to_async
from dbgpt.util.json_utils import EnhancedJSONEncoder
from dbgpt.util.tracer import trace
from dbgpt_app.scene import BaseChat, ChatScene

from .out_parser import TransformedExcelResponse
from .prompt import USER_INPUT


class ExcelLearning(BaseChat):
    chat_scene: str = ChatScene.ExcelLearning.value()

    def __init__(
        self,
        chat_session_id,
        user_input,
        temperature: float,
        max_new_tokens: int,
        parent_mode: Any = None,
        select_param: str = None,
        excel_reader: Any = None,
        model_name: str = None,
        user_name: str = None,
        system_app: SystemApp = None,
    ):
        chat_mode = ChatScene.ExcelLearning
        from ..excel_reader import ExcelReader

        """ """
        self.excel_reader: ExcelReader = excel_reader
        chat_param = {
            "chat_mode": chat_mode,
            "chat_session_id": chat_session_id,
            "current_user_input": user_input,
            "select_param": select_param,
            "model_name": model_name,
            "user_name": user_name,
            "temperature": temperature,
            "max_new_tokens": max_new_tokens,
        }
        self._curr_table = self.excel_reader.temp_table_name
        super().__init__(chat_param=chat_param, system_app=system_app)
        if parent_mode:
            self.current_message.chat_mode = parent_mode.value()

    @trace()
    async def generate_input_values(self) -> Dict:
        # colunms, datas = self.excel_reader.get_sample_data()
        colunms, datas = await blocking_func_to_async(
            self._executor, self.excel_reader.get_sample_data, self._curr_table
        )
        self.prompt_template.output_parser.update(colunms)
        datas.insert(0, colunms)

        table_schema = await blocking_func_to_async(
            self._executor, self.excel_reader.get_create_table_sql, self._curr_table
        )
        table_summary = await blocking_func_to_async(
            self._executor, self.excel_reader.get_summary, self._curr_table
        )

        input_values = {
            "data_example": json.dumps(
                datas, cls=EnhancedJSONEncoder, ensure_ascii=False
            ),
            "user_input": USER_INPUT,
            "table_summary": table_summary,
            "table_schema": table_schema,
        }
        return input_values

    def do_action(self, prompt_response: TransformedExcelResponse):
        self.excel_reader.transform_table(
            self._curr_table, self.excel_reader.table_name, prompt_response
        )
        return prompt_response

    def message_adjust(self):
        ### adjust learning result in messages
        # TODO: Can't work in multi-rounds chat
        view_message = ""
        for message in self.current_message.messages:
            if message.type == ModelMessageRoleType.VIEW:
                view_message = message.content

        for message in self.current_message.messages:
            if message.type == ModelMessageRoleType.AI:
                message.content = view_message
