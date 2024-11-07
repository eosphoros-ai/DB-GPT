import json
import logging
import os
from typing import AsyncIterator, List, Optional, cast

import schedule
from fastapi import HTTPException

from dbgpt._private.config import Config
from dbgpt._private.pydantic import model_to_json
from dbgpt.agent import AgentDummyTrigger
from dbgpt.component import SystemApp
from dbgpt.core.awel import DAG, BaseOperator, CommonLLMHttpRequestBody
from dbgpt.core.awel.flow.flow_factory import (
    FlowCategory,
    FlowFactory,
    State,
    fill_flow_panel,
)
from dbgpt.core.awel.trigger.http_trigger import CommonLLMHttpTrigger
from dbgpt.core.awel.util.chat_util import (
    is_chat_flow_type,
    safe_chat_stream_with_dag_task,
    safe_chat_with_dag_task,
)
from dbgpt.core.interface.llm import ModelOutput
from dbgpt.core.schema.api import (
    ChatCompletionResponseStreamChoice,
    ChatCompletionStreamResponse,
    DeltaMessage,
)
from dbgpt.serve.core import BaseService, blocking_func_to_async
from dbgpt.storage.metadata import BaseDao
from dbgpt.storage.metadata._base_dao import QUERY_SPEC
from dbgpt.util.dbgpts.loader import DBGPTsLoader
from dbgpt.util.pagination_utils import PaginationResult

from ..api.schemas import FlowDebugRequest, FlowInfo, ServeRequest, ServerResponse
from ..config import SERVE_CONFIG_KEY_PREFIX, SERVE_SERVICE_COMPONENT_NAME, ServeConfig
from ..models.models import ServeDao, ServeEntity

logger = logging.getLogger(__name__)

CFG = Config()


