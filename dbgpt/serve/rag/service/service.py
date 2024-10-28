import asyncio
import json
import logging
import os
import shutil
import tempfile
from datetime import datetime
from enum import Enum
from typing import List, Optional, cast

from fastapi import HTTPException

from dbgpt._private.config import Config
from dbgpt.app.knowledge.chunk_db import DocumentChunkDao, DocumentChunkEntity
from dbgpt.app.knowledge.document_db import (
    KnowledgeDocumentDao,
    KnowledgeDocumentEntity,
)
from dbgpt.app.knowledge.request.request import BusinessFieldType, KnowledgeSpaceRequest
from dbgpt.component import ComponentType, SystemApp
from dbgpt.configs import TAG_KEY_KNOWLEDGE_FACTORY_DOMAIN_TYPE
from dbgpt.configs.model_config import (
    EMBEDDING_MODEL_CONFIG,
    KNOWLEDGE_UPLOAD_ROOT_PATH,
)
from dbgpt.core import LLMClient
from dbgpt.model import DefaultLLMClient
from dbgpt.model.cluster import WorkerManagerFactory
from dbgpt.rag.assembler import EmbeddingAssembler
from dbgpt.rag.chunk_manager import ChunkParameters
from dbgpt.rag.embedding import EmbeddingFactory
from dbgpt.rag.knowledge import ChunkStrategy, KnowledgeFactory, KnowledgeType
from dbgpt.serve.core import BaseService
from dbgpt.serve.rag.connector import VectorStoreConnector
from dbgpt.storage.metadata import BaseDao
from dbgpt.storage.metadata._base_dao import QUERY_SPEC
from dbgpt.storage.vector_store.base import VectorStoreConfig
from dbgpt.util.pagination_utils import PaginationResult
from dbgpt.util.string_utils import remove_trailing_punctuation
from dbgpt.util.tracer import root_tracer, trace

from ..api.schemas import (
    ChunkServeRequest,
    DocumentServeRequest,
    DocumentServeResponse,
    DocumentVO,
    KnowledgeSyncRequest,
    SpaceServeRequest,
    SpaceServeResponse,
)
from ..config import SERVE_CONFIG_KEY_PREFIX, SERVE_SERVICE_COMPONENT_NAME, ServeConfig
from ..models.models import KnowledgeSpaceDao, KnowledgeSpaceEntity

logger = logging.getLogger(__name__)
CFG = Config()


class SyncStatus(Enum):
    TODO = "TODO"
    FAILED = "FAILED"
    RUNNING = "RUNNING"
    FINISHED = "FINISHED"


