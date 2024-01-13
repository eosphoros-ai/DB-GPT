import json
import os
from functools import reduce
from typing import Dict, List

from dbgpt._private.config import Config
from dbgpt.app.knowledge.chunk_db import DocumentChunkDao, DocumentChunkEntity
from dbgpt.app.knowledge.document_db import (
    KnowledgeDocumentDao,
    KnowledgeDocumentEntity,
)
from dbgpt.app.knowledge.service import KnowledgeService
from dbgpt.app.scene import BaseChat, ChatScene
from dbgpt.component import ComponentType
from dbgpt.configs.model_config import EMBEDDING_MODEL_CONFIG
from dbgpt.core import (
    ChatPromptTemplate,
    HumanPromptTemplate,
    MessagesPlaceholder,
    SystemPromptTemplate,
)
from dbgpt.model import DefaultLLMClient
from dbgpt.model.cluster import WorkerManagerFactory
from dbgpt.rag.retriever.rewrite import QueryRewrite
from dbgpt.util.tracer import trace

CFG = Config()


class ChatKnowledge(BaseChat):
    chat_scene: str = ChatScene.ChatKnowledge.value()
    """KBQA Chat Module"""

    def __init__(self, chat_param: Dict):
        """Chat Knowledge Module Initialization
        Args:
           - chat_param: Dict
            - chat_session_id: (str) chat session_id
            - current_user_input: (str) current user input
            - model_name:(str) llm model name
            - select_param:(str) space name
        """
        from dbgpt.rag.embedding.embedding_factory import EmbeddingFactory

        self.knowledge_space = chat_param["select_param"]
        chat_param["chat_mode"] = ChatScene.ChatKnowledge
        super().__init__(
            chat_param=chat_param,
        )
        self.space_context = self.get_space_context(self.knowledge_space)
        self.top_k = (
            CFG.KNOWLEDGE_SEARCH_TOP_SIZE
            if self.space_context is None
            else int(self.space_context["embedding"]["topk"])
        )
        self.recall_score = (
            CFG.KNOWLEDGE_SEARCH_RECALL_SCORE
            if self.space_context is None
            else float(self.space_context["embedding"]["recall_score"])
        )
        self.max_token = (
            CFG.KNOWLEDGE_SEARCH_MAX_TOKEN
            if self.space_context is None or self.space_context.get("prompt") is None
            else int(self.space_context["prompt"]["max_token"])
        )
        embedding_factory = CFG.SYSTEM_APP.get_component(
            "embedding_factory", EmbeddingFactory
        )
        from dbgpt.rag.retriever.embedding import EmbeddingRetriever
        from dbgpt.storage.vector_store.connector import VectorStoreConnector

        embedding_fn = embedding_factory.create(
            model_name=EMBEDDING_MODEL_CONFIG[CFG.EMBEDDING_MODEL]
        )
        from dbgpt.storage.vector_store.base import VectorStoreConfig

        config = VectorStoreConfig(name=self.knowledge_space, embedding_fn=embedding_fn)
        vector_store_connector = VectorStoreConnector(
            vector_store_type=CFG.VECTOR_STORE_TYPE,
            vector_store_config=config,
        )
        query_rewrite = None
        if CFG.KNOWLEDGE_SEARCH_REWRITE:
            query_rewrite = QueryRewrite(
                llm_client=self.llm_client,
                model_name=self.llm_model,
                language=CFG.LANGUAGE,
            )
        self.embedding_retriever = EmbeddingRetriever(
            top_k=self.top_k,
            vector_store_connector=vector_store_connector,
            query_rewrite=query_rewrite,
        )
        self.prompt_template.template_is_strict = False
        self.relations = None
        self.chunk_dao = DocumentChunkDao()
        document_dao = KnowledgeDocumentDao()
        documents = document_dao.get_documents(
            query=KnowledgeDocumentEntity(space=self.knowledge_space)
        )
        if len(documents) > 0:
            self.document_ids = [document.id for document in documents]

    async def stream_call(self):
        last_output = None
        async for output in super().stream_call():
            last_output = output
            yield output

        if (
            CFG.KNOWLEDGE_CHAT_SHOW_RELATIONS
            and last_output
            and type(self.relations) == list
            and len(self.relations) > 0
            and hasattr(last_output, "text")
        ):
            last_output.text = (
                last_output.text + "\n\nrelations:\n\n" + ",".join(self.relations)
            )
        reference = f"\n\n{self.parse_source_view(self.chunks_with_score)}"
        last_output = last_output + reference
        yield last_output

    def stream_call_reinforce_fn(self, text):
        """return reference"""
        return text + f"\n\n{self.parse_source_view(self.chunks_with_score)}"

    @trace()
    async def generate_input_values(self) -> Dict:
        if self.space_context and self.space_context.get("prompt"):
            # Not use template_define
            # self.prompt_template.template_define = self.space_context["prompt"]["scene"]
            # self.prompt_template.template = self.space_context["prompt"]["template"]
            # Replace the template with the prompt template
            self.prompt_template.prompt = ChatPromptTemplate(
                messages=[
                    SystemPromptTemplate.from_template(
                        self.space_context["prompt"]["template"]
                    ),
                    MessagesPlaceholder(variable_name="chat_history"),
                    HumanPromptTemplate.from_template("{question}"),
                ]
            )
        from dbgpt.util.chat_util import run_async_tasks

        tasks = [self.execute_similar_search(self.current_user_input)]
        candidates_with_scores = await run_async_tasks(tasks=tasks, concurrency_limit=1)
        candidates_with_scores = reduce(lambda x, y: x + y, candidates_with_scores)
        self.chunks_with_score = []
        if not candidates_with_scores or len(candidates_with_scores) == 0:
            print("no relevant docs to retrieve")
            context = "no relevant docs to retrieve"
        else:
            self.chunks_with_score = []
            for chunk in candidates_with_scores:
                chucks = self.chunk_dao.get_document_chunks(
                    query=DocumentChunkEntity(content=chunk.content),
                    document_ids=self.document_ids,
                )
                if len(chucks) > 0:
                    self.chunks_with_score.append((chucks[0], chunk.score))

            context = "\n".join([doc.content for doc in candidates_with_scores])
        self.relations = list(
            set(
                [
                    os.path.basename(str(d.metadata.get("source", "")))
                    for d in candidates_with_scores
                ]
            )
        )
        input_values = {
            "context": context,
            "question": self.current_user_input,
            "relations": self.relations,
        }
        return input_values

    def parse_source_view(self, chunks_with_score: List):
        """
        format knowledge reference view message to web
        <references title="'References'" references="'[{name:aa.pdf,chunks:[{10:text},{11:text}]},{name:bb.pdf,chunks:[{12,text}]}]'"> </references>
        """
        import xml.etree.ElementTree as ET

        references_ele = ET.Element("references")
        title = "References"
        references_ele.set("title", title)
        references_dict = {}
        for chunk, score in chunks_with_score:
            doc_name = chunk.doc_name
            if doc_name not in references_dict:
                references_dict[doc_name] = {
                    "name": doc_name,
                    "chunks": [
                        {
                            "id": chunk.id,
                            "content": chunk.content,
                            "meta_info": chunk.meta_info,
                            "recall_score": score,
                        }
                    ],
                }
            else:
                references_dict[doc_name]["chunks"].append(
                    {
                        "id": chunk.id,
                        "content": chunk.content,
                        "meta_info": chunk.meta_info,
                        "recall_score": score,
                    }
                )
        references_list = list(references_dict.values())
        references_ele.set("references", json.dumps(references_list))
        html = ET.tostring(references_ele, encoding="utf-8")
        reference = html.decode("utf-8")
        return reference.replace("\\n", "")

    @property
    def chat_type(self) -> str:
        return ChatScene.ChatKnowledge.value()

    def get_space_context(self, space_name):
        service = KnowledgeService()
        return service.get_space_context(space_name)

    async def execute_similar_search(self, query):
        """execute similarity search"""
        return await self.embedding_retriever.aretrieve_with_scores(
            query, self.recall_score
        )
