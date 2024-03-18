from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Dict, List, Optional

from dbgpt._private.config import Config
from dbgpt.app.openapi.api_view_model import Result
from dbgpt.app.openapi.editor_view_model import (
    ChartDetail,
    ChartList,
    ChatDbRounds,
    ChatSqlEditContext,
)
from dbgpt.component import BaseComponent, SystemApp
from dbgpt.core import BaseOutputParser
from dbgpt.core.interface.message import (
    MessageStorageItem,
    StorageConversation,
    _split_messages_by_round,
)
from dbgpt.serve.conversation.serve import Serve as ConversationServe

if TYPE_CHECKING:
    from dbgpt.datasource.base import BaseConnector

logger = logging.getLogger(__name__)


class EditorService(BaseComponent):
    name = "dbgpt_app_editor_service"

    def __init__(self, system_app: SystemApp):
        self._system_app: SystemApp = system_app
        super().__init__(system_app)

    def init_app(self, system_app: SystemApp):
        self._system_app = system_app

    def conv_serve(self) -> ConversationServe:
        return ConversationServe.get_instance(self._system_app)

    def get_storage_conv(self, conv_uid: str) -> StorageConversation:
        conv_serve: ConversationServe = self.conv_serve()
        return StorageConversation(
            conv_uid,
            conv_storage=conv_serve.conv_storage,
            message_storage=conv_serve.message_storage,
        )

    def get_editor_sql_rounds(self, conv_uid: str) -> List[ChatDbRounds]:
        storage_conv: StorageConversation = self.get_storage_conv(conv_uid)
        messages_by_round = _split_messages_by_round(storage_conv.messages)
        result: List[ChatDbRounds] = []
        for one_round_message in messages_by_round:
            if not one_round_message:
                continue
            for message in one_round_message:
                if message.type == "human":
                    round_name = message.content
                    if message.additional_kwargs.get("param_value"):
                        chat_db_round: ChatDbRounds = ChatDbRounds(
                            round=message.round_index,
                            db_name=message.additional_kwargs.get("param_value"),
                            round_name=round_name,
                        )
                        result.append(chat_db_round)

        return result

    def get_editor_sql_by_round(
        self, conv_uid: str, round_index: int
    ) -> Optional[Dict]:
        storage_conv: StorageConversation = self.get_storage_conv(conv_uid)
        messages_by_round = _split_messages_by_round(storage_conv.messages)
        for one_round_message in messages_by_round:
            if not one_round_message:
                continue
            for message in one_round_message:
                if message.type == "ai" and message.round_index == round_index:
                    content = message.content
                    logger.info(f"history ai json resp: {content}")
                    # context = content.replace("\\n", " ").replace("\n", " ")
                    context_dict = _parse_pure_dict(content)
                    return context_dict
        return None

    def sql_editor_submit_and_save(
        self, sql_edit_context: ChatSqlEditContext, connection: BaseConnector
    ):
        storage_conv: StorageConversation = self.get_storage_conv(
            sql_edit_context.conv_uid
        )
        if not storage_conv.save_message_independent:
            raise ValueError(
                "Submit sql and save just support independent conversation mode(after v0.4.6)"
            )
        conv_serve: ConversationServe = self.conv_serve()
        messages_by_round = _split_messages_by_round(storage_conv.messages)
        to_update_messages = []
        for one_round_message in messages_by_round:
            if not one_round_message:
                continue
            if one_round_message[0].round_index == sql_edit_context.conv_round:
                for message in one_round_message:
                    if message.type == "ai":
                        db_resp = _parse_pure_dict(message.content)
                        db_resp["thoughts"] = sql_edit_context.new_speak
                        db_resp["sql"] = sql_edit_context.new_sql
                        message.content = json.dumps(db_resp, ensure_ascii=False)
                        to_update_messages.append(
                            MessageStorageItem(
                                storage_conv.conv_uid, message.index, message.to_dict()
                            )
                        )
                    # TODO not support update view message now
                    # if message.type == "view":
                    #     data_loader = DbDataLoader()
                    #     message.content = data_loader.get_table_view_by_conn(
                    #         connection.run_to_df(sql_edit_context.new_sql),
                    #         sql_edit_context.new_speak,
                    #     )
                    #     to_update_messages.append(
                    #         MessageStorageItem(
                    #             storage_conv.conv_uid, message.index, message.to_dict()
                    #         )
                    #     )
                if to_update_messages:
                    conv_serve.message_storage.save_or_update_list(to_update_messages)
                return

    def get_editor_chart_list(self, conv_uid: str) -> Optional[ChartList]:
        storage_conv: StorageConversation = self.get_storage_conv(conv_uid)
        messages_by_round = _split_messages_by_round(storage_conv.messages)
        for one_round_message in messages_by_round:
            if not one_round_message:
                continue
            for message in one_round_message:
                if message.type == "ai":
                    context_dict = _parse_pure_dict(message.content)
                    chart_list: ChartList = ChartList(
                        round=message.round_index,
                        db_name=message.additional_kwargs.get("param_value"),
                        charts=context_dict,
                    )
                    return chart_list

    def get_editor_chart_info(
        self, conv_uid: str, chart_title: str, cfg: Config
    ) -> Result[ChartDetail]:
        storage_conv: StorageConversation = self.get_storage_conv(conv_uid)
        messages_by_round = _split_messages_by_round(storage_conv.messages)
        for one_round_message in messages_by_round:
            if not one_round_message:
                continue
            for message in one_round_message:
                db_name = message.additional_kwargs.get("param_value")
                if not db_name:
                    logger.error(
                        "this dashboard dialogue version too old, can't support editor!"
                    )
                    return Result.failed(
                        msg="this dashboard dialogue version too old, can't support editor!"
                    )
                if message.type == "view":
                    view_data: dict = _parse_pure_dict(message.content)
                    charts: List = view_data.get("charts")
                    find_chart = list(
                        filter(lambda x: x["chart_name"] == chart_title, charts)
                    )[0]

                    conn = cfg.local_db_manager.get_connector(db_name)
                    detail: ChartDetail = ChartDetail(
                        chart_uid=find_chart["chart_uid"],
                        chart_type=find_chart["chart_type"],
                        chart_desc=find_chart["chart_desc"],
                        chart_sql=find_chart["chart_sql"],
                        db_name=db_name,
                        chart_name=find_chart["chart_name"],
                        chart_value=find_chart["values"],
                        table_value=conn.run(find_chart["chart_sql"]),
                    )
                    return Result.succ(detail)
        return Result.failed(msg="Can't Find Chart Detail Info!")


def _parse_pure_dict(res_str: str) -> Dict:
    output_parser = BaseOutputParser()
    context = output_parser.parse_prompt_response(res_str)
    return json.loads(context)
