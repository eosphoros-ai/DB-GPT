from pilot.scene.base_chat import BaseChat
from pilot.singleton import Singleton


class ChatFactory(metaclass=Singleton):
    @staticmethod
    def get_implementation(chat_mode, **kwargs):
        # Lazy loading
        from pilot.scene.chat_execution.chat import ChatWithPlugin
        from pilot.scene.chat_normal.chat import ChatNormal
        from pilot.scene.chat_db.professional_qa.chat import ChatWithDbQA
        from pilot.scene.chat_db.auto_execute.chat import ChatWithDbAutoExecute
        from pilot.scene.chat_dashboard.chat import ChatDashboard
        from pilot.scene.chat_knowledge.v1.chat import ChatKnowledge
        from pilot.scene.chat_knowledge.inner_db_summary.chat import InnerChatDBSummary
        from pilot.scene.chat_data.chat_excel.excel_analyze.chat import ChatExcel

        chat_classes = BaseChat.__subclasses__()
        implementation = None
        for cls in chat_classes:
            if cls.chat_scene == chat_mode:
                implementation = cls(**kwargs)
        if implementation == None:
            raise Exception(f"Invalid implementation name:{chat_mode}")
        return implementation
