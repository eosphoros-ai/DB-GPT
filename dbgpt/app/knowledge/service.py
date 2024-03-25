import json
import logging
from datetime import datetime
from typing import List

from dbgpt._private.config import Config
from dbgpt.app.knowledge.chunk_db import DocumentChunkDao, DocumentChunkEntity
from dbgpt.app.knowledge.document_db import (
    KnowledgeDocumentDao,
    KnowledgeDocumentEntity,
)
from dbgpt.app.knowledge.request.request import (
    ChunkQueryRequest,
    DocumentQueryRequest,
    DocumentSummaryRequest,
    DocumentSyncRequest,
    KnowledgeDocumentRequest,
    KnowledgeSpaceRequest,
    SpaceArgumentRequest,
)
from dbgpt.app.knowledge.request.response import (
    ChunkQueryResponse,
    DocumentQueryResponse,
    SpaceQueryResponse,
)
from dbgpt.component import ComponentType
from dbgpt.configs.model_config import EMBEDDING_MODEL_CONFIG
from dbgpt.core import Chunk
from dbgpt.model import DefaultLLMClient
from dbgpt.rag.assembler.embedding import EmbeddingAssembler
from dbgpt.rag.assembler.summary import SummaryAssembler
from dbgpt.rag.chunk_manager import ChunkParameters
from dbgpt.rag.embedding.embedding_factory import EmbeddingFactory
from dbgpt.rag.knowledge.base import ChunkStrategy, KnowledgeType
from dbgpt.rag.knowledge.factory import KnowledgeFactory
from dbgpt.rag.text_splitter.text_splitter import (
    RecursiveCharacterTextSplitter,
    SpacyTextSplitter,
)
from dbgpt.serve.rag.api.schemas import KnowledgeSyncRequest
from dbgpt.serve.rag.models.models import KnowledgeSpaceDao, KnowledgeSpaceEntity
from dbgpt.serve.rag.service.service import Service, SyncStatus
from dbgpt.storage.vector_store.base import VectorStoreConfig
from dbgpt.storage.vector_store.connector import VectorStoreConnector
from dbgpt.util.executor_utils import ExecutorFactory, blocking_func_to_async
from dbgpt.util.tracer import root_tracer, trace

knowledge_space_dao = KnowledgeSpaceDao()
knowledge_document_dao = KnowledgeDocumentDao()
document_chunk_dao = DocumentChunkDao()

logger = logging.getLogger(__name__)
CFG = Config()


# default summary max iteration call with llm.
DEFAULT_SUMMARY_MAX_ITERATION = 5
# default summary concurrency call with llm.
DEFAULT_SUMMARY_CONCURRENCY_LIMIT = 3


