from datetime import datetime
from typing import Optional

from sqlalchemy import inspect as sa_inspect

from dbgpt.component import ComponentType, SystemApp
from dbgpt.storage.chat_history.chat_history_db import ChatHistoryEntity
from dbgpt.storage.metadata import (
    BaseDao,
    DatabaseManager,
    UnifiedDBManagerFactory,
    db,
)
from dbgpt_app.openapi.api_v1.feedback.feed_back_model import FeedBackBody
from dbgpt_serve.feedback.models.models import ServeEntity

ChatFeedBackEntity = ServeEntity


class ChatFeedBackDao(BaseDao):
    def __init__(
        self,
        db_manager: Optional[DatabaseManager] = None,
        conv_db_manager: Optional[DatabaseManager] = None,
    ) -> None:
        super().__init__(db_manager=db_manager)
        self._explicit_db_manager = db_manager
        self._conv_db_manager = conv_db_manager

    @staticmethod
    def _active_system_app() -> Optional[SystemApp]:
        from dbgpt._private.config import Config
        from dbgpt_serve.conversation.api import endpoints as conv_endpoints
        from dbgpt_serve.feedback.api import endpoints as fb_endpoints

        return (
            fb_endpoints.global_system_app
            or conv_endpoints.global_system_app
            or Config().SYSTEM_APP
        )

    def _resolve_feedback_db_manager(self) -> DatabaseManager:
        if self._explicit_db_manager is not None:
            return self._explicit_db_manager
        sys_app = self._active_system_app()
        if sys_app is not None:
            from dbgpt_serve.feedback.serve import Serve as FeedbackServe

            fb_serve = FeedbackServe.get_current_serve(sys_app)
            serve_db = getattr(fb_serve, "_db_manager", None)
            if serve_db is not None:
                return serve_db
            factory = sys_app.get_component(
                ComponentType.UNIFIED_METADATA_DB_MANAGER_FACTORY,
                UnifiedDBManagerFactory,
                default_component=None,
            )
            if factory is not None:
                try:
                    return factory.create()
                except RuntimeError:
                    pass
        return db

    def _resolve_conv_db_manager(self) -> DatabaseManager:
        if self._conv_db_manager is not None:
            return self._conv_db_manager
        sys_app = self._active_system_app()
        if sys_app is not None:
            from dbgpt_serve.conversation.serve import Serve as ConversationServe

            conv_serve = ConversationServe.get_current_serve(sys_app)
            if conv_serve is not None:
                serve_db = getattr(conv_serve, "_db_manager", None)
                if serve_db is not None:
                    return serve_db
                conv_storage = getattr(conv_serve, "conv_storage", None)
                storage_db = getattr(conv_storage, "_db_manager", None)
                if storage_db is not None:
                    return storage_db
            factory = sys_app.get_component(
                ComponentType.UNIFIED_METADATA_DB_MANAGER_FACTORY,
                UnifiedDBManagerFactory,
                default_component=None,
            )
            if factory is not None:
                try:
                    return factory.create()
                except RuntimeError:
                    pass
        if self._explicit_db_manager is not None:
            return self._explicit_db_manager
        return db

    def _verify_conversation_owner(
        self,
        conv_uid: str,
        effective_user: str,
        *,
        allow_default_conv_owner: bool = False,
    ) -> str:
        conv_db = self._resolve_conv_db_manager()
        if not conv_db.is_initialized or conv_db.engine is None:
            raise PermissionError("Conversation ownership store is unavailable")
        if not sa_inspect(conv_db.engine).has_table(ChatHistoryEntity.__tablename__):
            raise PermissionError("Conversation ownership store is unavailable")
        with conv_db.session(commit=False) as conv_session:
            conv = (
                conv_session.query(ChatHistoryEntity)
                .filter(ChatHistoryEntity.conv_uid == conv_uid)
                .first()
            )
            conv_owner = (conv.user_name or "").strip() if conv is not None else ""
            if (
                conv_owner
                and conv_owner != effective_user
                and not (allow_default_conv_owner and conv_owner == "001")
            ):
                raise PermissionError(
                    "Cannot submit feedback for another user's conversation"
                )
            return conv_owner

    def create_or_update_chat_feed_back(
        self,
        feed_back: FeedBackBody,
        user_name: Optional[str] = None,
        *,
        allow_default_conv_owner: bool = False,
    ):
        raw_user = user_name if user_name is not None else feed_back.user_name
        effective_user = (raw_user or "").strip()
        if not effective_user:
            raise PermissionError("Authenticated user identity is required")
        if not feed_back.conv_uid or feed_back.conv_index is None:
            raise ValueError("conv_uid and conv_index are required")

        conv_owner = self._verify_conversation_owner(
            feed_back.conv_uid,
            effective_user,
            allow_default_conv_owner=allow_default_conv_owner,
        )

        feedback_db = self._resolve_feedback_db_manager()
        with feedback_db.session(commit=True) as session:
            if allow_default_conv_owner and conv_owner in ("", "001"):
                conv_rows = (
                    session.query(ChatFeedBackEntity)
                    .filter(ChatFeedBackEntity.conv_uid == feed_back.conv_uid)
                    .all()
                )
                for existing_row in conv_rows:
                    row_owner = (existing_row.user_name or "").strip()
                    if row_owner and row_owner != effective_user:
                        raise PermissionError(
                            "Cannot submit feedback for another session's conversation"
                        )

            result = (
                session.query(ChatFeedBackEntity)
                .filter(ChatFeedBackEntity.conv_uid == feed_back.conv_uid)
                .filter(ChatFeedBackEntity.conv_index == feed_back.conv_index)
                .first()
            )
            now = datetime.now()
            if result is not None:
                direct_owner_reclaiming_session_row = (
                    not allow_default_conv_owner
                    and bool(conv_owner)
                    and conv_owner == effective_user
                    and (result.user_name or "").startswith("session:")
                )
                if (
                    result.user_name != effective_user
                    and not direct_owner_reclaiming_session_row
                ):
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

    def get_chat_feed_back(
        self,
        conv_uid: str,
        conv_index: int,
        user_name: Optional[str] = None,
    ) -> Optional[ServeEntity]:
        normalized_user = (user_name or "").strip()
        if not normalized_user:
            return None
        feedback_db = self._resolve_feedback_db_manager()
        with feedback_db.session(commit=False) as session:
            rows = (
                session.query(ChatFeedBackEntity)
                .filter(ChatFeedBackEntity.conv_uid == conv_uid)
                .filter(ChatFeedBackEntity.conv_index == conv_index)
                .all()
            )
            for row in rows:
                # Enforce exact case-sensitive owner comparison in Python so
                # deployments using case-insensitive collations (e.g. MySQL utf8mb4)
                # never leak `Alice`'s feedback to `alice`.
                if row.user_name == normalized_user:
                    _ = (
                        row.conv_uid,
                        row.conv_index,
                        row.question,
                        row.knowledge_space,
                        row.score,
                        row.ques_type,
                        row.user_name,
                        row.messages,
                    )
                    session.expunge(row)
                    return row
        return None
