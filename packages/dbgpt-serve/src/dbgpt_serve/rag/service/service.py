import asyncio
import json
import logging
import os
from datetime import datetime
from enum import Enum
from typing import List, Optional, cast

from fastapi import HTTPException

from dbgpt.component import ComponentType, SystemApp
from dbgpt.configs import TAG_KEY_KNOWLEDGE_FACTORY_DOMAIN_TYPE
from dbgpt.configs.model_config import (
    KNOWLEDGE_CACHE_ROOT_PATH,
)
from dbgpt.core import Chunk, LLMClient
from dbgpt.core.interface.file import _SCHEMA, FileStorageClient
from dbgpt.model import DefaultLLMClient
from dbgpt.model.cluster import WorkerManagerFactory
from dbgpt.rag.embedding.embedding_factory import RerankEmbeddingFactory
from dbgpt.rag.knowledge import ChunkStrategy, KnowledgeType
from dbgpt.rag.retriever.rerank import RerankEmbeddingsRanker
from dbgpt.storage.metadata import BaseDao
from dbgpt.storage.metadata._base_dao import QUERY_SPEC
from dbgpt.util.pagination_utils import PaginationResult
from dbgpt.util.string_utils import remove_trailing_punctuation
from dbgpt.util.tracer import root_tracer, trace
from dbgpt_app.knowledge.request.request import BusinessFieldType
from dbgpt_ext.rag.assembler import EmbeddingAssembler
from dbgpt_ext.rag.chunk_manager import ChunkParameters
from dbgpt_ext.rag.knowledge import KnowledgeFactory
from dbgpt_serve.core import BaseService, blocking_func_to_async

from ..api.schemas import (
    ChunkServeRequest,
    DocumentServeRequest,
    DocumentServeResponse,
    KnowledgeRetrieveRequest,
    KnowledgeSyncRequest,
    SpaceServeRequest,
    SpaceServeResponse,
)
from ..config import SERVE_SERVICE_COMPONENT_NAME, ServeConfig
from ..models.chunk_db import DocumentChunkDao, DocumentChunkEntity
from ..models.document_db import (
    KnowledgeDocumentDao,
    KnowledgeDocumentEntity,
)
from ..models.models import KnowledgeSpaceDao, KnowledgeSpaceEntity
from ..retriever.knowledge_space import KnowledgeSpaceRetriever
from ..storage_manager import StorageManager

