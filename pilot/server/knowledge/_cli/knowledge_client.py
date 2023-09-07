import os
import requests
import json
import logging

from urllib.parse import urljoin
from concurrent.futures import ThreadPoolExecutor, as_completed

from pilot.openapi.api_view_model import Result
from pilot.server.knowledge.request.request import (
    KnowledgeQueryRequest,
    KnowledgeDocumentRequest,
    ChunkQueryRequest,
    DocumentQueryRequest,
)

from pilot.embedding_engine.knowledge_type import KnowledgeType
from pilot.server.knowledge.request.request import DocumentSyncRequest

from pilot.server.knowledge.request.request import KnowledgeSpaceRequest

HTTP_HEADERS = {"Content-Type": "application/json"}


logger = logging.getLogger("dbgpt_cli")


class ApiClient:
    def __init__(self, api_address: str) -> None:
        self.api_address = api_address

    def _handle_response(self, response):
        if 200 <= response.status_code <= 300:
            result = Result(**response.json())
            if not result.success:
                raise Exception(result.err_msg)
            return result.data
        else:
            raise Exception(
                f"Http request error, code: {response.status_code}, message: {response.text}"
            )

    def _post(self, url: str, data=None):
        if not isinstance(data, dict):
            data = data.__dict__
        url = urljoin(self.api_address, url)
        logger.debug(f"Send request to {url}, data: {data}")
        response = requests.post(url, data=json.dumps(data), headers=HTTP_HEADERS)
        return self._handle_response(response)


class KnowledgeApiClient(ApiClient):
    def __init__(self, api_address: str) -> None:
        super().__init__(api_address)

    def space_add(self, request: KnowledgeSpaceRequest):
        try:
            return self._post("/knowledge/space/add", data=request)
        except Exception as e:
            if "have already named" in str(e):
                logger.warn(f"you have already named {request.name}")
            else:
                raise e

    def space_list(self, request: KnowledgeSpaceRequest):
        return self._post("/knowledge/space/list", data=request)

    def document_add(self, space_name: str, request: KnowledgeDocumentRequest):
        url = f"/knowledge/{space_name}/document/add"
        return self._post(url, data=request)

    def document_list(self, space_name: str, query_request: DocumentQueryRequest):
        url = f"/knowledge/{space_name}/document/list"
        return self._post(url, data=query_request)

    def document_upload(self, space_name, doc_name, doc_type, doc_file_path):
        """Upload with multipart/form-data"""
        url = f"{self.api_address}/knowledge/{space_name}/document/upload"
        with open(doc_file_path, "rb") as f:
            files = {"doc_file": f}
            data = {"doc_name": doc_name, "doc_type": doc_type}
            response = requests.post(url, data=data, files=files)
        return self._handle_response(response)

    def document_sync(self, space_name: str, request: DocumentSyncRequest):
        url = f"/knowledge/{space_name}/document/sync"
        return self._post(url, data=request)

    def chunk_list(self, space_name: str, query_request: ChunkQueryRequest):
        url = f"/knowledge/{space_name}/chunk/list"
        return self._post(url, data=query_request)

    def similar_query(self, vector_name: str, query_request: KnowledgeQueryRequest):
        url = f"/knowledge/{vector_name}/query"
        return self._post(url, data=query_request)


def knowledge_init(
    api_address: str,
    vector_name: str,
    vector_store_type: str,
    local_doc_dir: str,
    skip_wrong_doc: bool,
    max_workers: int = None,
):
    client = KnowledgeApiClient(api_address)
    space = KnowledgeSpaceRequest()
    space.name = vector_name
    space.desc = "DB-GPT cli"
    space.vector_type = vector_store_type
    space.owner = "DB-GPT"

    # Create space
    logger.info(f"Create space: {space}")
    client.space_add(space)
    logger.info("Create space successfully")
    space_list = client.space_list(KnowledgeSpaceRequest(name=space.name))
    if len(space_list) != 1:
        raise Exception(f"List space {space.name} error")
    space = KnowledgeSpaceRequest(**space_list[0])

    doc_ids = []

    def upload(filename: str):
        try:
            logger.info(f"Begin upload document: {filename} to {space.name}")
            return client.document_upload(
                space.name, filename, KnowledgeType.DOCUMENT.value, filename
            )
        except Exception as e:
            if skip_wrong_doc:
                logger.warn(f"Warning: {str(e)}")
            else:
                raise e

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        tasks = []
        for root, _, files in os.walk(local_doc_dir, topdown=False):
            for file in files:
                filename = os.path.join(root, file)
                tasks.append(pool.submit(upload, filename))
        doc_ids = [r.result() for r in as_completed(tasks)]
        doc_ids = list(filter(lambda x: x, doc_ids))
        if not doc_ids:
            logger.warn("Warning: no document to sync")
            return
        logger.info(f"Begin sync document: {doc_ids}")
        client.document_sync(space.name, DocumentSyncRequest(doc_ids=doc_ids))
