from enum import Enum


class ChatScene(Enum):
    ChatWithDb = "chat_with_db"
    ChatExecution = "chat_execution"
    ChatKnowledge = "chat_default_knowledge"
    ChatNewKnowledge = "chat_new_knowledge"
    ChatNormal = "chat_normal"
