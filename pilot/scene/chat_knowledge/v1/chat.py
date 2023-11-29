import json
import os
from functools import reduce
from typing import Dict, List

from pilot.scene.base_chat import BaseChat
from pilot.scene.base import ChatScene
from pilot.configs.config import Config

from pilot.configs.model_config import (
    EMBEDDING_MODEL_CONFIG,
)

from pilot.scene.chat_knowledge.v1.prompt import prompt
from pilot.server.knowledge.chunk_db import DocumentChunkDao, DocumentChunkEntity
from pilot.server.knowledge.document_db import (
    KnowledgeDocumentDao,
    KnowledgeDocumentEntity,
)
from pilot.server.knowledge.service import KnowledgeService
from pilot.utils.executor_utils import blocking_func_to_async
from pilot.utils.tracer import root_tracer, trace

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
        from pilot.embedding_engine.embedding_engine import EmbeddingEngine
        from pilot.embedding_engine.embedding_factory import EmbeddingFactory

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
        vector_store_config = {
            "vector_store_name": self.knowledge_space,
            "vector_store_type": CFG.VECTOR_STORE_TYPE,
        }
        embedding_factory = CFG.SYSTEM_APP.get_component(
            "embedding_factory", EmbeddingFactory
        )
        self.knowledge_embedding_client = EmbeddingEngine(
            model_name=EMBEDDING_MODEL_CONFIG[CFG.EMBEDDING_MODEL],
            vector_store_config=vector_store_config,
            embedding_factory=embedding_factory,
        )
        self.prompt_template.template_is_strict = False
        self.chunk_dao = DocumentChunkDao()
        document_dao = KnowledgeDocumentDao()
        documents = document_dao.get_documents(
            query=KnowledgeDocumentEntity(space=self.knowledge_space)
        )
        if len(documents) > 0:
            self.document_ids = [document.id for document in documents]

    async def stream_call(self):
        input_values = await self.generate_input_values()
        # Source of knowledge file
        relations = input_values.get("relations")
        last_output = None
        async for output in super().stream_call():
            last_output = output
            yield output

        if (
            CFG.KNOWLEDGE_CHAT_SHOW_RELATIONS
            and last_output
            and type(relations) == list
            and len(relations) > 0
            and hasattr(last_output, "text")
        ):
            last_output.text = (
                last_output.text + "\n\nrelations:\n\n" + ",".join(relations)
            )
        reference = f"\n\n{self.parse_source_view(self.chunks)}"
        last_output = last_output + reference
        yield last_output

    def stream_call_reinforce_fn(self, text):
        """return reference"""
        return text + f"\n\n{self.parse_source_view(self.chunks)}"

    @trace()
    async def generate_input_values(self) -> Dict:
        if self.space_context and self.space_context.get("prompt"):
            self.prompt_template.template_define = self.space_context["prompt"]["scene"]
            self.prompt_template.template = self.space_context["prompt"]["template"]
        from pilot.rag.retriever.reinforce import QueryReinforce

        # query reinforce, get similar queries
        query_reinforce = QueryReinforce(
            query=self.current_user_input, model_name=self.llm_model
        )
        queries = await query_reinforce.rewrite()
        queries.append(self.current_user_input)
        from pilot.common.chat_util import run_async_tasks

        # similarity search from vector db
        tasks = [self.execute_similar_search(query) for query in queries]
        docs_with_scores = await run_async_tasks(tasks=tasks)
        candidates_with_scores = reduce(lambda x, y: x + y, docs_with_scores)
        # candidates document rerank
        from pilot.rag.retriever.rerank import DefaultRanker

        ranker = DefaultRanker(self.top_k)
        docs = ranker.rank(candidates_with_scores)
        if not docs or len(docs) == 0:
            print("no relevant docs to retrieve")
            context = "no relevant docs to retrieve"
        else:
            self.chunks = [
                self.chunk_dao.get_document_chunks(
                    query=DocumentChunkEntity(content=d.page_content),
                    document_ids=self.document_ids,
                )[0]
                for d in docs
            ]

            context = [d.page_content for d in docs]

        context = context[: self.max_token]
        relations = list(
            set([os.path.basename(str(d.metadata.get("source", ""))) for d in docs])
        )
        input_values = {
            "context": context,
            "question": self.current_user_input,
            "relations": relations,
        }
        return input_values

    def parse_source_view(self, chunks: List):
        """
        format knowledge reference view message to web
        <references title="'References'" references="'[{name:aa.pdf,chunks:[{10:text},{11:text}]},{name:bb.pdf,chunks:[{12,text}]}]'"> </references>
        """
        title = "References"
        references_dict = {}
        for chunk in chunks:
            doc_name = chunk.doc_name
            if doc_name not in references_dict:
                references_dict[doc_name] = {
                    "name": doc_name,
                    "chunks": [
                        {
                            "id": chunk.id,
                            "content": chunk.content,
                            "metadata": chunk.meta_info,
                        }
                    ],
                }
            else:
                references_dict[doc_name]["chunks"].append(
                    {
                        "id": chunk.id,
                        "content": chunk.content,
                        "metadata": chunk.meta_info,
                    }
                )
        references_list = list(references_dict.values())
        html = f"""<references title="{title}" references="{json.dumps(references_list, ensure_ascii=False)}"></references>"""
        return html

    @property
    def chat_type(self) -> str:
        return ChatScene.ChatKnowledge.value()

    def get_space_context(self, space_name):
        service = KnowledgeService()
        return service.get_space_context(space_name)

    async def execute_similar_search(self, query):
        """execute similarity search"""
        return await blocking_func_to_async(
            self._executor,
            self.knowledge_embedding_client.similar_search_with_scores,
            query,
            self.top_k,
            self.recall_score,
        )
