import logging
from typing import Any, Dict, Optional, Type

from dbgpt.agent import (
    ActionOutput,
    Agent,
    AgentMemoryFragment,
    AgentMessage,
    ConversableAgent,
    ProfileConfig,
    StructuredAgentMemoryFragment,
)
from dbgpt.agent.core.role import AgentRunMode
from dbgpt.util.configure import DynConfig

logger = logging.getLogger(__name__)

_DATA_ANALYSIS_DEFAULT_GOAL = (
    """Perform data analysis tasks efficiently by selecting actions """
    """intelligently from the ACTION SPACE."""
)

_DATA_ANALYSIS_SYSTEM_TEMPLATE = """
You are a {{ role }}, {% if name %}named {{ name }}. {% endif %}{{ goal }}

You can only use actions in the ACTION SPACE. Your response must include:
- Thought: Your analysis process.
- Action: The selected action.
- Action Input: Any required input.

{{ action_space }}
"""


class DataAnalysisAgent(ConversableAgent):
    max_retry_count: int = 10
    run_mode: AgentRunMode = AgentRunMode.LOOP

    profile: ProfileConfig = ProfileConfig(
        name=DynConfig(
            "DataAnalysisAgent", category="agent", key="data_analysis_agent_name"
        ),
        role=DynConfig(
            "DataAnalyzer", category="agent", key="data_analysis_agent_role"
        ),
        goal=DynConfig(
            _DATA_ANALYSIS_DEFAULT_GOAL,
            category="agent",
            key="data_analysis_agent_goal",
        ),
        system_prompt_template=_DATA_ANALYSIS_SYSTEM_TEMPLATE,
    )

    async def act(
        self,
        message: AgentMessage,
        sender: Agent,
        reviewer: Optional[Agent] = None,
        is_retry_chat: bool = False,
        **kwargs,
    ) -> ActionOutput:
        """Perform a data analysis action."""
        message_content = message.content
        if not message_content:
            raise ValueError("The response is empty.")

        try:
            steps = self.parser.parse_current_step(message_content)
            err_msg = self.parser.validate_current_step(steps)
            if err_msg:
                return ActionOutput(is_exe_success=False, content=err_msg)
        except Exception as e:
            logger.warning(f"Parsing error: {e}")
            return ActionOutput(is_exe_success=False, content=str(e))

        action_output = await super().act(
            message=message,
            sender=sender,
            reviewer=reviewer,
            is_retry_chat=is_retry_chat,
            **kwargs,
        )
        return action_output

    def prepare_act_param(
        self,
        received_message: Optional[AgentMessage],
        sender: Agent,
        **kwargs,
    ) -> Dict[str, Any]:
        """Prepare parameters for the act method."""
        return {
            "parser": self.parser,
        }

    @property
    def memory_fragment_class(self) -> Type[AgentMemoryFragment]:
        return StructuredAgentMemoryFragment
