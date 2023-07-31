import threading
from datetime import datetime

from langchain.text_splitter import RecursiveCharacterTextSplitter, SpacyTextSplitter
from pilot.vector_store.connector import VectorStoreConnector

from pilot.configs.config import Config
from pilot.configs.model_config import LLM_MODEL_CONFIG, KNOWLEDGE_UPLOAD_ROOT_PATH
from pilot.embedding_engine.embedding_engine import EmbeddingEngine
from pilot.logs import logger
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

CFG = Config()


class SyncStatus(Enum):
    TODO = "TODO"
    FAILED = "FAILED"
    RUNNING = "RUNNING"
    FINISHED = "FINISHED"


# @singleton
class KnowledgeService:
    def __init__(self):
        pass

    """create knowledge space"""

    def create_knowledge_space(self, request: KnowledgeSpaceRequest):
        query = KnowledgeSpaceEntity(
            name=request.name,
        )
        spaces = knowledge_space_dao.get_knowledge_space(query)
        if len(spaces) > 0:
            raise Exception(f"space name:{request.name} have already named")
        knowledge_space_dao.create_knowledge_space(request)
        return True

    """create knowledge document"""

    def create_knowledge_document(self, space, request: KnowledgeDocumentRequest):
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

    """get knowledge space"""

    def get_knowledge_space(self, request: KnowledgeSpaceRequest):
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
            res.owner = space.owner
            query = KnowledgeDocumentEntity(space=space.name)
            doc_count = knowledge_document_dao.get_knowledge_documents_count(query)
            res.docs = doc_count
            responses.append(res)
        return responses

    """get knowledge get_knowledge_documents"""

    def get_knowledge_documents(self, space, request: DocumentQueryRequest):
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

    """sync knowledge document chunk into vector store"""

    def sync_knowledge_document(self, space_name, doc_ids):
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

            if CFG.LANGUAGE == "en":
                text_splitter = RecursiveCharacterTextSplitter(
                    chunk_size=CFG.KNOWLEDGE_CHUNK_SIZE,
                    chunk_overlap=20,
                    length_function=len,
                )
            else:
                try:
                    text_splitter = SpacyTextSplitter(
                        pipeline="zh_core_web_sm",
                        chunk_size=CFG.KNOWLEDGE_CHUNK_SIZE,
                        chunk_overlap=100,
                    )
                except Exception:
                    text_splitter = RecursiveCharacterTextSplitter(
                        chunk_size=CFG.KNOWLEDGE_CHUNK_SIZE, chunk_overlap=50
                    )
            client = EmbeddingEngine(
                knowledge_source=doc.content,
                knowledge_type=doc.doc_type.upper(),
                model_name=LLM_MODEL_CONFIG[CFG.EMBEDDING_MODEL],
                vector_store_config={
                    "vector_store_name": space_name,
                    "vector_store_type": CFG.VECTOR_STORE_TYPE,
                    "chroma_persist_path": KNOWLEDGE_UPLOAD_ROOT_PATH,
                },
                text_splitter=text_splitter,
            )
            chunk_docs = client.read()
            # update document status
            doc.status = SyncStatus.RUNNING.name
            doc.chunk_size = len(chunk_docs)
            doc.gmt_modified = datetime.now()
            knowledge_document_dao.update_knowledge_document(doc)
            # async doc embeddings
            thread = threading.Thread(
                target=self.async_doc_embedding, args=(client, chunk_docs, doc)
            )
            thread.start()
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

    """update knowledge space"""

    def update_knowledge_space(
        self, space_id: int, space_request: KnowledgeSpaceRequest
    ):
        knowledge_space_dao.update_knowledge_space(space_id, space_request)

    """delete knowledge space"""

    def delete_space(self, space_name: str):
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

    """get document chunks"""

    def get_document_chunks(self, request: ChunkQueryRequest):
        query = DocumentChunkEntity(
            id=request.id,
            document_id=request.document_id,
            doc_name=request.doc_name,
            doc_type=request.doc_type,
        )
        res = ChunkQueryResponse()
        res.data = document_chunk_dao.get_document_chunks(
            query, page=request.page, page_size=request.page_size
        )
        res.total = document_chunk_dao.get_document_chunks_count(query)
        res.page = request.page
        return res

    def async_doc_embedding(self, client, chunk_docs, doc):
        logger.info(
            f"async_doc_embedding, doc:{doc.doc_name}, chunk_size:{len(chunk_docs)}, begin embedding to vector store-{CFG.VECTOR_STORE_TYPE}"
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
