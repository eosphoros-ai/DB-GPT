"""AWEL: Simple llm client example

    DB-GPT will automatically load and execute the current file after startup.

    Example:

    .. code-block:: shell

        DBGPT_SERVER="http://127.0.0.1:5000"
        curl -X POST $DBGPT_SERVER/api/v1/awel/trigger/examples/simple_client/generate \
        -H "Content-Type: application/json" -d '{
            "model": "proxyllm",
            "messages": "hello"
        }'

        curl -X POST $DBGPT_SERVER/api/v1/awel/trigger/examples/simple_client/generate_stream \
        -H "Content-Type: application/json" -d '{
            "model": "proxyllm",
            "messages": "hello",
            "stream": true
        }'

        curl -X POST $DBGPT_SERVER/api/v1/awel/trigger/examples/simple_client/count_token \
        -H "Content-Type: application/json" -d '{
            "model": "proxyllm",
            "messages": "hello"
        }'

"""
from typing import Dict, Any, AsyncIterator, Optional, Union, List
from dbgpt._private.pydantic import BaseModel, Field
from dbgpt.component import ComponentType
from dbgpt.core.awel import DAG, HttpTrigger, MapOperator, TransformStreamAbsOperator
from dbgpt.core import (
    ModelMessage,
    LLMClient,
    LLMOperator,
    StreamingLLMOperator,
    ModelOutput,
    ModelRequest,
)
from dbgpt.model import DefaultLLMClient
from dbgpt.model.cluster import WorkerManagerFactory


class TriggerReqBody(BaseModel):
    messages: Union[str, List[Dict[str, str]]] = Field(
        ..., description="User input messages"
    )
    model: str = Field(..., description="Model name")
    stream: Optional[bool] = Field(default=False, description="Whether return stream")


class RequestHandleOperator(MapOperator[TriggerReqBody, ModelRequest]):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    async def map(self, input_value: TriggerReqBody) -> ModelRequest:
        messages = [ModelMessage.build_human_message(input_value.messages)]
        await self.current_dag_context.save_to_share_data(
            "request_model_name", input_value.model
        )
        return ModelRequest(
            model=input_value.model,
            messages=messages,
            echo=False,
        )


class LLMMixin:
    @property
    def llm_client(self) -> LLMClient:
        if not self._llm_client:
            worker_manager = self.system_app.get_component(
                ComponentType.WORKER_MANAGER_FACTORY, WorkerManagerFactory
            ).create()
            self._llm_client = DefaultLLMClient(worker_manager)
        return self._llm_client


class MyLLMOperator(LLMMixin, LLMOperator):
    def __init__(self, llm_client: LLMClient = None, **kwargs):
        super().__init__(llm_client, **kwargs)


class MyStreamingLLMOperator(LLMMixin, StreamingLLMOperator):
    def __init__(self, llm_client: LLMClient = None, **kwargs):
        super().__init__(llm_client, **kwargs)


class MyLLMStreamingOperator(TransformStreamAbsOperator[ModelOutput, str]):
    async def transform_stream(
        self, input_value: AsyncIterator[ModelOutput]
    ) -> AsyncIterator[str]:
        from dbgpt.model.utils.chatgpt_utils import _to_openai_stream

        model = await self.current_dag_context.get_share_data("request_model_name")
        async for output in _to_openai_stream(model, input_value):
            yield output


class MyModelToolOperator(LLMMixin, MapOperator[TriggerReqBody, Dict[str, Any]]):
    def __init__(self, llm_client: LLMClient = None, **kwargs):
        self._llm_client = llm_client
        MapOperator.__init__(self, **kwargs)

    async def map(self, input_value: TriggerReqBody) -> Dict[str, Any]:
        prompt_tokens = await self.llm_client.count_token(
            input_value.model, input_value.messages
        )
        available_models = await self.llm_client.models()
        return {
            "prompt_tokens": prompt_tokens,
            "available_models": available_models,
        }


with DAG("dbgpt_awel_simple_llm_client_generate") as client_generate_dag:
    # Receive http request and trigger dag to run.
    trigger = HttpTrigger(
        "/examples/simple_client/generate", methods="POST", request_body=TriggerReqBody
    )
    request_handle_task = RequestHandleOperator()
    model_task = MyLLMOperator()
    model_parse_task = MapOperator(lambda out: out.to_dict())
    trigger >> request_handle_task >> model_task >> model_parse_task

with DAG("dbgpt_awel_simple_llm_client_generate_stream") as client_generate_stream_dag:
    # Receive http request and trigger dag to run.
    trigger = HttpTrigger(
        "/examples/simple_client/generate_stream",
        methods="POST",
        request_body=TriggerReqBody,
        streaming_response=True,
    )
    request_handle_task = RequestHandleOperator()
    model_task = MyStreamingLLMOperator()
    openai_format_stream_task = MyLLMStreamingOperator()
    trigger >> request_handle_task >> model_task >> openai_format_stream_task

with DAG("dbgpt_awel_simple_llm_client_count_token") as client_count_token_dag:
    # Receive http request and trigger dag to run.
    trigger = HttpTrigger(
        "/examples/simple_client/count_token",
        methods="POST",
        request_body=TriggerReqBody,
    )
    model_task = MyModelToolOperator()
    trigger >> model_task
