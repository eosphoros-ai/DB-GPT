"""Implementation of Andrew Ng Translation Agent: https://github.com/andrewyng/translation-agent"""

import logging
import os
from abc import ABC
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, Iterable, List, Optional, Type, cast

from dbgpt.core import (
    ChatPromptTemplate,
    HumanPromptTemplate,
    LLMClient,
    ModelMessage,
    ModelRequest,
    SystemPromptTemplate,
)
from dbgpt.core.awel import (
    DAG,
    BranchFunc,
    BranchOperator,
    BranchTaskType,
    JoinOperator,
    MapOperator,
    is_empty_data,
)
from dbgpt.core.awel.flow import IOField, OperatorCategory, Parameter, ViewMetadata
from dbgpt.core.awel.trigger.http_trigger import (
    CommonLLMHttpRequestBody,
    CommonLLMHttpTrigger,
)
from dbgpt.model.operators import MixinLLMOperator
from dbgpt.rag.text_splitter.text_splitter import RecursiveCharacterTextSplitter

logger = logging.getLogger(__name__)

_ONE_CHUNK_INITIAL_TRANSLATION_SYSTEM_PROMPT = (
    "You are an expert linguist, "
    "specializing in translation from {source_lang} to {target_lang}."
)

_ONE_CHUNK_INITIAL_TRANSLATION_PROMPT = """This is an {source_lang} to {target_lang} \
translation, please provide the {target_lang} translation for this text. \
Do not provide any explanations or text apart from the translation.
{source_lang}: {source_text}

{target_lang}:"""

_ONE_CHUNK_REFLECTION_SYSTEM_PROMPT = """You are an expert linguist specializing in \
translation from {source_lang} to {target_lang}. You will be provided with a source \
text and its translation and your goal is to improve the translation."""

_ONE_CHUNK_REFLECTION_COUNTRY_PROMPT = """Your task is to carefully read a source text \
and a translation from {source_lang} to {target_lang}, and then give constructive \
criticism and helpful suggestions to improve the translation. The final style and tone \
of the translation should match the style of {target_lang} colloquially spoken in \
{country}.

The source text and initial translation, delimited by XML tags \
<SOURCE_TEXT></SOURCE_TEXT> and <TRANSLATION></TRANSLATION>, are as follows:

<SOURCE_TEXT>
{source_text}
</SOURCE_TEXT>

<TRANSLATION>
{translation_1}
</TRANSLATION>

When writing suggestions, pay attention to whether there are ways to improve the translation's \n\
(i) accuracy (by correcting errors of addition, mistranslation, omission, or untranslated text),\n\
(ii) fluency (by applying {target_lang} grammar, spelling and punctuation rules, and ensuring there are no unnecessary repetitions),\n\
(iii) style (by ensuring the translations reflect the style of the source text and takes into account any cultural context),\n\
(iv) terminology (by ensuring terminology use is consistent and reflects the source text domain; and by only ensuring you use equivalent idioms {target_lang}).\n\

Write a list of specific, helpful and constructive suggestions for improving the translation.
Each suggestion should address one specific part of the translation.
Output only the suggestions and nothing else."""

_ONE_CHUNK_REFLECTION_PROMPT = """Your task is to carefully read a source text and a \
translation from {source_lang} to {target_lang}, and then give constructive criticism \
and helpful suggestions to improve the translation. \

The source text and initial translation, delimited by XML tags \
<SOURCE_TEXT></SOURCE_TEXT> and <TRANSLATION></TRANSLATION>, are as follows:

<SOURCE_TEXT>
{source_text}
</SOURCE_TEXT>

<TRANSLATION>
{translation_1}
</TRANSLATION>

When writing suggestions, pay attention to whether there are ways to improve the translation's \n\
(i) accuracy (by correcting errors of addition, mistranslation, omission, or untranslated text),\n\
(ii) fluency (by applying {target_lang} grammar, spelling and punctuation rules, and ensuring there are no unnecessary repetitions),\n\
(iii) style (by ensuring the translations reflect the style of the source text and takes into account any cultural context),\n\
(iv) terminology (by ensuring terminology use is consistent and reflects the source text domain; and by only ensuring you use equivalent idioms {target_lang}).\n\

Write a list of specific, helpful and constructive suggestions for improving the translation.
Each suggestion should address one specific part of the translation.
Output only the suggestions and nothing else."""

_ONE_CHUNK_IMPROVE_TRANSLATION_SYSTEM_PROMPT = """You are an expert linguist, \
specializing in translation editing from {source_lang} to {target_lang}."""

_ONE_CHUNK_IMPROVE_TRANSLATION_PROMPT = """Your task is to carefully read, then edit, \
a translation from {source_lang} to {target_lang}, taking into account a list of expert \
suggestions and constructive criticisms.

The source text, the initial translation, and the expert linguist suggestions are \
delimited by XML tags <SOURCE_TEXT></SOURCE_TEXT>, <TRANSLATION></TRANSLATION> and \
<EXPERT_SUGGESTIONS></EXPERT_SUGGESTIONS> as follows:

<SOURCE_TEXT>
{source_text}
</SOURCE_TEXT>

<TRANSLATION>
{translation_1}
</TRANSLATION>

<EXPERT_SUGGESTIONS>
{reflection}
</EXPERT_SUGGESTIONS>

Please take into account the expert suggestions when editing the translation. Edit the \
translation by ensuring:

(i) accuracy (by correcting errors of addition, mistranslation, omission, or untranslated text),
(ii) fluency (by applying {target_lang} grammar, spelling and punctuation rules and ensuring there are no unnecessary repetitions), \
(iii) style (by ensuring the translations reflect the style of the source text)
(iv) terminology (inappropriate for context, inconsistent use), or
(v) other errors.

Output only the new translation and nothing else."""


_MULTI_CHUNK_INITIAL_TRANSLATION_SYSTEM_PROMPT = """You are an expert linguist, \
specializing in translation from {source_lang} to {target_lang}."""

_MULTI_CHUNK_INITIAL_TRANSLATION_PROMPT = """Your task is provide a professional \
translation from {source_lang} to {target_lang} of PART of a text.

The source text is below, delimited by XML tags <SOURCE_TEXT> and </SOURCE_TEXT>. \
Translate only the part within the source text
delimited by <TRANSLATE_THIS> and </TRANSLATE_THIS>. You can use the rest of the source\
 text as context, but do not translate any of the other text. Do not output anything \
 other than the translation of the indicated part of the text.

<SOURCE_TEXT>
{tagged_text}
</SOURCE_TEXT>

To reiterate, you should translate only this part of the text, shown here again between\
 <TRANSLATE_THIS> and </TRANSLATE_THIS>:
<TRANSLATE_THIS>
{chunk_to_translate}
</TRANSLATE_THIS>

Output only the translation of the portion you are asked to translate, and nothing else.
"""

