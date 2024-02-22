import json
import logging
import traceback
from typing import Any, List, Optional, cast

from fastapi import HTTPException

from dbgpt.component import SystemApp
from dbgpt.core.awel import (
    DAG,
    BaseOperator,
    CommonLLMHttpRequestBody,
    CommonLLMHttpResponseBody,
)
from dbgpt.core.awel.dag.dag_manager import DAGManager
from dbgpt.core.awel.flow.flow_factory import FlowCategory, FlowFactory
from dbgpt.core.awel.trigger.http_trigger import CommonLLMHttpTrigger
from dbgpt.core.interface.llm import ModelOutput
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
            DBGPTsLoader.name, DBGPTsLoader, or_register_component=DBGPTsLoader
        )

    def before_start(self):
        """Execute before the application starts"""
        self._dag_manager = DAGManager.get_instance(self._system_app)
        self._pre_load_dag_from_db()
        self._pre_load_dag_from_dbgpts()

    def after_start(self):
        """Execute after the application starts"""
        self.load_dag_from_db()
        self.load_dag_from_dbgpts()

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
        # Build DAG from request
        dag = self._flow_factory.build(request)
        request.dag_id = dag.dag_id
        # Save DAG to storage
        request.flow_category = self._parse_flow_category(dag)
        res = self.dao.create(request)
        # Register the DAG
        self.dag_manager.register_dag(dag)
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
                self.dag_manager.register_dag(dag)
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

    def load_dag_from_dbgpts(self):
        """Load DAG from dbgpts"""
        flows = self.dbgpts_loader.get_flows()
        for flow in flows:
            try:
                # Try to build the dag from the request
                self._flow_factory.build(flow)
                exist_inst = self.get({"name": flow.name})
                if not exist_inst:
                    self.create(flow)
                else:
                    # TODO check version, must be greater than the exist one
                    flow.uid = exist_inst.uid
                    self.update(flow, check_editable=False)
            except Exception as e:
                message = traceback.format_exc()
                logger.warning(
                    f"Load DAG {flow.name} from dbgpts error: {str(e)}, detail: {message}"
                )

    def update(
        self, request: ServeRequest, check_editable: bool = True
    ) -> ServerResponse:
        """Update a Flow entity

        Args:
            request (ServeRequest): The request
            check_editable (bool): Whether to check the editable

        Returns:
            ServerResponse: The response
        """
        # Try to build the dag from the request
        dag = self._flow_factory.build(request)

        # Build the query request from the request
        query_request = {"uid": request.uid}
        inst = self.get(query_request)
        if not inst:
            raise HTTPException(status_code=404, detail=f"Flow {request.uid} not found")
        if check_editable and not inst.editable:
            raise HTTPException(
                status_code=403, detail=f"Flow {request.uid} is not editable"
            )
        old_data: Optional[ServerResponse] = None
        try:
            request.flow_category = self._parse_flow_category(dag)
            update_obj = self.dao.update(query_request, update_request=request)
            old_data = self.delete(request.uid)
            if not old_data:
                raise HTTPException(
                    status_code=404, detail=f"Flow detail {request.uid} not found"
                )
            return self.create(update_obj)
        except Exception as e:
            if old_data:
                self.create(old_data)
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
        return self.dao.get_one(query_request)

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
        if not inst.dag_id:
            raise HTTPException(
                status_code=404, detail=f"Flow {uid}'s dag id not found"
            )
        try:
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

    async def chat_flow(
        self,
        flow_uid: str,
        request: CommonLLMHttpRequestBody,
        incremental: bool = False,
    ):
        """Chat with the AWEL flow.

        Args:
            flow_uid (str): The flow uid
            request (CommonLLMHttpRequestBody): The request
            incremental (bool): Whether to return the result incrementally
        """
        try:
            async for output in self._call_chat_flow(flow_uid, request, incremental):
                yield output
        except HTTPException as e:
            yield f"data:[SERVER_ERROR]{e.detail}\n\n"
        except Exception as e:
            yield f"data:[SERVER_ERROR]{str(e)}\n\n"

    async def _call_chat_flow(
        self,
        flow_uid: str,
        request: CommonLLMHttpRequestBody,
        incremental: bool = False,
    ):
        """Chat with the AWEL flow.

        Args:
            flow_uid (str): The flow uid
            request (CommonLLMHttpRequestBody): The request
            incremental (bool): Whether to return the result incrementally
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
        end_node = cast(BaseOperator, leaf_nodes[0])
        async for output in _chat_with_dag_task(end_node, request, incremental):
            yield output

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


def _is_chat_flow_type(obj: Any, is_class: bool = False) -> bool:
    try:
        from dbgpt.model.utils.chatgpt_utils import OpenAIStreamingOutputOperator
    except ImportError:
        OpenAIStreamingOutputOperator = None
    if is_class:
        return (
            obj == str
            or obj == CommonLLMHttpResponseBody
            or (OpenAIStreamingOutputOperator and obj == OpenAIStreamingOutputOperator)
        )
    else:
        chat_types = (str, CommonLLMHttpResponseBody)
        if OpenAIStreamingOutputOperator:
            chat_types += (OpenAIStreamingOutputOperator,)
        return isinstance(obj, chat_types)


async def _chat_with_dag_task(
    task: BaseOperator,
    request: CommonLLMHttpRequestBody,
    incremental: bool = False,
):
    """Chat with the DAG task.

    Args:
        task (BaseOperator): The task
        request (CommonLLMHttpRequestBody): The request
    """
    if request.stream and task.streaming_operator:
        try:
            from dbgpt.model.utils.chatgpt_utils import OpenAIStreamingOutputOperator
        except ImportError:
            OpenAIStreamingOutputOperator = None
        if incremental:
            async for output in await task.call_stream(request):
                yield output
        else:
            if OpenAIStreamingOutputOperator and isinstance(
                task, OpenAIStreamingOutputOperator
            ):
                from fastchat.protocol.openai_api_protocol import (
                    ChatCompletionResponseStreamChoice,
                )

                previous_text = ""
                async for output in await task.call_stream(request):
                    if not isinstance(output, str):
                        yield "data:[SERVER_ERROR]The output is not a stream format\n\n"
                        return
                    if output == "data: [DONE]\n\n":
                        return
                    json_data = "".join(output.split("data: ")[1:])
                    dict_data = json.loads(json_data)
                    if "choices" not in dict_data:
                        error_msg = dict_data.get("text", "Unknown error")
                        yield f"data:[SERVER_ERROR]{error_msg}\n\n"
                        return
                    choices = dict_data["choices"]
                    if choices:
                        choice = choices[0]
                        delta_data = ChatCompletionResponseStreamChoice(**choice)
                        if delta_data.delta.content:
                            previous_text += delta_data.delta.content
                        if previous_text:
                            full_text = previous_text.replace("\n", "\\n")
                            yield f"data:{full_text}\n\n"
            else:
                async for output in await task.call_stream(request):
                    if isinstance(output, str):
                        if output.strip():
                            yield output
                    else:
                        yield "data:[SERVER_ERROR]The output is not a stream format\n\n"
                        return
    else:
        result = await task.call(request)
        if result is None:
            yield "data:[SERVER_ERROR]The result is None\n\n"
        elif isinstance(result, str):
            yield f"data:{result}\n\n"
        elif isinstance(result, ModelOutput):
            if result.error_code != 0:
                yield f"data:[SERVER_ERROR]{result.text}\n\n"
            else:
                yield f"data:{result.text}\n\n"
        elif isinstance(result, CommonLLMHttpResponseBody):
            if result.error_code != 0:
                yield f"data:[SERVER_ERROR]{result.text}\n\n"
            else:
                yield f"data:{result.text}\n\n"
        elif isinstance(result, dict):
            yield f"data:{json.dumps(result, ensure_ascii=False)}\n\n"
        else:
            yield f"data:[SERVER_ERROR]The result is not a valid format({type(result)})\n\n"
