from datetime import datetime
from typing import Any, Dict, Union

from sqlalchemy import Column, DateTime, Index, Integer, String, Text, UniqueConstraint

from dbgpt.storage.metadata import BaseDao, Model, db

from ..api.schemas import DatasetServeRequest, DatasetServeResponse
from ..config import SERVER_APP_TABLE_NAME, ServeConfig


class DatasetServeEntity(Model):
    __tablename__ = "evaluate_datasets"
    __table_args__ = (
        UniqueConstraint(
            "code",
            name="uk_dataset",
        ),
        UniqueConstraint(
            "name",
            name="uk_dataset_name",
        ),
    )
    id = Column(Integer, primary_key=True, comment="Auto increment id")
    code = Column(String(256), comment="evaluate datasets Code")
    name = Column(String(1000), comment="evaluate datasets Name")
    file_type = Column(String(256), comment="datasets file type")
    storage_type = Column(String(256), comment="datasets storage type")
    storage_position = Column(Text, comment="datasets storage position")
    datasets_count = Column(Integer, comment="datasets row count")
    have_answer = Column(String(10), comment="datasets have answer")
    members = Column(String(1000), comment="evaluate datasets members")
    user_id = Column(String(100), index=True, nullable=True, comment="User id")
    user_name = Column(String(128), index=True, nullable=True, comment="User name")
    sys_code = Column(String(128), index=True, nullable=True, comment="System code")
    gmt_create = Column(DateTime, default=datetime.now, comment="Record creation time")
    gmt_modified = Column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now,
        comment="Record update time",
    )

    def __repr__(self):
        return f"ServeEntity(id={self.id}, code='{self.code}', name='{self.name}', file_type='{self.file_type}', storage_type='{self.storage_type}', storage_position='{self.storage_position}', datasets_count='{self.datasets_count}', user_id='{self.user_id}', user_name='{self.user_name}', sys_code='{self.sys_code}', gmt_create='{self.gmt_create}', gmt_modified='{self.gmt_modified}')"


class DatasetServeDao(
    BaseDao[DatasetServeEntity, DatasetServeRequest, DatasetServeResponse]
):
    """The DAO class for Prompt"""

    def __init__(self, serve_config: ServeConfig):
        super().__init__()
        self._serve_config = serve_config

    def from_request(
        self, request: Union[DatasetServeRequest, Dict[str, Any]]
    ) -> DatasetServeEntity:
        """Convert the request to an entity

        Args:
            request (Union[DatasetServeRequest, Dict[str, Any]]): The request

        Returns:
            T: The entity
        """
        request_dict = (
            request.dict() if isinstance(request, DatasetServeRequest) else request
        )
        entity = DatasetServeEntity(**request_dict)
        return entity

    def to_request(self, entity: DatasetServeEntity) -> DatasetServeRequest:
        """Convert the entity to a request

        Args:
            entity (T): The entity

        Returns:
            REQ: The request
        """
        return DatasetServeRequest(
            code=entity.code,
            name=entity.name,
            file_type=entity.file_type,
            storage_type=entity.storage_type,
            storage_position=entity.storage_position,
            datasets_count=entity.datasets_count,
            have_answer=entity.have_answer,
            members=entity.members,
            user_name=entity.user_name,
            user_id=entity.user_id,
            sys_code=entity.sys_code,
        )

    def to_response(self, entity: DatasetServeEntity) -> DatasetServeResponse:
        """Convert the entity to a response

        Args:
            entity (T): The entity

        Returns:
            RES: The response
        """
        gmt_created_str = entity.gmt_create.strftime("%Y-%m-%d %H:%M:%S")
        gmt_modified_str = entity.gmt_modified.strftime("%Y-%m-%d %H:%M:%S")
        return DatasetServeResponse(
            code=entity.code,
            name=entity.name,
            file_type=entity.file_type,
            storage_type=entity.storage_type,
            storage_position=entity.storage_position,
            datasets_count=entity.datasets_count,
            have_answer=entity.have_answer,
            members=entity.members,
            user_name=entity.user_name,
            user_id=entity.user_id,
            sys_code=entity.sys_code,
            gmt_create=gmt_created_str,
            gmt_modified=gmt_modified_str,
        )
