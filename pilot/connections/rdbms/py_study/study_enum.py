from enum import Enum
from typing import List


class Test(Enum):
    XXX = ("x", "1", True)
    YYY = ("Y", "2", False)
    ZZZ = ("Z", "3")

    def __init__(self, code, v, flag=False):
        self.code = code
        self.v = v
        self.flag = flag


class Scene:
    def __init__(
        self, code, name, describe, param_types: List = [], is_inner: bool = False
    ):
        self.code = code
        self.name = name
        self.describe = describe
        self.param_types = param_types
        self.is_inner = is_inner


class ChatScene(Enum):
    ChatWithDbExecute = Scene(
        "chat_with_db_execute",
        "Chat Data",
        "Dialogue with your private data through natural language.",
        ["DB Select"],
    )
    ChatWithDbQA = Scene(
        "chat_with_db_qa",
        "Chat Meta Data",
        "Have a Professional Conversation with Metadata.",
        ["DB Select"],
    )
    ChatExecution = Scene(
        "chat_execution",
        "Chat Plugin",
        "Use tools through dialogue to accomplish your goals.",
        ["Plugin Select"],
    )
    ChatDefaultKnowledge = Scene(
        "chat_default_knowledge",
        "Chat Default Knowledge",
        "Dialogue through natural language and private documents and knowledge bases.",
    )
    ChatNewKnowledge = Scene(
        "chat_new_knowledge",
        "Chat New Knowledge",
        "Dialogue through natural language and private documents and knowledge bases.",
        ["Knowledge Select"],
    )
    ChatUrlKnowledge = Scene(
        "chat_url_knowledge",
        "Chat URL",
        "Dialogue through natural language and private documents and knowledge bases.",
        ["Url Input"],
    )
    InnerChatDBSummary = Scene(
        "inner_chat_db_summary", "DB Summary", "Db Summary.", True
    )

    ChatNormal = Scene(
        "chat_normal", "Chat Normal", "Native LLM large model AI dialogue."
    )
    ChatDashboard = Scene(
        "chat_dashboard",
        "Chat Dashboard",
        "Provide you with professional analysis reports through natural language.",
        ["DB Select"],
    )
    ChatKnowledge = Scene(
        "chat_knowledge",
        "Chat Knowledge",
        "Dialogue through natural language and private documents and knowledge bases.",
        ["Knowledge Space Select"],
    )

    def scene_value(self):
        return self.value.code

    def scene_name(self):
        return self._value_.name


if __name__ == "__main__":
    print(ChatScene.ChatWithDbExecute.scene_value())
    # print(ChatScene.ChatWithDbExecute.value.describe)
