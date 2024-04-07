from datetime import datetime
from typing import Any, Dict, List, Union

from sqlalchemy import Column, DateTime, Integer, String, Text

from dbgpt.serve.rag.api.schemas import SpaceServeRequest, SpaceServeResponse
from dbgpt.storage.metadata import BaseDao, Model


class KnowledgeSpaceEntity(Model):
    __tablename__ = "knowledge_space"
    id = Column(Integer, primary_key=True)
    name = Column(String(100))
    vector_type = Column(String(100))
    desc = Column(String(100))
    owner = Column(String(100))
    context = Column(Text)
    gmt_created = Column(DateTime)
    gmt_modified = Column(DateTime)

    def __repr__(self):
        return f"KnowledgeSpaceEntity(id={self.id}, name='{self.name}', vector_type='{self.vector_type}', desc='{self.desc}', owner='{self.owner}' context='{self.context}', gmt_created='{self.gmt_created}', gmt_modified='{self.gmt_modified}')"


class KnowledgeSpaceDao(BaseDao):
    def create_knowledge_space(self, space: SpaceServeRequest):
        """Create knowledge space"""
        session = self.get_raw_session()
        knowledge_space = KnowledgeSpaceEntity(
            name=space.name,
            vector_type=space.vector_type,
            desc=space.desc,
            owner=space.owner,
            gmt_created=datetime.now(),
            gmt_modified=datetime.now(),
        )
        session.add(knowledge_space)
        session.commit()
        space_id = knowledge_space.id
        session.close()
        return self.to_response(knowledge_space)

    def get_knowledge_space(self, query: KnowledgeSpaceEntity):
        """Get knowledge space by query"""
        session = self.get_raw_session()
        knowledge_spaces = session.query(KnowledgeSpaceEntity)
        if query.id is not None:
            knowledge_spaces = knowledge_spaces.filter(
                KnowledgeSpaceEntity.id == query.id
            )
        if query.name is not None:
            knowledge_spaces = knowledge_spaces.filter(
                KnowledgeSpaceEntity.name == query.name
            )
        if query.vector_type is not None:
            knowledge_spaces = knowledge_spaces.filter(
                KnowledgeSpaceEntity.vector_type == query.vector_type
            )
        if query.desc is not None:
            knowledge_spaces = knowledge_spaces.filter(
                KnowledgeSpaceEntity.desc == query.desc
            )
        if query.owner is not None:
            knowledge_spaces = knowledge_spaces.filter(
                KnowledgeSpaceEntity.owner == query.owner
            )
        if query.gmt_created is not None:
            knowledge_spaces = knowledge_spaces.filter(
                KnowledgeSpaceEntity.gmt_created == query.gmt_created
            )
        if query.gmt_modified is not None:
            knowledge_spaces = knowledge_spaces.filter(
                KnowledgeSpaceEntity.gmt_modified == query.gmt_modified
            )
        knowledge_spaces = knowledge_spaces.order_by(
            KnowledgeSpaceEntity.gmt_created.desc()
        )
        result = knowledge_spaces.all()
        session.close()
        return result

    def update_knowledge_space(self, space: KnowledgeSpaceEntity):
        """Update knowledge space"""

        session = self.get_raw_session()
        request = SpaceServeRequest(id=space.id)
        update_request = self.to_request(space)
        query = self._create_query_object(session, request)
        entry = query.first()
        if entry is None:
            raise Exception("Invalid request")
        for key, value in update_request.dict().items():  # type: ignore
            if value is not None:
                setattr(entry, key, value)
        session.merge(entry)
        session.commit()
        session.close()
        return self.to_response(space)

    def delete_knowledge_space(self, space: KnowledgeSpaceEntity):
        """Delete knowledge space"""
        session = self.get_raw_session()
        if space:
            session.delete(space)
            session.commit()
        session.close()

    def from_request(
        self, request: Union[SpaceServeRequest, Dict[str, Any]]
    ) -> KnowledgeSpaceEntity:
        """Convert the request to an entity

        Args:
            request (Union[ServeRequest, Dict[str, Any]]): The request

        Returns:
            T: The entity
        """
        request_dict = (
            request.dict() if isinstance(request, SpaceServeRequest) else request
        )
        entity = KnowledgeSpaceEntity(**request_dict)
        return entity

    def to_request(self, entity: KnowledgeSpaceEntity) -> SpaceServeRequest:
        """Convert the entity to a request

        Args:
            entity (T): The entity

        Returns:
            REQ: The request
        """
        return SpaceServeRequest(
            id=entity.id,
            name=entity.name,
            vector_type=entity.vector_type,
            desc=entity.desc,
            owner=entity.owner,
            context=entity.context,
        )

    def to_response(self, entity: KnowledgeSpaceEntity) -> SpaceServeResponse:
        """Convert the entity to a response

        Args:
            entity (T): The entity

        Returns:
            REQ: The request
        """
        return SpaceServeResponse(
            id=entity.id,
            name=entity.name,
            vector_type=entity.vector_type,
            desc=entity.desc,
            owner=entity.owner,
        )