class KnowledgeService:
    """KnowledgeService
    Knowledge Management Service:
        -knowledge_space management
        -knowledge_document management
        -embedding management
    """

    def __init__(self):
        pass

    def create_knowledge_space(self, request: KnowledgeSpaceRequest):
        """create knowledge space
        Args:
           - request: KnowledgeSpaceRequest
        """
        query = KnowledgeSpaceEntity(
            name=request.name,
        )
        spaces = knowledge_space_dao.get_knowledge_space(query)
        if len(spaces) > 0:
            raise Exception(f"space name:{request.name} have already named")
        space_id = knowledge_space_dao.create_knowledge_space(request)
        return space_id

    def create_knowledge_document(self, space, request: KnowledgeDocumentRequest):
        """create knowledge document
        Args:
           - request: KnowledgeDocumentRequest
        """
        query = KnowledgeDocumentEntity(doc_name=request.doc_name, space=space)
        documents = knowledge_document_dao.get_knowledge_documents(query)
        if len(documents) > 0:
            raise Exception(f"document name:{request.doc_name} have already named")
        document = KnowledgeDocumentEntity(
            doc_name=request.doc_name,
            doc_type=request.doc_type,
            space=space,
            chunk_size=0,
            status=SyncStatus.TODO.name,
            last_sync=datetime.now(),
            content=request.content,
            result="",
        )
        doc_id = knowledge_document_dao.create_knowledge_document(document)
        if doc_id is None:
            raise Exception(f"create document failed, {request.doc_name}")
        return doc_id

    def get_knowledge_space(self, request: KnowledgeSpaceRequest):
        """get knowledge space
        Args:
           - request: KnowledgeSpaceRequest
        """
        query = KnowledgeSpaceEntity(
            name=request.name, vector_type=request.vector_type, owner=request.owner
        )
        spaces = knowledge_space_dao.get_knowledge_space(query)
        space_names = [space.name for space in spaces]
        docs_count = knowledge_document_dao.get_knowledge_documents_count_bulk(
            space_names
        )
        responses = []
        for space in spaces:
            res = SpaceQueryResponse()
            res.id = space.id
            res.name = space.name
            res.vector_type = space.vector_type
            res.desc = space.desc
            res.owner = space.owner
            res.gmt_created = space.gmt_created
            res.gmt_modified = space.gmt_modified
            res.context = space.context
            res.docs = docs_count.get(space.name, 0)
            responses.append(res)
        return responses

    def arguments(self, space_name):
        """show knowledge space arguments
        Args:
            - space_name: Knowledge Space Name
        """
        query = KnowledgeSpaceEntity(name=space_name)
        spaces = knowledge_space_dao.get_knowledge_space(query)
        if len(spaces) != 1:
            raise Exception(f"there are no or more than one space called {space_name}")
        space = spaces[0]
        if space.context is None:
            context = self._build_default_context()
        else:
            context = space.context
        return json.loads(context)

    def argument_save(self, space_name, argument_request: SpaceArgumentRequest):
        """save argument
        Args:
            - space_name: Knowledge Space Name
            - argument_request: SpaceArgumentRequest
        """
        query = KnowledgeSpaceEntity(name=space_name)
        spaces = knowledge_space_dao.get_knowledge_space(query)
        if len(spaces) != 1:
            raise Exception(f"there are no or more than one space called {space_name}")
        space = spaces[0]
        space.context = argument_request.argument
        return knowledge_space_dao.update_knowledge_space(space)

    def get_knowledge_documents(self, space, request: DocumentQueryRequest):
        """get knowledge documents
        Args:
            - space: Knowledge Space Name
            - request: DocumentQueryRequest
        Returns:
            - res DocumentQueryResponse
        """
        res = DocumentQueryResponse()
        if request.doc_ids and len(request.doc_ids) > 0:
            res.data = knowledge_document_dao.documents_by_ids(request.doc_ids)
        else:
            query = KnowledgeDocumentEntity(
                doc_name=request.doc_name,
                doc_type=request.doc_type,
                space=space,
                status=request.status,
            )
            res.data = knowledge_document_dao.get_knowledge_documents(
                query, page=request.page, page_size=request.page_size
            )
            res.total = knowledge_document_dao.get_knowledge_documents_count(query)
            res.page = request.page
        return res

    def batch_document_sync(
        self,
        space_name,
        sync_requests: List[KnowledgeSyncRequest],
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
            docs = knowledge_document_dao.documents_by_ids([sync_request.doc_id])
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
                space_context = self.get_space_context(space_name)
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
            self._sync_knowledge_document(space_name, doc, chunk_parameters)
            doc_ids.append(doc.id)
        return doc_ids

    def sync_knowledge_document(self, space_name, sync_request: DocumentSyncRequest):
        """sync knowledge document chunk into vector store
        Args:
            - space: Knowledge Space Name
            - sync_request: DocumentSyncRequest
        """
        from dbgpt.rag.text_splitter.pre_text_splitter import PreTextSplitter

        doc_ids = sync_request.doc_ids
        self.model_name = sync_request.model_name or CFG.LLM_MODEL
        for doc_id in doc_ids:
            query = KnowledgeDocumentEntity(
                id=doc_id,
                space=space_name,
            )
            doc = knowledge_document_dao.get_knowledge_documents(query)[0]
            if (
                doc.status == SyncStatus.RUNNING.name
                or doc.status == SyncStatus.FINISHED.name
            ):
                raise Exception(
                    f" doc:{doc.doc_name} status is {doc.status}, can not sync"
                )

            space_context = self.get_space_context(space_name)
            chunk_size = (
                CFG.KNOWLEDGE_CHUNK_SIZE
                if space_context is None
                else int(space_context["embedding"]["chunk_size"])
            )
            chunk_overlap = (
                CFG.KNOWLEDGE_CHUNK_OVERLAP
                if space_context is None
                else int(space_context["embedding"]["chunk_overlap"])
            )
            if sync_request.chunk_size:
                chunk_size = sync_request.chunk_size
            if sync_request.chunk_overlap:
                chunk_overlap = sync_request.chunk_overlap
            separators = sync_request.separators or None
            from dbgpt.rag.chunk_manager import ChunkParameters

            chunk_parameters = ChunkParameters(
                chunk_size=chunk_size, chunk_overlap=chunk_overlap
            )
            if CFG.LANGUAGE == "en":
                text_splitter = RecursiveCharacterTextSplitter(
                    separators=separators,
                    chunk_size=chunk_size,
                    chunk_overlap=chunk_overlap,
                    length_function=len,
                )
            else:
                if separators and len(separators) > 1:
                    raise ValueError(
                        "SpacyTextSplitter do not support multipsle separators"
                    )
                try:
                    separator = "\n\n" if not separators else separators[0]
                    text_splitter = SpacyTextSplitter(
                        separator=separator,
                        pipeline="zh_core_web_sm",
                        chunk_size=chunk_size,
                        chunk_overlap=chunk_overlap,
                    )
                except Exception:
                    text_splitter = RecursiveCharacterTextSplitter(
                        separators=separators,
                        chunk_size=chunk_size,
                        chunk_overlap=chunk_overlap,
                    )
            if sync_request.pre_separator:
                logger.info(f"Use preseparator, {sync_request.pre_separator}")
                text_splitter = PreTextSplitter(
                    pre_separator=sync_request.pre_separator,
                    text_splitter_impl=text_splitter,
                )
                chunk_parameters.text_splitter = text_splitter
            self._sync_knowledge_document(space_name, doc, chunk_parameters)
        return doc.id

    def _sync_knowledge_document(
        self,
        space_name,
        doc: KnowledgeDocumentEntity,
        chunk_parameters: ChunkParameters,
    ) -> List[Chunk]:
        """sync knowledge document chunk into vector store"""
        embedding_factory = CFG.SYSTEM_APP.get_component(
            "embedding_factory", EmbeddingFactory
        )
        embedding_fn = embedding_factory.create(
            model_name=EMBEDDING_MODEL_CONFIG[CFG.EMBEDDING_MODEL]
        )
        from dbgpt.storage.vector_store.base import VectorStoreConfig

        config = VectorStoreConfig(
            name=space_name,
            embedding_fn=embedding_fn,
            max_chunks_once_load=CFG.KNOWLEDGE_MAX_CHUNKS_ONCE_LOAD,
        )
        vector_store_connector = VectorStoreConnector(
            vector_store_type=CFG.VECTOR_STORE_TYPE,
            vector_store_config=config,
        )
        knowledge = KnowledgeFactory.create(
            datasource=doc.content,
            knowledge_type=KnowledgeType.get_by_value(doc.doc_type),
        )
        assembler = EmbeddingAssembler.load_from_knowledge(
            knowledge=knowledge,
            chunk_parameters=chunk_parameters,
            embeddings=embedding_fn,
            vector_store_connector=vector_store_connector,
        )
        chunk_docs = assembler.get_chunks()
        doc.status = SyncStatus.RUNNING.name
        doc.chunk_size = len(chunk_docs)
        doc.gmt_modified = datetime.now()
        knowledge_document_dao.update_knowledge_document(doc)
        executor = CFG.SYSTEM_APP.get_component(
            ComponentType.EXECUTOR_DEFAULT, ExecutorFactory
        ).create()
        executor.submit(self.async_doc_embedding, assembler, chunk_docs, doc)
        logger.info(f"begin save document chunks, doc:{doc.doc_name}")
        return chunk_docs

    async def document_summary(self, request: DocumentSummaryRequest):
        """get document summary
        Args:
            - request: DocumentSummaryRequest
        """
        doc_query = KnowledgeDocumentEntity(id=request.doc_id)
        documents = knowledge_document_dao.get_documents(doc_query)
        if len(documents) != 1:
            raise Exception(f"can not found document for {request.doc_id}")
        document = documents[0]
        from dbgpt.model.cluster import WorkerManagerFactory

        worker_manager = CFG.SYSTEM_APP.get_component(
            ComponentType.WORKER_MANAGER_FACTORY, WorkerManagerFactory
        ).create()
        chunk_parameters = ChunkParameters(
            chunk_strategy="CHUNK_BY_SIZE",
            chunk_size=CFG.KNOWLEDGE_CHUNK_SIZE,
            chunk_overlap=CFG.KNOWLEDGE_CHUNK_OVERLAP,
        )
        chunk_entities = document_chunk_dao.get_document_chunks(
            DocumentChunkEntity(document_id=document.id)
        )
        if (
            document.status not in [SyncStatus.RUNNING.name]
            and len(chunk_entities) == 0
        ):
            self._sync_knowledge_document(
                space_name=document.space,
                doc=document,
                chunk_parameters=chunk_parameters,
            )
        knowledge = KnowledgeFactory.create(
            datasource=document.content,
            knowledge_type=KnowledgeType.get_by_value(document.doc_type),
        )
        assembler = SummaryAssembler(
            knowledge=knowledge,
            model_name=request.model_name,
            llm_client=DefaultLLMClient(
                worker_manager=worker_manager, auto_convert_message=True
            ),
            language=CFG.LANGUAGE,
            chunk_parameters=chunk_parameters,
        )
        summary = await assembler.generate_summary()

        if len(assembler.get_chunks()) == 0:
            raise Exception(f"can not found chunks for {request.doc_id}")

        return await self._llm_extract_summary(
            summary, request.conv_uid, request.model_name
        )

    def update_knowledge_space(
        self, space_id: int, space_request: KnowledgeSpaceRequest
    ):
        """update knowledge space
        Args:
            - space_id: space id
            - space_request: KnowledgeSpaceRequest
        """
        entity = KnowledgeSpaceEntity(
            id=space_id,
            name=space_request.name,
            vector_type=space_request.vector_type,
            desc=space_request.desc,
            owner=space_request.owner,
        )

        knowledge_space_dao.update_knowledge_space(entity)

    def delete_space(self, space_name: str):
        """delete knowledge space
        Args:
            - space_name: knowledge space name
        """
        query = KnowledgeSpaceEntity(name=space_name)
        spaces = knowledge_space_dao.get_knowledge_space(query)
        if len(spaces) == 0:
            raise Exception(f"delete error, no space name:{space_name} in database")
        space = spaces[0]
        config = VectorStoreConfig(name=space.name)
        vector_store_connector = VectorStoreConnector(
            vector_store_type=CFG.VECTOR_STORE_TYPE,
            vector_store_config=config,
        )
        # delete vectors
        vector_store_connector.delete_vector_name(space.name)
        document_query = KnowledgeDocumentEntity(space=space.name)
        # delete chunks
        documents = knowledge_document_dao.get_documents(document_query)
        for document in documents:
            document_chunk_dao.raw_delete(document.id)
        # delete documents
        knowledge_document_dao.raw_delete(document_query)
        # delete space
        return knowledge_space_dao.delete_knowledge_space(space)

    def delete_document(self, space_name: str, doc_name: str):
        """delete document
        Args:
            - space_name: knowledge space name
            - doc_name: doocument name
        """
        document_query = KnowledgeDocumentEntity(doc_name=doc_name, space=space_name)
        documents = knowledge_document_dao.get_documents(document_query)
        if len(documents) != 1:
            raise Exception(f"there are no or more than one document called {doc_name}")
        vector_ids = documents[0].vector_ids
        if vector_ids is not None:
            config = VectorStoreConfig(name=space_name)
            vector_store_connector = VectorStoreConnector(
                vector_store_type=CFG.VECTOR_STORE_TYPE,
                vector_store_config=config,
            )
            # delete vector by ids
            vector_store_connector.delete_by_ids(vector_ids)
        # delete chunks
        document_chunk_dao.raw_delete(documents[0].id)
        # delete document
        return knowledge_document_dao.raw_delete(document_query)

    def get_document_chunks(self, request: ChunkQueryRequest):
        """get document chunks
        Args:
            - request: ChunkQueryRequest
        """
        query = DocumentChunkEntity(
            id=request.id,
            document_id=request.document_id,
            doc_name=request.doc_name,
            doc_type=request.doc_type,
        )
        document_query = KnowledgeDocumentEntity(id=request.document_id)
        documents = knowledge_document_dao.get_documents(document_query)

        res = ChunkQueryResponse()
        res.data = document_chunk_dao.get_document_chunks(
            query, page=request.page, page_size=request.page_size
        )
        res.summary = documents[0].summary
        res.total = document_chunk_dao.get_document_chunks_count(query)
        res.page = request.page
        return res

    @trace("async_doc_embedding")
    def async_doc_embedding(self, assembler, chunk_docs, doc):
        """async document embedding into vector db
        Args:
            - client: EmbeddingEngine Client
            - chunk_docs: List[Document]
            - doc: KnowledgeDocumentEntity
        """

        logger.info(
            f"async doc embedding sync, doc:{doc.doc_name}, chunks length is {len(chunk_docs)}, begin embedding to vector store-{CFG.VECTOR_STORE_TYPE}"
        )
        try:
            with root_tracer.start_span(
                "app.knowledge.assembler.persist",
                metadata={"doc": doc.doc_name, "chunks": len(chunk_docs)},
            ):
                vector_ids = assembler.persist()
            doc.status = SyncStatus.FINISHED.name
            doc.result = "document embedding success"
            if vector_ids is not None:
                doc.vector_ids = ",".join(vector_ids)
            logger.info(f"async document embedding, success:{doc.doc_name}")
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
            document_chunk_dao.create_documents_chunks(chunk_entities)
        except Exception as e:
            doc.status = SyncStatus.FAILED.name
            doc.result = "document embedding failed" + str(e)
            logger.error(f"document embedding, failed:{doc.doc_name}, {str(e)}")
        return knowledge_document_dao.update_knowledge_document(doc)

    def _build_default_context(self):
        from dbgpt.app.scene.chat_knowledge.v1.prompt import (
            _DEFAULT_TEMPLATE,
            PROMPT_SCENE_DEFINE,
        )

        context_template = {
            "embedding": {
                "topk": CFG.KNOWLEDGE_SEARCH_TOP_SIZE,
                "recall_score": CFG.KNOWLEDGE_SEARCH_RECALL_SCORE,
                "recall_type": "TopK",
                "model": EMBEDDING_MODEL_CONFIG[CFG.EMBEDDING_MODEL].rsplit("/", 1)[-1],
                "chunk_size": CFG.KNOWLEDGE_CHUNK_SIZE,
                "chunk_overlap": CFG.KNOWLEDGE_CHUNK_OVERLAP,
            },
            "prompt": {
                "max_token": 2000,
                "scene": PROMPT_SCENE_DEFINE,
                "template": _DEFAULT_TEMPLATE,
            },
            "summary": {
                "max_iteration": DEFAULT_SUMMARY_MAX_ITERATION,
                "concurrency_limit": DEFAULT_SUMMARY_CONCURRENCY_LIMIT,
            },
        }
        context_template_string = json.dumps(context_template, indent=4)
        return context_template_string

    def get_space_context(self, space_name):
        """get space contect
        Args:
           - space_name: space name
        """
        request = KnowledgeSpaceRequest()
        request.name = space_name
        spaces = self.get_knowledge_space(request)
        if len(spaces) != 1:
            raise Exception(
                f"have not found {space_name} space or found more than one space called {space_name}"
            )
        space = spaces[0]
        if space.context is not None:
            return json.loads(spaces[0].context)
        return None

    async def _llm_extract_summary(
        self, doc: str, conn_uid: str, model_name: str = None
    ):
        """Extract triplets from text by llm
        Args:
            doc: Document
            conn_uid: str,chat conversation id
            model_name: str, model name
        Returns:
             chat: BaseChat, refine summary chat.
        """
        from dbgpt.app.scene import ChatScene

        chat_param = {
            "chat_session_id": conn_uid,
            "current_user_input": "",
            "select_param": doc,
            "model_name": model_name,
            "model_cache_enable": False,
        }
        executor = CFG.SYSTEM_APP.get_component(
            ComponentType.EXECUTOR_DEFAULT, ExecutorFactory
        ).create()
        from dbgpt.app.openapi.api_v1.api_v1 import CHAT_FACTORY

        chat = await blocking_func_to_async(
            executor,
            CHAT_FACTORY.get_implementation,
            ChatScene.ExtractRefineSummary.value(),
            **{"chat_param": chat_param},
        )
        return chat