class Service(BaseService[ServeEntity, ServeRequest, ServerResponse]):
    """The service class for Flow"""

    name = SERVE_SERVICE_COMPONENT_NAME

    def __init__(self, system_app: SystemApp, dao: Optional[ServeDao] = None):
        self._system_app = None
        self._serve_config: ServeConfig = None
        self._dao: ServeDao = dao
        self._flow_factory: FlowFactory = FlowFactory()
        self._dbgpts_loader: Optional[DBGPTsLoader] = None

        super().__init__(system_app)

    def init_app(self, system_app: SystemApp) -> None:
        """Initialize the service

        Args:
            system_app (SystemApp): The system app
        """
        super().init_app(system_app)

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
        super().before_start()
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
            if request.define_type == "json":
                dag = self._flow_factory.build(request)
            else:
                dag = request.flow_dag
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
                raise ValueError(
                    f"Create DAG {request.name} error, define_type: {request.define_type}, error: {str(e)}"
                ) from e
        self.dao.create(request)
        # Query from database
        res = self.get({"uid": request.uid})

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
                if entity.define_type != "json":
                    continue
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
                if flow.define_type == "json":
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
                if flow.define_type == "python" and flow.flow_dag is None:
                    continue
                # Set state to DEPLOYED
                flow.state = State.DEPLOYED
                exist_inst = self.dao.get_one({"name": flow.name})
                if not exist_inst:
                    self.create_and_save_dag(flow, save_failed_flow=True)
                elif is_first_load or exist_inst.state != State.RUNNING:
                    # TODO check version, must be greater than the exist one
                    flow.uid = exist_inst.uid
                    self.update_flow(flow, check_editable=False, save_failed_flow=True)
            except Exception as e:
                import traceback

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
        new_state = State.DEPLOYED
        try:
            # Try to build the dag from the request
            if request.define_type == "json":
                dag = self._flow_factory.build(request)
            else:
                dag = request.flow_dag
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
            update_obj.flow_dag = request.flow_dag
            return self.create_and_save_dag(update_obj)
        except Exception as e:
            if old_data and old_data.state == State.RUNNING:
                # Old flow is running, try to recover it
                # first set the state to DEPLOYED
                old_data.state = State.DEPLOYED
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
            metadata = self.dag_manager.get_dag_metadata(
                flow.dag_id, alias_name=flow.uid
            )
            if metadata:
                flow.metadata = metadata.to_dict()
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
        page_result = self.dao.get_list_page(
            request, page, page_size, desc_order_column=ServeEntity.gmt_modified.name
        )
        for item in page_result.items:
            metadata = self.dag_manager.get_dag_metadata(
                item.dag_id, alias_name=item.uid
            )
            if metadata:
                item.metadata = metadata.to_dict()
        return page_result

    def get_flow_templates(
        self,
        user_name: Optional[str] = None,
        sys_code: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> PaginationResult[ServerResponse]:
        """Get a list of Flow templates

        Args:
            user_name (Optional[str]): The user name
            sys_code (Optional[str]): The system code
            page (int): The page number
            page_size (int): The page size
        Returns:
            List[ServerResponse]: The response
        """
        local_file_templates = self._get_flow_templates_from_files()
        return PaginationResult.build_from_all(local_file_templates, page, page_size)

    def _get_flow_templates_from_files(self) -> List[ServerResponse]:
        """Get a list of Flow templates from files"""
        user_lang = self._system_app.config.get_current_lang(default="en")
        # List files in current directory
        parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        template_dir = os.path.join(parent_dir, "templates", user_lang)
        default_template_dir = os.path.join(parent_dir, "templates", "en")
        if not os.path.exists(template_dir):
            template_dir = default_template_dir
        templates = []
        for root, _, files in os.walk(template_dir):
            for file in files:
                if file.endswith(".json"):
                    try:
                        with open(os.path.join(root, file), "r") as f:
                            data = json.load(f)
                            templates.append(_parse_flow_template_from_json(data))
                    except Exception as e:
                        logger.warning(f"Load template {file} error: {str(e)}")
        return templates

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
            if text:
                text = text.replace("\n", "\\n")
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
        json_data = model_to_json(chunk, exclude_unset=True, ensure_ascii=False)

        yield f"data: {json_data}\n\n"

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
            return await safe_chat_with_dag_task(task, request)
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
            async for output in safe_chat_stream_with_dag_task(
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
        # if (
        #     flow.flow_category != FlowCategory.CHAT_FLOW
        #     and self._parse_flow_category(dag) != FlowCategory.CHAT_FLOW
        # ):
        #     raise ValueError(f"Flow {flow_uid} is not a chat flow")
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

        leaf_node = cast(BaseOperator, leaf_nodes[0])
        if not leaf_node.metadata or not leaf_node.metadata.outputs:
            return FlowCategory.COMMON

        common_http_trigger = False
        agent_trigger = False
        for trigger in triggers:
            if isinstance(trigger, CommonLLMHttpTrigger):
                common_http_trigger = True
                break

            if isinstance(trigger, AgentDummyTrigger):
                agent_trigger = True
                break

        output = leaf_node.metadata.outputs[0]
        try:
            real_class = _get_type_cls(output.type_cls)
            if agent_trigger:
                return FlowCategory.CHAT_AGENT
            elif common_http_trigger and is_chat_flow_type(real_class, is_class=True):
                return FlowCategory.CHAT_FLOW
        except Exception:
            return FlowCategory.COMMON

    async def debug_flow(
        self, request: FlowDebugRequest, default_incremental: Optional[bool] = None
    ) -> AsyncIterator[ModelOutput]:
        """Debug the flow.

        Args:
            request (FlowDebugRequest): The request
            default_incremental (Optional[bool]): The default incremental configuration

        Returns:
            AsyncIterator[ModelOutput]: The output
        """
        from dbgpt.core.awel.dag.dag_manager import DAGMetadata, _parse_metadata

        dag = await blocking_func_to_async(
            self._system_app,
            self._flow_factory.build,
            request.flow,
        )
        leaf_nodes = dag.leaf_nodes
        if len(leaf_nodes) != 1:
            raise ValueError("Chat Flow just support one leaf node in dag")
        task = cast(BaseOperator, leaf_nodes[0])
        dag_metadata = _parse_metadata(dag)
        # TODO: Run task with variables
        variables = request.variables
        dag_request = request.request

        if isinstance(request.request, CommonLLMHttpRequestBody):
            incremental = request.request.incremental
        elif isinstance(request.request, dict):
            incremental = request.request.get("incremental", False)
        else:
            raise ValueError("Invalid request type")

        if default_incremental is not None:
            incremental = default_incremental

        try:
            async for output in safe_chat_stream_with_dag_task(
                task, dag_request, incremental
            ):
                yield output
        except HTTPException as e:
            yield ModelOutput(error_code=1, text=e.detail, incremental=incremental)
        except Exception as e:
            yield ModelOutput(error_code=1, text=str(e), incremental=incremental)

    async def _wrapper_chat_stream_flow_str(
        self, stream_iter: AsyncIterator[ModelOutput]
    ) -> AsyncIterator[str]:
        async for output in stream_iter:
            text = output.text
            if text:
                text = text.replace("\n", "\\n")
            if output.error_code != 0:
                yield f"data:[SERVER_ERROR]{text}\n\n"
                break
            else:
                yield f"data:{text}\n\n"

    async def get_flow_files(self, flow_uid: str):
        logger.info(f"get_flow_files:{flow_uid}")

        flow = self.get({"uid": flow_uid})
        if not flow:
            logger.warning(f"cant't find flow info!{flow_uid}")
            return None
        package = self.dbgpts_loader.get_flow_package(flow.name)
        if package:
            return FlowInfo(
                name=package.name,
                definition_type=package.definition_type,
                description=package.description,
                label=package.label,
                package=package.package,
                package_type=package.package_type,
                root=package.root,
                path=f"{package.root.replace(CFG.NOTE_BOOK_ROOT+'/', '')}/{package.name}",
                version=package.version,
            )
        return None


def _parse_flow_template_from_json(json_dict: dict) -> ServerResponse:
    """Parse the flow from json

    Args:
        json_dict (dict): The json dict

    Returns:
        ServerResponse: The flow
    """
    flow_json = json_dict["flow"]
    flow_json["editable"] = False
    del flow_json["uid"]
    flow_json["state"] = State.INITIALIZING
    flow_json["dag_id"] = None
    return ServerResponse(**flow_json)
