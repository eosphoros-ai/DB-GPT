from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Session

from dbgpt.core.interface.storage import ResourceIdentifier, StorageItemAdapter
from dbgpt.storage.metadata import Model

from .storage import ModelInstanceStorageItem


class ModelInstanceEntity(Model):
    """Model instance entity.

    Use database as the registry, here is the table schema of the model instance.
    """

    __tablename__ = "dbgpt_cluster_registry_instance"
    __table_args__ = (
        UniqueConstraint(
            "model_name",
            "host",
            "port",
            "sys_code",
            name="uk_model_instance",
        ),
    )
    id = Column(Integer, primary_key=True, comment="Auto increment id")
    model_name = Column(String(128), nullable=False, comment="Model name")
    host = Column(String(128), nullable=False, comment="Host of the model")
    port = Column(Integer, nullable=False, comment="Port of the model")
    weight = Column(Float, nullable=True, default=1.0, comment="Weight of the model")
    check_healthy = Column(
        Boolean,
        nullable=True,
        default=True,
        comment="Whether to check the health of the model",
    )
    healthy = Column(
        Boolean, nullable=True, default=False, comment="Whether the model is healthy"
    )
    enabled = Column(
        Boolean, nullable=True, default=True, comment="Whether the model is enabled"
    )
    prompt_template = Column(
        String(128),
        nullable=True,
        comment="Prompt template for the model instance",
    )
    last_heartbeat = Column(
        DateTime,
        nullable=True,
        comment="Last heartbeat time of the model instance",
    )
    user_name = Column(String(128), nullable=True, comment="User name")
    sys_code = Column(String(128), nullable=True, comment="System code")
    gmt_created = Column(DateTime, default=datetime.now, comment="Record creation time")
    gmt_modified = Column(DateTime, default=datetime.now, comment="Record update time")


class ModelInstanceItemAdapter(
    StorageItemAdapter[ModelInstanceStorageItem, ModelInstanceEntity]
):
    def to_storage_format(self, item: ModelInstanceStorageItem) -> ModelInstanceEntity:
        return ModelInstanceEntity(
            model_name=item.model_name,
            host=item.host,
            port=item.port,
            weight=item.weight,
            check_healthy=item.check_healthy,
            healthy=item.healthy,
            enabled=item.enabled,
            prompt_template=item.prompt_template,
            last_heartbeat=item.last_heartbeat,
            # user_name=item.user_name,
            # sys_code=item.sys_code,
        )

    def from_storage_format(
        self, model: ModelInstanceEntity
    ) -> ModelInstanceStorageItem:
        return ModelInstanceStorageItem(
            model_name=model.model_name,
            host=model.host,
            port=model.port,
            weight=model.weight,
            check_healthy=model.check_healthy,
            healthy=model.healthy,
            enabled=model.enabled,
            prompt_template=model.prompt_template,
            last_heartbeat=model.last_heartbeat,
        )

    def get_query_for_identifier(
        self,
        storage_format: ModelInstanceEntity,
        resource_id: ResourceIdentifier,
        **kwargs,
    ):
        session: Session = kwargs.get("session")
        if session is None:
            raise Exception("session is None")
        query_obj = session.query(ModelInstanceEntity)
        for key, value in resource_id.to_dict().items():
            if value is None:
                continue
            query_obj = query_obj.filter(getattr(ModelInstanceEntity, key) == value)
        return query_obj
