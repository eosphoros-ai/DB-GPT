from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, Text

from dbgpt.app.openapi.api_v1.feedback.feed_back_model import FeedBackBody
from dbgpt.serve.feedback.models.models import ServeEntity
from dbgpt.storage.metadata import BaseDao, Model

ChatFeedBackEntity = ServeEntity


class ChatFeedBackDao(BaseDao):
    def create_or_update_chat_feed_back(self, feed_back: FeedBackBody):
        # Todo: We need to have user information first.

        session = self.get_raw_session()
        chat_feed_back = ChatFeedBackEntity(
            conv_uid=feed_back.conv_uid,
            conv_index=feed_back.conv_index,
            score=feed_back.score,
            ques_type=feed_back.ques_type,
            question=feed_back.question,
            knowledge_space=feed_back.knowledge_space,
            messages=feed_back.messages,
            user_name=feed_back.user_name,
            gmt_created=datetime.now(),
            gmt_modified=datetime.now(),
        )
        result = (
            session.query(ChatFeedBackEntity)
            .filter(ChatFeedBackEntity.conv_uid == feed_back.conv_uid)
            .filter(ChatFeedBackEntity.conv_index == feed_back.conv_index)
            .first()
        )
        if result is not None:
            result.score = feed_back.score
            result.ques_type = feed_back.ques_type
            result.question = feed_back.question
            result.knowledge_space = feed_back.knowledge_space
            result.messages = feed_back.messages
            result.user_name = feed_back.user_name
            result.gmt_created = datetime.now()
            result.gmt_modified = datetime.now()
        else:
            session.merge(chat_feed_back)
        session.commit()
        session.close()

    def get_chat_feed_back(self, conv_uid: str, conv_index: int):
        session = self.get_raw_session()
        result = (
            session.query(ChatFeedBackEntity)
            .filter(ChatFeedBackEntity.conv_uid == conv_uid)
            .filter(ChatFeedBackEntity.conv_index == conv_index)
            .first()
        )
        session.close()
        return result
