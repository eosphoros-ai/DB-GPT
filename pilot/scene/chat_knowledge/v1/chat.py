import json
import os
from typing import Dict, List

from pilot.component import ComponentType
from pilot.scene.base_chat import BaseChat
from pilot.scene.base import ChatScene
from pilot.configs.config import Config

from pilot.configs.model_config import (
    KNOWLEDGE_UPLOAD_ROOT_PATH,
    EMBEDDING_MODEL_CONFIG,
)

from pilot.scene.chat_knowledge.v1.prompt import prompt
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
        self.max_token = (
            CFG.KNOWLEDGE_SEARCH_MAX_TOKEN
            if self.space_context is None
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
        reference = f"\n\n{self.parse_source_view(self.sources)}"
        last_output = last_output + reference
        yield last_output

    def knowledge_reference_call(self, text):
        """return reference"""
        return text + f"\n\n{self.parse_source_view(self.sources)}"

    @trace()
    async def generate_input_values(self) -> Dict:
        if self.space_context:
            self.prompt_template.template_define = self.space_context["prompt"]["scene"]
            self.prompt_template.template = self.space_context["prompt"]["template"]
        docs = await blocking_func_to_async(
            self._executor,
            self.knowledge_embedding_client.similar_search,
            self.current_user_input,
            self.top_k,
        )
        self.sources = self.merge_by_key(
            list(map(lambda doc: doc.metadata, docs)), "source"
        )

        if not docs or len(docs) == 0:
            print("no relevant docs to retrieve")
            context = "no relevant docs to retrieve"
            # raise ValueError(
            #     "you have no knowledge space, please add your knowledge space"
            # )
        else:
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

    def parse_source_view(self, sources: List):
        """
        build knowledge reference view message to web
        {
            "title":"References",
            "references":[{
                "name":"aa.pdf",
                "pages":["1","2","3"]
            }]
        }
        """
        references = {"title": "References", "references": []}
        for item in sources:
            reference = {}
            source = item["source"] if "source" in item else ""
            reference["name"] = source
            pages = item["pages"] if "pages" in item else []
            if len(pages) > 0:
                reference["pages"] = pages
            references["references"].append(reference)
        html = (
            f"""<references>{json.dumps(references, ensure_ascii=False)}</references>"""
        )
        return html

    def merge_by_key(self, data, key):
        result = {}
        for item in data:
            item_key = os.path.basename(item.get(key))
            if item_key in result:
                if "pages" in result[item_key] and "page" in item:
                    result[item_key]["pages"].append(str(item["page"]))
                elif "page" in item:
                    result[item_key]["pages"] = [
                        result[item_key]["pages"],
                        str(item["page"]),
                    ]
            else:
                if "page" in item:
                    result[item_key] = {
                        "source": item_key,
                        "pages": [str(item["page"])],
                    }
                else:
                    result[item_key] = {"source": item_key}
        return list(result.values())

    @property
    def chat_type(self) -> str:
        return ChatScene.ChatKnowledge.value()

    def get_space_context(self, space_name):
        service = KnowledgeService()
        return service.get_space_context(space_name)
