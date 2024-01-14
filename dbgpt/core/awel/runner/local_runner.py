import logging
from typing import Dict, List, Optional, Set

from dbgpt.component import SystemApp

from ..dag.base import DAGContext, DAGVar
from ..operator.base import CALL_DATA, BaseOperator, WorkflowRunner
from ..operator.common_operator import BranchOperator, JoinOperator, TriggerOperator
from ..task.base import TaskContext, TaskState
from ..task.task_impl import DefaultInputContext, DefaultTaskContext, SimpleTaskOutput
from .job_manager import JobManager

logger = logging.getLogger(__name__)


class DefaultWorkflowRunner(WorkflowRunner):
    async def execute_workflow(
        self,
        node: BaseOperator,
        call_data: Optional[CALL_DATA] = None,
        streaming_call: bool = False,
        exist_dag_ctx: Optional[DAGContext] = None,
    ) -> DAGContext:
        # Save node output
        # dag = node.dag
        job_manager = JobManager.build_from_end_node(node, call_data)
        if not exist_dag_ctx:
            # Create DAG context
            node_outputs: Dict[str, TaskContext] = {}
        else:
            # Share node output with exist dag context
            node_outputs = exist_dag_ctx._node_to_outputs
        dag_ctx = DAGContext(
            streaming_call=streaming_call,
            node_to_outputs=node_outputs,
            node_name_to_ids=job_manager._node_name_to_ids,
        )
        logger.info(f"Begin run workflow from end operator, id: {node.node_id}")
        logger.debug(f"Node id {node.node_id}, call_data: {call_data}")
        skip_node_ids = set()
        system_app: SystemApp = DAGVar.get_current_system_app()

        await job_manager.before_dag_run()
        await self._execute_node(
            job_manager, node, dag_ctx, node_outputs, skip_node_ids, system_app
        )
        if not streaming_call and node.dag:
            # streaming call not work for dag end
            await node.dag._after_dag_end()

        return dag_ctx

    async def _execute_node(
        self,
        job_manager: JobManager,
        node: BaseOperator,
        dag_ctx: DAGContext,
        node_outputs: Dict[str, TaskContext],
        skip_node_ids: Set[str],
        system_app: SystemApp,
    ):
        # Skip run node
        if node.node_id in node_outputs:
            return

        # Run all upstream node
        for upstream_node in node.upstream:
            if isinstance(upstream_node, BaseOperator):
                await self._execute_node(
                    job_manager,
                    upstream_node,
                    dag_ctx,
                    node_outputs,
                    skip_node_ids,
                    system_app,
                )

        inputs = [
            node_outputs[upstream_node.node_id] for upstream_node in node.upstream
        ]
        input_ctx = DefaultInputContext(inputs)
        task_ctx = DefaultTaskContext(node.node_id, TaskState.INIT, task_output=None)
        task_ctx.set_call_data(job_manager.get_call_data_by_id(node.node_id))

        task_ctx.set_task_input(input_ctx)
        dag_ctx.set_current_task_context(task_ctx)
        task_ctx.set_current_state(TaskState.RUNNING)

        if node.node_id in skip_node_ids:
            task_ctx.set_current_state(TaskState.SKIP)
            task_ctx.set_task_output(SimpleTaskOutput(None))
            node_outputs[node.node_id] = task_ctx
            return
        try:
            logger.debug(
                f"Begin run operator, node id: {node.node_id}, node name: {node.node_name}, cls: {node}"
            )
            if system_app is not None and node.system_app is None:
                node.set_system_app(system_app)

            await node._run(dag_ctx)
            node_outputs[node.node_id] = dag_ctx.current_task_context
            task_ctx.set_current_state(TaskState.SUCCESS)

            if isinstance(node, BranchOperator):
                skip_nodes = task_ctx.metadata.get("skip_node_names", [])
                logger.debug(
                    f"Current is branch operator, skip node names: {skip_nodes}"
                )
                _skip_current_downstream_by_node_name(node, skip_nodes, skip_node_ids)
        except Exception as e:
            logger.info(f"Run operator {node.node_id} error, error message: {str(e)}")
            task_ctx.set_current_state(TaskState.FAILED)
            raise e


def _skip_current_downstream_by_node_name(
    branch_node: BranchOperator, skip_nodes: List[str], skip_node_ids: Set[str]
):
    if not skip_nodes:
        return
    for child in branch_node.downstream:
        if child.node_name in skip_nodes:
            logger.info(f"Skip node name {child.node_name}, node id {child.node_id}")
            _skip_downstream_by_id(child, skip_node_ids)


def _skip_downstream_by_id(node: BaseOperator, skip_node_ids: Set[str]):
    if isinstance(node, JoinOperator):
        # Not skip join node
        return
    skip_node_ids.add(node.node_id)
    for child in node.downstream:
        _skip_downstream_by_id(child, skip_node_ids)