_MULTI_CHUNK_REFLECTION_SYSTEM_PROMPT = """You are an expert linguist specializing in \
translation from {source_lang} to {target_lang}. You will be provided with a source \
text and its translation and your goal is to improve the translation."""
_MULTI_CHUNK_REFLECTION_COUNTRY_PROMPT = """Your task is to carefully read a source text and \
part of a translation of that text from {source_lang} to {target_lang}, and then give \
constructive criticism and helpful suggestions for improving the translation.
The final style and tone of the translation should match the style of {target_lang} \
colloquially spoken in {country}.

The source text is below, delimited by XML tags <SOURCE_TEXT> and </SOURCE_TEXT>, and \
the part that has been translated
is delimited by <TRANSLATE_THIS> and </TRANSLATE_THIS> within the source text. You can \
use the rest of the source text
as context for critiquing the translated part.

<SOURCE_TEXT>
{tagged_text}
</SOURCE_TEXT>

To reiterate, only part of the text is being translated, shown here again between \
<TRANSLATE_THIS> and </TRANSLATE_THIS>:
<TRANSLATE_THIS>
{chunk_to_translate}
</TRANSLATE_THIS>

The translation of the indicated part, delimited below by <TRANSLATION> and \
</TRANSLATION>, is as follows:
<TRANSLATION>
{translation_1_chunk}
</TRANSLATION>

When writing suggestions, pay attention to whether there are ways to improve the translation's:\n\
(i) accuracy (by correcting errors of addition, mistranslation, omission, or untranslated text),\n\
(ii) fluency (by applying {target_lang} grammar, spelling and punctuation rules, and ensuring there are no unnecessary repetitions),\n\
(iii) style (by ensuring the translations reflect the style of the source text and takes into account any cultural context),\n\
(iv) terminology (by ensuring terminology use is consistent and reflects the source text domain; and by only ensuring you use equivalent idioms {target_lang}).\n\

Write a list of specific, helpful and constructive suggestions for improving the translation.
Each suggestion should address one specific part of the translation.
Output only the suggestions and nothing else."""

_MULTI_CHUNK_REFLECTION_PROMPT = """Your task is to carefully read a source text and \
part of a translation of that text from {source_lang} to {target_lang}, and then give \
constructive criticism and helpful suggestions for improving the translation.

The source text is below, delimited by XML tags <SOURCE_TEXT> and </SOURCE_TEXT>, and \
the part that has been translated
is delimited by <TRANSLATE_THIS> and </TRANSLATE_THIS> within the source text. You can \
use the rest of the source text
as context for critiquing the translated part.

<SOURCE_TEXT>
{tagged_text}
</SOURCE_TEXT>

To reiterate, only part of the text is being translated, shown here again between \
<TRANSLATE_THIS> and </TRANSLATE_THIS>:
<TRANSLATE_THIS>
{chunk_to_translate}
</TRANSLATE_THIS>

The translation of the indicated part, delimited below by <TRANSLATION> and \
</TRANSLATION>, is as follows:
<TRANSLATION>
{translation_1_chunk}
</TRANSLATION>

When writing suggestions, pay attention to whether there are ways to improve the translation's:\n\
(i) accuracy (by correcting errors of addition, mistranslation, omission, or untranslated text),\n\
(ii) fluency (by applying {target_lang} grammar, spelling and punctuation rules, and ensuring there are no unnecessary repetitions),\n\
(iii) style (by ensuring the translations reflect the style of the source text and takes into account any cultural context),\n\
(iv) terminology (by ensuring terminology use is consistent and reflects the source text domain; and by only ensuring you use equivalent idioms {target_lang}).\n\

Write a list of specific, helpful and constructive suggestions for improving the translation.
Each suggestion should address one specific part of the translation.
Output only the suggestions and nothing else."""

_MULTI_CHUNK_IMPROVE_TRANSLATION_SYSTEM_PROMPT = """You are an expert linguist, \
specializing in translation editing from {source_lang} to {target_lang}."""
_MULTI_CHUNK_IMPROVE_TRANSLATION_PROMPT = """Your task is to carefully read, then \
improve, a translation from {source_lang} to {target_lang}, taking into
account a set of expert suggestions and constructive critisms. Below, the source text, \
initial translation, and expert suggestions are provided.

The source text is below, delimited by XML tags <SOURCE_TEXT> and </SOURCE_TEXT>, and \
the part that has been translated
is delimited by <TRANSLATE_THIS> and </TRANSLATE_THIS> within the source text. You can \
use the rest of the source text
as context, but need to provide a translation only of the part indicated by \
<TRANSLATE_THIS> and </TRANSLATE_THIS>.

<SOURCE_TEXT>
{tagged_text}
</SOURCE_TEXT>

To reiterate, only part of the text is being translated, shown here again between \
<TRANSLATE_THIS> and </TRANSLATE_THIS>:
<TRANSLATE_THIS>
{chunk_to_translate}
</TRANSLATE_THIS>

The translation of the indicated part, delimited below by <TRANSLATION> and \
</TRANSLATION>, is as follows:
<TRANSLATION>
{translation_1_chunk}
</TRANSLATION>

The expert translations of the indicated part, delimited below by <EXPERT_SUGGESTIONS> \
and </EXPERT_SUGGESTIONS>, is as follows:
<EXPERT_SUGGESTIONS>
{reflection_chunk}
</EXPERT_SUGGESTIONS>

Taking into account the expert suggestions rewrite the translation to improve it, \
paying attention to whether there are ways to improve the translation's

(i) accuracy (by correcting errors of addition, mistranslation, omission, or untranslated text),
(ii) fluency (by applying {target_lang} grammar, spelling and punctuation rules and ensuring there are no unnecessary repetitions), \
(iii) style (by ensuring the translations reflect the style of the source text)
(iv) terminology (inappropriate for context, inconsistent use), or
(v) other errors.

Output only the new translation of the indicated part and nothing else."""


@dataclass
class OneChunkInitialTranslationText:
    source_text: str
    translation_text: str


@dataclass
class OneChunkReflectOnTranslationText:
    source_text: str
    translation_text: str
    reflection_text: str


@dataclass
class MultiChunkInitialTranslationText:
    source_text: List[str]
    translation_text: List[str]


@dataclass
class MultiChunkReflectOnTranslationText:
    source_text: List[str]
    translation_text: List[str]
    reflection_text: List[str]


