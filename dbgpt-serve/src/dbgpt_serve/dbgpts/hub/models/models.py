"""This is an auto-generated model file
You can define your own models and DAOs here
"""
from datetime import datetime
from typing import Any, Dict, Optional, Union

from sqlalchemy import Column, DateTime, Index, Integer, String, UniqueConstraint, desc

from dbgpt.storage.metadata import BaseDao, Model, db
from dbgpt.util.pagination_utils import PaginationResult

from ..api.schemas import ServeRequest, ServerResponse
from ..config import SERVER_APP_TABLE_NAME, ServeConfig


class ServeEntity(Model):
    __tablename__ = SERVER_APP_TABLE_NAME
    id = Column(Integer, primary_key=True, comment="Auto increment id")

    name = Column(String(255), unique=True, nullable=False, comment="dbgpts name")
    description = Column(String(255), nullable=False, comment="dbgpts description")
    author = Column(String(255), nullable=True, comment="dbgpts author")
    email = Column(String(255), nullable=True, comment="dbgpts author email")
    type = Column(String(255), comment="dbgpts type")
    version = Column(String(255), comment="dbgpts version")
    storage_channel = Column(String(255), comment="dbgpts storage channel")
    storage_url = Column(String(255), comment="dbgpts download url")
    download_param = Column(String(255), comment="dbgpts download param")
    gmt_created = Column(
        DateTime,
        default=datetime.utcnow,
        comment="plugin upload time",
    )
    gmt_modified = Column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.utcnow,
        comment="Record update time",
    )
    installed = Column(Integer, default=False, comment="plugin already installed count")

    UniqueConstraint("name", "type", name="uk_dbgpts")
    Index("idx_q_type", "type")

    def __repr__(self):
        return f"ServeEntity(id={self.id}, gmt_created='{self.gmt_created}', gmt_modified='{self.gmt_modified}')"


class ServeDao(BaseDao[ServeEntity, ServeRequest, ServerResponse]):
    """The DAO class for Dbgpts"""

    def __init__(self, serve_config: ServeConfig):
        super().__init__()
        self._serve_config = serve_config

    def from_request(self, request: Union[ServeRequest, Dict[str, Any]]) -> ServeEntity:
        """Convert the request to an entity

        Args:
            request (Union[ServeRequest, Dict[str, Any]]): The request

        Returns:
            T: The entity
        """
        request_dict = (
            request.to_dict() if isinstance(request, ServeRequest) else request
        )
        entity = ServeEntity(**request_dict)
        return entity

    def to_request(self, entity: ServeEntity) -> ServeRequest:
        """Convert the entity to a request

        Args:
            entity (T): The entity

        Returns:
            REQ: The request
        """

        return ServeRequest(
            id=entity.id,
            name=entity.name,
            description=entity.description,
            author=entity.author,
            email=entity.email,
            type=entity.type,
            version=entity.version,
            storage_channel=entity.storage_channel,
            storage_url=entity.storage_url,
            download_param=entity.download_param,
            installed=entity.installed,
        )

    def to_response(self, entity: ServeEntity) -> ServerResponse:
        """Convert the entity to a response

        Args:
            entity (T): The entity

        Returns:
            RES: The response
        """
        gmt_created_str = entity.gmt_created.strftime("%Y-%m-%d %H:%M:%S")
        gmt_modified_str = entity.gmt_modified.strftime("%Y-%m-%d %H:%M:%S")
        request = self.to_request(entity)

        return ServerResponse(
            **request.to_dict(),
            gmt_created=gmt_created_str,
            gmt_modified=gmt_modified_str,
        )

    def dbgpts_list(
        self,
        query_request: ServeRequest,
        page: int,
        page_size: int,
        desc_order_column: Optional[str] = None,
    ) -> PaginationResult[ServerResponse]:
        """Get a page of dbgpts.

        Args:
            query_request (ServeRequest): The request schema object or dict for query.
            page (int): The page number.
            page_size (int): The page size.
            desc_order_column(Optional[str]): The column for descending order.
        Returns:
            PaginationResult: The pagination result.
        """
        session = self.get_raw_session()
        try:
            query = session.query(ServeEntity)
            if query_request.name:
                query = query.filter(ServeEntity.name.like(f"%{query_request.name}%"))
            if desc_order_column:
                query = query.order_by(desc(getattr(ServeEntity, desc_order_column)))
            total_count = query.count()
            items = query.offset((page - 1) * page_size).limit(page_size)
            res_items = [self.to_response(item) for item in items]
            total_pages = (total_count + page_size - 1) // page_size
        finally:
            session.close()

        return PaginationResult(
            items=res_items,
            total_count=total_count,
            total_pages=total_pages,
            page=page,
            page_size=page_size,
        )
