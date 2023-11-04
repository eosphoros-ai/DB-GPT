import json
import logging
from datetime import datetime

from pilot.vector_store.connector import VectorStoreConnector

from pilot.configs.config import Config
from pilot.configs.model_config import (
    EMBEDDING_MODEL_CONFIG,
    KNOWLEDGE_UPLOAD_ROOT_PATH,
)
from pilot.component import ComponentType
from pilot.utils.executor_utils import ExecutorFactory

from pilot.server.knowledge.chunk_db import (
    DocumentChunkEntity,
    DocumentChunkDao,
)
from pilot.server.knowledge.document_db import (
    KnowledgeDocumentDao,
    KnowledgeDocumentEntity,
)
from pilot.server.knowledge.space_db import (
    KnowledgeSpaceDao,
    KnowledgeSpaceEntity,
)
from pilot.server.knowledge.request.request import (
    KnowledgeSpaceRequest,
    KnowledgeDocumentRequest,
    DocumentQueryRequest,
    ChunkQueryRequest,
    SpaceArgumentRequest,
    DocumentSyncRequest,
)
from enum import Enum

from pilot.server.knowledge.request.response import (
    ChunkQueryResponse,
    DocumentQueryResponse,
    SpaceQueryResponse,
)

knowledge_space_dao = KnowledgeSpaceDao()
knowledge_document_dao = KnowledgeDocumentDao()
document_chunk_dao = DocumentChunkDao()

logger = logging.getLogger(__name__)
CFG = Config()


class SyncStatus(Enum):
    TODO = "TODO"
    FAILED = "FAILED"
    RUNNING = "RUNNING"
    FINISHED = "FINISHED"


