import json
import os
from functools import reduce
from typing import Dict, List, Type

from dbgpt import SystemApp
from dbgpt.core import (
    ChatPromptTemplate,
    HumanPromptTemplate,
    MessagesPlaceholder,
    SystemPromptTemplate,
)
from dbgpt.core.interface.llm import ModelOutput
from dbgpt.rag.retriever.rerank import RerankEmbeddingsRanker
from dbgpt.rag.retriever.rewrite import QueryRewrite
from dbgpt.util.tracer import root_tracer, trace
from dbgpt_app.knowledge.request.request import KnowledgeSpaceRequest
from dbgpt_app.knowledge.service import KnowledgeService
from dbgpt_app.scene import BaseChat, ChatScene
from dbgpt_app.scene.base_chat import ChatParam
from dbgpt_app.scene.chat_knowledge.v1.config import ChatKnowledgeConfig
from dbgpt_serve.rag.models.chunk_db import DocumentChunkDao, DocumentChunkEntity
from dbgpt_serve.rag.models.document_db import (
    KnowledgeDocumentDao,
    KnowledgeDocumentEntity,
)
from dbgpt_serve.rag.retriever.knowledge_space import KnowledgeSpaceRetriever


class ChatKnowledge(BaseChat):
    """KBQA Chat Module"""

    chat_scene: str = ChatScene.ChatKnowledge.value()

    @classmethod
    def param_class(cls) -> Type[ChatKnowledgeConfig]:
        return ChatKnowledgeConfig

    def __init__(self, chat_param: ChatParam, system_app: SystemApp):
        """Chat Knowledge Module Initialization
        Args:
           - chat_param: Dict
            - chat_session_id: (str) chat session_id
            - current_user_input: (str) current user input
            - model_name:(str) llm model name
            - select_param:(str) space name
        """
        from dbgpt.rag.embedding.embedding_factory import RerankEmbeddingFactory

        self.curr_config = chat_param.real_app_config(ChatKnowledgeConfig)
        self.knowledge_space = chat_param.select_param
        super().__init__(chat_param=chat_param, system_app=system_app)
        from dbgpt_serve.rag.models.models import (
            KnowledgeSpaceDao,
        )

        space_dao = KnowledgeSpaceDao()
        space = space_dao.get_one({"name": self.knowledge_space})
        if not space:
            space = space_dao.get_one({"id": self.knowledge_space})
        if not space:
            raise Exception(f"have not found knowledge space:{self.knowledge_space}")
        self.rag_config = self.app_config.rag
        self.space_context = self.get_space_context(space.name)

        self.top_k = self.get_knowledge_search_top_size(space.name)
        self.recall_score = self.get_similarity_score_threshold()

        query_rewrite = None
        if self.rag_config.query_rewrite:
            query_rewrite = QueryRewrite(
                llm_client=self.llm_client,
                model_name=self.llm_model,
                language=self.system_app.config.configs.get(
                    "dbgpt.app.global.language"
                ),
            )
        reranker = None
        retriever_top_k = self.top_k
        if self.model_config.default_reranker:
            rerank_embeddings = RerankEmbeddingFactory.get_instance(
                self.system_app
            ).create()
            rerank_top_k = self.curr_config.knowledge_retrieve_rerank_top_k
            if not rerank_top_k:
                rerank_top_k = self.rag_config.rerank_top_k
            reranker = RerankEmbeddingsRanker(rerank_embeddings, topk=rerank_top_k)
            if retriever_top_k < rerank_top_k or retriever_top_k < 20:
                # We use reranker, so if the top_k is less than 20,
                # we need to set it to 20
                retriever_top_k = max(rerank_top_k, 20)
        self._space_retriever = KnowledgeSpaceRetriever(
            space_id=space.id,
            embedding_model=self.model_config.default_embedding,
            top_k=retriever_top_k,
            query_rewrite=query_rewrite,
            rerank=reranker,
            llm_model=self.llm_model,
            system_app=self.system_app,
        )

        self.prompt_template.template_is_strict = False
        self.relations = None
        self.chunk_dao = DocumentChunkDao()
        document_dao = KnowledgeDocumentDao()
        documents = document_dao.get_documents(
            query=KnowledgeDocumentEntity(space=space.name)
        )
        if len(documents) > 0:
            self.document_ids = [document.id for document in documents]

    async def _handle_final_output(
        self, final_output: ModelOutput, incremental: bool = False
    ):
        reference = f"\n\n{self.parse_source_view(self.chunks_with_score)}"
        view_message = final_output.text
        view_message = view_message + reference

        if final_output.has_thinking and not incremental:
            view_message = final_output.gen_text_with_thinking(new_text=view_message)
        return final_output.text, view_message

    def stream_call_reinforce_fn(self, text):
        """return reference"""
        return text + f"\n\n{self.parse_source_view(self.chunks_with_score)}"

    @trace()
    async def generate_input_values(self) -> Dict:
        if self.space_context and self.space_context.get("prompt"):
            # Not use template_define
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
        """  # noqa
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
        references_ele.set(
            "references", json.dumps(references_list, ensure_ascii=False)
        )
        html = ET.tostring(references_ele, encoding="utf-8")
        reference = html.decode("utf-8")
        return reference.replace("\\n", "")

    def get_space_context_by_id(self, space_id):
        service = KnowledgeService()
        return service.get_space_context_by_space_id(space_id)

    def get_space_context(self, space_name):
        service = KnowledgeService()
        return service.get_space_context(space_name)

    def get_knowledge_search_top_size(self, space_name) -> int:
        if self.space_context:
            return int(self.space_context["embedding"]["topk"])

        service = KnowledgeService()
        request = KnowledgeSpaceRequest(name=space_name)
        spaces = service.get_knowledge_space(request)
        if len(spaces) == 1:
            from dbgpt_ext.storage import __knowledge_graph__ as graph_storages

            if spaces[0].vector_type in graph_storages:
                return self.rag_config.kg_chunk_search_top_k
        if self.curr_config.knowledge_retrieve_top_k:
            return self.curr_config.knowledge_retrieve_top_k

        return self.rag_config.similarity_top_k

    def get_similarity_score_threshold(self):
        if self.space_context:
            return float(self.space_context["embedding"]["recall_score"])
        if self.curr_config.similarity_score_threshold >= 0:
            return self.curr_config.similarity_score_threshold
        return self.rag_config.similarity_score_threshold

    async def execute_similar_search(self, query):
        """execute similarity search"""
        with root_tracer.start_span(
            "execute_similar_search", metadata={"query": query}
        ):
            return await self._space_retriever.aretrieve_with_scores(
                query, self.recall_score
            )
