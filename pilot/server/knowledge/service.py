import json
import logging
import os
import zipfile
from datetime import datetime

from pilot.embedding_engine.identify_textsplitter import IdentifyTextSplitter
from pilot.log.common_task_log_db import CommonTaskLogEntity, CommonTaskType, CommonTaskState, CommonTaskLogDao
from pilot.vector_store.connector import VectorStoreConnector

from pilot.configs.config import Config
from pilot.configs.model_config import (
    EMBEDDING_MODEL_CONFIG,
    KNOWLEDGE_UPLOAD_ROOT_PATH,
)
from pilot.component import ComponentType
from pilot.utils.executor_utils import ExecutorFactory, blocking_func_to_async

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
    DocumentSummaryRequest,
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


common_task_log_dao = CommonTaskLogDao()

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
        pass

    def create_knowledge_space(self, request: KnowledgeSpaceRequest):
        """create knowledge space
        Args:
           - request: KnowledgeSpaceRequest
        """
        query = KnowledgeSpaceEntity(
            name=request.name, user_id=request.user_id
        )
        spaces = knowledge_space_dao.get_knowledge_space(query)
        if len(spaces) > 0:
            raise Exception(f"space name:{request.name} have already named")
        knowledge_space_dao.create_knowledge_space(request)
        return True

    def create_knowledge_document(self, space_id, request: KnowledgeDocumentRequest):
        """create knowledge document
        Args:
           - request: KnowledgeDocumentRequest
        """
        knowledge_spaces = knowledge_space_dao.get_knowledge_space(KnowledgeSpaceEntity(id=space_id))
        if len(knowledge_spaces) == 0:
            return None
        ks = knowledge_spaces[0]
        query = KnowledgeDocumentEntity(doc_name=request.doc_name, space_id=space_id)
        documents = knowledge_document_dao.get_knowledge_documents(query)
        if len(documents) > 0:
            raise Exception(f"document name:{request.doc_name} have already named")
        document = KnowledgeDocumentEntity(
            doc_name=request.doc_name,
            doc_type=request.doc_type,
            space_id=space_id,
            space=ks.name,
            chunk_size=0,
            status=SyncStatus.TODO.name,
            last_sync=datetime.now(),
            content=request.content,
            result="",
        )
        return knowledge_document_dao.create_knowledge_document(document)

    def get_knowledge_space_by_ids(self, ids):
        """
          get knowledge space by ids.
        """
        return knowledge_space_dao.get_knowledge_space_by_ids(ids)

    def get_knowledge_space(self, request: KnowledgeSpaceRequest):
        """get knowledge space
        Args:
           - request: KnowledgeSpaceRequest
        """
        query = KnowledgeSpaceEntity(
            name=request.name, vector_type=request.vector_type, owner=request.owner, user_id=request.user_id
        )
        spaces = knowledge_space_dao.get_knowledge_space(query)

        # 获取所有space名称
        space_ids = [space.id for space in spaces]

        # 批量查询文档数量
        docs_count = knowledge_document_dao.get_knowledge_documents_count_bulk(space_ids)

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
            # 为每个空间设置文档计数
            res.docs = docs_count.get(space.id, 0)
            responses.append(res)
        return responses

    def arguments(self, space_name: str, user_id: str):
        """show knowledge space arguments
        Args:
            - space_name: Knowledge Space Name
        """
        query = KnowledgeSpaceEntity(name=space_name, user_id=user_id)
        spaces = knowledge_space_dao.get_knowledge_space(query)
        if len(spaces) != 1:
            raise Exception(f"there are no or more than one space called {space_name}")
        space = spaces[0]
        if space.context is None:
            context = self._build_default_context()
        else:
            context = space.context
        return json.loads(context)

    def argument_save(self, space_name, argument_request: SpaceArgumentRequest, user_id: str):
        """save argument
        Args:
            - space_name: Knowledge Space Name
            - argument_request: SpaceArgumentRequest
        """
        query = KnowledgeSpaceEntity(name=space_name, user_id=user_id)
        spaces = knowledge_space_dao.get_knowledge_space(query)
        if len(spaces) != 1:
            raise Exception(f"there are no or more than one space called {space_name}")
        space = spaces[0]
        space.context = argument_request.argument
        return knowledge_space_dao.update_knowledge_space(space)

    def get_knowledge_documents(self, space_id, request: DocumentQueryRequest):
        """get knowledge documents
        Args:
            - space: Knowledge Space Name
            - request: DocumentQueryRequest
        """
        query = KnowledgeDocumentEntity(
            doc_name=request.doc_name,
            doc_type=request.doc_type,
            space_id=space_id,
            status=request.status,
        )
        res = DocumentQueryResponse()
        res.data = knowledge_document_dao.get_knowledge_documents(
            query, page=request.page, page_size=request.page_size
        )
        res.total = knowledge_document_dao.get_knowledge_documents_count(query)
        res.page = request.page
        return res

    def sync_knowledge_document(self, space_id, sync_request: DocumentSyncRequest, user_id: str = None):
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
        for doc_id in doc_ids:
            query = KnowledgeDocumentEntity(
                id=doc_id,
                space_id=space_id,
            )
            doc = knowledge_document_dao.get_knowledge_documents(query)[0]
            if (
                doc.status == SyncStatus.RUNNING.name
                or doc.status == SyncStatus.FINISHED.name
            ):
                raise Exception(
                    f" doc:{doc.doc_name} status is {doc.status}, can not sync"
                )
            try:
                # update document status
                doc.status = SyncStatus.RUNNING.name
                knowledge_document_dao.update_knowledge_document(doc)

                knowledge_spaces = knowledge_space_dao.get_knowledge_space(KnowledgeSpaceEntity(id=space_id))
                if len(knowledge_spaces) == 0:
                    continue
                ks = knowledge_spaces[0]
                space_context = self.get_space_context(ks.name, user_id)
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

                if separators is not None or "_identify_split" in doc.doc_name:
                    text_splitter = IdentifyTextSplitter([CFG.IDENTIFY_SPLIT])
                else:
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
                embedding_factory = CFG.SYSTEM_APP.get_component(
                    "embedding_factory", EmbeddingFactory
                )
                tmp_file_path = doc.content
                # download from oss
                # if doc.doc_type == 'DOCUMENT':
                #     tmp_file_name = str(uuid.uuid4().hex) + doc.doc_name
                #     tmp_file_path = os.path.join(KNOWLEDGE_UPLOAD_ROOT_PATH, tmp_file_name)
                #     download_status = get_object_to_file(oss_key=doc.oss_file_key, local_file_path=tmp_file_path,
                #                                          bucket=CFG.OSS_BUCKET)
                #     logger.info(f"download doc {doc.doc_name} to {tmp_file_path} success={download_status}")
                # else:
                #     tmp_file_path = doc.content

                client = EmbeddingEngine(
                    knowledge_source=doc.content,
                    knowledge_type=doc.doc_type.upper(),
                    model_name=EMBEDDING_MODEL_CONFIG[CFG.EMBEDDING_MODEL],
                    vector_store_config={
                        "vector_store_name": CFG.KS_EMBED_PREFIX + str(ks.id),
                        "vector_store_type": CFG.VECTOR_STORE_TYPE,
                    },
                    text_splitter=text_splitter,
                    embedding_factory=embedding_factory,
                )
                # if doc.doc_type == 'DOCUMENT' and not wait_for_file_exist(tmp_file_path):
                #     doc.status = SyncStatus.FAILED.name
                #     knowledge_document_dao.update_knowledge_document(doc)
                #     raise f"doc sync failed, file path {tmp_file_path} not exist"

                # 确保当前内容能够被正常加载
                if tmp_file_path.endswith(".zip"):
                    client.knowledge_source = "xxx.md"

                # TODO 异步处理split_chunks 和 embeddings工作
                chunk_docs = get_chuncks(tmp_file_path, embedding_factory, doc, ks, client, text_splitter)
                doc.chunk_size = len(chunk_docs)
                doc.gmt_modified = datetime.now()
                knowledge_document_dao.update_knowledge_document(doc)
                executor = CFG.SYSTEM_APP.get_component(
                    ComponentType.EXECUTOR_DEFAULT, ExecutorFactory
                ).create()
                executor.submit(self.async_doc_embedding, client, chunk_docs, doc)
            except Exception as ex:
                doc.status = SyncStatus.FAILED.name
                knowledge_document_dao.update_knowledge_document(doc)
                raise f"doc sync failed, {ex}"

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

            # delete file when embedding success.
            # if doc.doc_type == 'DOCUMENT':
            #     logger.info(f"start delete tmp_file {tmp_file_path}")
            #     delete_file(tmp_file_path)

        return True

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
        query = DocumentChunkEntity(
            document_id=request.doc_id,
        )
        chunks = document_chunk_dao.get_document_chunks(query, page=1, page_size=100)
        if len(chunks) == 0:
            raise Exception(f"can not found chunks for {request.doc_id}")
        from langchain.schema import Document

        chunk_docs = [Document(page_content=chunk.content) for chunk in chunks]
        return await self.async_document_summary(
            model_name=request.model_name,
            chunk_docs=chunk_docs,
            doc=document,
            conn_uid=request.conv_uid,
        )

    def update_knowledge_space(
        self, space_id: int, space_request: KnowledgeSpaceRequest
    ):
        """update knowledge space
        Args:
            - space_id: space id
            - space_request: KnowledgeSpaceRequest
        """
        knowledge_space_dao.update_knowledge_space(space_id, space_request)

    def delete_space(self, space_id: int):
        """delete knowledge space
        Args:
            - space_name: knowledge space name
        """

        spaces = knowledge_space_dao.get_knowledge_space(KnowledgeSpaceEntity(id=space_id))
        if len(spaces) == 0:
            raise f"Current Knowledge is not existed"
        space = spaces[0]
        vector_config = {}
        vector_config["vector_store_name"] = space.name + space.user_id
        vector_config["vector_store_type"] = CFG.VECTOR_STORE_TYPE
        vector_config["chroma_persist_path"] = KNOWLEDGE_UPLOAD_ROOT_PATH
        vector_client = VectorStoreConnector(
            vector_store_type=CFG.VECTOR_STORE_TYPE, ctx=vector_config
        )
        # delete vectors
        vector_client.delete_vector_name(space.name)
        document_query = KnowledgeDocumentEntity(space_id=space.id)
        # delete chunks
        documents = knowledge_document_dao.get_documents(document_query)
        for document in documents:
            document_chunk_dao.delete(document.id)
        # delete documents
        knowledge_document_dao.delete(document_query)
        # delete space
        return knowledge_space_dao.delete_knowledge_space(space)

    def delete_document(self, space_id: int, doc_name: str):
        """delete document
        Args:
            - space_name: knowledge space name
            - doc_name: doocument name
        """
        knowledge_spaces = knowledge_space_dao.get_knowledge_space(KnowledgeSpaceEntity(id=space_id))
        if len(knowledge_spaces) == 0:
            return None
        ks = knowledge_spaces[0]

        document_query = KnowledgeDocumentEntity(doc_name=doc_name, space_id=space_id)
        documents = knowledge_document_dao.get_documents(document_query)
        if len(documents) != 1:
            raise Exception(f"there are no or more than one document called {doc_name}")
        vector_ids = documents[0].vector_ids
        if vector_ids is not None:
            vector_config = {}
            vector_config["vector_store_name"] = ks.name + ks.user_id
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

    async def async_document_summary(self, model_name, chunk_docs, doc, conn_uid):
        """async document extract summary
        Args:
            - model_name: str
            - chunk_docs: List[Document]
            - doc: KnowledgeDocumentEntity
        """
        texts = [doc.page_content for doc in chunk_docs]
        from pilot.common.prompt_util import PromptHelper

        prompt_helper = PromptHelper()
        from pilot.scene.chat_knowledge.summary.prompt import prompt

        texts = prompt_helper.repack(prompt_template=prompt.template, text_chunks=texts)
        logger.info(
            f"async_document_summary, doc:{doc.doc_name}, chunk_size:{len(texts)}, begin generate summary"
        )
        space_context = self.get_space_context(doc.space)
        if space_context and space_context.get("summary"):
            summary = await self._mapreduce_extract_summary(
                docs=texts,
                model_name=model_name,
                max_iteration=int(space_context["summary"]["max_iteration"]),
                concurrency_limit=int(space_context["summary"]["concurrency_limit"]),
            )
        else:
            summary = await self._mapreduce_extract_summary(
                docs=texts, model_name=model_name
            )
        return await self._llm_extract_summary(summary, conn_uid, model_name)

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
            "summary": {
                "max_iteration": 5,
                "concurrency_limit": 3,
            },
        }
        context_template_string = json.dumps(context_template, indent=4)
        return context_template_string

    def get_space_context(self, space_name, user_id: str = None):
        """get space contect
        Args:
           - space_name: space name
        """
        request = KnowledgeSpaceRequest()
        request.name = space_name
        request.user_id = user_id
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
        from pilot.scene.base import ChatScene

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
        from pilot.openapi.api_v1.api_v1 import CHAT_FACTORY

        chat = await blocking_func_to_async(
            executor,
            CHAT_FACTORY.get_implementation,
            ChatScene.ExtractRefineSummary.value(),
            **{"chat_param": chat_param},
        )
        return chat

    async def _mapreduce_extract_summary(
        self,
        docs,
        model_name: str = None,
        max_iteration: int = 5,
        concurrency_limit: int = 3,
    ):
        """Extract summary by mapreduce mode
        map -> multi async call llm to generate summary
        reduce -> merge the summaries by map process
        Args:
            docs:List[str]
            model_name:model name str
            max_iteration:max iteration will call llm to summary
            concurrency_limit:the max concurrency threads to call llm
        Returns:
             Document: refine summary context document.
        """
        from pilot.scene.base import ChatScene
        from pilot.common.chat_util import llm_chat_response_nostream
        import uuid

        tasks = []
        if len(docs) == 1:
            return docs[0]
        else:
            max_iteration = max_iteration if len(docs) > max_iteration else len(docs)
            for doc in docs[0:max_iteration]:
                chat_param = {
                    "chat_session_id": uuid.uuid1(),
                    "current_user_input": "",
                    "select_param": doc,
                    "model_name": model_name,
                    "model_cache_enable": True,
                }
                tasks.append(
                    llm_chat_response_nostream(
                        ChatScene.ExtractSummary.value(), **{"chat_param": chat_param}
                    )
                )
            from pilot.common.chat_util import run_async_tasks

            summary_iters = await run_async_tasks(
                tasks=tasks, concurrency_limit=concurrency_limit
            )
            summary_iters = list(
                filter(
                    lambda content: "LLMServer Generate Error" not in content,
                    summary_iters,
                )
            )
            from pilot.common.prompt_util import PromptHelper
            from pilot.scene.chat_knowledge.summary.prompt import prompt

            prompt_helper = PromptHelper()
            summary_iters = prompt_helper.repack(
                prompt_template=prompt.template, text_chunks=summary_iters
            )
            return await self._mapreduce_extract_summary(
                summary_iters, model_name, max_iteration, concurrency_limit
            )


