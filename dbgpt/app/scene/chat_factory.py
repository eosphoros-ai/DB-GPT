from dbgpt.app.scene.base_chat import BaseChat
from dbgpt.util.singleton import Singleton
from dbgpt.util.tracer import root_tracer


class ChatFactory(metaclass=Singleton):
    @staticmethod
    def get_implementation(chat_mode, **kwargs):
        # Lazy loading
        from dbgpt.app.scene.chat_dashboard.chat import ChatDashboard
        from dbgpt.app.scene.chat_dashboard.prompt import prompt
        from dbgpt.app.scene.chat_data.chat_excel.excel_analyze.chat import ChatExcel
        from dbgpt.app.scene.chat_data.chat_excel.excel_analyze.prompt import prompt
        from dbgpt.app.scene.chat_data.chat_excel.excel_learning.prompt import prompt
        from dbgpt.app.scene.chat_db.auto_execute.chat import ChatWithDbAutoExecute
        from dbgpt.app.scene.chat_db.auto_execute.prompt import prompt
        from dbgpt.app.scene.chat_db.professional_qa.chat import ChatWithDbQA
        from dbgpt.app.scene.chat_db.professional_qa.prompt import prompt
        from dbgpt.app.scene.chat_knowledge.refine_summary.chat import (
            ExtractRefineSummary,
        )
        from dbgpt.app.scene.chat_knowledge.refine_summary.prompt import prompt
        from dbgpt.app.scene.chat_knowledge.v1.chat import ChatKnowledge
        from dbgpt.app.scene.chat_knowledge.v1.prompt import prompt
        from dbgpt.app.scene.chat_normal.chat import ChatNormal
        from dbgpt.app.scene.chat_normal.prompt import prompt

        chat_classes = BaseChat.__subclasses__()
        implementation = None
        for cls in chat_classes:
            if cls.chat_scene == chat_mode:
                metadata = {"cls": str(cls)}
                with root_tracer.start_span(
                    "get_implementation_of_chat", metadata=metadata
                ):
                    implementation = cls(**kwargs)
        if implementation == None:
            raise Exception(f"Invalid implementation name:{chat_mode}")
        return implementation