class TranslationMixinLLMOperator(MixinLLMOperator, ABC):
    _SOURCE_LANG_CACHE_KEY = "__translation_source_lang__"
    _TARGET_LANG_CACHE_KEY = "__translation_target_lang__"
    _MAX_TOKENS_CACHE_KEY = "__translation_max_tokens__"
    _TARGET_COUNTRY_CACHE_KEY = "__translation_target_country__"
    _TEMPERATURE_CACHE_KEY = "__translation_temperature__"
    _SOURCE_TEXT_TOKENS_CACHE_KEY = "__translation_source_text_tokens__"
    _MODEL_CACHE_KEY = "__translation_model__"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        from cachetools import TTLCache
        from dbgpt.util.cache_utils import cached

        @cached(TTLCache(maxsize=100, ttl=60))
        async def count_tokens(text: str, model: Optional[str] = None) -> int:
            models = await self.llm_client.models()
            if not models:
                raise Exception("No models available.")
            model = model or models[0].model
            num_tokens = await self.llm_client.count_token(model, text)
            return num_tokens

        self._cached_count_tokens_func = count_tokens

    async def call_llm(
        self,
        system_prompt: str,
        human_prompt: str,
        model: Optional[str] = None,
        **kwargs,
    ) -> str:
        prompt_template = ChatPromptTemplate(
            messages=[
                SystemPromptTemplate.from_template(system_prompt),
                HumanPromptTemplate.from_template(human_prompt),
            ]
        )

        messages = prompt_template.format_messages(**kwargs)
        model_messages = ModelMessage.from_base_messages(messages)

        models = await self.llm_client.models()
        if not models:
            raise Exception("No models available.")
        model = model or models[0].model

        model_request = ModelRequest.build_request(
            model, messages=model_messages, temperature=await self.get_temperature()
        )
        model_output = await self.llm_client.generate(model_request)
        if not model_output.success:
            raise Exception(f"Model generation failed: {model_output.text}")
        return model_output.text

    async def count_tokens(
        self,
        text: str,
        model: Optional[str] = None,
    ) -> int:
        return await self._cached_count_tokens_func(text, model)

    async def _save_if_not_exists(self, key: str, value: Any, overwrite: bool = False):
        if not await self.current_dag_context.get_from_share_data(key) or overwrite:
            await self.current_dag_context.save_to_share_data(
                key, value, overwrite=overwrite
            )

    async def save_to_cache(
        self,
        source_lang: str,
        target_lang: str,
        max_tokens: int,
        source_text_tokens: int,
        target_country: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
    ):
        await self._save_if_not_exists(self._SOURCE_LANG_CACHE_KEY, source_lang)
        await self._save_if_not_exists(self._TARGET_LANG_CACHE_KEY, target_lang)
        await self._save_if_not_exists(self._MAX_TOKENS_CACHE_KEY, max_tokens)
        await self._save_if_not_exists(
            self._SOURCE_TEXT_TOKENS_CACHE_KEY, source_text_tokens, overwrite=True
        )
        if target_country:
            await self._save_if_not_exists(
                self._TARGET_COUNTRY_CACHE_KEY, target_country
            )
        if model:
            await self._save_if_not_exists(self._MODEL_CACHE_KEY, model)
        if temperature is not None:
            await self._save_if_not_exists(self._TEMPERATURE_CACHE_KEY, temperature)

    async def get_source_lang(self) -> str:
        source_lang = await self.current_dag_context.get_from_share_data(
            self._SOURCE_LANG_CACHE_KEY
        )
        if not source_lang:
            raise Exception("Source language not set.")
        return source_lang

    async def get_target_lang(self) -> str:
        target_lang = await self.current_dag_context.get_from_share_data(
            self._TARGET_LANG_CACHE_KEY
        )
        if not target_lang:
            raise Exception("Target language not set.")
        return target_lang

    async def get_target_country(self) -> Optional[str]:
        return await self.current_dag_context.get_from_share_data(
            self._TARGET_COUNTRY_CACHE_KEY
        )

    async def get_max_tokens(self) -> int:
        max_tokens = await self.current_dag_context.get_from_share_data(
            self._MAX_TOKENS_CACHE_KEY
        )
        if not max_tokens:
            raise Exception("Max tokens not set.")
        return max_tokens

    async def get_source_text_tokens(self) -> int:
        source_text_tokens = await self.current_dag_context.get_from_share_data(
            self._SOURCE_TEXT_TOKENS_CACHE_KEY
        )
        if not source_text_tokens:
            raise Exception("Source text tokens not set.")
        return source_text_tokens

    async def get_model(self, default_model: Optional[str] = None) -> Optional[str]:
        model = await self.current_dag_context.get_from_share_data(
            self._MODEL_CACHE_KEY
        )
        if not model:
            return default_model
        return model

    async def get_temperature(self, default_temperature: float = 0.3) -> float:
        temperature = await self.current_dag_context.get_from_share_data(
            self._TEMPERATURE_CACHE_KEY
        )
        return temperature or default_temperature


_SOURCE_LANG_PARAMETER = Parameter.build_from(
    "Source Language",
    "source_lang",
    str,
    optional=True,
    default="English",
    description="The source language of the text.",
)
_TARGET_LANG_PARAMETER = Parameter.build_from(
    "Target Language",
    "target_lang",
    str,
    optional=True,
    default="Chinese",
    description="The target language for translation.",
)
_MODEL_PARAMETER = Parameter.build_from(
    "Model",
    "model",
    str,
    optional=True,
    default=None,
    description="The model to use for translation.",
)
_LLM_CLIENT_PARAMETER = Parameter.build_from(
    "LLM Client",
    "llm_client",
    LLMClient,
    optional=True,
    default=None,
    description="The LLM Client.",
)
_CONCURRENT_LIMIT_PARAMETER = Parameter.build_from(
    "Concurrency Limit",
    "concurrency_limit",
    int,
    optional=True,
    default=5,
    description="The maximum number of concurrent tasks to call the LLM.",
)


class OneChunkInputTranslationOperator(
    TranslationMixinLLMOperator, MapOperator[str, str]
):
    """Dummy operator to translate the entire text as one chunk using an LLM.

    one_chunk_input_translation
    """

    metadata = ViewMetadata(
        label="One Chunk Input Translation",
        name="one_chunk_input_translation",
        category=OperatorCategory.COMMON,
        description="Dummy operator to translate the entire text as one chunk using an LLM.",
        parameters=[],
        inputs=[
            IOField.build_from(
                "Source Text",
                "source_text",
                str,
                description="The text to be translated.",
            )
        ],
        outputs=[
            IOField.build_from(
                "Source Text",
                "source_text",
                str,
                description="The text to be translated.",
            )
        ],
    )

    def __init__(
        self,
        task_name: str = "one_chunk_input_translation",
        **kwargs,
    ):
        TranslationMixinLLMOperator.__init__(self)
        MapOperator.__init__(self, task_name=task_name, **kwargs)

    async def map(self, source_text: str) -> str:
        return source_text


class OneChunkInitialTranslationOperator(
    TranslationMixinLLMOperator, MapOperator[str, OneChunkInitialTranslationText]
):
    """Translate the entire text as one chunk using an LLM.

    one_chunk_initial_translation
    """

    metadata = ViewMetadata(
        label="One Chunk Initial Translation",
        name="one_chunk_initial_translation",
        category=OperatorCategory.COMMON,
        description="Translate the entire text as one chunk using an LLM.",
        parameters=[
            Parameter.build_from(
                "System Prompt Template",
                "system_prompt",
                str,
                optional=True,
                default=_ONE_CHUNK_INITIAL_TRANSLATION_SYSTEM_PROMPT,
                description="The system prompt template for the translation task.",
            ),
            Parameter.build_from(
                "Translation Prompt Template",
                "translation_prompt",
                str,
                optional=True,
                default=_ONE_CHUNK_INITIAL_TRANSLATION_PROMPT,
                description="The translation prompt template for the translation task.",
            ),
            _MODEL_PARAMETER.new(),
            _LLM_CLIENT_PARAMETER.new(),
        ],
        inputs=[
            IOField.build_from(
                "Source Text",
                "source_text",
                str,
                description="The text to be translated.",
            )
        ],
        outputs=[
            IOField.build_from(
                "Translation",
                "translation",
                OneChunkInitialTranslationText,
                description="The translated text.",
            )
        ],
    )

    def __init__(
        self,
        system_prompt: str = _ONE_CHUNK_INITIAL_TRANSLATION_SYSTEM_PROMPT,
        translation_prompt: str = _ONE_CHUNK_INITIAL_TRANSLATION_PROMPT,
        model: Optional[str] = None,
        llm_client: Optional[LLMClient] = None,
        **kwargs,
    ):
        TranslationMixinLLMOperator.__init__(self, default_client=llm_client)
        MapOperator.__init__(self, **kwargs)
        self.system_prompt = system_prompt
        self.translation_prompt = translation_prompt
        self.model = model

    async def map(self, source_text: str) -> OneChunkInitialTranslationText:
        translation_text = await self.call_llm(
            self.system_prompt,
            self.translation_prompt,
            model=await self.get_model(default_model=self.model),
            source_lang=await self.get_source_lang(),
            target_lang=await self.get_target_lang(),
            source_text=source_text,
        )
        return OneChunkInitialTranslationText(
            source_text=source_text, translation_text=translation_text
        )


