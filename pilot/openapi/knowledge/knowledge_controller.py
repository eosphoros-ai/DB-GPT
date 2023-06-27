from tempfile import NamedTemporaryFile

from fastapi import APIRouter, File, UploadFile

from langchain.embeddings import HuggingFaceEmbeddings

from pilot.configs.config import Config
from pilot.configs.model_config import LLM_MODEL_CONFIG

from pilot.openapi.api_v1.api_view_model import Result
from pilot.embedding_engine.knowledge_embedding import KnowledgeEmbedding

from pilot.openapi.knowledge.knowledge_service import KnowledgeService
from pilot.openapi.knowledge.request.knowledge_request import (
    KnowledgeQueryRequest,
    KnowledgeQueryResponse, KnowledgeDocumentRequest, DocumentSyncRequest, ChunkQueryRequest, DocumentQueryRequest,
)

from pilot.openapi.knowledge.request.knowledge_request import KnowledgeSpaceRequest

CFG = Config()
router = APIRouter()


embeddings = HuggingFaceEmbeddings(model_name=LLM_MODEL_CONFIG[CFG.EMBEDDING_MODEL])

knowledge_space_service = KnowledgeService()


@router.post("/knowledge/space/add")
def space_add(request: KnowledgeSpaceRequest):
    print(f"/space/add params: {request}")
    try:
        knowledge_space_service.create_knowledge_space(request)
        return Result.succ([])
    except Exception as e:
        return Result.faild(code="E000X", msg=f"space add error {e}")


@router.post("/knowledge/space/list")
def space_list(request: KnowledgeSpaceRequest):
    print(f"/space/list params:")
    try:
        return Result.succ(knowledge_space_service.get_knowledge_space(request))
    except Exception as e:
        return Result.faild(code="E000X", msg=f"space list error {e}")


@router.post("/knowledge/{space_name}/document/add")
def document_add(space_name: str, request: KnowledgeDocumentRequest):
    print(f"/document/add params: {space_name}, {request}")
    try:
        knowledge_space_service.create_knowledge_document(
            space=space_name, request=request
        )
        return Result.succ([])
    except Exception as e:
        return Result.faild(code="E000X", msg=f"document add error {e}")


@router.post("/knowledge/{space_name}/document/list")
def document_list(space_name: str, query_request: DocumentQueryRequest):
    print(f"/document/list params: {space_name}, {query_request}")
    try:
        return Result.succ(knowledge_space_service.get_knowledge_documents(
                space_name,
                query_request
            ))
    except Exception as e:
        return Result.faild(code="E000X", msg=f"document list error {e}")


@router.post("/knowledge/{space_name}/document/upload")
def document_sync(space_name: str, file: UploadFile = File(...)):
    print(f"/document/upload params: {space_name}")
    try:
        with NamedTemporaryFile(delete=False) as tmp:
            tmp.write(file.read())
            tmp_path = tmp.name
            tmp_content = tmp.read()

        return {"file_path": tmp_path, "file_content": tmp_content}
        Result.succ([])
    except Exception as e:
        return Result.faild(code="E000X", msg=f"document sync error {e}")


@router.post("/knowledge/{space_name}/document/sync")
def document_sync(space_name: str, request: DocumentSyncRequest):
    print(f"Received params: {space_name}, {request}")
    try:
        knowledge_space_service.sync_knowledge_document(
            space_name=space_name, doc_ids=request.doc_ids
        )
        Result.succ([])
    except Exception as e:
        return Result.faild(code="E000X", msg=f"document sync error {e}")


@router.post("/knowledge/{space_name}/chunk/list")
def document_list(space_name: str, query_request: ChunkQueryRequest):
    print(f"/document/list params: {space_name}, {query_request}")
    try:
        return Result.succ(knowledge_space_service.get_document_chunks(
                query_request
            ))
    except Exception as e:
        return Result.faild(code="E000X", msg=f"document chunk list error {e}")


@router.post("/knowledge/{vector_name}/query")
def similar_query(space_name: str, query_request: KnowledgeQueryRequest):
    print(f"Received params: {space_name}, {query_request}")
    client = KnowledgeEmbedding(
        model_name=embeddings, vector_store_config={"vector_store_name": space_name}
    )
    docs = client.similar_search(query_request.query, query_request.top_k)
    res = [
        KnowledgeQueryResponse(text=d.page_content, source=d.metadata["source"])
        for d in docs
    ]
    return {"response": res}
