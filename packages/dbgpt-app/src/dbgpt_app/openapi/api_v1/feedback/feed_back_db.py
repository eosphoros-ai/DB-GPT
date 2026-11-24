from datetime import datetime
from typing import Optional

from sqlalchemy import inspect as sa_inspect

from dbgpt.storage.chat_history.chat_history_db import ChatHistoryEntity
from dbgpt.storage.metadata import BaseDao
from dbgpt_app.openapi.api_v1.feedback.feed_back_model import FeedBackBody
from dbgpt_serve.feedback.models.models import ServeEntity

ChatFeedBackEntity = ServeEntity


class ChatFeedBackDao(BaseDao):
    def create_or_update_chat_feed_back(
        self, feed_back: FeedBackBody, user_name: Optional[str] = None
    ):
        raw_user = user_name if user_name is not None else feed_back.user_name
        effective_user = (raw_user or "").strip()
        if not effective_user:
            raise PermissionError("Authenticated user identity is required")
        if not feed_back.conv_uid or feed_back.conv_index is None:
            raise ValueError("conv_uid and conv_index are required")

        session = self.get_raw_session()
        try:
            bind = session.get_bind()
            if bind is not None and sa_inspect(bind).has_table(
                ChatHistoryEntity.__tablename__
            ):
                conv = (
                    session.query(ChatHistoryEntity)
                    .filter(ChatHistoryEntity.conv_uid == feed_back.conv_uid)
                    .first()
                )
                if (
                    conv is not None
                    and conv.user_name
                    and conv.user_name != effective_user
                ):
                    raise PermissionError(
                        "Cannot submit feedback for another user's conversation"
                    )

            result = (
                session.query(ChatFeedBackEntity)
                .filter(ChatFeedBackEntity.conv_uid == feed_back.conv_uid)
                .filter(ChatFeedBackEntity.conv_index == feed_back.conv_index)
                .first()
            )
            now = datetime.now()
            if result is not None:
                if result.user_name != effective_user:
                    raise PermissionError("Cannot modify another user's feedback")
                result.score = feed_back.score
                result.ques_type = feed_back.ques_type
                result.question = feed_back.question
                result.knowledge_space = feed_back.knowledge_space
                result.messages = feed_back.messages
                result.user_name = effective_user
                result.gmt_modified = now
            else:
                chat_feed_back = ChatFeedBackEntity(
                    conv_uid=feed_back.conv_uid,
                    conv_index=feed_back.conv_index,
                    score=feed_back.score,
                    ques_type=feed_back.ques_type,
                    question=feed_back.question,
                    knowledge_space=feed_back.knowledge_space,
                    messages=feed_back.messages,
                    user_name=effective_user,
                    gmt_created=now,
                    gmt_modified=now,
                )
                session.merge(chat_feed_back)
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def get_chat_feed_back(
        self,
        conv_uid: str,
        conv_index: int,
        user_name: Optional[str] = None,
    ) -> Optional[ServeEntity]:
        normalized_user = (user_name or "").strip()
        if not normalized_user:
            return None
        session = self.get_raw_session()
        try:
            return (
                session.query(ChatFeedBackEntity)
                .filter(ChatFeedBackEntity.conv_uid == conv_uid)
                .filter(ChatFeedBackEntity.conv_index == conv_index)
                .filter(ChatFeedBackEntity.user_name == normalized_user)
                .first()
            )
        finally:
            session.close()