class OneChunkReflectOnTranslationOperator(
    TranslationMixinLLMOperator,
    MapOperator[OneChunkInitialTranslationText, OneChunkReflectOnTranslationText],
):
    """Use an LLM to reflect on the translation, treating the entire text as one chunk.

    one_chunk_reflect_on_translation
    """

    metadata = ViewMetadata(
        label="One Chunk Reflect on Translation",
        name="one_chunk_reflect_on_translation",
        category=OperatorCategory.COMMON,
        description="Use an LLM to reflect on the translation, treating the entire text as one chunk.",
        parameters=[
            Parameter.build_from(
                "Country",
                "country",
                str,
                optional=True,
                default="",
                description="Country specified for target language.",
            ),
            Parameter.build_from(
                "System Prompt Template",
                "system_prompt",
                str,
                optional=True,
                default=_ONE_CHUNK_REFLECTION_SYSTEM_PROMPT,
                description="The system prompt template for the reflection task.",
            ),
            Parameter.build_from(
                "Reflection Country Prompt Template",
                "reflection_country_prompt",
                str,
                optional=True,
                default=_ONE_CHUNK_REFLECTION_COUNTRY_PROMPT,
                description="The reflection country prompt template for the reflection task.",
            ),
            Parameter.build_from(
                "Reflection Prompt Template",
                "reflection_prompt",
                str,
                optional=True,
                default=_ONE_CHUNK_REFLECTION_PROMPT,
                description="The reflection prompt template for the reflection task.",
            ),
            _MODEL_PARAMETER.new(),
            _LLM_CLIENT_PARAMETER.new(),
        ],
        inputs=[
            IOField.build_from(
                "Translation",
                "translation_1",
                OneChunkInitialTranslationText,
                description="The initial translation to reflect on.",
            )
        ],
        outputs=[
            IOField.build_from(
                "Reflection",
                "reflection",
                OneChunkReflectOnTranslationText,
                description="The reflection on the translation.",
            )
        ],
    )

    def __init__(
        self,
        country: str = "",
        system_prompt: str = _ONE_CHUNK_REFLECTION_SYSTEM_PROMPT,
        reflection_country_prompt: str = _ONE_CHUNK_REFLECTION_COUNTRY_PROMPT,
        reflection_prompt: str = _ONE_CHUNK_REFLECTION_PROMPT,
        model: Optional[str] = None,
        llm_client: Optional[LLMClient] = None,
        **kwargs,
    ):
        TranslationMixinLLMOperator.__init__(self, default_client=llm_client)
        MapOperator.__init__(self, **kwargs)
        self.country = country
        self.system_prompt = system_prompt
        self.reflection_country_prompt = reflection_country_prompt
        self.reflection_prompt = reflection_prompt
        self.model = model

    async def map(
        self, prv: OneChunkInitialTranslationText
    ) -> OneChunkReflectOnTranslationText:
        reflection_text = await self.reflection(prv.translation_text, prv.source_text)
        return OneChunkReflectOnTranslationText(
            source_text=prv.source_text,
            translation_text=prv.translation_text,
            reflection_text=reflection_text,
        )

    async def reflection(self, translation_1: str, source_text: str) -> str:
        country = await self.get_target_country() or self.country

        return await self.call_llm(
            self.system_prompt,
            self.reflection_country_prompt if country else self.reflection_prompt,
            model=await self.get_model(default_model=self.model),
            source_lang=await self.get_source_lang(),
            target_lang=await self.get_target_lang(),
            source_text=source_text,
            translation_1=translation_1,
            country=self.country,
        )


class OneChunkImproveTranslationOperator(
    TranslationMixinLLMOperator,
    MapOperator[OneChunkReflectOnTranslationText, str],
):
    """Use the reflection to improve the translation, treating the entire text as one chunk..

    one_chunk_improve_translation
    """

    metadata = ViewMetadata(
        label="One Chunk Improve Translation",
        name="one_chunk_improve_translation",
        category=OperatorCategory.COMMON,
        description="Use the reflection to improve the translation, treating the entire text as one chunk.",
        parameters=[
            Parameter.build_from(
                "System Prompt Template",
                "system_prompt",
                str,
                optional=True,
                default=_ONE_CHUNK_IMPROVE_TRANSLATION_SYSTEM_PROMPT,
                description="The system prompt template for the improvement task.",
            ),
            Parameter.build_from(
                "Improvement Prompt Template",
                "improve_prompt",
                str,
                optional=True,
                default=_ONE_CHUNK_IMPROVE_TRANSLATION_PROMPT,
                description="The improvement prompt template for the improvement task.",
            ),
            _MODEL_PARAMETER.new(),
            _LLM_CLIENT_PARAMETER.new(),
        ],
        inputs=[
            IOField.build_from(
                "Reflection",
                "reflection",
                OneChunkReflectOnTranslationText,
                description="The reflection on the translation.",
            ),
        ],
        outputs=[
            IOField.build_from(
                "Translation 2",
                "translation_2",
                str,
                description="The improved translation.",
            )
        ],
    )

    def __init__(
        self,
        system_prompt: str = _ONE_CHUNK_IMPROVE_TRANSLATION_SYSTEM_PROMPT,
        improve_prompt: str = _ONE_CHUNK_IMPROVE_TRANSLATION_PROMPT,
        model: Optional[str] = None,
        llm_client: Optional[LLMClient] = None,
        **kwargs,
    ):
        TranslationMixinLLMOperator.__init__(self, default_client=llm_client)
        MapOperator.__init__(self, **kwargs)
        self.system_prompt = system_prompt
        self.improve_prompt = improve_prompt
        self.model = model

    async def map(self, prev: OneChunkReflectOnTranslationText) -> str:
        return await self.improve_translation(
            prev.reflection_text, prev.translation_text, prev.source_text
        )

    async def improve_translation(
        self,
        reflection: str,
        translation_1: str,
        source_text: str,
    ) -> str:
        return await self.call_llm(
            self.system_prompt,
            self.improve_prompt,
            model=await self.get_model(default_model=self.model),
            source_lang=await self.get_source_lang(),
            target_lang=await self.get_target_lang(),
            source_text=source_text,
            translation_1=translation_1,
            reflection=reflection,
        )


class MultiChunkInitialTranslationOperator(
    TranslationMixinLLMOperator,
    MapOperator[List[str], MultiChunkInitialTranslationText],
):
    """Translate a text in multiple chunks from the source language to the target language.

    multichunk_initial_translation
    """

    metadata = ViewMetadata(
        label="Multi Chunk Initial Translation",
        name="multi_chunk_initial_translation",
        category=OperatorCategory.COMMON,
        description="Translate the text in multiple chunks using an LLM.",
        parameters=[
            Parameter.build_from(
                "System Prompt Template",
                "system_prompt",
                str,
                optional=True,
                default=_MULTI_CHUNK_INITIAL_TRANSLATION_SYSTEM_PROMPT,
                description="The system prompt template for the translation task.",
            ),
            Parameter.build_from(
                "Translation Prompt Template",
                "translation_prompt",
                str,
                optional=True,
                default=_MULTI_CHUNK_INITIAL_TRANSLATION_PROMPT,
                description="The translation prompt template for the translation task.",
            ),
            _MODEL_PARAMETER.new(),
            _LLM_CLIENT_PARAMETER.new(),
            _CONCURRENT_LIMIT_PARAMETER.new(),
        ],
        inputs=[
            IOField.build_from(
                "Source Text Chunks",
                "source_text_chunks",
                str,
                is_list=True,
                description="The text chunks to be translated.",
            )
        ],
        outputs=[
            IOField.build_from(
                "Translation Chunks",
                "translation_chunks",
                MultiChunkInitialTranslationText,
                description="The translated text chunks.",
            )
        ],
    )

    def __init__(
        self,
        system_prompt: str = _MULTI_CHUNK_INITIAL_TRANSLATION_SYSTEM_PROMPT,
        translation_prompt: str = _MULTI_CHUNK_INITIAL_TRANSLATION_PROMPT,
        model: Optional[str] = None,
        llm_client: Optional[LLMClient] = None,
        concurrency_limit: int = 5,
        **kwargs,
    ):
        TranslationMixinLLMOperator.__init__(self, default_client=llm_client)
        MapOperator.__init__(self, **kwargs)
        self.system_prompt = system_prompt
        self.translation_prompt = translation_prompt
        self.model = model
        self.concurrency_limit = concurrency_limit

    async def map(
        self, source_text_chunks: List[str]
    ) -> MultiChunkInitialTranslationText:
        translation_chunk_tasks = []

        from dbgpt.util.chat_util import run_async_tasks

        for i in range(len(source_text_chunks)):
            # Will translate chunk i
            tagged_text = (
                "".join(source_text_chunks[0:i])
                + "<TRANSLATE_THIS>"
                + source_text_chunks[i]
                + "</TRANSLATE_THIS>"
                + "".join(source_text_chunks[i + 1 :])
            )

            translation_chunk_tasks.append(
                self.call_llm(
                    self.system_prompt,
                    self.translation_prompt,
                    model=await self.get_model(default_model=self.model),
                    source_lang=await self.get_source_lang(),
                    target_lang=await self.get_target_lang(),
                    tagged_text=tagged_text,
                    chunk_to_translate=source_text_chunks[i],
                )
            )
        translation_chunks = await run_async_tasks(
            tasks=translation_chunk_tasks, concurrency_limit=self.concurrency_limit
        )

        return MultiChunkInitialTranslationText(
            source_text=source_text_chunks, translation_text=translation_chunks
        )


