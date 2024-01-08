import dataclasses
from abc import ABC
from typing import Any, AsyncIterator, Dict, List, Optional, Union

from dbgpt._private.pydantic import BaseModel
from dbgpt.core.awel import (
    BranchFunc,
    BranchOperator,
    DAGContext,
    MapOperator,
    StreamifyAbsOperator,
)
from dbgpt.core.interface.llm import (
    LLMClient,
    ModelOutput,
    ModelRequest,
    ModelRequestContext,
)
from dbgpt.core.interface.message import ModelMessage

RequestInput = Union[
    ModelRequest,
    str,
    Dict[str, Any],
    BaseModel,
    ModelMessage,
    List[ModelMessage],
]


class RequestBuilderOperator(MapOperator[RequestInput, ModelRequest], ABC):
    """Build the model request from the input value."""

    def __init__(self, model: Optional[str] = None, **kwargs):
        self._model = model
        super().__init__(**kwargs)

    async def map(self, input_value: RequestInput) -> ModelRequest:
        req_dict = {}
        if not input_value:
            raise ValueError("input_value is not set")
        if isinstance(input_value, str):
            req_dict = {"messages": [ModelMessage.build_human_message(input_value)]}
        elif isinstance(input_value, dict):
            req_dict = input_value
        elif isinstance(input_value, ModelMessage):
            req_dict = {"messages": [input_value]}
        elif isinstance(input_value, list) and isinstance(input_value[0], ModelMessage):
            req_dict = {"messages": input_value}
        elif dataclasses.is_dataclass(input_value):
            req_dict = dataclasses.asdict(input_value)
        elif isinstance(input_value, BaseModel):
            req_dict = input_value.dict()
        elif isinstance(input_value, ModelRequest):
            if not input_value.model:
                input_value.model = self._model
            return input_value
        if "messages" not in req_dict:
            raise ValueError("messages is not set")
        messages = req_dict["messages"]
        if isinstance(messages, str):
            # Single message, transform to a list including one human message
            req_dict["messages"] = [ModelMessage.build_human_message(messages)]
        if "model" not in req_dict:
            req_dict["model"] = self._model
        if not req_dict["model"]:
            raise ValueError("model is not set")
        stream = False
        has_stream = False
        if "stream" in req_dict:
            has_stream = True
            stream = req_dict["stream"]
            del req_dict["stream"]
        if "context" not in req_dict:
            req_dict["context"] = ModelRequestContext(stream=stream)
        else:
            context_dict = req_dict["context"]
            if not isinstance(context_dict, dict):
                raise ValueError("context is not a dict")
            if has_stream:
                context_dict["stream"] = stream
            req_dict["context"] = ModelRequestContext(**context_dict)
        return ModelRequest(**req_dict)


class BaseLLM:
    """The abstract operator for a LLM."""

    SHARE_DATA_KEY_MODEL_NAME = "share_data_key_model_name"
    SHARE_DATA_KEY_MODEL_OUTPUT = "share_data_key_model_output"

    def __init__(self, llm_client: Optional[LLMClient] = None):
        self._llm_client = llm_client

    @property
    def llm_client(self) -> LLMClient:
        """Return the LLM client."""
        if not self._llm_client:
            raise ValueError("llm_client is not set")
        return self._llm_client

    async def save_model_output(
        self, current_dag_context: DAGContext, model_output: ModelOutput
    ) -> None:
        """Save the model output to the share data."""
        await current_dag_context.save_to_share_data(
            self.SHARE_DATA_KEY_MODEL_OUTPUT, model_output
        )


class BaseLLMOperator(BaseLLM, MapOperator[ModelRequest, ModelOutput], ABC):
    """The operator for a LLM.

    Args:
        llm_client (LLMClient, optional): The LLM client. Defaults to None.

    This operator will generate a no streaming response.
    """

    def __init__(self, llm_client: Optional[LLMClient] = None, **kwargs):
        super().__init__(llm_client=llm_client)
        MapOperator.__init__(self, **kwargs)

    async def map(self, request: ModelRequest) -> ModelOutput:
        await self.current_dag_context.save_to_share_data(
            self.SHARE_DATA_KEY_MODEL_NAME, request.model
        )
        model_output = await self.llm_client.generate(request)
        await self.save_model_output(self.current_dag_context, model_output)
        return model_output


class BaseStreamingLLMOperator(
    BaseLLM, StreamifyAbsOperator[ModelRequest, ModelOutput], ABC
):
    """The streaming operator for a LLM.

    Args:
        llm_client (LLMClient, optional): The LLM client. Defaults to None.

    This operator will generate streaming response.
    """

    def __init__(self, llm_client: Optional[LLMClient] = None, **kwargs):
        super().__init__(llm_client=llm_client)
        StreamifyAbsOperator.__init__(self, **kwargs)

    async def streamify(self, request: ModelRequest) -> AsyncIterator[ModelOutput]:
        await self.current_dag_context.save_to_share_data(
            self.SHARE_DATA_KEY_MODEL_NAME, request.model
        )
        model_output = None
        async for output in self.llm_client.generate_stream(request):
            model_output = output
            yield output
        if model_output:
            await self.save_model_output(self.current_dag_context, model_output)


class LLMBranchOperator(BranchOperator[ModelRequest, ModelRequest]):
    """Branch operator for LLM.

    This operator will branch the workflow based on the stream flag of the request.
    """

    def __init__(self, stream_task_name: str, no_stream_task_name: str, **kwargs):
        super().__init__(**kwargs)
        if not stream_task_name:
            raise ValueError("stream_task_name is not set")
        if not no_stream_task_name:
            raise ValueError("no_stream_task_name is not set")
        self._stream_task_name = stream_task_name
        self._no_stream_task_name = no_stream_task_name

    async def branches(self) -> Dict[BranchFunc[ModelRequest], str]:
        """
        Return a dict of branch function and task name.

        Returns:
            Dict[BranchFunc[ModelRequest], str]: A dict of branch function and task name.
                the key is a predicate function, the value is the task name. If the predicate function returns True,
                we will run the corresponding task.
        """

        async def check_stream_true(r: ModelRequest) -> bool:
            # If stream is true, we will run the streaming task. otherwise, we will run the non-streaming task.
            return r.stream

        return {
            check_stream_true: self._stream_task_name,
            lambda x: not x.stream: self._no_stream_task_name,
        }
