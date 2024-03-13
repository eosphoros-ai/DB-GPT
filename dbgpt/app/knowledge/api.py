import logging
import os
import shutil
import tempfile
from typing import List

from fastapi import APIRouter, File, Form, UploadFile

from dbgpt._private.config import Config
from dbgpt.app.knowledge.request.request import (
    ChunkQueryRequest,
    DocumentQueryRequest,
    DocumentSummaryRequest,
    DocumentSyncRequest,
    EntityExtractRequest,
    KnowledgeDocumentRequest,
    KnowledgeQueryRequest,
    KnowledgeSpaceRequest,
    KnowledgeSyncRequest,
    SpaceArgumentRequest,
)
from dbgpt.app.knowledge.request.response import KnowledgeQueryResponse
from dbgpt.app.knowledge.service import KnowledgeService
from dbgpt.app.openapi.api_v1.api_v1 import no_stream_generator, stream_generator
from dbgpt.app.openapi.api_view_model import Result
from dbgpt.configs.model_config import (
    EMBEDDING_MODEL_CONFIG,
    KNOWLEDGE_UPLOAD_ROOT_PATH,
)
from dbgpt.rag.embedding.embedding_factory import EmbeddingFactory
from dbgpt.rag.knowledge.base import ChunkStrategy
from dbgpt.rag.knowledge.factory import KnowledgeFactory
from dbgpt.rag.retriever.embedding import EmbeddingRetriever
from dbgpt.storage.vector_store.base import VectorStoreConfig
from dbgpt.storage.vector_store.connector import VectorStoreConnector
from dbgpt.util.tracer import SpanType, root_tracer

logger = logging.getLogger(__name__)

CFG = Config()
router = APIRouter()


knowledge_space_service = KnowledgeService()


@router.post("/knowledge/space/add")
def space_add(request: KnowledgeSpaceRequest):
    print(f"/space/add params: {request}")
    try:
        knowledge_space_service.create_knowledge_space(request)
        return Result.succ([])
    except Exception as e:
        return Result.failed(code="E000X", msg=f"space add error {e}")


@router.post("/knowledge/space/list")
def space_list(request: KnowledgeSpaceRequest):
    print(f"/space/list params:")
    try:
        return Result.succ(knowledge_space_service.get_knowledge_space(request))
    except Exception as e:
        return Result.failed(code="E000X", msg=f"space list error {e}")


@router.post("/knowledge/space/delete")
def space_delete(request: KnowledgeSpaceRequest):
    print(f"/space/delete params:")
    try:
        return Result.succ(knowledge_space_service.delete_space(request.name))
    except Exception as e:
        return Result.failed(code="E000X", msg=f"space list error {e}")


@router.post("/knowledge/{space_name}/arguments")
def arguments(space_name: str):
    print(f"/knowledge/space/arguments params:")
    try:
        return Result.succ(knowledge_space_service.arguments(space_name))
    except Exception as e:
        return Result.failed(code="E000X", msg=f"space list error {e}")


@router.post("/knowledge/{space_name}/argument/save")
def arguments_save(space_name: str, argument_request: SpaceArgumentRequest):
    print(f"/knowledge/space/argument/save params:")
    try:
        return Result.succ(
            knowledge_space_service.argument_save(space_name, argument_request)
        )
    except Exception as e:
        return Result.failed(code="E000X", msg=f"space list error {e}")


@router.post("/knowledge/{space_name}/document/add")
def document_add(space_name: str, request: KnowledgeDocumentRequest):
    print(f"/document/add params: {space_name}, {request}")
    try:
        return Result.succ(
            knowledge_space_service.create_knowledge_document(
                space=space_name, request=request
            )
        )
        # return Result.succ([])
    except Exception as e:
        return Result.failed(code="E000X", msg=f"document add error {e}")


@router.get("/knowledge/document/chunkstrategies")
def chunk_strategies():
    """Get chunk strategies"""
    print(f"/document/chunkstrategies:")
    try:
        return Result.succ(
            [
                {
                    "strategy": strategy.name,
                    "name": strategy.value[2],
                    "description": strategy.value[3],
                    "parameters": strategy.value[1],
                    "suffix": [
                        knowledge.document_type().value
                        for knowledge in KnowledgeFactory.subclasses()
                        if strategy in knowledge.support_chunk_strategy()
                        and knowledge.document_type() is not None
                    ],
                    "type": set(
                        [
                            knowledge.type().value
                            for knowledge in KnowledgeFactory.subclasses()
                            if strategy in knowledge.support_chunk_strategy()
                        ]
                    ),
                }
                for strategy in ChunkStrategy
            ]
        )
    except Exception as e:
        return Result.failed(code="E000X", msg=f"chunk strategies error {e}")


@router.post("/knowledge/{space_name}/document/list")
def document_list(space_name: str, query_request: DocumentQueryRequest):
    print(f"/document/list params: {space_name}, {query_request}")
    try:
        return Result.succ(
            knowledge_space_service.get_knowledge_documents(space_name, query_request)
        )
    except Exception as e:
        return Result.failed(code="E000X", msg=f"document list error {e}")


@router.post("/knowledge/{space_name}/document/delete")
def document_delete(space_name: str, query_request: DocumentQueryRequest):
    print(f"/document/list params: {space_name}, {query_request}")
    try:
        return Result.succ(
            knowledge_space_service.delete_document(space_name, query_request.doc_name)
        )
    except Exception as e:
        return Result.failed(code="E000X", msg=f"document list error {e}")