class MultiChunkReflectOnTranslationOperator(
    TranslationMixinLLMOperator,
    MapOperator[MultiChunkInitialTranslationText, MultiChunkReflectOnTranslationText],
):
    """Provides constructive criticism and suggestions for improving a partial translation.

    multichunk_reflect_on_translation
    """

    metadata = ViewMetadata(
        label="Multi Chunk Reflect on Translation",
        name="multi_chunk_reflect_on_translation",
        category=OperatorCategory.COMMON,
        description="Provides constructive criticism and suggestions for improving a partial translation.",
        parameters=[
            Parameter.build_from(
                "Country",
                "country",
                str,
                optional=True,
                default="",
                description="Country specified for target language.",
            ),
            Parameter.build_from(
                "System Prompt Template",
                "system_prompt",
                str,
                optional=True,
                default=_MULTI_CHUNK_REFLECTION_SYSTEM_PROMPT,
                description="The system prompt template for the reflection task.",
            ),
            Parameter.build_from(
                "Reflection Country Prompt Template",
                "reflection_country_prompt",
                str,
                optional=True,
                default=_MULTI_CHUNK_REFLECTION_COUNTRY_PROMPT,
                description="The reflection country prompt template for the reflection task.",
            ),
            Parameter.build_from(
                "Reflection Prompt Template",
                "reflection_prompt",
                str,
                optional=True,
                default=_MULTI_CHUNK_REFLECTION_PROMPT,
                description="The reflection prompt template for the reflection task.",
            ),
            _MODEL_PARAMETER.new(),
            _LLM_CLIENT_PARAMETER.new(),
        ],
        inputs=[
            IOField.build_from(
                "Translation Chunks",
                "translation_1_chunks",
                MultiChunkInitialTranslationText,
                description="The initial translation chunks to reflect on.",
            ),
        ],
        outputs=[
            IOField.build_from(
                "Reflection Chunks",
                "reflection_chunks",
                MultiChunkReflectOnTranslationText,
                description="The reflection on the translation chunks.",
            )
        ],
    )

    def __init__(
        self,
        country: str = "",
        system_prompt: str = _MULTI_CHUNK_REFLECTION_SYSTEM_PROMPT,
        reflection_country_prompt: str = _MULTI_CHUNK_REFLECTION_COUNTRY_PROMPT,
        reflection_prompt: str = _MULTI_CHUNK_REFLECTION_PROMPT,
        model: Optional[str] = None,
        llm_client: Optional[LLMClient] = None,
        concurrency_limit: int = 5,
        **kwargs,
    ):
        TranslationMixinLLMOperator.__init__(self, default_client=llm_client)
        MapOperator.__init__(self, **kwargs)
        self.country = country
        self.system_prompt = system_prompt
        self.reflection_country_prompt = reflection_country_prompt
        self.reflection_prompt = reflection_prompt
        self.model = model
        self.concurrency_limit = concurrency_limit

    async def map(
        self, prv: MultiChunkInitialTranslationText
    ) -> MultiChunkReflectOnTranslationText:
        reflection_chunks = await self.reflection(prv.translation_text, prv.source_text)
        return MultiChunkReflectOnTranslationText(
            source_text=prv.source_text,
            translation_text=prv.translation_text,
            reflection_text=reflection_chunks,
        )

    async def reflection(
        self, translation_1_chunks: List[str], source_text_chunks: List[str]
    ) -> List[str]:
        reflection_chunk_tasks = []

        from dbgpt.util.chat_util import run_async_tasks

        country = await self.get_target_country() or self.country

        reflection_prompt = (
            self.reflection_country_prompt if country else self.reflection_prompt
        )

        for i in range(len(source_text_chunks)):
            # Will translate chunk i
            tagged_text = (
                "".join(source_text_chunks[0:i])
                + "<TRANSLATE_THIS>"
                + source_text_chunks[i]
                + "</TRANSLATE_THIS>"
                + "".join(source_text_chunks[i + 1 :])
            )

            reflection_chunk_tasks.append(
                self.call_llm(
                    self.system_prompt,
                    reflection_prompt,
                    model=await self.get_model(default_model=self.model),
                    source_lang=await self.get_source_lang(),
                    target_lang=await self.get_target_lang(),
                    tagged_text=tagged_text,
                    chunk_to_translate=source_text_chunks[i],
                    translation_1_chunk=translation_1_chunks[i],
                    country=self.country,
                )
            )
        reflection_chunks = await run_async_tasks(
            tasks=reflection_chunk_tasks, concurrency_limit=self.concurrency_limit
        )

        return reflection_chunks


class MultiChunkImproveTranslationOperator(
    TranslationMixinLLMOperator, MapOperator[MultiChunkReflectOnTranslationText, str]
):
    """Improves the translation of a text from source language to target language by considering expert suggestions.

    multichunk_improve_translation
    """

    metadata = ViewMetadata(
        label="Multi Chunk Improve Translation",
        name="multi_chunk_improve_translation",
        category=OperatorCategory.COMMON,
        description="Improves the translation of a text from source language to target language by considering expert suggestions.",
        parameters=[
            Parameter.build_from(
                "System Prompt Template",
                "system_prompt",
                str,
                optional=True,
                default=_MULTI_CHUNK_IMPROVE_TRANSLATION_SYSTEM_PROMPT,
                description="The system prompt template for the improvement task.",
            ),
            Parameter.build_from(
                "Improvement Prompt Template",
                "improve_prompt",
                str,
                optional=True,
                default=_MULTI_CHUNK_IMPROVE_TRANSLATION_PROMPT,
                description="The improvement prompt template for the improvement task.",
            ),
            _MODEL_PARAMETER.new(),
            _LLM_CLIENT_PARAMETER.new(),
            _CONCURRENT_LIMIT_PARAMETER.new(),
        ],
        inputs=[
            IOField.build_from(
                "Reflection Chunks",
                "reflection_chunks",
                MultiChunkReflectOnTranslationText,
                description="The reflection on the translation chunks.",
            ),
        ],
        outputs=[
            IOField.build_from(
                "Translation 2 Chunks",
                "translation_2_chunks",
                str,
                description="The improved translation chunks.",
            )
        ],
    )

    def __init__(
        self,
        system_prompt: str = _MULTI_CHUNK_IMPROVE_TRANSLATION_SYSTEM_PROMPT,
        improve_prompt: str = _MULTI_CHUNK_IMPROVE_TRANSLATION_PROMPT,
        model: Optional[str] = None,
        llm_client: Optional[LLMClient] = None,
        concurrency_limit: int = 5,
        **kwargs,
    ):
        TranslationMixinLLMOperator.__init__(self, default_client=llm_client)
        MapOperator.__init__(self, **kwargs)
        self.system_prompt = system_prompt
        self.improve_prompt = improve_prompt
        self.model = model
        self.concurrency_limit = concurrency_limit

    async def map(self, prev: MultiChunkReflectOnTranslationText) -> str:
        return await self.improve_translation(
            prev.reflection_text, prev.translation_text, prev.source_text
        )

    async def improve_translation(
        self,
        reflection_chunks: List[str],
        translation_1_chunks: List[str],
        source_text_chunks: List[str],
    ) -> str:
        translation_chunk_tasks = []

        from dbgpt.util.chat_util import run_async_tasks

        for i in range(len(source_text_chunks)):
            # Will translate chunk i
            tagged_text = (
                "".join(source_text_chunks[0:i])
                + "<TRANSLATE_THIS>"
                + source_text_chunks[i]
                + "</TRANSLATE_THIS>"
                + "".join(source_text_chunks[i + 1 :])
            )
            translation_chunk_tasks.append(
                self.call_llm(
                    self.system_prompt,
                    self.improve_prompt,
                    model=await self.get_model(default_model=self.model),
                    source_lang=await self.get_source_lang(),
                    target_lang=await self.get_target_lang(),
                    tagged_text=tagged_text,
                    chunk_to_translate=source_text_chunks[i],
                    translation_1_chunk=translation_1_chunks[i],
                    reflection_chunk=reflection_chunks[i],
                )
            )
        translation_chunks = await run_async_tasks(
            tasks=translation_chunk_tasks, concurrency_limit=self.concurrency_limit
        )

        return "".join(translation_chunks)


