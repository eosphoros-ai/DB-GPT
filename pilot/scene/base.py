from enum import Enum


class ChatScene(Enum):
    ChatWithDbExecute = "chat_with_db_execute"
    ChatWithDbQA = "chat_with_db_qa"
    ChatExecution = "chat_execution"
    ChatKnowledge = "chat_default_knowledge"
    ChatNewKnowledge = "chat_new_knowledge"
    ChatUrlKnowledge = "chat_url_knowledge"
    ChatNormal = "chat_normal"
