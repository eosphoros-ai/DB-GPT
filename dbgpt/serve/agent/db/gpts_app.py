import json
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Integer,
    String,
    Text,
    UniqueConstraint,
)

from dbgpt.agent.agents.resource import AgentResource
from dbgpt.storage.metadata import BaseDao, Model


class GptsAppDetail(BaseModel):
    app_code: str = str(uuid.uuid1())
    app_name: str
    agent_name: str
    node_id: str
    resources: Optional[list[AgentResource]] = None
    prompt_template: Optional[str] = None
    llm_strategy: Optional[str] = None
    llm_strategy_value: Optional[str] = None
    created_at: datetime = datetime.now()
    updated_at: DateTime = datetime.now()

    def to_dict(self):
        return {k: self._serialize(v) for k, v in self.__dict__.items()}

    def _serialize(self, value):
        if isinstance(value, BaseModel):
            return value.to_dict()
        elif isinstance(value, list):
            return [self._serialize(item) for item in value]
        elif isinstance(value, dict):
            return {k: self._serialize(v) for k, v in value.items()}
        else:
            return value

    @classmethod
    def from_dict(cls, d: Dict[str, Any]):
        return cls(
            app_code=d["app_code"],
            app_name=d["app_name"],
            agent_name=d["agent_name"],
            node_id=d["node_id"],
            resources=d.get("resources", None),
            prompt_template=d.get("prompt_template", None),
            llm_strategy=d.get("llm_strategy", None),
            llm_strategy_value=d.get("llm_strategy_value", None),
            created_at=d.get("created_at", None),
            updated_at=d.get("updated_at", None),
        )


class GptsApp(BaseModel):
    app_code: str = str(uuid.uuid1())
    app_name: str
    app_describe: Optional[str]
    team_mode: str
    language: str
    team_context: Optional[str] = None
    user_code: Optional[str] = None
    sys_code: Optional[str] = None
    created_at: datetime = datetime.now()
    updated_at: DateTime = datetime.now()
    details: List[GptsAppDetail] = []

    def to_dict(self):
        return {k: self._serialize(v) for k, v in self.__dict__.items()}

    def _serialize(self, value):
        if isinstance(value, BaseModel):
            return value.to_dict()
        elif isinstance(value, list):
            return [self._serialize(item) for item in value]
        elif isinstance(value, dict):
            return {k: self._serialize(v) for k, v in value.items()}
        else:
            return value

    @classmethod
    def from_dict(cls, d: Dict[str, Any]):
        return cls(
            app_code=d.get("app_code", None),
            app_name=d["app_name"],
            app_describe=d["app_describe"],
            team_mode=d["team_mode"],
            team_context=d.get("team_context", None),
            user_code=d.get("user_code", None),
            sys_code=d.get("sys_code", None),
            created_at=d.get("created_at", None),
            updated_at=d.get("updated_at", None),
            details=d.get("details", None),
        )


class GptsAppEntity(Model):
    __tablename__ = "gpts_app"
    id = Column(Integer, primary_key=True, comment="autoincrement id")
    app_code = Column(String(255), nullable=False, comment="Current AI assistant code")
    app_name = Column(String(255), nullable=False, comment="Current AI assistant name")
    app_describe = Column(
        String(2255), nullable=False, comment="Current AI assistant describe"
    )
    language = Column(String(100), nullable=False, comment="gpts language")
    team_mode = Column(String(255), nullable=False, comment="Team work mode")
    team_context = Column(
        Text,
        nullable=True,
        comment="The execution logic and team member content that teams with different working modes rely on",
    )

    user_code = Column(String(255), nullable=True, comment="user code")
    sys_code = Column(String(255), nullable=True, comment="system app code")

    created_at = Column(DateTime, default=datetime.utcnow, comment="create time")
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        comment="last update time",
    )

    __table_args__ = (UniqueConstraint("app_name", name="uk_gpts_app"),)


class GptsAppDetailEntity(Model):
    __tablename__ = "gpts_app_detail"
    id = Column(Integer, primary_key=True, comment="autoincrement id")
    app_code = Column(String(255), nullable=False, comment="Current AI assistant code")
    app_name = Column(String(255), nullable=False, comment="Current AI assistant name")
    agent_name = Column(String(255), nullable=False, comment=" Agent name")
    node_id = Column(
        String(255), nullable=False, comment="Current AI assistant Agent Node id"
    )
    resources = Column(Text, nullable=True, comment="Agent bind  resource")
    prompt_template = Column(Text, nullable=True, comment="Agent bind  template")
    llm_strategy = Column(String(25), nullable=True, comment="Agent use llm strategy")
    llm_strategy_value = Column(
        Text, nullable=True, comment="Agent use llm strategy value"
    )
    created_at = Column(DateTime, default=datetime.utcnow, comment="create time")
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        comment="last update time",
    )

    __table_args__ = (
        UniqueConstraint(
            "app_name", "agent_name", "node_id", name="uk_gpts_app_agent_node"
        ),
    )

    def to_dict(self):
        return {k: self._serialize(v) for k, v in self.__dict__.items()}

    def _serialize(self, value):
        if isinstance(value, BaseModel):
            return value.to_dict()
        elif isinstance(value, list):
            return [self._serialize(item) for item in value]
        elif isinstance(value, dict):
            return {k: self._serialize(v) for k, v in value.items()}
        else:
            return value


