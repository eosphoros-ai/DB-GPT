from typing import Dict, Optional, List
from dataclasses import dataclass
import datetime
import os
from dbgpt.core.awel import MapOperator
from dbgpt.core.interface.prompt import PromptTemplate
from dbgpt._private.config import Config
from dbgpt.app.scene import ChatScene
from dbgpt.core.interface.message import OnceConversation
from dbgpt.core.interface.message import ModelMessage, ModelMessageRoleType


from dbgpt.storage.chat_history.base import BaseChatHistoryMemory
from dbgpt.storage.chat_history.chat_hisotry_factory import ChatHistory

# TODO move global config
CFG = Config()


@dataclass
class ChatContext:
    current_user_input: str
    model_name: Optional[str]
    chat_session_id: Optional[str] = None
    select_param: Optional[str] = None
    chat_scene: Optional[ChatScene] = ChatScene.ChatNormal
    prompt_template: Optional[PromptTemplate] = None
    chat_retention_rounds: Optional[int] = 0
    history_storage: Optional[BaseChatHistoryMemory] = None
    history_manager: Optional["ChatHistoryManager"] = None
    # The input values for prompt template
    input_values: Optional[Dict] = None
    echo: Optional[bool] = False

    def build_model_payload(self) -> Dict:
        if not self.input_values:
            raise ValueError("The input value can't be empty")
        llm_messages = self.history_manager._new_chat(self.input_values)
        return {
            "model": self.model_name,
            "prompt": "",
            "messages": llm_messages,
            "temperature": float(self.prompt_template.temperature),
            "max_new_tokens": int(self.prompt_template.max_new_tokens),
            "echo": self.echo,
        }


class ChatHistoryManager:
    def __init__(
        self,
        chat_ctx: ChatContext,
        prompt_template: PromptTemplate,
        history_storage: BaseChatHistoryMemory,
        chat_retention_rounds: Optional[int] = 0,
    ) -> None:
        self._chat_ctx = chat_ctx
        self.chat_retention_rounds = chat_retention_rounds
        self.current_message: OnceConversation = OnceConversation(
            chat_ctx.chat_scene.value()
        )
        self.prompt_template = prompt_template
        self.history_storage: BaseChatHistoryMemory = history_storage
        self.history_message: List[OnceConversation] = history_storage.messages()
        self.current_message.model_name = chat_ctx.model_name
        if chat_ctx.select_param:
            if len(chat_ctx.chat_scene.param_types()) > 0:
                self.current_message.param_type = chat_ctx.chat_scene.param_types()[0]
            self.current_message.param_value = chat_ctx.select_param

    def _new_chat(self, input_values: Dict) -> List[ModelMessage]:
        self.current_message.chat_order = len(self.history_message) + 1
        self.current_message.add_user_message(
            self._chat_ctx.current_user_input, check_duplicate_type=True
        )
        self.current_message.start_date = datetime.datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        self.current_message.tokens = 0
        if self.prompt_template.template:
            current_prompt = self.prompt_template.format(**input_values)
            self.current_message.add_system_message(current_prompt)
        return self._generate_llm_messages()

    def _generate_llm_messages(self) -> List[ModelMessage]:
        from dbgpt.app.scene.base_chat import (
            _load_system_message,
            _load_example_messages,
            _load_history_messages,
            _load_user_message,
        )

        messages = []
        ### Load scene setting or character definition as system message
        if self.prompt_template.template_define:
            messages.append(
                ModelMessage(
                    role=ModelMessageRoleType.SYSTEM,
                    content=self.prompt_template.template_define,
                )
            )
        ### Load prompt
        messages += _load_system_message(
            self.current_message, self.prompt_template, str_message=False
        )
        ### Load examples
        messages += _load_example_messages(self.prompt_template, str_message=False)

        ### Load History
        messages += _load_history_messages(
            self.prompt_template,
            self.history_message,
            self.chat_retention_rounds,
            str_message=False,
        )

        ### Load User Input
        messages += _load_user_message(
            self.current_message, self.prompt_template, str_message=False
        )
        return messages


