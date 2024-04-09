import json
import logging
import time
import traceback
from typing import Any, AsyncIterator, List, Optional, cast

import schedule
from fastapi import HTTPException

from dbgpt._private.pydantic import model_to_json
from dbgpt.component import SystemApp
from dbgpt.core.awel import (
    DAG,
    BaseOperator,
    CommonLLMHttpRequestBody,
    CommonLLMHttpResponseBody,
)
from dbgpt.core.awel.dag.dag_manager import DAGManager
from dbgpt.core.awel.flow.flow_factory import (
    FlowCategory,
    FlowFactory,
    State,
    fill_flow_panel,
)
from dbgpt.core.awel.trigger.http_trigger import CommonLLMHttpTrigger
from dbgpt.core.interface.llm import ModelOutput
from dbgpt.core.schema.api import (
    ChatCompletionResponse,
    ChatCompletionResponseChoice,
    ChatCompletionResponseStreamChoice,
    ChatCompletionStreamResponse,
    DeltaMessage,
)
from dbgpt.serve.core import BaseService
from dbgpt.storage.metadata import BaseDao
from dbgpt.storage.metadata._base_dao import QUERY_SPEC
from dbgpt.util.dbgpts.loader import DBGPTsLoader
from dbgpt.util.pagination_utils import PaginationResult

from ..api.schemas import ServeRequest, ServerResponse
from ..config import SERVE_CONFIG_KEY_PREFIX, SERVE_SERVICE_COMPONENT_NAME, ServeConfig
from ..models.models import ServeDao, ServeEntity

logger = logging.getLogger(__name__)


