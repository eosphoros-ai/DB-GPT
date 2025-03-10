"""Base class for intent detection."""

import json
from abc import ABC, abstractmethod
from typing import List, Optional, Type

from dbgpt._private.pydantic import BaseModel, Field
from dbgpt.core import (
    BaseOutputParser,
    LLMClient,
    ModelMessage,
    ModelRequest,
    PromptTemplate,
)

_DEFAULT_PROMPT = """Please select the most matching intent from the intent definitions below based on the user's question, 
and return the complete intent information according to the requirements and output format.
1. Strictly follow the given intent definition for output; do not create intents or slot attributes on your own. If an intent has no defined slots, the output should not include slots either.
2. Extract slot attribute values from the user's input and historical dialogue information according to the intent definition. If the corresponding target information for the slot attribute cannot be obtained, the slot value should be empty.
3. When extracting slot values, ensure to only obtain the effective value part. Do not include auxiliary descriptions or modifiers. Ensure that all slot attributes defined in the intent are output, regardless of whether values are obtained. If no values are found, output the slot name with an empty value.
4. Ensure that if the user's question does not provide the content defined in the intent slots, the slot values must be empty. Do not fill slots with invalid information such as 'user did not provide'.
5. If the information extracted from the user's question does not fully correspond to the matched intent slots, generate a new question to ask the user, prompting them to provide the missing slot data.

{response}

You can refer to the following examples:
{example}

The known intent information is defined as follows:
{intent_definitions}

Here are the known historical dialogue messages. If they are not relevant to the user's question, they can be ignored(Some times you can extract useful intent and slot information from the historical dialogue messages).
{history}

User question: {user_input}
"""  # noqa

_DEFAULT_PROMPT_ZH = """从下面的意图定义中选择一个和用户问题最匹配的意图，并根据要求和输出格式返回意图完整信息。
1. 严格根给出的意图定义输出，不要自行生成意图和槽位属性，意图没有定义槽位则输出也不应该包含槽位。 
2. 从用户输入和历史对话信息中提取意图定义中槽位属性的值，如果无法获取到槽位属性对应的目标信息，则槽位值输出空。
3. 槽位值提取时请注意只获取有效值部分，不要填入辅助描述或定语确保意图定义的槽位属性不管是否获取到值，都要输出全部定义给出的槽位属性，没有找到值的输出槽位名和空值。
4. 请确保如果用户问题中未提供意图槽位定义的内容，则槽位值必须为空，不要在槽位里填‘用户未提供’这类无效信息。
5. 如果用户问题内容提取的信息和匹配到的意图槽位无法完全对应，则生成新的问题向用户提问，提示用户补充缺少的槽位数据。

{response}

可以参考下面的例子：
{example}

已知的意图信息定义如下：
{intent_definitions}

以下是已知的历史对话消息，如果和用户问题无关可以忽略（有时可以从历史对话消息中提取有用的意图和槽位信息）。
{history}

用户问题：{user_input}
"""  # noqa


class IntentDetectionResponse(BaseModel):
    """Response schema for intent detection."""

    intent: str = Field(
        ...,
        description="The intent of user question.",
    )
    thought: str = Field(
        ...,
        description="Logic and rationale for selecting the current application.",
    )
    task_name: str = Field(
        ...,
        description="The task name of the intent.",
    )
    slots: Optional[dict] = Field(
        None,
        description="The slots of user question.",
    )
    user_input: str = Field(
        ...,
        description="Instructions generated based on intent and slot.",
    )
    ask_user: Optional[str] = Field(
        None,
        description="Questions to users.",
    )

    def has_empty_slot(self):
        """Check if the response has empty slot."""
        if self.slots:
            for key, value in self.slots.items():
                if not value or len(value) <= 0:
                    return True
        return False

    @classmethod
    def to_response_format(cls) -> str:
        """Get the response format."""
        schema_dict = {
            "intent": "[Intent placeholder]",
            "thought": "Your reasoning idea here.",
            "task_name": "[Task name of the intent]",
            "slots": {
                "Slot attribute 1 in the intention definition": "[Slot value 1]",
                "Slot attribute 2 in the intention definition": "[Slot value 2]",
            },
            "ask_user": "If you want the user to supplement the slot data, the problem"
            " is raised to the user, please use the same language as the user.",
            "user_input": "Complete instructions generated according to the intention "
            "and slot, please use the same language as the user.",
        }
        # How to integration the streaming json
        schema_str = json.dumps(schema_dict, indent=2, ensure_ascii=False)
        response_format = (
            f"Please output in the following JSON format: \n{schema_str}"
            f"\nMake sure the response is correct json and can be parsed by Python "
            f"json.loads."
        )
        return response_format


class BaseIntentDetection(ABC):
    """Base class for intent detection."""

    def __init__(
        self,
        intent_definitions: str,
        prompt_template: Optional[str] = None,
        response_format: Optional[str] = None,
        examples: Optional[str] = None,
    ):
        """Create a new intent detection instance."""
        self._intent_definitions = intent_definitions
        self._prompt_template = prompt_template
        self._response_format = response_format
        self._examples = examples

    @property
    @abstractmethod
    def llm_client(self) -> LLMClient:
        """Get the LLM client."""

    @property
    def response_schema(self) -> Type[IntentDetectionResponse]:
        """Return the response schema."""
        return IntentDetectionResponse

    async def detect_intent(
        self,
        messages: List[ModelMessage],
        model: Optional[str] = None,
        language: str = "en",
    ) -> IntentDetectionResponse:
        """Detect intent from messages."""
        default_prompt = _DEFAULT_PROMPT if language == "en" else _DEFAULT_PROMPT_ZH

        models = await self.llm_client.models()
        if not models:
            raise Exception("No models available.")
        model = model or models[0].model
        history_messages = ModelMessage.messages_to_string(
            messages[:-1], human_prefix="user", ai_prefix="assistant"
        )

        prompt_template = self._prompt_template or default_prompt

        template: PromptTemplate = PromptTemplate.from_template(prompt_template)
        response_schema = self.response_schema
        response_format = self._response_format or response_schema.to_response_format()
        formatted_message = template.format(
            response=response_format,
            example=self._examples,
            intent_definitions=self._intent_definitions,
            history=history_messages,
            user_input=messages[-1].content,
        )
        model_messages = ModelMessage.build_human_message(formatted_message)
        model_request = ModelRequest.build_request(model, messages=[model_messages])
        model_output = await self.llm_client.generate(model_request)
        output_parser = BaseOutputParser()
        str_out = output_parser.parse_model_nostream_resp(model_output)
        json_out = output_parser.parse_prompt_response(str_out)
        dict_out = json.loads(json_out)
        return response_schema.model_validate(dict_out)
