from enum import Enum

class Scene:
    def __init__(self, code, describe, is_inner):
        self.code = code
        self.describe = describe
        self.is_inner = is_inner

class ChatScene(Enum):
    ChatWithDbExecute = "chat_with_db_execute"
    ChatWithDbQA = "chat_with_db_qa"
    ChatExecution = "chat_execution"
    ChatDefaultKnowledge = "chat_default_knowledge"
    ChatNewKnowledge = "chat_new_knowledge"
    ChatUrlKnowledge = "chat_url_knowledge"
    InnerChatDBSummary = "inner_chat_db_summary"

    ChatNormal = "chat_normal"
    ChatDashboard = "chat_dashboard"
    ChatKnowledge = "chat_knowledge"
    # ChatDb = "chat_db"
    # ChatData= "chat_data"

    @staticmethod
    def is_valid_mode(mode):
        return any(mode == item.value for item in ChatScene)

