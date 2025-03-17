from dbgpt.component import SystemApp
from dbgpt.util.singleton import Singleton
from dbgpt.util.tracer import root_tracer
from dbgpt_app.scene.base_chat import BaseChat, ChatParam
from dbgpt_serve.core.config import parse_config


class ChatFactory(metaclass=Singleton):
    @staticmethod
    def get_implementation(
        chat_mode: str, system_app: SystemApp, chat_param: ChatParam, **kwargs
    ):
        # Lazy loading
        from dbgpt_app.scene.chat_dashboard.chat import ChatDashboard  # noqa: F401
        from dbgpt_app.scene.chat_dashboard.prompt import prompt  # noqa: F401
        from dbgpt_app.scene.chat_data.chat_excel.excel_analyze.chat import (  # noqa: F401
            ChatExcel,
        )
        from dbgpt_app.scene.chat_data.chat_excel.excel_analyze.prompt import (  # noqa: F401,F811
            prompt,
        )
        from dbgpt_app.scene.chat_data.chat_excel.excel_learning.prompt import (  # noqa: F401, F811
            prompt,
        )
        from dbgpt_app.scene.chat_db.auto_execute.chat import (  # noqa: F401
            ChatWithDbAutoExecute,
        )
        from dbgpt_app.scene.chat_db.auto_execute.prompt import (  # noqa: F401,F811
            prompt,
        )
        from dbgpt_app.scene.chat_db.professional_qa.chat import (  # noqa: F401
            ChatWithDbQA,
        )
        from dbgpt_app.scene.chat_db.professional_qa.prompt import (  # noqa: F401, F811
            prompt,
        )
        from dbgpt_app.scene.chat_knowledge.refine_summary.chat import (  # noqa: F401
            ExtractRefineSummary,
        )
        from dbgpt_app.scene.chat_knowledge.refine_summary.prompt import (  # noqa: F401,F811
            prompt,
        )
        from dbgpt_app.scene.chat_knowledge.v1.chat import ChatKnowledge  # noqa: F401
        from dbgpt_app.scene.chat_knowledge.v1.prompt import prompt  # noqa: F401,F811
        from dbgpt_app.scene.chat_normal.chat import ChatNormal  # noqa: F401
        from dbgpt_app.scene.chat_normal.prompt import prompt  # noqa: F401,F811

        chat_classes = BaseChat.__subclasses__()
        implementation = None
        for cls in chat_classes:
            if cls.chat_scene == chat_mode:
                metadata = {"cls": str(cls)}
                with root_tracer.start_span(
                    "get_implementation_of_chat", metadata=metadata
                ):
                    config = parse_config(
                        system_app, chat_mode, type_class=cls.param_class()
                    )
                    chat_param.app_config = config
                    implementation = cls(
                        **kwargs, chat_param=chat_param, system_app=system_app
                    )
        if implementation is None:
            raise Exception(f"Invalid implementation name:{chat_mode}")
        return implementation
