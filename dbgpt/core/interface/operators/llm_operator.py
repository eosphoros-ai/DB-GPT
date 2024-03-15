"""The LLM operator."""

import dataclasses
from abc import ABC
from typing import Any, AsyncIterator, Dict, List, Optional, Union

from dbgpt._private.pydantic import BaseModel
from dbgpt.core.awel import (
    BaseOperator,
    BranchFunc,
    BranchOperator,
    CommonLLMHttpRequestBody,
    CommonLLMHttpResponseBody,
    DAGContext,
    JoinOperator,
    MapOperator,
    StreamifyAbsOperator,
    TransformStreamAbsOperator,
)
from dbgpt.core.awel.flow import (
    IOField,
    OperatorCategory,
    OperatorType,
    Parameter,
    ViewMetadata,
)
from dbgpt.core.interface.llm import (
    LLMClient,
    ModelOutput,
    ModelRequest,
    ModelRequestContext,
)
from dbgpt.core.interface.message import ModelMessage
from dbgpt.util.function_utils import rearrange_args_by_type

RequestInput = Union[
    ModelRequest,
    str,
    Dict[str, Any],
    BaseModel,
    ModelMessage,
    List[ModelMessage],
]


class RequestBuilderOperator(MapOperator[RequestInput, ModelRequest]):
    """Build the model request from the input value."""

    metadata = ViewMetadata(
        label="Build Model Request",
        name="request_builder_operator",
        category=OperatorCategory.COMMON,
        description="Build the model request from the http request body.",
        parameters=[
            Parameter.build_from(
                "Default Model Name",
                "model",
                str,
                optional=True,
                default=None,
                description="The model name of the model request.",
            ),
        ],
        inputs=[
            IOField.build_from(
                "Request Body",
                "input_value",
                CommonLLMHttpRequestBody,
                description="The input value of the operator.",
            ),
        ],
        outputs=[
            IOField.build_from(
                "Model Request",
                "output_value",
                ModelRequest,
                description="The output value of the operator.",
            ),
        ],
    )

    def __init__(self, model: Optional[str] = None, **kwargs):
        """Create a new request builder operator."""
        self._model = model
        super().__init__(**kwargs)

    async def map(self, input_value: RequestInput) -> ModelRequest:
        """Transform the input value to a model request."""
        req_dict: Dict[str, Any] = {}
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
        elif dataclasses.is_dataclass(input_value) and not isinstance(
            input_value, type
        ):
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


class MergedRequestBuilderOperator(JoinOperator[ModelRequest]):
    """Build the model request from the input value."""

    metadata = ViewMetadata(
        label="Merge Model Request Messages",
        name="merged_request_builder_operator",
        category=OperatorCategory.COMMON,
        description="Merge the model request from the input value.",
        parameters=[],
        inputs=[
            IOField.build_from(
                "Model Request",
                "model_request",
                ModelRequest,
                description="The model request of upstream.",
            ),
            IOField.build_from(
                "Model messages",
                "messages",
                ModelMessage,
                description="The model messages of upstream.",
                is_list=True,
            ),
        ],
        outputs=[
            IOField.build_from(
                "Model Request",
                "output_value",
                ModelRequest,
                description="The output value of the operator.",
            ),
        ],
    )

    def __init__(self, **kwargs):
        """Create a new request builder operator."""
        super().__init__(combine_function=self.merge_func, **kwargs)

    @rearrange_args_by_type
    def merge_func(
        self, model_request: ModelRequest, messages: List[ModelMessage]
    ) -> ModelRequest:
        """Merge the model request with the messages."""
        model_request.messages = messages
        return model_request


class BaseLLM:
    """The abstract operator for a LLM."""

    SHARE_DATA_KEY_MODEL_NAME = "share_data_key_model_name"
    SHARE_DATA_KEY_MODEL_OUTPUT = "share_data_key_model_output"

    def __init__(self, llm_client: Optional[LLMClient] = None):
        """Create a new LLM operator."""
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
        """Create a new LLM operator."""
        super().__init__(llm_client=llm_client)
        MapOperator.__init__(self, **kwargs)

    async def map(self, request: ModelRequest) -> ModelOutput:
        """Generate the model output.

        Args:
            request (ModelRequest): The model request.

        Returns:
            ModelOutput: The model output.
        """
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
        """Create a streaming operator for a LLM.

        Args:
            llm_client (LLMClient, optional): The LLM client. Defaults to None.
        """
        super().__init__(llm_client=llm_client)
        BaseOperator.__init__(self, **kwargs)

    async def streamify(  # type: ignore
        self, request: ModelRequest  # type: ignore
    ) -> AsyncIterator[ModelOutput]:  # type: ignore
        """Streamify the request."""
        await self.current_dag_context.save_to_share_data(
            self.SHARE_DATA_KEY_MODEL_NAME, request.model
        )
        model_output = None
        async for output in self.llm_client.generate_stream(request):  # type: ignore
            model_output = output
            yield output
        if model_output:
            await self.save_model_output(self.current_dag_context, model_output)


