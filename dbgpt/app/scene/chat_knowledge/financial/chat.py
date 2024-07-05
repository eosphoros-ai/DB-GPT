from typing import Dict

from dbgpt._private.config import Config
from dbgpt.app.scene import BaseChat, ChatScene
from dbgpt.app.scene.chat_knowledge.financial import FinReportJoinOperator
from dbgpt.app.scene.chat_knowledge.financial.chat_database import (
    ChatDatabaseChartOperator,
    ChatDatabaseOutputParserOperator,
    ChatDataOperator,
)
from dbgpt.app.scene.chat_knowledge.financial.chat_indicator import (
    ChatIndicatorOperator,
)
from dbgpt.app.scene.chat_knowledge.financial.chat_knowledge import (
    ChatKnowledgeOperator,
)
from dbgpt.app.scene.chat_knowledge.financial.classifier import (
    QuestionClassifierBranchOperator,
    QuestionClassifierOperator,
)
from dbgpt.core import ModelRequest
from dbgpt.core.awel import DAG, InputOperator, SimpleCallDataInputSource
from dbgpt.core.interface.operators.llm_operator import RequestBuilderOperator
from dbgpt.model.operators import LLMOperator, StreamingLLMOperator
from dbgpt.rag.extractor.fin_report import FinIntentExtractor, FinReportIntent
from dbgpt.serve.flow.service.service import _chat_stream_with_dag_task
from dbgpt.util.tracer import root_tracer, trace

CFG = Config()


class ChatFinReport(BaseChat):
    chat_scene: str = ChatScene.ChatFinReport.value()
    """KBQA Chat Module"""

    def __init__(self, chat_param: Dict):
        """Chat Knowledge Module Initialization
        Args:
           - chat_param: Dict
            - chat_session_id: (str) chat session_id
            - current_user_input: (str) current user input
            - model_name:(str) llm model name
            - select_param:(str) space name
        """

        self.knowledge_space = chat_param["select_param"]
        chat_param["chat_mode"] = ChatScene.ChatFinReport
        super().__init__(
            chat_param=chat_param,
        )
        self.knowledge_space = chat_param["select_param"]
        connector_manager = CFG.local_db_manager
        self.db_list = [item["db_name"] for item in connector_manager.get_db_list()]
        dbnames = [item for item in self.db_list if self.knowledge_space in item]
        if len(dbnames) == 0:
            raise ValueError(
                f"fin repost dbname {self.knowledge_space}_fin_report not found."
            )
        self.fin_db_name = dbnames[0]

    async def fin_call(self):
        """Call the chat module"""
        with root_tracer.start_span(
            "call", metadata={"chat_scene": self.chat_type}
        ) as span:
            intent_extractor = FinIntentExtractor(
                llm_client=self.llm_client, model_name=self.llm_model
            )
            fin_intent = await intent_extractor.extract(self.current_user_input)
            payload = await self._build_model_request()
            llm_task = self._build_fin_report_chat_task(
                request=payload, fin_intent=fin_intent
            )
            async for output in _chat_stream_with_dag_task(llm_task, payload, False):
                text = output.text
                if text:
                    text = text.replace("\n", "\\n")
                if output.error_code != 0:
                    yield f"data:[SERVER_ERROR]{text}\n\n"
                    break
                else:
                    yield f"data:{text}\n\n"
            # return await llm_task.call_stream(call_data=payload)

    @trace()
    async def generate_input_values(self) -> Dict:
        input_values = {
            "context": {},
            "question": self.current_user_input,
            "relations": {},
        }
        return input_values

    @property
    def chat_type(self) -> str:
        return ChatScene.ChatFinReport.value()

    def _build_fin_report_chat_task(
        self, request: ModelRequest, fin_intent: FinReportIntent
    ):
        """Build financial report chat task"""
        with DAG("fin_report_assistant_example") as dag:
            input_task = InputOperator(SimpleCallDataInputSource())
            model_request_task = RequestBuilderOperator()
            query_classifier = QuestionClassifierOperator(
                model=CFG.FIN_REPORT_MODEL, classifier_pkl=CFG.FIN_CLASSIFIER_PKL
            )
            classifier_branch = QuestionClassifierBranchOperator()
            chat_data_task = ChatDataOperator(
                db_name=self.fin_db_name, intent=fin_intent
            )
            llm_task = LLMOperator()
            sql_parse_task = ChatDatabaseOutputParserOperator()
            sql_chart_task = ChatDatabaseChartOperator()
            indicator_task = ChatIndicatorOperator(
                db_name=self.fin_db_name, intent=fin_intent
            )
            indicator_llm_task = LLMOperator()
            indicator_sql_parse_task = ChatDatabaseOutputParserOperator(
                task_name="indicator_sql_parse_task"
            )
            indicator_sql_chart_task = ChatDatabaseChartOperator(
                task_name="indicator_sql_chart_task"
            )
            chat_knowledge_task = ChatKnowledgeOperator(
                knowledge_space=self.knowledge_space
            )
            stream_llm_task = StreamingLLMOperator(self.llm_client)
            join_task = FinReportJoinOperator()
            input_task >> model_request_task >> query_classifier >> classifier_branch
            (
                classifier_branch
                >> chat_data_task
                >> llm_task
                >> sql_parse_task
                >> sql_chart_task
                >> join_task
            )
            (
                classifier_branch
                >> indicator_task
                >> indicator_llm_task
                >> indicator_sql_parse_task
                >> indicator_sql_chart_task
                >> join_task
            )
            (classifier_branch >> chat_knowledge_task >> stream_llm_task >> join_task)

            return join_task