class PromptManagerOperator(MapOperator[ChatContext, ChatContext]):
    def __init__(self, prompt_template: PromptTemplate = None, **kwargs):
        super().__init__(**kwargs)
        self._prompt_template = prompt_template

    async def map(self, input_value: ChatContext) -> ChatContext:
        if not self._prompt_template:
            self._prompt_template: PromptTemplate = (
                CFG.prompt_template_registry.get_prompt_template(
                    input_value.chat_scene.value(),
                    language=CFG.LANGUAGE,
                    model_name=input_value.model_name,
                    proxyllm_backend=CFG.PROXYLLM_BACKEND,
                )
            )
        input_value.prompt_template = self._prompt_template
        return input_value


class ChatHistoryStorageOperator(MapOperator[ChatContext, ChatContext]):
    def __init__(self, history: BaseChatHistoryMemory = None, **kwargs):
        super().__init__(**kwargs)
        self._history = history

    async def map(self, input_value: ChatContext) -> ChatContext:
        if self._history:
            return self._history
        chat_history_fac = ChatHistory()
        input_value.history_storage = chat_history_fac.get_store_instance(
            input_value.chat_session_id
        )
        return input_value


class ChatHistoryOperator(MapOperator[ChatContext, ChatContext]):
    def __init__(self, history: BaseChatHistoryMemory = None, **kwargs):
        super().__init__(**kwargs)
        self._history = history

    async def map(self, input_value: ChatContext) -> ChatContext:
        history_storage = self._history or input_value.history_storage
        if not history_storage:
            from dbgpt.storage.chat_history.store_type.mem_history import (
                MemHistoryMemory,
            )

            history_storage = MemHistoryMemory(input_value.chat_session_id)
            input_value.history_storage = history_storage
        input_value.history_manager = ChatHistoryManager(
            input_value,
            input_value.prompt_template,
            history_storage,
            input_value.chat_retention_rounds,
        )
        return input_value


class EmbeddingEngingOperator(MapOperator[ChatContext, ChatContext]):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    async def map(self, input_value: ChatContext) -> ChatContext:
        from dbgpt.configs.model_config import EMBEDDING_MODEL_CONFIG
        from dbgpt.rag.embedding_engine.embedding_engine import EmbeddingEngine
        from dbgpt.rag.embedding_engine.embedding_factory import EmbeddingFactory

        # TODO, decompose the current operator into some atomic operators
        knowledge_space = input_value.select_param
        vector_store_config = {
            "vector_store_name": knowledge_space,
            "vector_store_type": CFG.VECTOR_STORE_TYPE,
        }
        embedding_factory = self.system_app.get_component(
            "embedding_factory", EmbeddingFactory
        )
        knowledge_embedding_client = EmbeddingEngine(
            model_name=EMBEDDING_MODEL_CONFIG[CFG.EMBEDDING_MODEL],
            vector_store_config=vector_store_config,
            embedding_factory=embedding_factory,
        )
        space_context = await self._get_space_context(knowledge_space)
        top_k = (
            CFG.KNOWLEDGE_SEARCH_TOP_SIZE
            if space_context is None
            else int(space_context["embedding"]["topk"])
        )
        max_token = (
            CFG.KNOWLEDGE_SEARCH_MAX_TOKEN
            if space_context is None or space_context.get("prompt") is None
            else int(space_context["prompt"]["max_token"])
        )
        input_value.prompt_template.template_is_strict = False
        if space_context and space_context.get("prompt"):
            input_value.prompt_template.template_define = space_context["prompt"][
                "scene"
            ]
            input_value.prompt_template.template = space_context["prompt"]["template"]

        docs = await self.blocking_func_to_async(
            knowledge_embedding_client.similar_search,
            input_value.current_user_input,
            top_k,
        )
        if not docs or len(docs) == 0:
            print("no relevant docs to retrieve")
            context = "no relevant docs to retrieve"
        else:
            context = [d.page_content for d in docs]
        context = context[:max_token]
        relations = list(
            set([os.path.basename(str(d.metadata.get("source", ""))) for d in docs])
        )
        input_value.input_values = {
            "context": context,
            "question": input_value.current_user_input,
            "relations": relations,
        }
        return input_value

    async def _get_space_context(self, space_name):
        from dbgpt.app.knowledge.service import KnowledgeService

        service = KnowledgeService()
        return await self.blocking_func_to_async(service.get_space_context, space_name)


class BaseChatOperator(MapOperator[ChatContext, Dict]):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    async def map(self, input_value: ChatContext) -> Dict:
        return input_value.build_model_payload()
