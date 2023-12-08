import os
import shutil
import tempfile
import logging

from fastapi import APIRouter, File, UploadFile, Form

from dbgpt._private.config import Config
from dbgpt.configs.model_config import (
    EMBEDDING_MODEL_CONFIG,
    KNOWLEDGE_UPLOAD_ROOT_PATH,
)
from dbgpt.app.openapi.api_v1.api_v1 import no_stream_generator, stream_generator

from dbgpt.app.openapi.api_view_model import Result
from dbgpt.rag.embedding_engine.embedding_engine import EmbeddingEngine
from dbgpt.rag.embedding_engine.embedding_factory import EmbeddingFactory

from dbgpt.app.knowledge.service import KnowledgeService
from dbgpt.app.knowledge.request.request import (
    KnowledgeQueryRequest,
    KnowledgeQueryResponse,
    KnowledgeDocumentRequest,
    DocumentSyncRequest,
    ChunkQueryRequest,
    DocumentQueryRequest,
    SpaceArgumentRequest,
    EntityExtractRequest,
    DocumentSummaryRequest,
)

from dbgpt.app.knowledge.request.request import KnowledgeSpaceRequest
from dbgpt.util.tracer import root_tracer, SpanType

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
    client = EmbeddingEngine(
        model_name=EMBEDDING_MODEL_CONFIG[CFG.EMBEDDING_MODEL],
        vector_store_config={"vector_store_name": space_name},
        embedding_factory=embedding_factory,
    )
    docs = client.similar_search(query_request.query, query_request.top_k)
    res = [
        KnowledgeQueryResponse(text=d.page_content, source=d.metadata["source"])
        for d in docs
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
        from dbgpt.app.scene import ChatScene
        from dbgpt._private.chat_util import llm_chat_response_nostream
        import uuid

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
