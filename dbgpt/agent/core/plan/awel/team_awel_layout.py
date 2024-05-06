"""The manager of the team for the AWEL layout."""

import logging
from abc import ABC, abstractmethod
from typing import Optional, cast

from dbgpt._private.config import Config
from dbgpt._private.pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_to_dict,
    validator,
)
from dbgpt.core.awel import DAG
from dbgpt.core.awel.dag.dag_manager import DAGManager

from ...action.base import ActionOutput
from ...agent import Agent, AgentGenerateContext, AgentMessage
from ...base_team import ManagerAgent
from ...profile import DynConfig, ProfileConfig
from .agent_operator import AWELAgentOperator, WrappedAgentOperator

logger = logging.getLogger(__name__)


class AWELTeamContext(BaseModel):
    """The context of the team for the AWEL layout."""

    dag_id: str = Field(
        ...,
        description="The unique id of dag",
        examples=["flow_dag_testflow_66d8e9d6-f32e-4540-a5bd-ea0648145d0e"],
    )
    uid: str = Field(
        default=None,
        description="The unique id of flow",
        examples=["66d8e9d6-f32e-4540-a5bd-ea0648145d0e"],
    )
    name: Optional[str] = Field(
        default=None,
        description="The name of dag",
    )
    label: Optional[str] = Field(
        default=None,
        description="The label of dag",
    )
    version: Optional[str] = Field(
        default=None,
        description="The version of dag",
    )
    description: Optional[str] = Field(
        default=None,
        description="The description of dag",
    )
    editable: bool = Field(
        default=False,
        description="is the dag is editable",
        examples=[True, False],
    )
    state: Optional[str] = Field(
        default=None,
        description="The state of dag",
    )
    user_name: Optional[str] = Field(
        default=None,
        description="The owner of current dag",
    )
    sys_code: Optional[str] = Field(
        default=None,
        description="The system code of current dag",
    )
    flow_category: Optional[str] = Field(
        default="common",
        description="The flow category of current dag",
    )

    def to_dict(self):
        """Convert the object to a dictionary."""
        return model_to_dict(self)


class AWELBaseManager(ManagerAgent, ABC):
    """AWEL base manager."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    profile: ProfileConfig = ProfileConfig(
        name="AWELBaseManager",
        role=DynConfig(
            "PlanManager", category="agent", key="dbgpt_agent_plan_awel_profile_name"
        ),
        goal=DynConfig(
            "Promote and solve user problems according to the process arranged "
            "by AWEL.",
            category="agent",
            key="dbgpt_agent_plan_awel_profile_goal",
        ),
        desc=DynConfig(
            "Promote and solve user problems according to the process arranged "
            "by AWEL.",
            category="agent",
            key="dbgpt_agent_plan_awel_profile_desc",
        ),
    )

    async def _a_process_received_message(self, message: AgentMessage, sender: Agent):
        """Process the received message."""
        pass

    @abstractmethod
    def get_dag(self) -> DAG:
        """Get the DAG of the manager."""

    async def act(
        self,
        message: Optional[str],
        sender: Optional[Agent] = None,
        reviewer: Optional[Agent] = None,
        **kwargs,
    ) -> Optional[ActionOutput]:
        """Perform the action."""
        try:
            agent_dag = self.get_dag()
            last_node: AWELAgentOperator = cast(
                AWELAgentOperator, agent_dag.leaf_nodes[0]
            )

            start_message_context: AgentGenerateContext = AgentGenerateContext(
                message=AgentMessage(content=message, current_goal=message),
                sender=sender,
                reviewer=reviewer,
                memory=self.memory.structure_clone(),
                agent_context=self.agent_context,
                resource_loader=self.resource_loader,
                llm_client=self.not_null_llm_config.llm_client,
            )
            final_generate_context: AgentGenerateContext = await last_node.call(
                call_data=start_message_context
            )
            last_message = final_generate_context.rely_messages[-1]

            last_agent = await last_node.get_agent(final_generate_context)
            if final_generate_context.round_index is not None:
                last_agent.consecutive_auto_reply_counter = (
                    final_generate_context.round_index
                )
            if not sender:
                raise ValueError("sender is required!")
            await last_agent.send(
                last_message, sender, start_message_context.reviewer, False
            )

            view_message: Optional[str] = None
            if last_message.action_report:
                view_message = last_message.action_report.get("view", None)

            return ActionOutput(
                content=last_message.content,
                view=view_message,
            )
        except Exception as e:
            logger.exception(f"DAG run failed!{str(e)}")

            return ActionOutput(
                is_exe_success=False,
                content=f"Failed to complete goal! {str(e)}",
            )


class WrappedAWELLayoutManager(AWELBaseManager):
    """The manager of the team for the AWEL layout.

    Receives a DAG or builds a DAG from the agents.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    dag: Optional[DAG] = Field(None, description="The DAG of the manager")

    def get_dag(self) -> DAG:
        """Get the DAG of the manager."""
        if self.dag:
            return self.dag
        conv_id = self.not_null_agent_context.conv_id
        last_node: Optional[WrappedAgentOperator] = None
        with DAG(
            f"layout_agents_{self.not_null_agent_context.gpts_app_name}_{conv_id}"
        ) as dag:
            for agent in self.agents:
                now_node = WrappedAgentOperator(agent=agent)
                if not last_node:
                    last_node = now_node
                else:
                    last_node >> now_node
                    last_node = now_node
        self.dag = dag
        return dag

    async def act(
        self,
        message: Optional[str],
        sender: Optional[Agent] = None,
        reviewer: Optional[Agent] = None,
        **kwargs,
    ) -> Optional[ActionOutput]:
        """Perform the action."""
        try:
            dag = self.get_dag()
            last_node: WrappedAgentOperator = cast(
                WrappedAgentOperator, dag.leaf_nodes[0]
            )
            start_message_context: AgentGenerateContext = AgentGenerateContext(
                message=AgentMessage(content=message, current_goal=message),
                sender=self,
                reviewer=reviewer,
            )
            final_generate_context: AgentGenerateContext = await last_node.call(
                call_data=start_message_context
            )
            last_message = final_generate_context.rely_messages[-1]

            last_agent = last_node.agent
            await last_agent.send(
                last_message,
                self,
                start_message_context.reviewer,
                False,
            )

            view_message: Optional[str] = None
            if last_message.action_report:
                view_message = last_message.action_report.get("view", None)

            return ActionOutput(
                content=last_message.content,
                view=view_message,
            )
        except Exception as e:
            logger.exception(f"DAG run failed!{str(e)}")

            return ActionOutput(
                is_exe_success=False,
                content=f"Failed to complete goal! {str(e)}",
            )


class DefaultAWELLayoutManager(AWELBaseManager):
    """The manager of the team for the AWEL layout."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    dag: AWELTeamContext = Field(...)

    @validator("dag")
    def check_dag(cls, value):
        """Check the DAG of the manager."""
        assert value is not None and value != "", "dag must not be empty"
        return value

    def get_dag(self) -> DAG:
        """Get the DAG of the manager."""
        cfg = Config()
        _dag_manager = DAGManager.get_instance(cfg.SYSTEM_APP)  # type: ignore
        agent_dag: Optional[DAG] = _dag_manager.get_dag(alias_name=self.dag.uid)
        if agent_dag is None:
            raise ValueError(f"The configured flow cannot be found![{self.dag.name}]")
        return agent_dag