class Service(BaseService[ServeEntity, ServeRequest, ServerResponse]):
    """The service class for Flow"""

    name = SERVE_SERVICE_COMPONENT_NAME

    def __init__(self, system_app: SystemApp, dao: Optional[ServeDao] = None):
        self._system_app = None
        self._serve_config: ServeConfig = None
        self._dao: ServeDao = dao
        self._dag_manager: Optional[DAGManager] = None
        self._flow_factory: FlowFactory = FlowFactory()
        self._dbgpts_loader: Optional[DBGPTsLoader] = None

        super().__init__(system_app)

    def init_app(self, system_app: SystemApp) -> None:
        """Initialize the service

        Args:
            system_app (SystemApp): The system app
        """
        self._serve_config = ServeConfig.from_app_config(
            system_app.config, SERVE_CONFIG_KEY_PREFIX
        )
        self._dao = self._dao or ServeDao(self._serve_config)
        self._system_app = system_app
        self._dbgpts_loader = system_app.get_component(
            DBGPTsLoader.name,
            DBGPTsLoader,
            or_register_component=DBGPTsLoader,
            load_dbgpts_interval=self._serve_config.load_dbgpts_interval,
        )

    def before_start(self):
        """Execute before the application starts"""
        self._dag_manager = DAGManager.get_instance(self._system_app)
        self._pre_load_dag_from_db()
        self._pre_load_dag_from_dbgpts()

    def after_start(self):
        """Execute after the application starts"""
        self.load_dag_from_db()
        self.load_dag_from_dbgpts(is_first_load=True)
        schedule.every(self._serve_config.load_dbgpts_interval).seconds.do(
            self.load_dag_from_dbgpts
        )

    @property
    def dao(self) -> BaseDao[ServeEntity, ServeRequest, ServerResponse]:
        """Returns the internal DAO."""
        return self._dao

    @property
    def dag_manager(self) -> DAGManager:
        """Returns the internal DAGManager."""
        if self._dag_manager is None:
            raise ValueError("DAGManager is not initialized")
        return self._dag_manager

    @property
    def dbgpts_loader(self) -> DBGPTsLoader:
        """Returns the internal DBGPTsLoader."""
        if self._dbgpts_loader is None:
            raise ValueError("DBGPTsLoader is not initialized")
        return self._dbgpts_loader

    @property
    def config(self) -> ServeConfig:
        """Returns the internal ServeConfig."""
        return self._serve_config

    def create(self, request: ServeRequest) -> ServerResponse:
        """Create a new Flow entity

        Args:
            request (ServeRequest): The request

        Returns:
            ServerResponse: The response
        """

    def create_and_save_dag(
        self, request: ServeRequest, save_failed_flow: bool = False
    ) -> ServerResponse:
        """Create a new Flow entity and save the DAG

        Args:
            request (ServeRequest): The request
            save_failed_flow (bool): Whether to save the failed flow

        Returns:
            ServerResponse: The response
        """
        try:
            # Build DAG from request
            dag = self._flow_factory.build(request)
            request.dag_id = dag.dag_id
            # Save DAG to storage
            request.flow_category = self._parse_flow_category(dag)
        except Exception as e:
            if save_failed_flow:
                request.state = State.LOAD_FAILED
                request.error_message = str(e)
                request.dag_id = ""
                return self.dao.create(request)
            else:
                raise e
        res = self.dao.create(request)

        state = request.state
        try:
            if state == State.DEPLOYED:
                # Register the DAG
                self.dag_manager.register_dag(dag, request.uid)
                # Update state to RUNNING
                request.state = State.RUNNING
                request.error_message = ""
                self.dao.update({"uid": request.uid}, request)
            else:
                logger.info(f"Flow state is {state}, skip register DAG")
        except Exception as e:
            logger.warning(f"Register DAG({dag.dag_id}) error: {str(e)}")
            if save_failed_flow:
                request.state = State.LOAD_FAILED
                request.error_message = f"Register DAG error: {str(e)}"
                request.dag_id = ""
                self.dao.update({"uid": request.uid}, request)
            else:
                # Rollback
                self.delete(request.uid)
            raise e
        return res

    def _pre_load_dag_from_db(self):
        """Pre load DAG from db"""
        entities = self.dao.get_list({})
        for entity in entities:
            try:
                self._flow_factory.pre_load_requirements(entity)
            except Exception as e:
                logger.warning(
                    f"Pre load requirements for DAG({entity.name}, {entity.dag_id}) "
                    f"from db error: {str(e)}"
                )

    def load_dag_from_db(self):
        """Load DAG from db"""
        entities = self.dao.get_list({})
        for entity in entities:
            try:
                dag = self._flow_factory.build(entity)
                if entity.state in [State.DEPLOYED, State.RUNNING] or (
                    entity.version == "0.1.0" and entity.state == State.INITIALIZING
                ):
                    # Register the DAG
                    self.dag_manager.register_dag(dag, entity.uid)
                    # Update state to RUNNING
                    entity.state = State.RUNNING
                    entity.error_message = ""
                    self.dao.update({"uid": entity.uid}, entity)
            except Exception as e:
                logger.warning(
                    f"Load DAG({entity.name}, {entity.dag_id}) from db error: {str(e)}"
                )

    def _pre_load_dag_from_dbgpts(self):
        """Pre load DAG from dbgpts"""
        flows = self.dbgpts_loader.get_flows()
        for flow in flows:
            try:
                self._flow_factory.pre_load_requirements(flow)
            except Exception as e:
                logger.warning(
                    f"Pre load requirements for DAG({flow.name}) from "
                    f"dbgpts error: {str(e)}"
                )

    def load_dag_from_dbgpts(self, is_first_load: bool = False):
        """Load DAG from dbgpts"""
        flows = self.dbgpts_loader.get_flows()
        for flow in flows:
            try:
                # Set state to DEPLOYED
                flow.state = State.DEPLOYED
                exist_inst = self.get({"name": flow.name})
                if not exist_inst:
                    self.create_and_save_dag(flow, save_failed_flow=True)
                elif is_first_load or exist_inst.state != State.RUNNING:
                    # TODO check version, must be greater than the exist one
                    flow.uid = exist_inst.uid
                    self.update_flow(flow, check_editable=False, save_failed_flow=True)
            except Exception as e:
                message = traceback.format_exc()
                logger.warning(
                    f"Load DAG {flow.name} from dbgpts error: {str(e)}, detail: {message}"
                )

    def update_flow(
        self,
        request: ServeRequest,
        check_editable: bool = True,
        save_failed_flow: bool = False,
    ) -> ServerResponse:
        """Update a Flow entity

        Args:
            request (ServeRequest): The request
            check_editable (bool): Whether to check the editable
            save_failed_flow (bool): Whether to save the failed flow
        Returns:
            ServerResponse: The response
        """
        new_state = request.state
        try:
            # Try to build the dag from the request
            dag = self._flow_factory.build(request)
            request.flow_category = self._parse_flow_category(dag)
        except Exception as e:
            if save_failed_flow:
                request.state = State.LOAD_FAILED
                request.error_message = str(e)
                request.dag_id = ""
                return self.dao.update({"uid": request.uid}, request)
            else:
                raise e
        # Build the query request from the request
        query_request = {"uid": request.uid}
        inst = self.get(query_request)
        if not inst:
            raise HTTPException(status_code=404, detail=f"Flow {request.uid} not found")
        if check_editable and not inst.editable:
            raise HTTPException(
                status_code=403, detail=f"Flow {request.uid} is not editable"
            )
        old_state = inst.state
        if not State.can_change_state(old_state, new_state):
            raise HTTPException(
                status_code=400,
                detail=f"Flow {request.uid} state can't change from {old_state} to "
                f"{new_state}",
            )
        old_data: Optional[ServerResponse] = None
        try:
            update_obj = self.dao.update(query_request, update_request=request)
            old_data = self.delete(request.uid)
            old_data.state = old_state
            if not old_data:
                raise HTTPException(
                    status_code=404, detail=f"Flow detail {request.uid} not found"
                )
            return self.create_and_save_dag(update_obj)
        except Exception as e:
            if old_data:
                self.create_and_save_dag(old_data)
            raise e

    def get(self, request: QUERY_SPEC) -> Optional[ServerResponse]:
        """Get a Flow entity

        Args:
            request (ServeRequest): The request

        Returns:
            ServerResponse: The response
        """
        # TODO: implement your own logic here
        # Build the query request from the request
        query_request = request
        flow = self.dao.get_one(query_request)
        if flow:
            fill_flow_panel(flow)
        return flow

    def delete(self, uid: str) -> Optional[ServerResponse]:
        """Delete a Flow entity

        Args:
            uid (str): The uid

        Returns:
            ServerResponse: The data after deletion
        """

        # TODO: implement your own logic here
        # Build the query request from the request
        query_request = {"uid": uid}
        inst = self.get(query_request)
        if inst is None:
            raise HTTPException(status_code=404, detail=f"Flow {uid} not found")
        if inst.state == State.RUNNING and not inst.dag_id:
            raise HTTPException(
                status_code=404, detail=f"Running flow {uid}'s dag id not found"
            )
        try:
            if inst.dag_id:
                self.dag_manager.unregister_dag(inst.dag_id)
        except Exception as e:
            logger.warning(f"Unregister DAG({inst.dag_id}) error: {str(e)}")
        self.dao.delete(query_request)
        return inst

    def get_list(self, request: ServeRequest) -> List[ServerResponse]:
        """Get a list of Flow entities

        Args:
            request (ServeRequest): The request

        Returns:
            List[ServerResponse]: The response
        """
        # TODO: implement your own logic here
        # Build the query request from the request
        query_request = request
        return self.dao.get_list(query_request)

    def get_list_by_page(
        self, request: QUERY_SPEC, page: int, page_size: int
    ) -> PaginationResult[ServerResponse]:
        """Get a list of Flow entities by page

        Args:
            request (ServeRequest): The request
            page (int): The page number
            page_size (int): The page size

        Returns:
            List[ServerResponse]: The response
        """
        return self.dao.get_list_page(request, page, page_size)

    async def chat_stream_flow_str(
        self, flow_uid: str, request: CommonLLMHttpRequestBody
    ) -> AsyncIterator[str]:
        """Stream chat with the AWEL flow.

        Args:
            flow_uid (str): The flow uid
            request (CommonLLMHttpRequestBody): The request
        """
        # Must be non-incremental
        request.incremental = False
        async for output in self.safe_chat_stream_flow(flow_uid, request):
            text = output.text
            # if text:
            #     text = text.replace("\n", "\\n")
            if output.error_code != 0:
                yield f"data:[SERVER_ERROR]{text}\n\n"
                break
            else:
                yield f"data:{text}\n\n"

    async def chat_stream_openai(
        self, flow_uid: str, request: CommonLLMHttpRequestBody
    ) -> AsyncIterator[str]:
        conv_uid = request.conv_uid
        choice_data = ChatCompletionResponseStreamChoice(
            index=0,
            delta=DeltaMessage(role="assistant"),
            finish_reason=None,
        )
        chunk = ChatCompletionStreamResponse(
            id=conv_uid, choices=[choice_data], model=request.model
        )
        yield f"data: {chunk.json(exclude_unset=True, ensure_ascii=False)}\n\n"

        request.incremental = True
        async for output in self.safe_chat_stream_flow(flow_uid, request):
            if not output.success:
                yield f"data: {json.dumps(output.to_dict(), ensure_ascii=False)}\n\n"
                yield "data: [DONE]\n\n"
                return
            choice_data = ChatCompletionResponseStreamChoice(
                index=0,
                delta=DeltaMessage(role="assistant", content=output.text),
            )
            chunk = ChatCompletionStreamResponse(
                id=conv_uid,
                choices=[choice_data],
                model=request.model,
            )
            json_data = model_to_json(chunk, exclude_unset=True, ensure_ascii=False)
            yield f"data: {json_data}\n\n"
        yield "data: [DONE]\n\n"

    async def safe_chat_flow(
        self, flow_uid: str, request: CommonLLMHttpRequestBody
    ) -> ModelOutput:
        """Chat with the AWEL flow.

        Args:
            flow_uid (str): The flow uid
            request (CommonLLMHttpRequestBody): The request

        Returns:
            ModelOutput: The output
        """
        incremental = request.incremental
        try:
            task = await self._get_callable_task(flow_uid)
            return await _safe_chat_with_dag_task(task, request)
        except HTTPException as e:
            return ModelOutput(error_code=1, text=e.detail, incremental=incremental)
        except Exception as e:
            return ModelOutput(error_code=1, text=str(e), incremental=incremental)

    async def safe_chat_stream_flow(
        self, flow_uid: str, request: CommonLLMHttpRequestBody
    ) -> AsyncIterator[ModelOutput]:
        """Stream chat with the AWEL flow.

        Args:
            flow_uid (str): The flow uid
            request (CommonLLMHttpRequestBody): The request

        Returns:
            AsyncIterator[ModelOutput]: The output
        """
        incremental = request.incremental
        try:
            task = await self._get_callable_task(flow_uid)
            async for output in _safe_chat_stream_with_dag_task(
                task, request, incremental
            ):
                yield output
        except HTTPException as e:
            yield ModelOutput(error_code=1, text=e.detail, incremental=incremental)
        except Exception as e:
            yield ModelOutput(error_code=1, text=str(e), incremental=incremental)

    async def _get_callable_task(
        self,
        flow_uid: str,
    ) -> BaseOperator:
        """Return the callable task.

        Returns:
            BaseOperator: The callable task

        Raises:
            HTTPException: If the flow is not found
            ValueError: If the flow is not a chat flow or the leaf node is not found.
        """
        flow = self.get({"uid": flow_uid})
        if not flow:
            raise HTTPException(status_code=404, detail=f"Flow {flow_uid} not found")
        dag_id = flow.dag_id
        if not dag_id or dag_id not in self.dag_manager.dag_map:
            raise HTTPException(
                status_code=404, detail=f"Flow {flow_uid}'s dag id not found"
            )
        dag = self.dag_manager.dag_map[dag_id]
        if (
            flow.flow_category != FlowCategory.CHAT_FLOW
            and self._parse_flow_category(dag) != FlowCategory.CHAT_FLOW
        ):
            raise ValueError(f"Flow {flow_uid} is not a chat flow")
        leaf_nodes = dag.leaf_nodes
        if len(leaf_nodes) != 1:
            raise ValueError("Chat Flow just support one leaf node in dag")
        return cast(BaseOperator, leaf_nodes[0])

    def _parse_flow_category(self, dag: DAG) -> FlowCategory:
        """Parse the flow category

        Args:
            flow_category (str): The flow category

        Returns:
            FlowCategory: The flow category
        """
        from dbgpt.core.awel.flow.base import _get_type_cls

        triggers = dag.trigger_nodes
        leaf_nodes = dag.leaf_nodes
        if (
            not triggers
            or not leaf_nodes
            or len(leaf_nodes) > 1
            or not isinstance(leaf_nodes[0], BaseOperator)
        ):
            return FlowCategory.COMMON
        common_http_trigger = False
        for trigger in triggers:
            if isinstance(trigger, CommonLLMHttpTrigger):
                common_http_trigger = True
                break
        leaf_node = cast(BaseOperator, leaf_nodes[0])
        if not leaf_node.metadata or not leaf_node.metadata.outputs:
            return FlowCategory.COMMON
        output = leaf_node.metadata.outputs[0]
        try:
            real_class = _get_type_cls(output.type_cls)
            if common_http_trigger and _is_chat_flow_type(real_class, is_class=True):
                return FlowCategory.CHAT_FLOW
        except Exception:
            return FlowCategory.COMMON


