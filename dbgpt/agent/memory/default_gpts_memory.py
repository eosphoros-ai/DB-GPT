from dataclasses import fields
from typing import List, Optional

import pandas as pd

from dbgpt.agent.common.schema import Status

from .base import GptsMessage, GptsMessageMemory, GptsPlan, GptsPlansMemory


class DefaultGptsPlansMemory(GptsPlansMemory):
    def __init__(self):
        self.df = pd.DataFrame(columns=[field.name for field in fields(GptsPlan)])

    def batch_save(self, plans: list[GptsPlan]):
        new_rows = pd.DataFrame([item.to_dict() for item in plans])
        self.df = pd.concat([self.df, new_rows], ignore_index=True)

    def get_by_conv_id(self, conv_id: str) -> List[GptsPlan]:
        result = self.df.query(f"conv_id==@conv_id")
        plans = []
        for row in result.itertuples(index=False, name=None):
            row_dict = dict(zip(self.df.columns, row))
            plans.append(GptsPlan.from_dict(row_dict))
        return plans

    def get_by_conv_id_and_num(
        self, conv_id: str, task_nums: List[int]
    ) -> List[GptsPlan]:
        task_nums_int = [int(num) for num in task_nums]
        result = self.df.query(f"conv_id==@conv_id and sub_task_num in @task_nums_int")
        plans = []
        for row in result.itertuples(index=False, name=None):
            row_dict = dict(zip(self.df.columns, row))
            plans.append(GptsPlan.from_dict(row_dict))
        return plans

    def get_todo_plans(self, conv_id: str) -> List[GptsPlan]:
        todo_states = [Status.TODO.value, Status.RETRYING.value]
        result = self.df.query(f"conv_id==@conv_id and state in @todo_states")
        plans = []
        for row in result.itertuples(index=False, name=None):
            row_dict = dict(zip(self.df.columns, row))
            plans.append(GptsPlan.from_dict(row_dict))
        return plans

    def complete_task(self, conv_id: str, task_num: int, result: str):
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
        agent: str = None,
        model=None,
        result: str = None,
    ):
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
        self.df.drop(self.df[self.df["conv_id"] == conv_id].index, inplace=True)


class DefaultGptsMessageMemory(GptsMessageMemory):
    def __init__(self):
        self.df = pd.DataFrame(columns=[field.name for field in fields(GptsMessage)])

    def append(self, message: GptsMessage):
        self.df.loc[len(self.df)] = message.to_dict()

    def get_by_agent(self, conv_id: str, agent: str) -> Optional[List[GptsMessage]]:
        result = self.df.query(
            f"conv_id==@conv_id and (sender==@agent or receiver==@agent)"
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
        current_gogal: Optional[str] = None,
    ) -> Optional[List[GptsMessage]]:
        if current_gogal:
            result = self.df.query(
                f"conv_id==@conv_id and ((sender==@agent1 and receiver==@agent2) or (sender==@agent2 and receiver==@agent1)) and current_gogal==@current_gogal"
            )
        else:
            result = self.df.query(
                f"conv_id==@conv_id and ((sender==@agent1 and receiver==@agent2) or (sender==@agent2 and receiver==@agent1))"
            )
        messages = []
        for row in result.itertuples(index=False, name=None):
            row_dict = dict(zip(self.df.columns, row))
            messages.append(GptsMessage.from_dict(row_dict))
        return messages

    def get_by_conv_id(self, conv_id: str) -> Optional[List[GptsMessage]]:
        result = self.df.query(f"conv_id==@conv_id")
        messages = []
        for row in result.itertuples(index=False, name=None):
            row_dict = dict(zip(self.df.columns, row))
            messages.append(GptsMessage.from_dict(row_dict))
        return messages
