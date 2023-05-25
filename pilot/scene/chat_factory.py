from pilot.scene.base_chat import BaseChat
from pilot.singleton import Singleton
from pilot.scene.chat_db.chat import ChatWithDb
from pilot.scene.chat_execution.chat import ChatWithPlugin


class ChatFactory(metaclass=Singleton):
    @staticmethod
    def get_implementation(chat_mode, **kwargs):
        chat_classes = BaseChat.__subclasses__()
        implementation = None
        for cls in chat_classes:
            if cls.chat_scene == chat_mode:
                implementation = cls(**kwargs)
        if implementation == None:
            raise Exception("Invalid implementation name:" + chat_mode)
        return implementation