def get_chuncks(tmp_file_path, embedding_factory, doc, ks, client, text_splitter):
    """
      Split file into chunks, support zip file.
    """
    from pilot.embedding_engine.embedding_engine import EmbeddingEngine
    if tmp_file_path.endswith(".zip"):
        current_read_index: int = 0
        succeed_read_num: int = 0
        total_emd_number: int = 0
        task_result = {
            "current_embed_index": current_read_index,
            "total_emd_number": total_emd_number,
        }
        common_task_log = common_task_log_dao.create_common_task_log(
            CommonTaskLogEntity(
                type=CommonTaskType.ZIP_EMBEDDING_READ.value,
                state=CommonTaskState.RUNNING.value,
                param_idx=str(ks.name),
                task_result=json.dumps(task_result),
                msg="",
            )
        )
        if not common_task_log:
            raise f"create common task log error!"
        # 将下载的zip文件解压，然后通过一个异步任务拆解为多个docs -> chunk_docs
        # 解压文件并记录日志
        chunk_docs = []
        with zipfile.ZipFile(tmp_file_path, 'r') as zip_ref:
            zip_ref.extractall(KNOWLEDGE_UPLOAD_ROOT_PATH)

        log: str = f"\n{str(datetime.now())} --- unzip file {doc.doc_name} success."
        common_task_log.msg = common_task_log.msg + log
        common_task_log_dao.update_task_log(common_task_log)

        # 计算需要embeddings的文件数
        directory = os.path.join(KNOWLEDGE_UPLOAD_ROOT_PATH, doc.doc_name.replace(".zip", ""))
        total_emd_number = count_files(directory)
        interval: int = 100
        common_task_log.msg += f"\n{str(datetime.now())} --- total_emd_number is {total_emd_number}"
        common_task_log_dao.update_task_log(common_task_log)

        # 遍历文件夹将所有文件
        for root, dirs, files in os.walk(directory):
            for file in files:
                file_path = os.path.join(root, file)
                print(file_path)
                if os.path.isfile(file_path):
                    current_read_index += 1
                    # 每100个文件做一次记录
                    if current_read_index % interval == 0:
                        common_task_log.msg += f"\n{str(datetime.now())} --- curren readfile index is {current_read_index}"
                        common_task_log_dao.update_task_log(common_task_log)

                    try:
                        with open(file_path, 'r') as infile:
                            if "_identify_split" in file_path or "_identify_split" in tmp_file_path:
                                text_splitter = IdentifyTextSplitter([CFG.IDENTIFY_SPLIT])
                            client = EmbeddingEngine(
                                knowledge_source=file_path,
                                knowledge_type=doc.doc_type.upper(),
                                model_name=EMBEDDING_MODEL_CONFIG[CFG.EMBEDDING_MODEL],
                                vector_store_config={
                                    "vector_store_name": CFG.KS_EMBED_PREFIX + str(ks.id),
                                    "vector_store_type": CFG.VECTOR_STORE_TYPE,
                                },
                                text_splitter=text_splitter,
                                embedding_factory=embedding_factory,
                            )
                            sub_chunk_docs = client.read()
                            chunk_docs.extend(sub_chunk_docs)
                            succeed_read_num += 1
                    except Exception as ex:
                        print(f"文件{file_path}读取异常, {str(ex)}")
                        common_task_log.msg += f"\n{str(datetime.now())} --- embed file {file_path} failed, current_index={current_read_index}, {str(ex)}"
                        common_task_log_dao.update_task_log(common_task_log)
        if succeed_read_num == total_emd_number:
            common_task_log.state = CommonTaskState.FINISHED.value
        else:
            common_task_log.state = CommonTaskState.FAILED.value
            common_task_log.msg += f"\n succeed={succeed_read_num} total={total_emd_number}"
        common_task_log_dao.update_task_log(common_task_log)
    else:
        chunk_docs = client.read()
    return chunk_docs


def count_files(directory: str):
    """
      count files in folder.

      params:
        directory:
    """
    count: int = 0
    for root, dirs, files in os.walk(directory):
        for file in files:
            file_path = os.path.join(root, file)
            if os.path.isfile(file_path):
                count += 1

    return count