class TranslationSplitTextOperator(
    TranslationMixinLLMOperator, MapOperator[str, List[str]]
):
    """Split the source text into chunks based on the number of tokens."""

    metadata = ViewMetadata(
        label="Translation Split Text",
        name="translation_split_text",
        category=OperatorCategory.COMMON,
        description="Split the source text into chunks based on the number of tokens.",
        parameters=[
            _LLM_CLIENT_PARAMETER.new(),
        ],
        inputs=[
            IOField.build_from(
                "Source Text",
                "source_text",
                str,
                description="The source text to be split.",
            )
        ],
        outputs=[
            IOField.build_from(
                "Source Text Chunks",
                "source_text_chunks",
                str,
                is_list=True,
                description="The source text chunks.",
            )
        ],
    )

    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        task_name: str = "translation_split_text_task",
        **kwargs,
    ):
        TranslationMixinLLMOperator.__init__(self, default_client=llm_client)
        MapOperator.__init__(self, task_name=task_name, **kwargs)

    async def map(self, source_text: str) -> List[str]:
        num_tokens = await self.get_source_text_tokens()
        max_tokens = await self.get_max_tokens()
        model = await self.get_model()
        if not model:
            models = await self.llm_client.models()
            if not models:
                raise Exception("No models available.")
            model = model or models[0].model
        chunk_size = calculate_chunk_size(num_tokens, max_tokens)

        text_splitter = AsyncRecursiveCharacterTextSplitter.from_llm_client(
            llm_client=self.llm_client,
            model=model,
            chunk_size=chunk_size,
            chunk_overlap=0,
        )

        source_text_chunks = await text_splitter.a_split_text(source_text)
        return source_text_chunks


class TranslationConfigOperator(TranslationMixinLLMOperator, MapOperator[str, str]):
    metadata = ViewMetadata(
        label="Translation Config Operator",
        name="translation_config_operator",
        category=OperatorCategory.COMMON,
        description="Configure the translation settings.",
        parameters=[
            _SOURCE_LANG_PARAMETER.new(),
            _TARGET_LANG_PARAMETER.new(),
            Parameter.build_from(
                "Max Tokens",
                "max_tokens",
                int,
                optional=True,
                default=1000,
                description="The maximum number of tokens per chunk.",
            ),
            _MODEL_PARAMETER.new(),
            _LLM_CLIENT_PARAMETER.new(),
        ],
        inputs=[
            IOField.build_from(
                "Source Text",
                "source_text",
                str,
                description="The source text to be translated.",
            )
        ],
        outputs=[
            IOField.build_from(
                "Source Text",
                "source_text",
                str,
                description="The source text to be translated.",
            )
        ],
    )

    def __init__(
        self,
        source_lang: str = "English",
        target_lang: str = "Chinese",
        max_tokens: int = 1000,
        model: Optional[str] = None,
        llm_client: Optional[LLMClient] = None,
        **kwargs,
    ):
        TranslationMixinLLMOperator.__init__(self, default_client=llm_client)
        MapOperator.__init__(self, **kwargs)
        self._source_lang = source_lang
        self._target_lang = target_lang
        self._max_tokens = max_tokens
        self._model = model

    async def map(self, source_text: str) -> str:
        num_tokens = await self.count_tokens(source_text, self._model)
        await self.save_to_cache(
            source_lang=self._source_lang,
            target_lang=self._target_lang,
            max_tokens=self._max_tokens,
            source_text_tokens=num_tokens,
            model=self._model,
        )
        return source_text


class TranslationBranchOperator(TranslationMixinLLMOperator, BranchOperator[str, str]):
    metadata = ViewMetadata(
        label="Translation Branch Operator",
        name="translation_branch_operator",
        category=OperatorCategory.COMMON,
        description="Branch the translation based on the number of tokens in the source text.",
        parameters=[],
        inputs=[
            IOField.build_from(
                "Source Text",
                "source_text",
                str,
                description="The source text to be translated.",
            )
        ],
        outputs=[
            IOField.build_from(
                "Source Text",
                "source_text",
                str,
                description="The source text to be translated.",
            ),
            IOField.build_from(
                "Source Text",
                "source_text",
                str,
                description="The source text to be translated.",
            ),
        ],
    )

    def __init__(self, **kwargs):
        TranslationMixinLLMOperator.__init__(self)
        BranchOperator.__init__(self, **kwargs)

    async def branches(self) -> Dict[BranchFunc[str], BranchTaskType]:
        async def check_less_max_tokens(source_text: str):
            # Read from cache
            max_tokens = await self.get_max_tokens()
            num_tokens = await self.get_source_text_tokens()
            return num_tokens < max_tokens

        async def check_not_less_max_tokens(source_text: str):
            res = await check_less_max_tokens(source_text)
            return not res

        one_chunk_node_id = ""
        multi_chunk_node_id = ""
        for node in self.downstream:
            if isinstance(node, TranslationSplitTextOperator):
                multi_chunk_node_id = node.node_name
            else:
                one_chunk_node_id = node.node_name

        return {
            check_less_max_tokens: one_chunk_node_id,
            check_not_less_max_tokens: multi_chunk_node_id,
        }


class TranslationJoinOperator(JoinOperator[str]):
    metadata = ViewMetadata(
        label="Translation Join Operator",
        name="translation_join_operator",
        category=OperatorCategory.COMMON,
        description="Join the translation results from the one chunk and multi chunk translations.",
        parameters=[],
        inputs=[
            IOField.build_from(
                "One Chunk Translation",
                "one_chunk_result",
                str,
                description="The translation result from the one chunk translation.",
            ),
            IOField.build_from(
                "Multi Chunk Translation",
                "multi_chunk_result",
                str,
                description="The translation result from the multi chunk translation.",
            ),
        ],
        outputs=[
            IOField.build_from(
                "Final Translation",
                "translation",
                str,
                description="Final translation.",
            )
        ],
    )

    def __init__(self, **kwargs):
        JoinOperator.__init__(
            self,
            combine_function=self.no_empty_data,
            can_skip_in_branch=False,
            **kwargs,
        )

    async def no_empty_data(
        self, one_chunk_result: Optional[str], multi_chunk_result: Optional[str]
    ) -> str:
        if is_empty_data(one_chunk_result):
            return multi_chunk_result
        return one_chunk_result