logger = logging.getLogger(__name__)


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
        config: ServeConfig,
        dao: Optional[KnowledgeSpaceDao] = None,
        document_dao: Optional[KnowledgeDocumentDao] = None,
        chunk_dao: Optional[DocumentChunkDao] = None,
    ):
        self._system_app = system_app
        self._dao: KnowledgeSpaceDao = dao
        self._document_dao: KnowledgeDocumentDao = document_dao
        self._chunk_dao: DocumentChunkDao = chunk_dao
        self._serve_config = config

        super().__init__(system_app)

    def init_app(self, system_app: SystemApp) -> None:
        """Initialize the service

        Args:
            system_app (SystemApp): The system app
        """
        super().init_app(system_app)
        self._dao = self._dao or KnowledgeSpaceDao()
        self._document_dao = self._document_dao or KnowledgeDocumentDao()
        self._chunk_dao = self._chunk_dao or DocumentChunkDao()
        self._system_app = system_app

    @property
    def storage_manager(self):
        return StorageManager.get_instance(self._system_app)

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

    def get_fs(self) -> FileStorageClient:
        """Get the FileStorageClient instance"""
        return FileStorageClient.get_instance(self.system_app)

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

    def create_document(self, request: DocumentServeRequest) -> str:
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
            safe_filename = os.path.basename(doc_file.filename)
            custom_metadata = {
                "space_name": space.name,
                "doc_name": doc_file.filename,
                "doc_type": request.doc_type,
            }
            bucket = "dbgpt_knowledge_file"
            file_uri = self.get_fs().save_file(
                bucket,
                safe_filename,
                doc_file.file,
                custom_metadata=custom_metadata,
            )
            request.content = file_uri
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
        return str(doc_id)

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
                    self._serve_config.chunk_size
                    if space_context is None
                    else int(space_context["embedding"]["chunk_size"])
                )
                chunk_parameters.chunk_overlap = (
                    self._serve_config.chunk_overlap
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
        vector_store_connector = self.create_vector_store(space.name)
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
                self._chunk_dao.update({"id": update_chunk.id}, update_chunk)
        if not request.questions:
            entity.questions = ""
        else:
            questions = [
                remove_trailing_punctuation(question) for question in request.questions
            ]
            entity.questions = json.dumps(questions, ensure_ascii=False)
        self._document_dao.update(
            {"id": entity.id}, self._document_dao.to_request(entity)
        )

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
            vector_store_connector = self.create_vector_store(space.name)
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
        self, request: QUERY_SPEC
    ) -> PaginationResult[DocumentServeResponse]:
        """Get a list of Flow entities by page

        Args:
            request (SpaceServeRequest): The request
            page (int): The page number
            page_size (int): The page size

        Returns:
            List[SpaceServeResponse]: The response
        """
        return self._document_dao.get_list(request)

    def get_document_list_page(
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
                    self._serve_config.chunk_size
                    if space_context is None
                    else int(space_context["embedding"]["chunk_size"])
                )
                chunk_parameters.chunk_overlap = (
                    self._serve_config.chunk_overlap
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
        space = self.get({"id": space_id})
        storage_connector = self.storage_manager.get_storage_connector(
            space.name, space.vector_type
        )
        knowledge_content = doc.content
        if (
            doc.doc_type == KnowledgeType.DOCUMENT.value
            and knowledge_content.startswith(_SCHEMA)
        ):
            logger.info(
                f"Download file from file storage, doc: {doc.doc_name}, file url: "
                f"{doc.content}"
            )
            local_file_path, file_meta = await blocking_func_to_async(
                self.system_app,
                self.get_fs().download_file,
                knowledge_content,
                dest_dir=KNOWLEDGE_CACHE_ROOT_PATH,
            )
            logger.info(f"Downloaded file to {local_file_path}")
            knowledge_content = local_file_path
        knowledge = None
        if not space.domain_type or (
            space.domain_type.lower() == BusinessFieldType.NORMAL.value.lower()
        ):
            knowledge = KnowledgeFactory.create(
                datasource=knowledge_content,
                knowledge_type=KnowledgeType.get_by_value(doc.doc_type),
            )
        doc.status = SyncStatus.RUNNING.name

        doc.gmt_modified = datetime.now()
        await blocking_func_to_async(
            self.system_app, self._document_dao.update_knowledge_document, doc
        )
        asyncio.create_task(
            self.async_doc_process(
                knowledge,
                chunk_parameters,
                storage_connector,
                doc,
                space,
                knowledge_content,
            )
        )
        logger.info(f"begin save document chunks, doc:{doc.doc_name}")

    @trace("async_doc_process")
    async def async_doc_process(
        self,
        knowledge,
        chunk_parameters,
        storage_connector,
        doc,
        space,
        knowledge_content: str,
    ):
        """async document process into storage
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
                        {"file_path": knowledge_content, "space": doc.space}
                    )
                    doc.chunk_size = len(chunk_docs)
                    vector_ids = [chunk.chunk_id for chunk in chunk_docs]
                else:
                    max_chunks_once_load = self.config.max_chunks_once_load
                    max_threads = self.config.max_threads
                    assembler = await EmbeddingAssembler.aload_from_knowledge(
                        knowledge=knowledge,
                        index_store=storage_connector,
                        chunk_parameters=chunk_parameters,
                    )

                    chunk_docs = assembler.get_chunks()
                    doc.chunk_size = len(chunk_docs)
                    # this will be the start point where file_id is added
                    vector_ids = await assembler.apersist(
                        max_chunks_once_load=max_chunks_once_load,
                        max_threads=max_threads,
                        file_id=doc.id,
                    )
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
                f"have not found {space_id} space or found more than one space called "
                f"{space_id}"
            )
        if space.context is not None:
            return json.loads(space.context)
        return None

    async def retrieve(
        self, request: KnowledgeRetrieveRequest, space: SpaceServeResponse
    ) -> List[Chunk]:
        """Retrieve the service."""
        reranker: Optional[RerankEmbeddingsRanker] = None
        top_k = request.top_k
        if self._serve_config.rerank_model:
            reranker_top_k = self._serve_config.rerank_top_k
            rerank_embeddings = RerankEmbeddingFactory.get_instance(
                self._system_app
            ).create()
            reranker = RerankEmbeddingsRanker(rerank_embeddings, topk=reranker_top_k)
            if top_k < reranker_top_k or self._top_k < 20:
                # We use reranker, so if the top_k is less than 20,
                # we need to set it to 20
                top_k = max(reranker_top_k, 20)

        space_retriever = KnowledgeSpaceRetriever(
            space_id=space.id,
            embedding_model=self._serve_config.embedding_model,
            top_k=top_k,
            rerank=reranker,
            system_app=self._system_app,
        )
        return await space_retriever.aretrieve_with_scores(
            request.query, request.score_threshold
        )
