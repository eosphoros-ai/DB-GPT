import json
import logging
import re
import timeit
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
    DocumentRecallTestRequest,
    DocumentSummaryRequest,
    KnowledgeDocumentRequest,
    KnowledgeSpaceRequest,
    SpaceArgumentRequest,
)
from dbgpt.app.knowledge.request.response import (
    ChunkQueryResponse,
    DocumentQueryResponse,
    DocumentResponse,
    SpaceQueryResponse,
)
from dbgpt.component import ComponentType
from dbgpt.configs import DOMAIN_TYPE_FINANCIAL_REPORT
from dbgpt.configs.model_config import EMBEDDING_MODEL_CONFIG
from dbgpt.core import LLMClient
from dbgpt.model import DefaultLLMClient
from dbgpt.model.cluster import WorkerManagerFactory
from dbgpt.rag.assembler.summary import SummaryAssembler
from dbgpt.rag.chunk_manager import ChunkParameters
from dbgpt.rag.embedding.embedding_factory import EmbeddingFactory
from dbgpt.rag.knowledge.base import KnowledgeType
from dbgpt.rag.knowledge.factory import KnowledgeFactory
from dbgpt.rag.retriever.rerank import RerankEmbeddingsRanker
from dbgpt.serve.rag.connector import VectorStoreConnector
from dbgpt.serve.rag.models.models import KnowledgeSpaceDao, KnowledgeSpaceEntity
from dbgpt.serve.rag.retriever.knowledge_space import KnowledgeSpaceRetriever
from dbgpt.serve.rag.service.service import SyncStatus
from dbgpt.storage.vector_store.base import VectorStoreConfig
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

    @property
    def llm_client(self) -> LLMClient:
        worker_manager = CFG.SYSTEM_APP.get_component(
            ComponentType.WORKER_MANAGER_FACTORY, WorkerManagerFactory
        ).create()
        return DefaultLLMClient(worker_manager, True)

    def create_knowledge_space(self, request: KnowledgeSpaceRequest):
        """create knowledge space
        Args:
           - request: KnowledgeSpaceRequest
        """
        query = KnowledgeSpaceEntity(
            name=request.name,
        )
        if request.vector_type == "VectorStore":
            request.vector_type = CFG.VECTOR_STORE_TYPE
        if request.vector_type == "KnowledgeGraph":
            knowledge_space_name_pattern = r"^[a-zA-Z0-9\u4e00-\u9fa5]+$"
            if not re.match(knowledge_space_name_pattern, request.name):
                raise Exception(f"space name:{request.name} invalid")
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
            id=request.id,
            name=request.name,
            vector_type=request.vector_type,
            owner=request.owner,
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
            res.domain_type = space.domain_type
            res.desc = space.desc
            res.owner = space.owner
            res.gmt_created = space.gmt_created
            res.gmt_modified = space.gmt_modified
            res.context = space.context
            res.docs = docs_count.get(space.name, 0)
            responses.append(res)
        return responses

    def arguments(self, space):
        """show knowledge space arguments
        Args:
            - space_name: Knowledge Space Name
        """
        query = KnowledgeSpaceEntity(name=space)
        spaces = knowledge_space_dao.get_knowledge_space(query)
        if len(spaces) != 1:
            raise Exception(f"there are no or more than one space called {space}")
        space = spaces[0]
        if space.context is None:
            context = self._build_default_context()
        else:
            context = space.context
        return json.loads(context)

    def argument_save(self, space, argument_request: SpaceArgumentRequest):
        """save argument
        Args:
            - space_name: Knowledge Space Name
            - argument_request: SpaceArgumentRequest
        """
        query = KnowledgeSpaceEntity(name=space)
        spaces = knowledge_space_dao.get_knowledge_space(query)
        if len(spaces) != 1:
            raise Exception(f"there are no or more than one space called {space}")
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
        if request.page_size <= 0:
            request.page_size = 20
        ks = knowledge_space_dao.get_one({"name": space})
        if ks is None:
            raise Exception(f"there is no space id called {space}")
        res = DocumentQueryResponse()
        if request.doc_ids and len(request.doc_ids) > 0:
            documents: List[
                KnowledgeDocumentEntity
            ] = knowledge_document_dao.documents_by_ids(request.doc_ids)
            res.data = [item.to_dict() for item in documents]
        else:
            space_name = ks.name
            query = {
                "doc_type": request.doc_type,
                "space": space_name,
                "status": request.status,
            }
            if request.doc_name:
                docs = knowledge_document_dao.get_list({"space": space_name})
                docs = [DocumentResponse.serve_to_response(doc) for doc in docs]
                res.data = [
                    doc
                    for doc in docs
                    if doc.doc_name and request.doc_name in doc.doc_name
                ]
            else:
                result = knowledge_document_dao.get_list_page(
                    query, page=request.page, page_size=request.page_size
                )
                docs = result.items
                docs = [DocumentResponse.serve_to_response(doc) for doc in docs]
                res.data = docs
                res.total = result.total_count
                res.page = result.page
        return res

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
            from dbgpt.serve.rag.service.service import Service

            rag_service = Service.get_instance(CFG.SYSTEM_APP)
            space = rag_service.get({"name": document.space})
            document_vo = KnowledgeDocumentEntity.to_document_vo(documents)
            await rag_service._sync_knowledge_document(
                space_id=space.id,
                doc_vo=document_vo[0],
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

    def get_space_context_by_space_id(self, space_id):
        """get space contect
        Args:
           - space_id: space name
        """
        spaces = self.get_knowledge_space_by_ids([space_id])
        if len(spaces) != 1:
            raise Exception(
                f"have not found {space_id} space or found more than one space called {space_id}"
            )
        space = spaces[0]
        if space.context is not None:
            return json.loads(spaces[0].context)
        return None

    def get_knowledge_space_by_ids(self, ids):
        """
        get knowledge space by ids.
        """
        return knowledge_space_dao.get_knowledge_space_by_ids(ids)

    async def recall_test(
        self, space_name, doc_recall_test_request: DocumentRecallTestRequest
    ):
        logger.info(f"recall_test {space_name}, {doc_recall_test_request}")
        from dbgpt.rag.embedding.embedding_factory import RerankEmbeddingFactory

        try:
            start_time = timeit.default_timer()
            question = doc_recall_test_request.question
            space_context = self.get_space_context(space_name)
            logger.info(f"space_context is {space_context}")
            space = knowledge_space_dao.get_one({"name": space_name})

            top_k = int(doc_recall_test_request.recall_top_k)
            score_threshold = (
                float(space_context["embedding"].get("recall_score", 0.3))
                if (space_context and "embedding" in space_context)
                else 0.3
            )

            if CFG.RERANK_MODEL is not None:
                if top_k < int(CFG.RERANK_TOP_K) or top_k < 20:
                    # We use reranker, so if the top_k is less than 20,
                    # we need to set it to 20
                    top_k = max(int(CFG.RERANK_TOP_K), 20)

            knowledge_space_retriever = KnowledgeSpaceRetriever(
                space_id=space.id, top_k=top_k
            )
            chunks = await knowledge_space_retriever.aretrieve_with_scores(
                question, score_threshold
            )
            retrievers_end_time = timeit.default_timer()
            retrievers_cost_time = retrievers_end_time - start_time
            logger.info(
                f"retrieve chunks size is {len(chunks)}, "
                f"retrievers_cost_time is {retrievers_cost_time} seconds"
            )

            recall_top_k = int(doc_recall_test_request.recall_top_k)
            if CFG.RERANK_MODEL is not None:
                rerank_embeddings = RerankEmbeddingFactory.get_instance(
                    CFG.SYSTEM_APP
                ).create()
                reranker = RerankEmbeddingsRanker(rerank_embeddings, topk=recall_top_k)
                chunks = reranker.rank(candidates_with_scores=chunks, query=question)

            recall_score_threshold = doc_recall_test_request.recall_score_threshold
            if recall_score_threshold is not None:
                chunks = [
                    chunk for chunk in chunks if chunk.score >= recall_score_threshold
                ]
            recall_end_time = timeit.default_timer()
            recall_cost_time = recall_end_time - start_time
            cost_time_map = {
                "retrievers_cost_time": retrievers_cost_time,
                "recall_cost_time": recall_cost_time,
            }
            logger.info(
                f"recall chunks size is {len(chunks)}, "
                f"recall_cost_time is {recall_cost_time} seconds, {cost_time_map}"
            )

            # return chunks, cost_time_map
            return chunks
        except Exception as e:
            logger.error(f" recall_test error: {str(e)}")
        return []

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
        spaces = knowledge_space_dao.get_knowledge_space(
            KnowledgeSpaceEntity(name=space_name)
        )
        if len(spaces) != 1:
            raise Exception(f"invalid space name:{space_name}")
        space = spaces[0]

        embedding_factory = CFG.SYSTEM_APP.get_component(
            "embedding_factory", EmbeddingFactory
        )
        embedding_fn = embedding_factory.create(
            model_name=EMBEDDING_MODEL_CONFIG[CFG.EMBEDDING_MODEL]
        )
        config = VectorStoreConfig(
            name=space.name,
            embedding_fn=embedding_fn,
            llm_client=self.llm_client,
            model_name=None,
        )
        if space.domain_type == DOMAIN_TYPE_FINANCIAL_REPORT:
            conn_manager = CFG.local_db_manager
            conn_manager.delete_db(f"{space.name}_fin_report")

        vector_store_connector = VectorStoreConnector(
            vector_store_type=space.vector_type, vector_store_config=config
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

        spaces = self.get_knowledge_space(KnowledgeSpaceRequest(name=space_name))
        if len(spaces) != 1:
            raise Exception(f"invalid space name:{space_name}")
        space = spaces[0]

        vector_ids = documents[0].vector_ids
        if vector_ids is not None:
            embedding_factory = CFG.SYSTEM_APP.get_component(
                "embedding_factory", EmbeddingFactory
            )
            embedding_fn = embedding_factory.create(
                model_name=EMBEDDING_MODEL_CONFIG[CFG.EMBEDDING_MODEL]
            )
            config = VectorStoreConfig(
                name=space.name,
                embedding_fn=embedding_fn,
                llm_client=self.llm_client,
                model_name=None,
            )
            vector_store_connector = VectorStoreConnector(
                vector_store_type=space.vector_type, vector_store_config=config
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
        res = ChunkQueryResponse()
        res.data = [
            chunk.to_dict()
            for chunk in document_chunk_dao.get_document_chunks(
                query, page=request.page, page_size=request.page_size
            )
        ]
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
            f"async doc embedding sync, doc:{doc.doc_name}, chunks length is {len(chunk_docs)}"
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

    def query_graph(self, space_name, limit):
        embedding_factory = CFG.SYSTEM_APP.get_component(
            "embedding_factory", EmbeddingFactory
        )
        embedding_fn = embedding_factory.create(
            model_name=EMBEDDING_MODEL_CONFIG[CFG.EMBEDDING_MODEL]
        )
        spaces = self.get_knowledge_space(KnowledgeSpaceRequest(name=space_name))
        if len(spaces) != 1:
            raise Exception(f"invalid space name:{space_name}")
        space = spaces[0]
        print(CFG.LLM_MODEL)
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
        graph = vector_store_connector.client.query_graph(limit=limit)
        res = {"nodes": [], "edges": []}
        for node in graph.vertices():
            res["nodes"].append(
                {
                    "id": node.vid,
                    "communityId": node.get_prop("_community_id"),
                    "name": node.name,
                    "type": node.get_prop("type") or "",
                }
            )
        for edge in graph.edges():
            res["edges"].append(
                {
                    "source": edge.sid,
                    "target": edge.tid,
                    "name": edge.name,
                    "type": edge.get_prop("type") or "",
                }
            )
        return res
