from typing import Dict, Optional
from ..dag.base import DAGContext
from ..operator.base import WorkflowRunner, BaseOperator, CALL_DATA
from ..task.base import TaskContext, TaskState
from ..task.task_impl import DefaultInputContext, DefaultTaskContext
from .job_manager import JobManager


class DefaultWorkflowRunner(WorkflowRunner):
    async def execute_workflow(
        self, node: BaseOperator, call_data: Optional[CALL_DATA] = None
    ) -> DAGContext:
        # Create DAG context
        dag_ctx = DAGContext()
        job_manager = JobManager.build_from_end_node(node, call_data)
        dag = node.dag
        # Save node output
        node_outputs: Dict[str, TaskContext] = {}
        await self._execute_node(job_manager, node, dag_ctx, node_outputs)

        return dag_ctx

    async def _execute_node(
        self,
        job_manager: JobManager,
        node: BaseOperator,
        dag_ctx: DAGContext,
        node_outputs: Dict[str, TaskContext],
    ):
        # Skip run node
        if node.node_id in node_outputs:
            return

        # Run all upstream node
        for upstream_node in node.upstream:
            if isinstance(upstream_node, BaseOperator):
                await self._execute_node(
                    job_manager, upstream_node, dag_ctx, node_outputs
                )
        # if node.current_task_context.current_state == TaskState.SKIP:
        #     return

        # for upstream_node in node.upstream:
        #     if (
        #         isinstance(upstream_node, BaseOperator)
        #         and upstream_node.current_task_context.current_state == TaskState.SKIP
        #     ):
        #         return
        # Get the input from upstream node
        inputs = [
            node_outputs[upstream_node.node_id] for upstream_node in node.upstream
        ]
        input_ctx = DefaultInputContext(inputs)
        task_ctx = DefaultTaskContext(node.node_id, TaskState.INIT, task_output=None)
        task_ctx.set_call_data(job_manager.get_call_data_by_id(node.node_id))

        task_ctx.set_task_input(input_ctx)
        dag_ctx.set_current_task_context(task_ctx)

        task_ctx.set_current_state(TaskState.RUNNING)
        try:
            # print(f"Begin run {node}")
            await node._run(dag_ctx)
            node_outputs[node.node_id] = dag_ctx.current_task_context
            task_ctx.set_current_state(TaskState.SUCCESS)
        except Exception as e:
            task_ctx.set_current_state(TaskState.FAILED)
            raise e