@router.post("/knowledge/{space_name}/document/upload")
async def document_upload(
    space_name: str,
    doc_name: str = Form(...),
    doc_type: str = Form(...),
    doc_file: UploadFile = File(...),
):
    print(f"/document/upload params: {space_name}")
    try:
        if doc_file:
            if not os.path.exists(os.path.join(KNOWLEDGE_UPLOAD_ROOT_PATH, space_name)):
                os.makedirs(os.path.join(KNOWLEDGE_UPLOAD_ROOT_PATH, space_name))
            # We can not move temp file in windows system when we open file in context of `with`
            tmp_fd, tmp_path = tempfile.mkstemp(
                dir=os.path.join(KNOWLEDGE_UPLOAD_ROOT_PATH, space_name)
            )
            with os.fdopen(tmp_fd, "wb") as tmp:
                tmp.write(await doc_file.read())
            shutil.move(
                tmp_path,
                os.path.join(KNOWLEDGE_UPLOAD_ROOT_PATH, space_name, doc_file.filename),
            )
            request = KnowledgeDocumentRequest()
            request.doc_name = doc_name
            request.doc_type = doc_type
            request.content = os.path.join(
                KNOWLEDGE_UPLOAD_ROOT_PATH, space_name, doc_file.filename
            )
            space_res = knowledge_space_service.get_knowledge_space(
                KnowledgeSpaceRequest(name=space_name)
            )
            if len(space_res) == 0:
                # create default space
                if "default" != space_name:
                    raise Exception(f"you have not create your knowledge space.")
                knowledge_space_service.create_knowledge_space(
                    KnowledgeSpaceRequest(
                        name=space_name,
                        desc="first db-gpt rag application",
                        owner="dbgpt",
                    )
                )
            return Result.succ(
                knowledge_space_service.create_knowledge_document(
                    space=space_name, request=request
                )
            )
        return Result.failed(code="E000X", msg=f"doc_file is None")
    except Exception as e:
        return Result.failed(code="E000X", msg=f"document add error {e}")


@router.post("/knowledge/{space_name}/document/sync")
def document_sync(space_name: str, request: DocumentSyncRequest):
    logger.info(f"Received params: {space_name}, {request}")
    try:
        knowledge_space_service.sync_knowledge_document(
            space_name=space_name, sync_request=request
        )
        return Result.succ([])
    except Exception as e:
        return Result.failed(code="E000X", msg=f"document sync error {e}")


@router.post("/knowledge/{space_name}/document/sync_batch")
def batch_document_sync(space_name: str, request: List[KnowledgeSyncRequest]):
    logger.info(f"Received params: {space_name}, {request}")
    try:
        doc_ids = knowledge_space_service.batch_document_sync(
            space_name=space_name, sync_requests=request
        )
        return Result.succ({"tasks": doc_ids})
    except Exception as e:
        return Result.failed(code="E000X", msg=f"document sync error {e}")


@router.post("/knowledge/{space_name}/chunk/list")
def document_list(space_name: str, query_request: ChunkQueryRequest):
    print(f"/document/list params: {space_name}, {query_request}")
    try:
        return Result.succ(knowledge_space_service.get_document_chunks(query_request))
    except Exception as e:
        return Result.failed(code="E000X", msg=f"document chunk list error {e}")


@router.post("/knowledge/{vector_name}/query")
def similar_query(space_name: str, query_request: KnowledgeQueryRequest):
    print(f"Received params: {space_name}, {query_request}")
    embedding_factory = CFG.SYSTEM_APP.get_component(
        "embedding_factory", EmbeddingFactory
    )
    config = VectorStoreConfig(
        name=space_name,
        embedding_fn=embedding_factory.create(
            EMBEDDING_MODEL_CONFIG[CFG.EMBEDDING_MODEL]
        ),
    )
    vector_store_connector = VectorStoreConnector(
        vector_store_type=CFG.VECTOR_STORE_TYPE,
        vector_store_config=config,
    )
    retriever = EmbeddingRetriever(
        top_k=query_request.top_k, vector_store_connector=vector_store_connector
    )
    chunks = retriever.retrieve(query_request.query)
    res = [
        KnowledgeQueryResponse(text=d.content, source=d.metadata["source"])
        for d in chunks
    ]
    return {"response": res}


@router.post("/knowledge/document/summary")
async def document_summary(request: DocumentSummaryRequest):
    print(f"/document/summary params: {request}")
    try:
        with root_tracer.start_span(
            "get_chat_instance", span_type=SpanType.CHAT, metadata=request
        ):
            chat = await knowledge_space_service.document_summary(request=request)
        headers = {
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Transfer-Encoding": "chunked",
        }
        from starlette.responses import StreamingResponse

        if not chat.prompt_template.stream_out:
            return StreamingResponse(
                no_stream_generator(chat),
                headers=headers,
                media_type="text/event-stream",
            )
        else:
            return StreamingResponse(
                stream_generator(chat, False, request.model_name),
                headers=headers,
                media_type="text/plain",
            )
    except Exception as e:
        return Result.failed(code="E000X", msg=f"document summary error {e}")


@router.post("/knowledge/entity/extract")
async def entity_extract(request: EntityExtractRequest):
    logger.info(f"Received params: {request}")
    try:
        import uuid

        from dbgpt.app.scene import ChatScene
        from dbgpt.util.chat_util import llm_chat_response_nostream

        chat_param = {
            "chat_session_id": uuid.uuid1(),
            "current_user_input": request.text,
            "select_param": "entity",
            "model_name": request.model_name,
        }

        res = await llm_chat_response_nostream(
            ChatScene.ExtractEntity.value(), **{"chat_param": chat_param}
        )
        return Result.succ(res)
    except Exception as e:
        return Result.failed(code="E000X", msg=f"entity extract error {e}")
