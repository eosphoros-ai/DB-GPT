import os
import requests
import json
import logging

from urllib.parse import urljoin
from concurrent.futures import ThreadPoolExecutor, as_completed

from dbgpt.app.openapi.api_view_model import Result
from dbgpt.app.knowledge.request.request import (
    KnowledgeQueryRequest,
    KnowledgeDocumentRequest,
    ChunkQueryRequest,
    DocumentQueryRequest,
)

from dbgpt.rag.embedding_engine.knowledge_type import KnowledgeType
from dbgpt.app.knowledge.request.request import DocumentSyncRequest

from dbgpt.app.knowledge.request.request import KnowledgeSpaceRequest

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

    def space_delete(self, request: KnowledgeSpaceRequest):
        return self._post("/knowledge/space/delete", data=request)

    def space_list(self, request: KnowledgeSpaceRequest):
        return self._post("/knowledge/space/list", data=request)

    def document_add(self, space_name: str, request: KnowledgeDocumentRequest):
        url = f"/knowledge/{space_name}/document/add"
        return self._post(url, data=request)

    def document_delete(self, space_name: str, request: KnowledgeDocumentRequest):
        url = f"/knowledge/{space_name}/document/delete"
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
    space_name: str,
    vector_store_type: str,
    local_doc_path: str,
    skip_wrong_doc: bool,
    overwrite: bool,
    max_workers: int,
    pre_separator: str,
    separator: str,
    chunk_size: int,
    chunk_overlap: int,
):
    client = KnowledgeApiClient(api_address)
    space = KnowledgeSpaceRequest()
    space.name = space_name
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
            doc_id = None
            try:
                doc_id = client.document_upload(
                    space.name, filename, KnowledgeType.DOCUMENT.value, filename
                )
            except Exception as ex:
                if overwrite and "have already named" in str(ex):
                    logger.warn(
                        f"Document {filename} already exist in space {space.name}, overwrite it"
                    )
                    client.document_delete(
                        space.name, KnowledgeDocumentRequest(doc_name=filename)
                    )
                    doc_id = client.document_upload(
                        space.name, filename, KnowledgeType.DOCUMENT.value, filename
                    )
                else:
                    raise ex
            sync_req = DocumentSyncRequest(doc_ids=[doc_id])
            if pre_separator:
                sync_req.pre_separator = pre_separator
            if separator:
                sync_req.separators = [separator]
            if chunk_size:
                sync_req.chunk_size = chunk_size
            if chunk_overlap:
                sync_req.chunk_overlap = chunk_overlap

            client.document_sync(space.name, sync_req)
            return doc_id
        except Exception as e:
            if skip_wrong_doc:
                logger.warn(f"Upload {filename} to {space.name} failed: {str(e)}")
            else:
                raise e

    if not os.path.exists(local_doc_path):
        raise Exception(f"{local_doc_path} not exists")

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        tasks = []
        file_names = []
        if os.path.isdir(local_doc_path):
            for root, _, files in os.walk(local_doc_path, topdown=False):
                for file in files:
                    file_names.append(os.path.join(root, file))
        else:
            # Single file
            file_names.append(local_doc_path)

        [tasks.append(pool.submit(upload, filename)) for filename in file_names]

        doc_ids = [r.result() for r in as_completed(tasks)]
        doc_ids = list(filter(lambda x: x, doc_ids))
        if not doc_ids:
            logger.warn("Warning: no document to sync")
            return


from prettytable import PrettyTable