def calculate_chunk_size(token_count: int, token_limit: int) -> int:
    """
    Calculate the chunk size based on the token count and token limit.

    Args:
        token_count (int): The total number of tokens.
        token_limit (int): The maximum number of tokens allowed per chunk.

    Returns:
        int: The calculated chunk size.

    Description:
        This function calculates the chunk size based on the given token count and token limit.
        If the token count is less than or equal to the token limit, the function returns the token count as the chunk size.
        Otherwise, it calculates the number of chunks needed to accommodate all the tokens within the token limit.
        The chunk size is determined by dividing the token limit by the number of chunks.
        If there are remaining tokens after dividing the token count by the token limit,
        the chunk size is adjusted by adding the remaining tokens divided by the number of chunks.

    Example:
        >>> calculate_chunk_size(1000, 500)
        500
        >>> calculate_chunk_size(1530, 500)
        389
        >>> calculate_chunk_size(2242, 500)
        496
    """

    if token_count <= token_limit:
        return token_count

    num_chunks = (token_count + token_limit - 1) // token_limit
    chunk_size = token_count // num_chunks

    remaining_tokens = token_count % token_limit
    if remaining_tokens > 0:
        chunk_size += remaining_tokens // num_chunks

    return chunk_size


class AsyncRecursiveCharacterTextSplitter(RecursiveCharacterTextSplitter):
    def __init__(
        self, _async_length_function: Callable[[str], Awaitable[int]], **kwargs
    ):
        super().__init__(**kwargs)
        self._async_length_function = _async_length_function

    @classmethod
    def from_llm_client(
        cls: Type["AsyncRecursiveCharacterTextSplitter"],
        llm_client: LLMClient,
        model: str,
        **kwargs,
    ) -> "AsyncRecursiveCharacterTextSplitter":
        async def _length_function(text: str) -> int:
            num_tokens = await llm_client.count_token(model, text)
            return num_tokens

        return cls(_async_length_function=_length_function, **kwargs)

    async def a_split_text(
        self, text: str, separator: Optional[str] = None, **kwargs
    ) -> List[str]:
        """Split incoming text and return chunks."""
        final_chunks = []
        # Get appropriate separator to use
        separator = self._separators[-1]
        for _s in self._separators:
            if _s == "":
                separator = _s
                break
            if _s in text:
                separator = _s
                break
        # Now that we have the separator, split the text
        if separator:
            splits = text.split(separator)
        else:
            splits = list(text)
        # Now go merging things, recursively splitting longer texts.
        _good_splits = []
        for s in splits:
            if await self._async_length_function(s) < self._chunk_size:
                _good_splits.append(s)
            else:
                if _good_splits:
                    merged_text = await self._a_merge_splits(
                        _good_splits,
                        separator,
                        chunk_size=kwargs.get("chunk_size", None),
                        chunk_overlap=kwargs.get("chunk_overlap", None),
                    )
                    final_chunks.extend(merged_text)
                    _good_splits = []
                other_info = await self.a_split_text(s)
                final_chunks.extend(other_info)
        if _good_splits:
            merged_text = await self._a_merge_splits(
                _good_splits,
                separator,
                chunk_size=kwargs.get("chunk_size", None),
                chunk_overlap=kwargs.get("chunk_overlap", None),
            )
            final_chunks.extend(merged_text)
        return final_chunks

    async def _a_merge_splits(
        self,
        splits: Iterable[str | dict],
        separator: Optional[str] = None,
        chunk_size: Optional[int] = None,
        chunk_overlap: Optional[int] = None,
    ) -> List[str]:
        # We now want to combine these smaller pieces into medium size
        # chunks to send to the LLM.
        if chunk_size is None:
            chunk_size = self._chunk_size
        if chunk_overlap is None:
            chunk_overlap = self._chunk_overlap
        if separator is None:
            separator = self._separator
        separator_len = await self._async_length_function(separator)

        docs = []
        current_doc: List[str] = []
        total = 0
        for s in splits:
            d = cast(str, s)
            _len = await self._async_length_function(d)
            if (
                total + _len + (separator_len if len(current_doc) > 0 else 0)
                > chunk_size
            ):
                if total > chunk_size:
                    logger.warning(
                        f"Created a chunk of size {total}, "
                        f"which is longer than the specified {chunk_size}"
                    )
                if len(current_doc) > 0:
                    doc = self._join_docs(current_doc, separator)
                    if doc is not None:
                        docs.append(doc)
                    # Keep on popping if:
                    # - we have a larger chunk than in the chunk overlap
                    # - or if we still have any chunks and the length is long
                    while total > chunk_overlap or (
                        total + _len + (separator_len if len(current_doc) > 0 else 0)
                        > chunk_size
                        and total > 0
                    ):
                        total -= await self._async_length_function(current_doc[0]) + (
                            separator_len if len(current_doc) > 1 else 0
                        )
                        current_doc = current_doc[1:]
            current_doc.append(d)
            total += _len + (separator_len if len(current_doc) > 1 else 0)
        doc = self._join_docs(current_doc, separator)
        if doc is not None:
            docs.append(doc)
        return docs


async def _translate(
    source_lang: str,
    target_lang: str,
    source_text: str,
    country: str,
    max_tokens: int = 1000,
    concurrency_limit: int = 5,
):
    """Translate the source_text from source_lang to target_lang.

    Just for local testing purposes.
    """
    from dbgpt.core.awel import InputOperator, InputSource
    from dbgpt.model.proxy import OpenAILLMClient

    # please make sure to install tiktoken to count tokens
    llm_client = OpenAILLMClient(model_alias="gpt-4o")

    with DAG("Translate Text") as dag:
        input_task = InputOperator(input_source=InputSource.from_callable())
        config_task = TranslationConfigOperator(
            source_lang=source_lang,
            target_lang=target_lang,
            llm_client=llm_client,
            max_tokens=max_tokens,
        )
        branch_task = TranslationBranchOperator()
        # One chunk tasks definition
        one_chunk_input_task = OneChunkInputTranslationOperator()
        one_chunk_initial_translation_task = OneChunkInitialTranslationOperator(
            llm_client=llm_client
        )

        one_chunk_reflection_task = OneChunkReflectOnTranslationOperator(
            country=country,
            llm_client=llm_client,
        )

        one_chunk_improve_translation_task = OneChunkImproveTranslationOperator(
            llm_client=llm_client
        )

        # Multi chunk tasks definition
        multi_chunk_input_task = TranslationSplitTextOperator(llm_client=llm_client)
        multi_chunk_initial_translation_task = MultiChunkInitialTranslationOperator(
            llm_client=llm_client, concurrency_limit=concurrency_limit
        )
        multi_chunk_reflection_task = MultiChunkReflectOnTranslationOperator(
            country=country, llm_client=llm_client, concurrency_limit=concurrency_limit
        )
        multi_chunk_improve_translation_task = MultiChunkImproveTranslationOperator(
            llm_client=llm_client, concurrency_limit=concurrency_limit
        )

        join_task = TranslationJoinOperator()

        # Configure and branch
        input_task >> config_task >> branch_task
        branch_task >> one_chunk_input_task
        branch_task >> multi_chunk_input_task

        # One chunk branch

        (
            one_chunk_input_task
            >> one_chunk_initial_translation_task
            >> one_chunk_reflection_task
            >> one_chunk_improve_translation_task
        )

        # Multi chunk branch
        (
            multi_chunk_input_task
            >> multi_chunk_initial_translation_task
            >> multi_chunk_reflection_task
            >> multi_chunk_improve_translation_task
        )

        one_chunk_improve_translation_task >> join_task
        multi_chunk_improve_translation_task >> join_task

    result = await join_task.call(source_text)
    print(result)


