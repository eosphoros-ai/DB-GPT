import json
import logging
import os
from typing import Any, Dict, Type, Union

from dbgpt import SystemApp
from dbgpt.agent.util.api_call import ApiCall
from dbgpt.configs.model_config import DATA_DIR
from dbgpt.core import ModelOutput
from dbgpt.core.interface.file import _SCHEMA, FileStorageClient
from dbgpt.util.executor_utils import blocking_func_to_async
from dbgpt.util.json_utils import EnhancedJSONEncoder
from dbgpt.util.tracer import root_tracer, trace
from dbgpt_app.scene import BaseChat, ChatScene
from dbgpt_app.scene.base_chat import ChatParam
from dbgpt_app.scene.chat_data.chat_excel.config import ChatExcelConfig
from dbgpt_app.scene.chat_data.chat_excel.excel_learning.chat import ExcelLearning
from dbgpt_app.scene.chat_data.chat_excel.excel_reader import ExcelReader

logger = logging.getLogger(__name__)


class ChatExcel(BaseChat):
    """a Excel analyzer to analyze Excel Data"""

    chat_scene: str = ChatScene.ChatExcel.value()

    @classmethod
    def param_class(cls) -> Type[ChatExcelConfig]:
        return ChatExcelConfig

    def __init__(self, chat_param: ChatParam, system_app: SystemApp):
        """Chat Excel Module Initialization
        Args:
           - chat_param: Dict
            - chat_session_id: (str) chat session_id
            - current_user_input: (str) current user input
            - model_name:(str) llm model name
            - select_param:(str) file path
        """
        self.fs_client = FileStorageClient.get_instance(system_app)
        self.select_param = chat_param.select_param
        if not self.select_param:
            raise ValueError("Please upload the Excel document you want to talk to！")
        self.model_name = chat_param.model_name
        self.curr_config = chat_param.real_app_config(ChatExcelConfig)
        self.chat_param = chat_param
        self._bucket = "dbgpt_app_file"
        file_path, file_name, database_file_path, database_file_id = self._resolve_path(
            self.select_param,
            chat_param.chat_session_id,
            self.fs_client,
            self._bucket,
        )
        self._curr_table = "data_analysis_table"
        self._file_name = file_name
        self._database_file_path = database_file_path
        self._database_file_id = database_file_id
        self.excel_reader = ExcelReader(
            chat_param.chat_session_id,
            file_path,
            file_name,
            read_type="direct",
            database_name=database_file_path,
            table_name=self._curr_table,
            duckdb_extensions_dir=self.curr_config.duckdb_extensions_dir,
            force_install=self.curr_config.force_install,
        )

        self.api_call = ApiCall()
        super().__init__(chat_param=chat_param, system_app=system_app)

    def _resolve_path(
        self, file_param: Any, conv_uid: str, fs_client: FileStorageClient, bucket: str
    ) -> Union[str, str, str]:
        if isinstance(file_param, str) and os.path.isabs(file_param):
            file_path = file_param
            file_name = os.path.basename(file_param)
        else:
            if isinstance(file_param, dict):
                file_path = file_param.get("file_path", None)
                if not file_path:
                    raise ValueError("Not find file path!")
                else:
                    file_name = os.path.basename(file_path.replace(f"{conv_uid}_", ""))

            else:
                temp_obj = json.loads(file_param)
                file_path = temp_obj.get("file_path")
                if not file_path:
                    raise ValueError("Not find file path!")
                file_name = os.path.basename(file_path.replace(f"{conv_uid}_", ""))

        database_root_path = os.path.join(DATA_DIR, "_chat_excel_tmp")
        os.makedirs(database_root_path, exist_ok=True)
        database_file_path = os.path.join(
            database_root_path, f"_chat_excel_{file_name}.duckdb"
        )
        database_file_id = None

        if file_path.startswith(_SCHEMA):
            file_path, file_meta = fs_client.download_file(file_path, dest_dir=DATA_DIR)
            file_name = os.path.basename(file_path)
            database_file_path = os.path.join(
                database_root_path, f"_chat_excel_{file_name}.duckdb"
            )
            database_file_id = f"{file_meta.file_id}_{conv_uid}"
            db_files = fs_client.list_files(
                bucket,
                filters={
                    "file_id": database_file_id,
                },
            )
            if db_files:
                logger.info("Database file exists in file storage. Downloading...")
                fs_client.download_file(db_files[0].uri, database_file_path)
                logger.info(f"Database file downloaded to {database_file_path}")

        return file_path, file_name, database_file_path, database_file_id

    @trace()
    async def generate_input_values(self) -> Dict:
        table_schema = await blocking_func_to_async(
            self._executor, self.excel_reader.get_create_table_sql, self._curr_table
        )
        # table_summary = await blocking_func_to_async(
        #     self._executor, self.excel_reader.get_summary, self._curr_table
        # )
        colunms, datas = await blocking_func_to_async(
            self._executor, self.excel_reader.get_sample_data, self._curr_table
        )

        input_values = {
            "user_input": self.current_user_input,
            "table_name": self._curr_table,
            "display_type": self._generate_numbered_list(),
            # "table_summary": table_summary,
            "table_schema": table_schema,
            "data_example": json.dumps(
                datas, cls=EnhancedJSONEncoder, ensure_ascii=False
            ),
        }
        return input_values

    async def prepare(self):
        logger.info(f"{self.chat_mode} prepare start!")
        if self.has_history_messages():
            return None

        chat_param = ChatParam(
            chat_session_id=self.chat_session_id,
            current_user_input="["
            + self.excel_reader.excel_file_name
            + "]"
            + " Analyze！",
            select_param=self.select_param,
            chat_mode=ChatScene.ExcelLearning,
            model_name=self.model_name,
            user_name=self.chat_param.user_name,
            sys_code=self.chat_param.sys_code,
        )
        if self._chat_param.temperature is not None:
            chat_param.temperature = self._chat_param.temperature
        if self._chat_param.max_new_tokens is not None:
            chat_param.max_new_tokens = self._chat_param.max_new_tokens
        learn_chat = ExcelLearning(
            chat_param,
            system_app=self.system_app,
            parent_mode=self.chat_mode,
            excel_reader=self.excel_reader,
        )
        result = await learn_chat.nostream_call()

        if (
            os.path.exists(self._database_file_path)
            and self._database_file_id is not None
        ):
            await blocking_func_to_async(self._executor, self.excel_reader.close)
            await blocking_func_to_async(
                self._executor,
                self.fs_client.upload_file,
                self._bucket,
                self._database_file_path,
                file_id=self._database_file_id,
            )
        return result

    def stream_plugin_call(self, text):
        with root_tracer.start_span(
            "ChatExcel.stream_plugin_call.run_display_sql", metadata={"text": text}
        ):
            return self.api_call.display_sql_llmvis(
                text,
                self.excel_reader.get_df_by_sql_ex,
            )

    async def _handle_final_output(
        self, final_output: ModelOutput, incremental: bool = False
    ):
        text_msg = final_output.text if final_output.has_text else ""
        view_msg = self.stream_plugin_call(text_msg)
        view_msg = final_output.gen_text_with_thinking(new_text=view_msg)
        view_msg = view_msg.replace("\n", "\\n")

        return final_output.text, view_msg