def _is_chat_flow_type(output_obj: Any, is_class: bool = False) -> bool:
    if is_class:
        return (
            output_obj == str
            or output_obj == CommonLLMHttpResponseBody
            or output_obj == ModelOutput
        )
    else:
        chat_types = (str, CommonLLMHttpResponseBody)
        return isinstance(output_obj, chat_types)


async def _safe_chat_with_dag_task(task: BaseOperator, request: Any) -> ModelOutput:
    """Chat with the DAG task."""
    try:
        finish_reason = None
        usage = None
        metrics = None
        error_code = 0
        text = ""
        async for output in _safe_chat_stream_with_dag_task(task, request, False):
            finish_reason = output.finish_reason
            usage = output.usage
            metrics = output.metrics
            error_code = output.error_code
            text = output.text
        return ModelOutput(
            error_code=error_code,
            text=text,
            metrics=metrics,
            usage=usage,
            finish_reason=finish_reason,
        )
    except Exception as e:
        return ModelOutput(error_code=1, text=str(e), incremental=False)


async def _safe_chat_stream_with_dag_task(
    task: BaseOperator,
    request: Any,
    incremental: bool,
) -> AsyncIterator[ModelOutput]:
    """Chat with the DAG task."""
    try:
        async for output in _chat_stream_with_dag_task(task, request, incremental):
            yield output
    except Exception as e:
        yield ModelOutput(error_code=1, text=str(e), incremental=incremental)
    finally:
        if task.streaming_operator:
            if task.dag:
                await task.dag._after_dag_end(task.current_event_loop_task_id)