class Service(BaseService[KnowledgeSpaceEntity, SpaceServeRequest, SpaceServeResponse]):
    """The service class for Flow"""

    name = SERVE_SERVICE_COMPONENT_NAME

    def __init__(
        self,
        system_app: SystemApp,
        dao: Optional[KnowledgeSpaceDao] = None,
        document_dao: Optional[KnowledgeDocumentDao] = None,
        chunk_dao: Optional[DocumentChunkDao] = None,
    ):
        self._system_app = system_app
        self._dao: KnowledgeSpaceDao = dao
        self._document_dao: KnowledgeDocumentDao = document_dao
        self._chunk_dao: DocumentChunkDao = chunk_dao

        super().__init__(system_app)

    def init_app(self, system_app: SystemApp) -> None:
        """Initialize the service

        Args:
            system_app (SystemApp): The system app
        """
        super().init_app(system_app)
        self._serve_config = ServeConfig.from_app_config(
            system_app.config, SERVE_CONFIG_KEY_PREFIX
        )
        self._dao = self._dao or KnowledgeSpaceDao()
        self._document_dao = self._document_dao or KnowledgeDocumentDao()
        self._chunk_dao = self._chunk_dao or DocumentChunkDao()
        self._system_app = system_app

    @property
    def dao(
        self,
    ) -> BaseDao[KnowledgeSpaceEntity, SpaceServeRequest, SpaceServeResponse]:
        """Returns the internal DAO."""
        return self._dao

    @property
    def config(self) -> ServeConfig:
        """Returns the internal ServeConfig."""
        return self._serve_config

    @property
    def llm_client(self) -> LLMClient:
        worker_manager = self._system_app.get_component(
            ComponentType.WORKER_MANAGER_FACTORY, WorkerManagerFactory
        ).create()
        return DefaultLLMClient(worker_manager, True)

    def create_space(self, request: SpaceServeRequest) -> SpaceServeResponse:
        """Create a new Space entity

        Args:
            request (KnowledgeSpaceRequest): The request

        Returns:
            SpaceServeResponse: The response
        """
        query = {"name": request.name}
        space = self.get(query)
        if space is not None:
            raise HTTPException(
                status_code=400,
                detail=f"space name:{request.name} have already named",
            )
        return self._dao.create_knowledge_space(request)

    def update_space(self, request: SpaceServeRequest) -> SpaceServeResponse:
        """Create a new Space entity

        Args:
            request (KnowledgeSpaceRequest): The request

        Returns:
            SpaceServeResponse: The response
        """
        spaces = self._dao.get_knowledge_space(
            KnowledgeSpaceEntity(id=request.id, name=request.name)
        )
        if len(spaces) == 0:
            raise HTTPException(
                status_code=400,
                detail=f"no space name named {request.name}",
            )
        update_obj = self._dao.update_knowledge_space(self._dao.from_request(request))
        return update_obj

    async def create_document(
        self, request: DocumentServeRequest
    ) -> SpaceServeResponse:
        """Create a new document entity

        Args:
            request (KnowledgeSpaceRequest): The request

        Returns:
            SpaceServeResponse: The response
        """
        space = self.get({"id": request.space_id})
        if space is None:
            raise Exception(f"space id:{request.space_id} not found")
        query = KnowledgeDocumentEntity(doc_name=request.doc_name, space=space.name)
        documents = self._document_dao.get_knowledge_documents(query)
        if len(documents) > 0:
            raise Exception(f"document name:{request.doc_name} have already named")
        if request.doc_file and request.doc_type == KnowledgeType.DOCUMENT.name:
            doc_file = request.doc_file
            if not os.path.exists(os.path.join(KNOWLEDGE_UPLOAD_ROOT_PATH, space.name)):
                os.makedirs(os.path.join(KNOWLEDGE_UPLOAD_ROOT_PATH, space.name))
            tmp_fd, tmp_path = tempfile.mkstemp(
                dir=os.path.join(KNOWLEDGE_UPLOAD_ROOT_PATH, space.name)
            )
            with os.fdopen(tmp_fd, "wb") as tmp:
                tmp.write(await request.doc_file.read())
            shutil.move(
                tmp_path,
                os.path.join(KNOWLEDGE_UPLOAD_ROOT_PATH, space.name, doc_file.filename),
            )
            request.content = os.path.join(
                KNOWLEDGE_UPLOAD_ROOT_PATH, space.name, doc_file.filename
            )
        document = KnowledgeDocumentEntity(
            doc_name=request.doc_name,
            doc_type=request.doc_type,
            space=space.name,
            chunk_size=0,
            status=SyncStatus.TODO.name,
            last_sync=datetime.now(),
            content=request.content,
            result="",
        )
        doc_id = self._document_dao.create_knowledge_document(document)
        if doc_id is None:
            raise Exception(f"create document failed, {request.doc_name}")
        return doc_id

    async def sync_document(self, requests: List[KnowledgeSyncRequest]) -> List:
        """Create a new document entity

        Args:
            request (KnowledgeSpaceRequest): The request

        Returns:
            SpaceServeResponse: The response
        """
        doc_ids = []
        for sync_request in requests:
            space_id = sync_request.space_id
            docs = self._document_dao.documents_by_ids([sync_request.doc_id])
            if len(docs) == 0:
                raise Exception(
                    f"there are document called, doc_id: {sync_request.doc_id}"
                )
            doc = docs[0]
            if (
                doc.status == SyncStatus.RUNNING.name
                or doc.status == SyncStatus.FINISHED.name
            ):
                raise Exception(
                    f" doc:{doc.doc_name} status is {doc.status}, can not sync"
                )
            chunk_parameters = sync_request.chunk_parameters
            if chunk_parameters.chunk_strategy != ChunkStrategy.CHUNK_BY_SIZE.name:
                space_context = self.get_space_context(space_id)
                chunk_parameters.chunk_size = (
                    CFG.KNOWLEDGE_CHUNK_SIZE
                    if space_context is None
                    else int(space_context["embedding"]["chunk_size"])
                )
                chunk_parameters.chunk_overlap = (
                    CFG.KNOWLEDGE_CHUNK_OVERLAP
                    if space_context is None
                    else int(space_context["embedding"]["chunk_overlap"])
                )
            await self._sync_knowledge_document(space_id, doc, chunk_parameters)
            doc_ids.append(doc.id)
        return doc_ids

    def get(self, request: QUERY_SPEC) -> Optional[SpaceServeResponse]:
        """Get a Flow entity

        Args:
            request (SpaceServeRequest): The request

        Returns:
            SpaceServeResponse: The response
        """
        # TODO: implement your own logic here
        # Build the query request from the request
        query_request = request
        return self._dao.get_one(query_request)

    def get_document(self, request: QUERY_SPEC) -> Optional[SpaceServeResponse]:
        """Get a Flow entity

        Args:
            request (SpaceServeRequest): The request

        Returns:
            SpaceServeResponse: The response
        """
        # TODO: implement your own logic here
        # Build the query request from the request
        query_request = request
        return self._document_dao.get_one(query_request)

    def delete(self, space_id: str) -> Optional[SpaceServeResponse]:
        """Delete a Flow entity

        Args:
            uid (str): The uid

        Returns:
            SpaceServeResponse: The data after deletion
        """

        # TODO: implement your own logic here
        # Build the query request from the request
        query_request = {"id": space_id}
        space = self.get(query_request)
        if space is None:
            raise HTTPException(status_code=400, detail=f"Space {space_id} not found")
        config = VectorStoreConfig(
            name=space.name, llm_client=self.llm_client, model_name=None
        )
        vector_store_connector = VectorStoreConnector(
            vector_store_type=space.vector_type, vector_store_config=config
        )
        # delete vectors
        vector_store_connector.delete_vector_name(space.name)
        document_query = KnowledgeDocumentEntity(space=space.name)
        # delete chunks
        documents = self._document_dao.get_documents(document_query)
        for document in documents:
            self._chunk_dao.raw_delete(document.id)
        # delete documents
        self._document_dao.raw_delete(document_query)
        # delete space
        self._dao.delete(query_request)
        return space

    def update_document(self, request: DocumentServeRequest):
        """update knowledge document

        Args:
            - space_id: space id
            - request: KnowledgeDocumentRequest
        """
        if not request.id:
            raise Exception("doc_id is required")
        document = self._document_dao.get_one({"id": request.id})
        entity = self._document_dao.from_response(document)
        if request.doc_name:
            entity.doc_name = request.doc_name
            update_chunk = self._chunk_dao.get_one({"document_id": entity.id})
            if update_chunk:
                update_chunk.doc_name = request.doc_name
                self._chunk_dao.update_chunk(update_chunk)
        if len(request.questions) == 0:
            request.questions = ""
        questions = [
            remove_trailing_punctuation(question) for question in request.questions
        ]
        entity.questions = json.dumps(questions, ensure_ascii=False)
        self._document_dao.update_knowledge_document(entity)

    def delete_document(self, document_id: str) -> Optional[DocumentServeResponse]:
        """Delete a Flow entity

        Args:
            uid (str): The uid

        Returns:
            SpaceServeResponse: The data after deletion
        """

        query_request = {"id": document_id}
        docuemnt = self._document_dao.get_one(query_request)
        if docuemnt is None:
            raise Exception(f"there are no or more than one document  {document_id}")

        # get space by name
        spaces = self._dao.get_knowledge_space(
            KnowledgeSpaceEntity(name=docuemnt.space)
        )
        if len(spaces) != 1:
            raise Exception(f"invalid space name: {docuemnt.space}")
        space = spaces[0]

        vector_ids = docuemnt.vector_ids
        if vector_ids is not None:
            config = VectorStoreConfig(
                name=space.name, llm_client=self.llm_client, model_name=None
            )
            vector_store_connector = VectorStoreConnector(
                vector_store_type=space.vector_type, vector_store_config=config
            )
            # delete vector by ids
            vector_store_connector.delete_by_ids(vector_ids)
        # delete chunks
        self._chunk_dao.raw_delete(docuemnt.id)
        # delete document
        self._document_dao.raw_delete(docuemnt)
        return docuemnt

    def get_list(self, request: SpaceServeRequest) -> List[SpaceServeResponse]:
        """Get a list of Flow entities

        Args:
            request (SpaceServeRequest): The request

        Returns:
            List[SpaceServeResponse]: The response
        """
        # TODO: implement your own logic here
        # Build the query request from the request
        query_request = request
        return self.dao.get_list(query_request)

    def get_list_by_page(
        self, request: QUERY_SPEC, page: int, page_size: int
    ) -> PaginationResult[SpaceServeResponse]:
        """Get a list of Flow entities by page

        Args:
            request (SpaceServeRequest): The request
            page (int): The page number
            page_size (int): The page size

        Returns:
            List[SpaceServeResponse]: The response
        """
        return self.dao.get_list_page(request, page, page_size)

    def get_document_list(
        self, request: QUERY_SPEC, page: int, page_size: int
    ) -> PaginationResult[DocumentServeResponse]:
        """Get a list of Flow entities by page

        Args:
            request (SpaceServeRequest): The request
            page (int): The page number
            page_size (int): The page size

        Returns:
            List[SpaceServeResponse]: The response
        """
        return self._document_dao.get_list_page(request, page, page_size)

    def get_chunk_list_page(self, request: QUERY_SPEC, page: int, page_size: int):
        """get document chunks with page
        Args:
            - request: QUERY_SPEC
        """
        return self._chunk_dao.get_list_page(request, page, page_size)

    def get_chunk_list(self, request: QUERY_SPEC):
        """get document chunks
        Args:
            - request: QUERY_SPEC
        """
        return self._chunk_dao.get_list(request)

    def update_chunk(self, request: ChunkServeRequest):
        """update knowledge document chunk"""
        if not request.id:
            raise Exception("chunk_id is required")
        chunk = self._chunk_dao.get_one({"id": request.id})
        entity = self._chunk_dao.from_response(chunk)
        if request.content:
            entity.content = request.content
        if request.questions:
            questions = [
                remove_trailing_punctuation(question) for question in request.questions
            ]
            entity.questions = json.dumps(questions, ensure_ascii=False)
        self._chunk_dao.update_chunk(entity)

    async def _batch_document_sync(
        self, space_id, sync_requests: List[KnowledgeSyncRequest]
    ) -> List[int]:
        """batch sync knowledge document chunk into vector store
        Args:
            - space: Knowledge Space Name
            - sync_requests: List[KnowledgeSyncRequest]
        Returns:
            - List[int]: document ids
        """
        doc_ids = []
        for sync_request in sync_requests:
            docs = self._document_dao.documents_by_ids([sync_request.doc_id])
            if len(docs) == 0:
                raise Exception(
                    f"there are document called, doc_id: {sync_request.doc_id}"
                )
            doc = docs[0]
            if (
                doc.status == SyncStatus.RUNNING.name
                or doc.status == SyncStatus.FINISHED.name
            ):
                raise Exception(
                    f" doc:{doc.doc_name} status is {doc.status}, can not sync"
                )
            chunk_parameters = sync_request.chunk_parameters
            if chunk_parameters.chunk_strategy != ChunkStrategy.CHUNK_BY_SIZE.name:
                space_context = self.get_space_context(space_id)
                chunk_parameters.chunk_size = (
                    CFG.KNOWLEDGE_CHUNK_SIZE
                    if space_context is None
                    else int(space_context["embedding"]["chunk_size"])
                )
                chunk_parameters.chunk_overlap = (
                    CFG.KNOWLEDGE_CHUNK_OVERLAP
                    if space_context is None
                    else int(space_context["embedding"]["chunk_overlap"])
                )
            await self._sync_knowledge_document(space_id, doc, chunk_parameters)
            doc_ids.append(doc.id)
        return doc_ids

    async def _sync_knowledge_document(
        self,
        space_id,
        doc: KnowledgeDocumentEntity,
        chunk_parameters: ChunkParameters,
    ) -> None:
        """sync knowledge document chunk into vector store"""
        embedding_factory = CFG.SYSTEM_APP.get_component(
            "embedding_factory", EmbeddingFactory
        )
        embedding_fn = embedding_factory.create(
            model_name=EMBEDDING_MODEL_CONFIG[CFG.EMBEDDING_MODEL]
        )
        from dbgpt.storage.vector_store.base import VectorStoreConfig

        space = self.get({"id": space_id})
        config = VectorStoreConfig(
            name=space.name,
            embedding_fn=embedding_fn,
            max_chunks_once_load=CFG.KNOWLEDGE_MAX_CHUNKS_ONCE_LOAD,
            llm_client=self.llm_client,
            model_name=None,
        )
        vector_store_connector = VectorStoreConnector(
            vector_store_type=space.vector_type, vector_store_config=config
        )
        knowledge = None
        if not space.domain_type or (
            space.domain_type.lower() == BusinessFieldType.NORMAL.value.lower()
        ):
            knowledge = KnowledgeFactory.create(
                datasource=doc.content,
                knowledge_type=KnowledgeType.get_by_value(doc.doc_type),
            )
        doc.status = SyncStatus.RUNNING.name

        doc.gmt_modified = datetime.now()
        self._document_dao.update_knowledge_document(doc)
        asyncio.create_task(
            self.async_doc_embedding(
                knowledge, chunk_parameters, vector_store_connector, doc, space
            )
        )
        logger.info(f"begin save document chunks, doc:{doc.doc_name}")

    @trace("async_doc_embedding")
    async def async_doc_embedding(
        self, knowledge, chunk_parameters, vector_store_connector, doc, space
    ):
        """async document embedding into vector db
        Args:
            - knowledge: Knowledge
            - chunk_parameters: ChunkParameters
            - vector_store_connector: vector_store_connector
            - doc: doc
        """

        logger.info(f"async doc persist sync, doc:{doc.doc_name}")
        try:
            with root_tracer.start_span(
                "app.knowledge.assembler.persist",
                metadata={"doc": doc.doc_name},
            ):
                from dbgpt.core.awel import BaseOperator
                from dbgpt.serve.flow.service.service import Service as FlowService

                dags = self.dag_manager.get_dags_by_tag(
                    TAG_KEY_KNOWLEDGE_FACTORY_DOMAIN_TYPE, space.domain_type
                )
                if dags and dags[0].leaf_nodes:
                    end_task = cast(BaseOperator, dags[0].leaf_nodes[0])
                    logger.info(
                        f"Found dag by tag key: {TAG_KEY_KNOWLEDGE_FACTORY_DOMAIN_TYPE}"
                        f" and value: {space.domain_type}, dag: {dags[0]}"
                    )
                    db_name, chunk_docs = await end_task.call(
                        {"file_path": doc.content, "space": doc.space}
                    )
                    doc.chunk_size = len(chunk_docs)
                    vector_ids = [chunk.chunk_id for chunk in chunk_docs]
                else:
                    assembler = await EmbeddingAssembler.aload_from_knowledge(
                        knowledge=knowledge,
                        index_store=vector_store_connector.index_client,
                        chunk_parameters=chunk_parameters,
                    )

                    chunk_docs = assembler.get_chunks()
                    doc.chunk_size = len(chunk_docs)
                    vector_ids = await assembler.apersist()
            doc.status = SyncStatus.FINISHED.name
            doc.result = "document persist into index store success"
            if vector_ids is not None:
                doc.vector_ids = ",".join(vector_ids)
            logger.info(f"async document persist index store success:{doc.doc_name}")
            # save chunk details
            chunk_entities = [
                DocumentChunkEntity(
                    doc_name=doc.doc_name,
                    doc_type=doc.doc_type,
                    document_id=doc.id,
                    content=chunk_doc.content,
                    meta_info=str(chunk_doc.metadata),
                    gmt_created=datetime.now(),
                    gmt_modified=datetime.now(),
                )
                for chunk_doc in chunk_docs
            ]
            self._chunk_dao.create_documents_chunks(chunk_entities)
        except Exception as e:
            doc.status = SyncStatus.FAILED.name
            doc.result = "document embedding failed" + str(e)
            logger.error(f"document embedding, failed:{doc.doc_name}, {str(e)}")
        return self._document_dao.update_knowledge_document(doc)

    def get_space_context(self, space_id):
        """get space contect
        Args:
           - space_name: space name
        """
        space = self.get({"id": space_id})
        if space is None:
            raise Exception(
                f"have not found {space_id} space or found more than one space called {space_id}"
            )
        if space.context is not None:
            return json.loads(space.context)
        return None