# @singleton
class KnowledgeService:
    """KnowledgeService
    Knowledge Management Service:
        -knowledge_space management
        -knowledge_document management
        -embedding management
    """

    def __init__(self):
        from pilot.graph_engine.graph_engine import RAGGraphEngine

        # source = "/Users/chenketing/Desktop/project/llama_index/examples/paul_graham_essay/data/test/test_kg_text.txt"

        # pass

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
        knowledge_space_dao.create_knowledge_space(request)
        return True

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
        return knowledge_document_dao.create_knowledge_document(document)

    def get_knowledge_space(self, request: KnowledgeSpaceRequest):
        """get knowledge space
        Args:
           - request: KnowledgeSpaceRequest
        """
        query = KnowledgeSpaceEntity(
            name=request.name, vector_type=request.vector_type, owner=request.owner
        )
        responses = []
        spaces = knowledge_space_dao.get_knowledge_space(query)
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
            query = KnowledgeDocumentEntity(space=space.name)
            doc_count = knowledge_document_dao.get_knowledge_documents_count(query)
            res.docs = doc_count
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
        """
        query = KnowledgeDocumentEntity(
            doc_name=request.doc_name,
            doc_type=request.doc_type,
            space=space,
            status=request.status,
        )
        res = DocumentQueryResponse()
        res.data = knowledge_document_dao.get_knowledge_documents(
            query, page=request.page, page_size=request.page_size
        )
        res.total = knowledge_document_dao.get_knowledge_documents_count(query)
        res.page = request.page
        return res

    def sync_knowledge_document(self, space_name, sync_request: DocumentSyncRequest):
        """sync knowledge document chunk into vector store
        Args:
            - space: Knowledge Space Name
            - sync_request: DocumentSyncRequest
        """
        from pilot.embedding_engine.embedding_engine import EmbeddingEngine
        from pilot.embedding_engine.embedding_factory import EmbeddingFactory
        from pilot.embedding_engine.pre_text_splitter import PreTextSplitter
        from langchain.text_splitter import (
            RecursiveCharacterTextSplitter,
            SpacyTextSplitter,
        )

        # import langchain is very very slow!!!

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
                        "SpacyTextSplitter do not support multiple separators"
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
            from pilot.graph_engine.graph_engine import RAGGraphEngine

            # source = "/Users/chenketing/Desktop/project/llama_index/examples/paul_graham_essay/data/test/test_kg_text.txt"
            # engine = RAGGraphEngine(knowledge_source=source, model_name="proxyllm", text_splitter=text_splitter)
            embedding_factory = CFG.SYSTEM_APP.get_component(
                "embedding_factory", EmbeddingFactory
            )
            client = EmbeddingEngine(
                knowledge_source=doc.content,
                knowledge_type=doc.doc_type.upper(),
                model_name=EMBEDDING_MODEL_CONFIG[CFG.EMBEDDING_MODEL],
                vector_store_config={
                    "vector_store_name": space_name,
                    "vector_store_type": CFG.VECTOR_STORE_TYPE,
                },
                text_splitter=text_splitter,
                embedding_factory=embedding_factory,
            )
            chunk_docs = client.read()
            # update document status
            doc.status = SyncStatus.RUNNING.name
            doc.chunk_size = len(chunk_docs)
            doc.gmt_modified = datetime.now()
            knowledge_document_dao.update_knowledge_document(doc)
            executor = CFG.SYSTEM_APP.get_component(
                ComponentType.EXECUTOR_DEFAULT, ExecutorFactory
            ).create()
            # executor.submit(self.async_document_summary, chunk_docs, doc)
            executor.submit(self.async_doc_embedding, client, chunk_docs, doc)
            logger.info(f"begin save document chunks, doc:{doc.doc_name}")
            # save chunk details
            chunk_entities = [
                DocumentChunkEntity(
                    doc_name=doc.doc_name,
                    doc_type=doc.doc_type,
                    document_id=doc.id,
                    content=chunk_doc.page_content,
                    meta_info=str(chunk_doc.metadata),
                    gmt_created=datetime.now(),
                    gmt_modified=datetime.now(),
                )
                for chunk_doc in chunk_docs
            ]
            document_chunk_dao.create_documents_chunks(chunk_entities)

        return True

    def update_knowledge_space(
        self, space_id: int, space_request: KnowledgeSpaceRequest
    ):
        """update knowledge space
        Args:
            - space_id: space id
            - space_request: KnowledgeSpaceRequest
        """
        knowledge_space_dao.update_knowledge_space(space_id, space_request)

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
        vector_config = {}
        vector_config["vector_store_name"] = space.name
        vector_config["vector_store_type"] = CFG.VECTOR_STORE_TYPE
        vector_config["chroma_persist_path"] = KNOWLEDGE_UPLOAD_ROOT_PATH
        vector_client = VectorStoreConnector(
            vector_store_type=CFG.VECTOR_STORE_TYPE, ctx=vector_config
        )
        # delete vectors
        vector_client.delete_vector_name(space.name)
        document_query = KnowledgeDocumentEntity(space=space.name)
        # delete chunks
        documents = knowledge_document_dao.get_documents(document_query)
        for document in documents:
            document_chunk_dao.delete(document.id)
        # delete documents
        knowledge_document_dao.delete(document_query)
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
            vector_config = {}
            vector_config["vector_store_name"] = space_name
            vector_config["vector_store_type"] = CFG.VECTOR_STORE_TYPE
            vector_config["chroma_persist_path"] = KNOWLEDGE_UPLOAD_ROOT_PATH
            vector_client = VectorStoreConnector(
                vector_store_type=CFG.VECTOR_STORE_TYPE, ctx=vector_config
            )
            # delete vector by ids
            vector_client.delete_by_ids(vector_ids)
        # delete chunks
        document_chunk_dao.delete(documents[0].id)
        # delete document
        return knowledge_document_dao.delete(document_query)

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

    def async_knowledge_graph(self, chunk_docs, doc):
        """async document extract triplets and save into graph db
        Args:
            - chunk_docs: List[Document]
            - doc: KnowledgeDocumentEntity
        """
        logger.info(
            f"async_knowledge_graph, doc:{doc.doc_name}, chunk_size:{len(chunk_docs)}, begin embedding to graph store"
        )
        try:
            from pilot.graph_engine.graph_factory import RAGGraphFactory

            rag_engine = CFG.SYSTEM_APP.get_component(
                ComponentType.RAG_GRAPH_DEFAULT.value, RAGGraphFactory
            ).create()
            rag_engine.knowledge_graph(chunk_docs)
            doc.status = SyncStatus.FINISHED.name
            doc.result = "document build graph success"
        except Exception as e:
            doc.status = SyncStatus.FAILED.name
            doc.result = "document build graph failed" + str(e)
            logger.error(f"document build graph failed:{doc.doc_name}, {str(e)}")
        return knowledge_document_dao.update_knowledge_document(doc)

    def async_document_summary(self, chunk_docs, doc):
        """async document extract summary
        Args:
            - chunk_docs: List[Document]
            - doc: KnowledgeDocumentEntity
        """
        from llama_index import PromptHelper
        from llama_index.prompts.default_prompt_selectors import (
            DEFAULT_TREE_SUMMARIZE_PROMPT_SEL,
        )

        texts = [doc.page_content for doc in chunk_docs]
        prompt_helper = PromptHelper(context_window=2000)

        texts = prompt_helper.repack(
            prompt=DEFAULT_TREE_SUMMARIZE_PROMPT_SEL, text_chunks=texts
        )
        logger.info(
            f"async_document_summary, doc:{doc.doc_name}, chunk_size:{len(texts)}, begin generate summary"
        )
        summary = self._mapreduce_extract_summary(texts)
        print(f"final summary:{summary}")
        doc.summary = summary
        return knowledge_document_dao.update_knowledge_document(doc)

    def async_doc_embedding(self, client, chunk_docs, doc):
        """async document embedding into vector db
        Args:
            - client: EmbeddingEngine Client
            - chunk_docs: List[Document]
            - doc: KnowledgeDocumentEntity
        """
        logger.info(
            f"async doc sync, doc:{doc.doc_name}, chunk_size:{len(chunk_docs)}, begin embedding to vector store-{CFG.VECTOR_STORE_TYPE}"
        )
        try:
            vector_ids = client.knowledge_embedding_batch(chunk_docs)
            doc.status = SyncStatus.FINISHED.name
            doc.result = "document embedding success"
            if vector_ids is not None:
                doc.vector_ids = ",".join(vector_ids)
            logger.info(f"async document embedding, success:{doc.doc_name}")
        except Exception as e:
            doc.status = SyncStatus.FAILED.name
            doc.result = "document embedding failed" + str(e)
            logger.error(f"document embedding, failed:{doc.doc_name}, {str(e)}")
        return knowledge_document_dao.update_knowledge_document(doc)

    def _build_default_context(self):
        from pilot.scene.chat_knowledge.v1.prompt import (
            PROMPT_SCENE_DEFINE,
            _DEFAULT_TEMPLATE,
        )

        context_template = {
            "embedding": {
                "topk": CFG.KNOWLEDGE_SEARCH_TOP_SIZE,
                "recall_score": 0.0,
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

    def _llm_extract_summary(self, doc: str):
        """Extract triplets from text by llm"""
        from pilot.scene.base import ChatScene
        from pilot.common.chat_util import llm_chat_response_nostream
        import uuid

        chat_param = {
            "chat_session_id": uuid.uuid1(),
            "current_user_input": doc,
            "select_param": doc,
            "model_name": self.model_name,
        }
        from pilot.common.chat_util import run_async_tasks

        summary_iters = run_async_tasks(
            [
                llm_chat_response_nostream(
                    ChatScene.ExtractRefineSummary.value(), **{"chat_param": chat_param}
                )
            ]
        )
        return summary_iters[0]

    def _mapreduce_extract_summary(self, docs):
        """Extract summary by mapreduce mode
        map -> multi async thread generate summary
        reduce -> merge the summaries by map process
        Args:
            docs:List[str]
        """
        from pilot.scene.base import ChatScene
        from pilot.common.chat_util import llm_chat_response_nostream
        import uuid

        tasks = []
        max_iteration = 5
        if len(docs) == 1:
            summary = self._llm_extract_summary(doc=docs[0])
            return summary
        else:
            max_iteration = max_iteration if len(docs) > max_iteration else len(docs)
            for doc in docs[0:max_iteration]:
                chat_param = {
                    "chat_session_id": uuid.uuid1(),
                    "current_user_input": doc,
                    "select_param": "summary",
                    "model_name": self.model_name,
                }
                tasks.append(
                    llm_chat_response_nostream(
                        ChatScene.ExtractSummary.value(), **{"chat_param": chat_param}
                    )
                )
            from pilot.common.chat_util import run_async_tasks

            summary_iters = run_async_tasks(tasks)
            from pilot.common.prompt_util import PromptHelper
            from llama_index.prompts.default_prompt_selectors import (
                DEFAULT_TREE_SUMMARIZE_PROMPT_SEL,
            )

            prompt_helper = PromptHelper(context_window=2500)
            summary_iters = prompt_helper.repack(
                prompt=DEFAULT_TREE_SUMMARIZE_PROMPT_SEL, text_chunks=summary_iters
            )
            return self._mapreduce_extract_summary(summary_iters)