async def _chat_stream_with_dag_task(
    task: BaseOperator,
    request: Any,
    incremental: bool,
) -> AsyncIterator[ModelOutput]:
    """Chat with the DAG task."""
    is_sse = task.output_format and task.output_format.upper() == "SSE"
    if not task.streaming_operator:
        try:
            result = await task.call(request)
            model_output = _parse_single_output(result, is_sse)
            model_output.incremental = incremental
            yield model_output
        except Exception as e:
            yield ModelOutput(error_code=1, text=str(e), incremental=incremental)
    else:
        from dbgpt.model.utils.chatgpt_utils import OpenAIStreamingOutputOperator

        if OpenAIStreamingOutputOperator and isinstance(
            task, OpenAIStreamingOutputOperator
        ):
            full_text = ""
            async for output in await task.call_stream(request):
                model_output = _parse_openai_output(output)
                # The output of the OpenAI streaming API is incremental
                full_text += model_output.text
                model_output.incremental = incremental
                model_output.text = model_output.text if incremental else full_text
                yield model_output
                if not model_output.success:
                    break
        else:
            full_text = ""
            previous_text = ""
            async for output in await task.call_stream(request):
                model_output = _parse_single_output(output, is_sse)
                model_output.incremental = incremental
                if task.incremental_output:
                    # Output is incremental, append the text
                    full_text += model_output.text
                else:
                    # Output is not incremental, last output is the full text
                    full_text = model_output.text
                if not incremental:
                    # Return the full text
                    model_output.text = full_text
                else:
                    # Return the incremental text
                    delta_text = full_text[len(previous_text) :]
                    previous_text = (
                        full_text
                        if len(full_text) > len(previous_text)
                        else previous_text
                    )
                    model_output.text = delta_text
                yield model_output
                if not model_output.success:
                    break


