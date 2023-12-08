import json
from typing import Any, Dict

from dbgpt.core.interface.message import ViewMessage, AIMessage
from dbgpt.app.scene import BaseChat, ChatScene
from dbgpt.util.json_utils import DateTimeEncoder
from dbgpt.util.executor_utils import blocking_func_to_async
from dbgpt.util.tracer import trace


class ExcelLearning(BaseChat):
    chat_scene: str = ChatScene.ExcelLearning.value()

    def __init__(
        self,
        chat_session_id,
        user_input,
        parent_mode: Any = None,
        select_param: str = None,
        excel_reader: Any = None,
        model_name: str = None,
    ):
        chat_mode = ChatScene.ExcelLearning
        """ """
        self.excel_file_path = select_param
        self.excel_reader = excel_reader
        chat_param = {
            "chat_mode": chat_mode,
            "chat_session_id": chat_session_id,
            "current_user_input": user_input,
            "select_param": select_param,
            "model_name": model_name,
        }
        super().__init__(chat_param=chat_param)
        if parent_mode:
            self.current_message.chat_mode = parent_mode.value()

    @trace()
    async def generate_input_values(self) -> Dict:
        # colunms, datas = self.excel_reader.get_sample_data()
        colunms, datas = await blocking_func_to_async(
            self._executor, self.excel_reader.get_sample_data
        )
        self.prompt_template.output_parser.update(colunms)
        datas.insert(0, colunms)

        input_values = {
            "data_example": json.dumps(datas, cls=DateTimeEncoder),
            "file_name": self.excel_reader.excel_file_name,
        }
        return input_values

    def message_adjust(self):
        ### adjust learning result in messages
        view_message = ""
        for message in self.current_message.messages:
            if message.type == ViewMessage.type:
                view_message = message.content

        for message in self.current_message.messages:
            if message.type == AIMessage.type:
                message.content = view_message
