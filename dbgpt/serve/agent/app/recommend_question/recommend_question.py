import json
from datetime import datetime
from typing import Any, Dict, Optional, Union

from sqlalchemy import Column, DateTime, Index, Integer, String, Text

from dbgpt._private.pydantic import BaseModel, Field
from dbgpt.storage.metadata import BaseDao, Model


class RecommendQuestion(BaseModel):
    id: Optional[int] = Field(None, description="id")
    app_code: Optional[str] = Field(None, description="The unique identify of app")
    question: Optional[str] = Field(None, description="The question you may ask")
    user_code: Optional[str] = Field(None, description="The user code")
    sys_code: Optional[str] = Field(None, description="The system code")
    gmt_create: datetime = datetime.now()
    gmt_modified: datetime = datetime.now()
    params: Optional[dict] = Field(default={}, description="The params of app")
    valid: Optional[Union[str, bool]] = Field(
        default=None, description="is the question valid to display, default is true"
    )
    chat_mode: Optional[str] = Field(
        default=None, description="is the question valid to display, default is true"
    )
    is_hot_question: Optional[str] = Field(default=None, description="is hot question.")

    @classmethod
    def from_dict(cls, d: Dict[str, Any]):
        return cls(
            id=d["id"],
            app_code=d.get("app_code", None),
            question=d.get("question", None),
            user_code=str(d.get("user_code", None)),
            sys_code=d.get("sys_code", None),
            gmt_create=d.get("gmt_create", None),
            updated_at=d.get("updated_at", None),
            gmt_modified=d.get("gmt_modified", None),
            params=d.get("params", None),
            valid=d.get("valid", False),
            chat_mode=d.get("chat_mode", None),
            is_hot_question=d.get("is_hot_question", False),
        )

    @classmethod
    def from_entity(cls, entity):
        return RecommendQuestion.from_dict(
            {
                "id": entity.id,
                "app_code": entity.app_code,
                "question": entity.question,
                "user_code": entity.user_code,
                "sys_code": entity.sys_code,
                "gmt_create": entity.gmt_create,
                "gmt_modified": entity.gmt_modified,
                "params": json.loads(entity.params),
                "valid": entity.valid,
                "chat_mode": entity.chat_mode,
                "is_hot_question": entity.is_hot_question,
            }
        )


class RecommendQuestionEntity(Model):
    __tablename__ = "recommend_question"
    id = Column(Integer, primary_key=True, comment="autoincrement id")
    app_code = Column(String(255), nullable=False, comment="Current AI assistant code")
    user_code = Column(String(255), nullable=True, comment="user code")
    sys_code = Column(String(255), nullable=True, comment="system app code")
    gmt_create = Column(DateTime, default=datetime.utcnow, comment="create time")
    gmt_modified = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        comment="last update time",
    )
    question = Column(Text, default=None, comment="question")
    valid = Column(String(31), default=True, comment="is valid")
    params = Column(Text, nullable=True, comment="is valid")
    chat_mode = Column(
        String(31),
        nullable=True,
        comment="chat_mode, such as chat_knowledge, chat_normal",
    )
    is_hot_question = Column(
        String(10),
        default=False,
        comment="hot question would be displayed on the main page.",
    )
    __table_args__ = (Index("idx_app_code", "app_code"),)


class RecommendQuestionDao(BaseDao):
    def list_questions(self, rq: RecommendQuestion):
        questions = []
        with self.session() as session:
            qry = session.query(RecommendQuestionEntity)
            if rq.valid is not None:
                qry = qry.filter(RecommendQuestionEntity.valid == rq.valid)
            if rq.app_code is not None:
                qry = qry.filter(RecommendQuestionEntity.app_code == rq.app_code)
            if rq.chat_mode is not None:
                qry = qry.filter(RecommendQuestionEntity.chat_mode == rq.chat_mode)
            if rq.is_hot_question is not None:
                qry = qry.filter(
                    RecommendQuestionEntity.is_hot_question == rq.is_hot_question
                )
            entities = qry.all()
            for entity in entities:
                questions.append(RecommendQuestion.from_entity(entity))
        return questions

    def create(self, recommend_question: RecommendQuestion):
        with self.session() as session:
            entity = RecommendQuestionEntity(
                app_code=recommend_question.app_code,
                question=recommend_question.question,
                user_code=recommend_question.user_code,
                sys_code=recommend_question.sys_code,
                gmt_create=recommend_question.gmt_create,
                gmt_modified=recommend_question.gmt_modified,
                params=json.dumps(recommend_question.params),
                valid=recommend_question.valid,
                chat_mode=recommend_question.chat_mode,
                is_hot_question=recommend_question.is_hot_question,
            )
            session.add(entity)
            return RecommendQuestion.from_entity(entity)

    def update_question(self, recommend_question: RecommendQuestion):
        with self.session() as session:
            qry = session.query(RecommendQuestionEntity)
            qry = qry.filter(RecommendQuestionEntity.id == recommend_question.id)
            entity = qry.one()
            if entity is not None:
                if recommend_question.question is not None:
                    entity.question = recommend_question.question
                if recommend_question.app_code is not None:
                    entity.app_code = recommend_question.app_code
                if recommend_question.valid is not None:
                    entity.valid = recommend_question.valid
                if recommend_question.user_code is not None:
                    entity.user_code = recommend_question.user_code
                if recommend_question.is_hot_question is not None:
                    entity.is_hot_question = recommend_question.is_hot_question
                session.merge(entity)

    def delete_question(self, recommend_question: RecommendQuestion):
        with self.session() as session:
            qry = session.query(RecommendQuestionEntity)
            qry = qry.filter(RecommendQuestionEntity.id == recommend_question.id)
            entity = qry.one()
            if entity is not None:
                session.delete(entity)

    def delete_by_app_code(self, app_code: str):
        with self.session() as session:
            qry = session.query(RecommendQuestionEntity)
            qry = qry.filter(RecommendQuestionEntity.app_code == app_code)
            qry.delete()