class LLMBranchOperator(BranchOperator[ModelRequest, ModelRequest]):
    """Branch operator for LLM.

    This operator will branch the workflow based on
    the stream flag of the request.
    """

    metadata = ViewMetadata(
        label="LLM Branch Operator",
        name="llm_branch_operator",
        category=OperatorCategory.LLM,
        operator_type=OperatorType.BRANCH,
        description="Branch the workflow based on the stream flag of the request.",
        parameters=[
            Parameter.build_from(
                "Streaming Task Name",
                "stream_task_name",
                str,
                optional=True,
                default="streaming_llm_task",
                description="The name of the streaming task.",
            ),
            Parameter.build_from(
                "Non-Streaming Task Name",
                "no_stream_task_name",
                str,
                optional=True,
                default="llm_task",
                description="The name of the non-streaming task.",
            ),
        ],
        inputs=[
            IOField.build_from(
                "Model Request",
                "input_value",
                ModelRequest,
                description="The input value of the operator.",
            ),
        ],
        outputs=[
            IOField.build_from(
                "Streaming Model Request",
                "streaming_request",
                ModelRequest,
                description="The streaming request, to streaming Operator.",
            ),
            IOField.build_from(
                "Non-Streaming Model Request",
                "no_streaming_request",
                ModelRequest,
                description="The non-streaming request, to non-streaming Operator.",
            ),
        ],
    )

    def __init__(self, stream_task_name: str, no_stream_task_name: str, **kwargs):
        """Create a new LLM branch operator.

        Args:
            stream_task_name (str): The name of the streaming task.
            no_stream_task_name (str): The name of the non-streaming task.
        """
        super().__init__(**kwargs)
        if not stream_task_name:
            raise ValueError("stream_task_name is not set")
        if not no_stream_task_name:
            raise ValueError("no_stream_task_name is not set")
        self._stream_task_name = stream_task_name
        self._no_stream_task_name = no_stream_task_name

    async def branches(
        self,
    ) -> Dict[BranchFunc[ModelRequest], Union[BaseOperator, str]]:
        """
        Return a dict of branch function and task name.

        Returns:
            Dict[BranchFunc[ModelRequest], str]: A dict of branch function and task
                name. the key is a predicate function, the value is the task name.
                If the predicate function returns True, we will run the corresponding
                task.
        """

        async def check_stream_true(r: ModelRequest) -> bool:
            # If stream is true, we will run the streaming task. otherwise, we will run
            # the non-streaming task.
            return r.stream

        return {
            check_stream_true: self._stream_task_name,
            lambda x: not x.stream: self._no_stream_task_name,
        }


class ModelOutput2CommonResponseOperator(
    MapOperator[ModelOutput, CommonLLMHttpResponseBody]
):
    """Map the model output to the common response body."""

    metadata = ViewMetadata(
        label="Map Model Output to Common Response Body",
        name="model_output_2_common_response_body_operator",
        category=OperatorCategory.COMMON,
        description="Map the model output to the common response body.",
        parameters=[],
        inputs=[
            IOField.build_from(
                "Model Output",
                "input_value",
                ModelOutput,
                description="The input value of the operator.",
            ),
        ],
        outputs=[
            IOField.build_from(
                "Common Response Body",
                "output_value",
                CommonLLMHttpResponseBody,
                description="The output value of the operator.",
            ),
        ],
    )

    def __int__(self, **kwargs):
        """Create a new operator."""
        super().__init__(**kwargs)

    async def map(self, input_value: ModelOutput) -> CommonLLMHttpResponseBody:
        """Map the model output to the common response body."""
        metrics = input_value.metrics.to_dict() if input_value.metrics else None
        return CommonLLMHttpResponseBody(
            text=input_value.text,
            error_code=input_value.error_code,
            metrics=metrics,
        )


class CommonStreamingOutputOperator(TransformStreamAbsOperator[ModelOutput, str]):
    """The Common Streaming Output Operator.

    Transform model output to the string output to show in DB-GPT chat flow page.
    """

    metadata = ViewMetadata(
        label="Common Streaming Output Operator",
        name="common_streaming_output_operator",
        operator_type=OperatorType.TRANSFORM_STREAM,
        category=OperatorCategory.OUTPUT_PARSER,
        description="The common streaming LLM operator, for chat flow.",
        parameters=[],
        inputs=[
            IOField.build_from(
                "Upstream Model Output",
                "output_iter",
                ModelOutput,
                is_list=True,
                description="The model output of upstream.",
            )
        ],
        outputs=[
            IOField.build_from(
                "Model Output",
                "model_output",
                str,
                is_list=True,
                description="The model output after transform to common stream format",
            )
        ],
    )

    async def transform_stream(self, output_iter: AsyncIterator[ModelOutput]):
        """Transform upstream output iter to string foramt."""
        async for model_output in output_iter:
            if model_output.error_code != 0:
                error_msg = (
                    f"[ERROR](error_code: {model_output.error_code}): "
                    f"{model_output.text}"
                )
                yield f"data:{error_msg}"
                return
            decoded_unicode = model_output.text.replace("\ufffd", "")
            msg = decoded_unicode.replace("\n", "\\n")
            yield f"data:{msg}\n\n"


class StringOutput2ModelOutputOperator(MapOperator[str, ModelOutput]):
    """Map String to ModelOutput."""

    metadata = ViewMetadata(
        label="Map String to ModelOutput",
        name="string_2_model_output_operator",
        category=OperatorCategory.COMMON,
        description="Map String to ModelOutput.",
        parameters=[],
        inputs=[
            IOField.build_from(
                "String",
                "input_value",
                str,
                description="The input value of the operator.",
            ),
        ],
        outputs=[
            IOField.build_from(
                "Model Output",
                "input_value",
                ModelOutput,
                description="The input value of the operator.",
            ),
        ],
    )

    def __int__(self, **kwargs):
        """Create a new operator."""
        super().__init__(**kwargs)

    async def map(self, input_value: str) -> ModelOutput:
        """Map the model output to the common response body."""
        return ModelOutput(
            text=input_value,
            error_code=500,
        )