def _parse_single_output(output: Any, is_sse: bool) -> ModelOutput:
    """Parse the single output."""
    finish_reason = None
    usage = None
    metrics = None
    if output is None:
        error_code = 1
        text = "The output is None!"
    elif isinstance(output, str):
        if is_sse:
            sse_output = _parse_sse_data(output)
            if sse_output is None:
                error_code = 1
                text = "The output is not a SSE format"
            else:
                error_code = 0
                text = sse_output
        else:
            error_code = 0
            text = output
    elif isinstance(output, ModelOutput):
        error_code = output.error_code
        text = output.text
        finish_reason = output.finish_reason
        usage = output.usage
        metrics = output.metrics
    elif isinstance(output, CommonLLMHttpResponseBody):
        error_code = output.error_code
        text = output.text
    elif isinstance(output, dict):
        error_code = 0
        text = json.dumps(output, ensure_ascii=False)
    else:
        error_code = 1
        text = f"The output is not a valid format({type(output)})"
    return ModelOutput(
        error_code=error_code,
        text=text,
        finish_reason=finish_reason,
        usage=usage,
        metrics=metrics,
    )


def _parse_openai_output(output: Any) -> ModelOutput:
    """Parse the OpenAI output."""
    text = ""
    if not isinstance(output, str):
        return ModelOutput(
            error_code=1,
            text="The output is not a stream format",
        )
    if output.strip() == "data: [DONE]" or output.strip() == "data:[DONE]":
        return ModelOutput(error_code=0, text="")
    if not output.startswith("data:"):
        return ModelOutput(
            error_code=1,
            text="The output is not a stream format",
        )

    sse_output = _parse_sse_data(output)
    if sse_output is None:
        return ModelOutput(error_code=1, text="The output is not a SSE format")
    json_data = sse_output.strip()
    try:
        dict_data = json.loads(json_data)
    except Exception as e:
        return ModelOutput(
            error_code=1,
            text=f"Invalid JSON data: {json_data}, {e}",
        )
    if "choices" not in dict_data:
        return ModelOutput(
            error_code=1,
            text=dict_data.get("text", "Unknown error"),
        )
    choices = dict_data["choices"]
    finish_reason: Optional[str] = None
    if choices:
        choice = choices[0]
        delta_data = ChatCompletionResponseStreamChoice(**choice)
        if delta_data.delta.content:
            text = delta_data.delta.content
        finish_reason = delta_data.finish_reason
    return ModelOutput(error_code=0, text=text, finish_reason=finish_reason)


def _parse_sse_data(output: str) -> Optional[str]:
    if output.startswith("data:"):
        if output.startswith("data: "):
            output = output[6:]
        else:
            output = output[5:]

        return output
    else:
        return None