class GptsAppDao(BaseDao):
    def app_list(
        self,
        name_prefix: Optional[str] = None,
        user_code: Optional[str] = None,
        sys_code: Optional[str] = None,
    ):
        with self.session() as session:
            app_qry = session.query(GptsAppEntity)
            if name_prefix:
                app_qry.filter(GptsAppEntity.app_name.like(f"%{name_prefix}%"))
            if user_code:
                app_qry.filter(GptsAppEntity.user_code == user_code)
            if sys_code:
                app_qry.filter(GptsAppEntity.sys_code == sys_code)

            return app_qry.all()

    def app_detail(self, app_code: str):
        with self.session() as session:
            app_qry = session.query(GptsAppEntity)
            app_qry.filter(GptsAppEntity.app_code == app_code)
            app_info = app_qry.first()

            app_detail_qry = session.query(GptsAppDetailEntity).filter(
                GptsAppDetailEntity.app_code == app_code
            )
            app_details = app_detail_qry.all()

            return GptsApp.from_dict(
                {
                    "app_code": app_info.app_code,
                    "app_name": app_info.app_name,
                    "app_describe": app_info.app_describe,
                    "team_mode": app_info.team_mode,
                    "team_context": app_info.team_context,
                    "user_code": app_info.user_code,
                    "sys_code": app_info.sys_code,
                    "created_at": app_info.created_at,
                    "updated_at": app_info.updated_at,
                    "details": [item.to_dict() for item in app_details],
                }
            )

    def delete(self, app_code: str):
        with self.session() as session:
            app_qry = session.query(GptsAppEntity)
            app_qry.filter(GptsAppEntity.app_code == app_code)
            app_qry.delete()

    def create(self, gpts_app: GptsApp):
        with self.session() as session:
            app_entity = GptsAppEntity(
                app_code=gpts_app.app_code,
                app_name=gpts_app.app_name,
                app_describe=gpts_app.app_describe,
                team_mode=gpts_app.team_mode,
                team_context=gpts_app.team_context,
                language=gpts_app.language,
                user_code=gpts_app.user_code,
                sys_code=gpts_app.sys_code,
                created_at=gpts_app.created_at,
                updated_at=gpts_app.updated_at,
            )
            session.add(app_entity)

            app_details = []
            for item in gpts_app.details:
                app_details.append(
                    GptsAppDetailEntity(
                        app_code=item.app_code,
                        app_name=item.app_code,
                        agent_name=item.agent_name,
                        node_id=item.node_id,
                        resources=json.dumps(item.resources, ensure_ascii=False),
                        prompt_template=item.prompt_template,
                        llm_strategy=item.llm_strategy,
                        llm_strategy_value=item.llm_strategy_value,
                        created_at=item.created_at,
                        updated_at=item.updated_at,
                    )
                )
            session.add_all(app_details)

    def edit(self, id: int, gpts_app: GptsApp):
        with self.session() as session:
            app_entity = GptsAppEntity(
                id=id,
                app_code=gpts_app.app_code,
                app_name=gpts_app.app_name,
                app_describe=gpts_app.app_describe,
                team_mode=gpts_app.team_mode,
                team_context=gpts_app.team_context,
                language=gpts_app.language,
                user_code=gpts_app.user_code,
                sys_code=gpts_app.sys_code,
                created_at=gpts_app.created_at,
                updated_at=gpts_app.updated_at,
            )
            session.merge(app_entity)

            old_details = session.query(GptsAppDetailEntity).filter(
                GptsAppDetailEntity.app_code == gpts_app.app_code
            )
            old_details.delete()
            session.commit()

            app_details = []
            for item in old_details:
                app_details.append(
                    GptsAppDetailEntity(
                        app_code=item.app_code,
                        app_name=item.app_code,
                        agent_name=item.agent_name,
                        node_id=item.node_id,
                        resources=json.dumps(item.resources, ensure_ascii=False),
                        prompt_template=item.prompt_template,
                        llm_strategy=item.llm_strategy,
                        llm_strategy_value=item.llm_strategy_value,
                        created_at=item.created_at,
                        updated_at=item.updated_at,
                    )
                )
            session.add_all(app_details)
