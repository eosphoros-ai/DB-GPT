"""Default memory for storing plans and messages."""

from dataclasses import fields
from typing import List, Optional

import pandas as pd

from ...schema import Status
from .base import GptsMessage, GptsMessageMemory, GptsPlan, GptsPlansMemory


class DefaultGptsPlansMemory(GptsPlansMemory):
    """Default memory for storing plans."""

    def __init__(self):
        """Create a memory to store plans."""
        self.df = pd.DataFrame(columns=[field.name for field in fields(GptsPlan)])

    def batch_save(self, plans: list[GptsPlan]):
        """Save plans in batch."""
        new_rows = pd.DataFrame([item.to_dict() for item in plans])
        self.df = pd.concat([self.df, new_rows], ignore_index=True)

    def get_by_conv_id(self, conv_id: str) -> List[GptsPlan]:
        """Get plans by conv_id."""
        result = self.df.query("conv_id==@conv_id")  # noqa: F541
        plans = []
        for row in result.itertuples(index=False, name=None):
            row_dict = dict(zip(self.df.columns, row))
            plans.append(GptsPlan.from_dict(row_dict))
        return plans

    def get_by_conv_id_and_num(
        self, conv_id: str, task_nums: List[int]
    ) -> List[GptsPlan]:
        """Get plans by conv_id and task number."""
        task_nums_int = [int(num) for num in task_nums]  # noqa:F841
        result = self.df.query(  # noqa
            "conv_id==@conv_id and sub_task_num in @task_nums_int"  # noqa
        )
        plans = []
        for row in result.itertuples(index=False, name=None):
            row_dict = dict(zip(self.df.columns, row))
            plans.append(GptsPlan.from_dict(row_dict))
        return plans

    def get_todo_plans(self, conv_id: str) -> List[GptsPlan]:
        """Get unfinished planning steps."""
        todo_states = [Status.TODO.value, Status.RETRYING.value]  # noqa: F841
        result = self.df.query("conv_id==@conv_id and state in @todo_states")  # noqa
        plans = []
        for row in result.itertuples(index=False, name=None):
            row_dict = dict(zip(self.df.columns, row))
            plans.append(GptsPlan.from_dict(row_dict))
        return plans

    def complete_task(self, conv_id: str, task_num: int, result: str):
        """Set the planning step to complete."""
        condition = (self.df["conv_id"] == conv_id) & (
            self.df["sub_task_num"] == task_num
        )
        self.df.loc[condition, "state"] = Status.COMPLETE.value
        self.df.loc[condition, "result"] = result

    def update_task(
        self,
        conv_id: str,
        task_num: int,
        state: str,
        retry_times: int,
        agent: Optional[str] = None,
        model: Optional[str] = None,
        result: Optional[str] = None,
    ):
        """Update the state of the planning step."""
        condition = (self.df["conv_id"] == conv_id) & (
            self.df["sub_task_num"] == task_num
        )
        self.df.loc[condition, "state"] = state
        self.df.loc[condition, "retry_times"] = retry_times
        self.df.loc[condition, "result"] = result

        if agent:
            self.df.loc[condition, "sub_task_agent"] = agent

        if model:
            self.df.loc[condition, "agent_model"] = model

    def remove_by_conv_id(self, conv_id: str):
        """Remove all plans in the conversation."""
        self.df.drop(self.df[self.df["conv_id"] == conv_id].index, inplace=True)


class DefaultGptsMessageMemory(GptsMessageMemory):
    """Default memory for storing messages."""

    def __init__(self):
        """Create a memory to store messages."""
        self.df = pd.DataFrame(columns=[field.name for field in fields(GptsMessage)])

    def append(self, message: GptsMessage):
        """Append a message to the memory."""
        self.df.loc[len(self.df)] = message.to_dict()

    def get_by_agent(self, conv_id: str, agent: str) -> Optional[List[GptsMessage]]:
        """Get all messages sent or received by the agent in the conversation."""
        result = self.df.query(
            "conv_id==@conv_id and (sender==@agent or receiver==@agent)"  # noqa: F541
        )
        messages = []
        for row in result.itertuples(index=False, name=None):
            row_dict = dict(zip(self.df.columns, row))
            messages.append(GptsMessage.from_dict(row_dict))
        return messages

    def get_between_agents(
        self,
        conv_id: str,
        agent1: str,
        agent2: str,
        current_goal: Optional[str] = None,
    ) -> List[GptsMessage]:
        """Get all messages between two agents in the conversation."""
        if current_goal:
            result = self.df.query(
                "conv_id==@conv_id and ((sender==@agent1 and receiver==@agent2) or (sender==@agent2 and receiver==@agent1)) and current_goal==@current_goal"  # noqa
            )
        else:
            result = self.df.query(
                "conv_id==@conv_id and ((sender==@agent1 and receiver==@agent2) or (sender==@agent2 and receiver==@agent1))"  # noqa
            )
        messages = []
        for row in result.itertuples(index=False, name=None):
            row_dict = dict(zip(self.df.columns, row))
            messages.append(GptsMessage.from_dict(row_dict))
        return messages

    def get_by_conv_id(self, conv_id: str) -> List[GptsMessage]:
        """Get all messages in the conversation."""
        result = self.df.query("conv_id==@conv_id")  # noqa: F541
        messages = []
        for row in result.itertuples(index=False, name=None):
            row_dict = dict(zip(self.df.columns, row))
            messages.append(GptsMessage.from_dict(row_dict))
        return messages

    def get_last_message(self, conv_id: str) -> Optional[GptsMessage]:
        """Get the last message in the conversation."""
        return None