class TranslationRequestHandleOperator(
    TranslationMixinLLMOperator, MapOperator[CommonLLMHttpRequestBody, str]
):
    metadata = ViewMetadata(
        label="Translation Request Handle Operator",
        name="translation_request_handle_operator",
        category=OperatorCategory.COMMON,
        description="Handle the translation request.",
        parameters=[],
        inputs=[
            IOField.build_from(
                "Request Body",
                "request_body",
                CommonLLMHttpRequestBody,
                description="The request body.",
            )
        ],
        outputs=[
            IOField.build_from(
                "Source Text",
                "source_text",
                str,
                description="The source text to be translated.",
            )
        ],
    )

    def __init__(self, **kwargs):
        MapOperator.__init__(self, **kwargs)

    async def map(self, request_body: CommonLLMHttpRequestBody) -> str:
        source_text = (
            request_body.messages[-1]
            if isinstance(request_body.messages, list)
            else request_body.messages
        )
        temperature = request_body.temperature
        extra = request_body.extra or {}
        source_lang = extra.get(
            "source_lang", os.getenv("ANDREWYNG_TRANSLATION_SOURCE_LANG", "English")
        )
        target_lang = extra.get(
            "target_lang", os.getenv("ANDREWYNG_TRANSLATION_TARGET_LANG", "Chinese")
        )
        max_tokens = extra.get(
            "max_tokens", int(os.getenv("ANDREWYNG_TRANSLATION_MAX_TOKENS", 1000))
        )
        country = extra.get(
            "country", os.getenv("ANDREWYNG_TRANSLATION_COUNTRY", "中国大陆")
        )
        model = request_body.model

        await self.save_to_cache(
            source_lang=source_lang,
            target_lang=target_lang,
            max_tokens=max_tokens,
            source_text_tokens=-1,
            target_country=country,
            model=model,
            temperature=temperature,
        )

        return source_text


with DAG("andrewyng_translation_agent_dag") as dag:
    concurrency_limit = int(os.getenv("ANDREWYNG_TRANSLATION_CONCURRENCY_LIMIT", 5))

    trigger = CommonLLMHttpTrigger(
        "/dbgpts/andrewyng_translation_agent_dag",
        methods="POST",
        streaming_predict_func=lambda x: x.stream,
    )
    request_parse_task = TranslationRequestHandleOperator()
    config_task = TranslationConfigOperator()
    branch_task = TranslationBranchOperator()
    # One chunk tasks definition
    one_chunk_input_task = OneChunkInputTranslationOperator()
    one_chunk_initial_translation_task = OneChunkInitialTranslationOperator()

    one_chunk_reflection_task = OneChunkReflectOnTranslationOperator()

    one_chunk_improve_translation_task = OneChunkImproveTranslationOperator()

    # Multi chunk tasks definition
    multi_chunk_input_task = TranslationSplitTextOperator()
    multi_chunk_initial_translation_task = MultiChunkInitialTranslationOperator(
        concurrency_limit=concurrency_limit
    )
    multi_chunk_reflection_task = MultiChunkReflectOnTranslationOperator(
        concurrency_limit=concurrency_limit
    )
    multi_chunk_improve_translation_task = MultiChunkImproveTranslationOperator(
        concurrency_limit=concurrency_limit
    )

    join_task = TranslationJoinOperator()

    # Configure and branch
    trigger >> request_parse_task >> config_task >> branch_task
    branch_task >> one_chunk_input_task
    branch_task >> multi_chunk_input_task

    # One chunk branch

    (
        one_chunk_input_task
        >> one_chunk_initial_translation_task
        >> one_chunk_reflection_task
        >> one_chunk_improve_translation_task
    )

    # Multi chunk branch
    (
        multi_chunk_input_task
        >> multi_chunk_initial_translation_task
        >> multi_chunk_reflection_task
        >> multi_chunk_improve_translation_task
    )

    one_chunk_improve_translation_task >> join_task
    multi_chunk_improve_translation_task >> join_task


if __name__ == "__main__":
    import asyncio

    short_text = """Last week, I spoke about AI and regulation at the U.S. Capitol at an event that was attended by legislative and business leaders. I’m encouraged by the progress the open source community has made fending off regulations that would have stifled innovation. But opponents of open source are continuing to shift their arguments, with the latest worries centering on open source's impact on national security. I hope we’ll all keep protecting open source!

Based on my conversations with legislators, I’m encouraged by the progress the U.S. federal government has made getting a realistic grasp of AI’s risks. To be clear, guardrails are needed. But they should be applied to AI applications, not to general-purpose AI technology.    
"""
    long_text = """
    Last week, I spoke about AI and regulation at the U.S. Capitol at an event that was attended by legislative and business leaders. I’m encouraged by the progress the open source community has made fending off regulations that would have stifled innovation. But opponents of open source are continuing to shift their arguments, with the latest worries centering on open source's impact on national security. I hope we’ll all keep protecting open source!

Based on my conversations with legislators, I’m encouraged by the progress the U.S. federal government has made getting a realistic grasp of AI’s risks. To be clear, guardrails are needed. But they should be applied to AI applications, not to general-purpose AI technology.

Nonetheless, as I wrote previously, some companies are eager to limit open source, possibly to protect the value of massive investments they’ve made in proprietary models and to deter competitors. It has been fascinating to watch their arguments change over time.

For instance, about 12 months ago, the Center For AI Safety’s “Statement on AI Risk” warned that AI could cause human extinction and stoked fears of AI taking over. This alarmed leaders in Washington. But many people in AI pointed out that this dystopian science-fiction scenario has little basis in reality. About six months later, when I testified at the U.S. Senate’s AI Insight forum, legislators no longer worried much about an AI takeover.

Then the opponents of open source shifted gears. Their leading argument shifted to the risk of AI helping to create bioweapons. Soon afterward, OpenAI and RAND showed that current AI does not significantly increase the ability of malefactors to build bioweapons. This fear of AI-enabled bioweapons has diminished. To be sure, the possibility that bad actors could use bioweapons — with or without AI — remains a topic of great international concern.


The latest argument for blocking open source AI has shifted to national security. AI is useful for both economic competition and warfare, and open source opponents say the U.S. should make sure its adversaries don’t have access to the latest foundation models. While I don’t want authoritarian governments to use AI, particularly to wage unjust wars, the LLM cat is out of the bag, and authoritarian countries will fill the vacuum if democratic nations limit access. When, some day, a child somewhere asks an AI system questions about democracy, the role of a free press, or the function of an independent judiciary in preserving the rule of law, I would like the AI to reflect democratic values rather than favor authoritarian leaders’ goals over, say, human rights.

I came away from Washington optimistic about the progress we’ve made. A  year ago, legislators seemed to me to spend 80% of their time talking about guardrails for AI and 20% about investing in innovation. I was delighted that the ratio has flipped, and there was far more talk of investing in innovation.

Looking beyond the U.S. federal government, there are many jurisdictions globally. Unfortunately, arguments in favor of  regulations that would stifle AI development continue to proliferate. But I’ve learned from my trips to Washington and other nations’ capitals that talking to regulators does have an impact. If you get a chance to talk to a regulator at any level, I hope you’ll do what you can to help governments better understand AI.
"""
    asyncio.run(_translate("English", "Chinese", short_text, "中国大陆"))
    # asyncio.run(_translate("English", "Chinese", long_text, "中国大陆"))
    # dag.visualize_dag(directory="/tmp")