class _KnowledgeVisualizer:
    def __init__(self, api_address: str, out_format: str):
        self.client = KnowledgeApiClient(api_address)
        self.out_format = out_format
        self.out_kwargs = {}
        if out_format == "json":
            self.out_kwargs["ensure_ascii"] = False

    def print_table(self, table):
        print(table.get_formatted_string(out_format=self.out_format, **self.out_kwargs))

    def list_spaces(self):
        spaces = self.client.space_list(KnowledgeSpaceRequest())
        table = PrettyTable(
            ["Space ID", "Space Name", "Vector Type", "Owner", "Description"],
            title="All knowledge spaces",
        )
        for sp in spaces:
            context = sp.get("context")
            table.add_row(
                [
                    sp.get("id"),
                    sp.get("name"),
                    sp.get("vector_type"),
                    sp.get("owner"),
                    sp.get("desc"),
                ]
            )
        self.print_table(table)

    def list_documents(self, space_name: str, page: int, page_size: int):
        space_data = self.client.document_list(
            space_name, DocumentQueryRequest(page=page, page_size=page_size)
        )

        space_table = PrettyTable(
            [
                "Space Name",
                "Total Documents",
                "Current Page",
                "Current Size",
                "Page Size",
            ],
            title=f"Space {space_name} description",
        )
        space_table.add_row(
            [space_name, space_data["total"], page, len(space_data["data"]), page_size]
        )

        table = PrettyTable(
            [
                "Space Name",
                "Document ID",
                "Document Name",
                "Type",
                "Chunks",
                "Last Sync",
                "Status",
                "Result",
            ],
            title=f"Documents of space {space_name}",
        )
        for doc in space_data["data"]:
            table.add_row(
                [
                    space_name,
                    doc.get("id"),
                    doc.get("doc_name"),
                    doc.get("doc_type"),
                    doc.get("chunk_size"),
                    doc.get("last_sync"),
                    doc.get("status"),
                    doc.get("result"),
                ]
            )
        if self.out_format == "text":
            self.print_table(space_table)
            print("")
        self.print_table(table)

    def list_chunks(
        self,
        space_name: str,
        doc_id: int,
        page: int,
        page_size: int,
        show_content: bool,
    ):
        doc_data = self.client.chunk_list(
            space_name,
            ChunkQueryRequest(document_id=doc_id, page=page, page_size=page_size),
        )

        doc_table = PrettyTable(
            [
                "Space Name",
                "Document ID",
                "Total Chunks",
                "Current Page",
                "Current Size",
                "Page Size",
            ],
            title=f"Document {doc_id} in {space_name} description",
        )
        doc_table.add_row(
            [
                space_name,
                doc_id,
                doc_data["total"],
                page,
                len(doc_data["data"]),
                page_size,
            ]
        )

        table = PrettyTable(
            ["Space Name", "Document ID", "Document Name", "Content", "Meta Data"],
            title=f"chunks of document id {doc_id} in space {space_name}",
        )
        for chunk in doc_data["data"]:
            table.add_row(
                [
                    space_name,
                    doc_id,
                    chunk.get("doc_name"),
                    chunk.get("content") if show_content else "[Hidden]",
                    chunk.get("meta_info"),
                ]
            )
        if self.out_format == "text":
            self.print_table(doc_table)
            print("")
        self.print_table(table)


def knowledge_list(
    api_address: str,
    space_name: str,
    page: int,
    page_size: int,
    doc_id: int,
    show_content: bool,
    out_format: str,
):
    visualizer = _KnowledgeVisualizer(api_address, out_format)
    if not space_name:
        visualizer.list_spaces()
    elif not doc_id:
        visualizer.list_documents(space_name, page, page_size)
    else:
        visualizer.list_chunks(space_name, doc_id, page, page_size, show_content)


def knowledge_delete(
    api_address: str, space_name: str, doc_name: str, confirm: bool = False
):
    client = KnowledgeApiClient(api_address)
    space = KnowledgeSpaceRequest()
    space.name = space_name
    space_list = client.space_list(KnowledgeSpaceRequest(name=space.name))
    if not space_list:
        raise Exception(f"No knowledge space name {space_name}")

    if not doc_name:
        if not confirm:
            # Confirm by user
            user_input = (
                input(
                    f"Are you sure you want to delete the whole knowledge space {space_name}? Type 'yes' to confirm: "
                )
                .strip()
                .lower()
            )
            if user_input != "yes":
                logger.warn("Delete operation cancelled.")
                return
        client.space_delete(space)
        logger.info("Delete the whole knowledge space successfully!")
    else:
        if not confirm:
            # Confirm by user
            user_input = (
                input(
                    f"Are you sure you want to delete the doucment {doc_name} in knowledge space {space_name}? Type 'yes' to confirm: "
                )
                .strip()
                .lower()
            )
            if user_input != "yes":
                logger.warn("Delete operation cancelled.")
                return
        client.document_delete(space_name, KnowledgeDocumentRequest(doc_name=doc_name))
        logger.info(
            f"Delete the doucment {doc_name} in knowledge space {space_name} successfully!"
        )
