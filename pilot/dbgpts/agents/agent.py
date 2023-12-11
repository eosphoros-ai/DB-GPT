from typing import Dict, List, Optional, Union
from pydantic import BaseModel, Extra, root_validator
from ..memory.gpts_memory import GptsMemory
class Agent:
    """
    An interface for AI agent.
    An agent can communicate with other agents and perform actions.
    """

    def __init__(
        self,
        name: str,
        memory: GptsMemory,
        describe: str,
    ):
        """
        Args:
            name (str): name of the agent.
        """
        self._name = name
        self._describe = describe

        # the agent's collective memory
        self._memory = memory

    @property
    def name(self):
        """Get the name of the agent."""
        return self._name

    @property
    def memory(self):
        return self._memory

    @property
    def describe(self):
        """Get the name of the agent."""
        return self._describe

    async def a_send(
        self,
        message: Union[Dict, str],
        recipient: "Agent",
        reviewer: "Agent",
        request_reply: Optional[bool] = None,
        is_plan_goals: Optional[bool] = False,
    ):
        """(Abstract async method) Send a message to another agent."""


    async def a_receive(
        self,
        message: Union[Dict],
        sender: "Agent",
        reviewer: "Agent",
        request_reply: Optional[bool] = None,
        silent: Optional[bool] = False,
        is_plan_goals: Optional[bool] = False,
    ):
        """(Abstract async method) Receive a message from another agent."""



    async def a_review(self,   message: Union[Dict, str], censored:"Agent"):
        """

        Args:
            message:
            censored:

        Returns:

        """

    def reset(self):
        """(Abstract method) Reset the agent."""


    async def a_generate_reply(
        self,
        messages: Optional[List[Dict]] = None,
        sender: Optional["Agent"] = None,
        is_plan_goals: Optional[bool] = False,
        **kwargs,
    ) -> Union[str, Dict, None]:
        """(Abstract async method) Generate a reply based on the received messages.

        Args:
            messages (list[dict]): a list of messages received.
            sender: sender of an Agent instance.
        Returns:
            str or dict or None: the generated reply. If None, no reply is generated.
        """


    async def a_generate_action_reply(
        self,
        messages: Optional[List[Dict]] = None,
        **kwargs,
    ) -> Union[str, Dict, None]:
        """(Abstract async method) Generate agent reply based on the generated llm message.
        Args:
            messages (list[dict]): a list of messages received.
            sender: sender of an Agent instance.
        Returns:
            str or dict or None: the generated reply. If None, no reply is generated.
        """

    async def a_agent_reply_evolution(self,   sender: Optional["Agent"] = None):
        """

        Args:
            sender:

        Returns:

        """

class AgentContext(BaseModel):
    conv_id: str
    gpts_name: Optional[str]
    resources: Optional[Dict] = {}
    db_type: Optional[str] = "mysql"
    db_name: Optional[str] = None
    llm_models: Optional[List[str]] = None
    agents: Optional[List[str]] = None
    max_chat_round: Optional[int] = 50
    max_retry_round: Optional[int] = 3
    max_new_tokens:Optional[int] = 1024
    temperature:Optional[float] = 0.5
    allow_format_str_template:Optional[bool] = False

    class Config:
        """Configuration for this pydantic object."""
        extra = Extra.forbid