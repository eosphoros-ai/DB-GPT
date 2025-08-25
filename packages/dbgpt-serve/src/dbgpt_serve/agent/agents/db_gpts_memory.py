from abc import ABC
from typing import List, Optional

from dbgpt.agent.core.memory.gpts import (
    GptsMessage,
    GptsMessageMemory,
    GptsPlan,
    GptsPlansMemory,
)

from ..db import GptsMessagesEntity
from ..db.gpts_messages_db import GptsMessagesDao
from ..db.gpts_plans_db import GptsPlansDao, GptsPlansEntity


class MetaDbGptsPlansMemory(GptsPlansMemory):
    def __init__(self):
        self.gpts_plan = GptsPlansDao()

    def get_plans_by_msg_round(self, conv_id: str, rounds_id: str) -> List[GptsPlan]:
        db_results: List[GptsPlansEntity] = self.gpts_plan.get_by_conv_id(
            conv_id=conv_id, conv_round_id=rounds_id
        )
        results = []
        for item in db_results:
            results.append(GptsPlan.from_dict(item.__dict__))
        return results

    def batch_save(self, plans: List[GptsPlan]):
        self.gpts_plan.batch_save([item.to_dict() for item in plans])

    def get_by_conv_id(self, conv_id: str) -> List[GptsPlan]:
        db_results: List[GptsPlansEntity] = self.gpts_plan.get_by_conv_id(
            conv_id=conv_id
        )
        results = []
        for item in db_results:
            results.append(GptsPlan.from_dict(item.__dict__))
        return results

    def get_by_conv_id_and_num(
        self, conv_id: str, task_ids: List[str]
    ) -> List[GptsPlan]:
        db_results: List[GptsPlansEntity] = self.gpts_plan.get_by_conv_id_and_num(
            conv_id=conv_id, task_ids=task_ids
        )
        results = []
        for item in db_results:
            results.append(GptsPlan.from_dict(item.__dict__))
        return results

    def get_todo_plans(self, conv_id: str) -> List[GptsPlan]:
        db_results: List[GptsPlansEntity] = self.gpts_plan.get_todo_plans(
            conv_id=conv_id
        )
        results = []
        for item in db_results:
            results.append(GptsPlan.from_dict(item.__dict__))
        return results

    def complete_task(self, conv_id: str, task_id: str, result: str):
        self.gpts_plan.complete_task(conv_id=conv_id, task_id=task_id, result=result)

    def update_task(
        self,
        conv_id: str,
        task_id: str,
        state: str,
        retry_times: int,
        agent: Optional[str] = None,
        model: Optional[str] = None,
        result: Optional[str] = None,
    ):
        self.gpts_plan.update_task(
            conv_id=conv_id,
            task_id=task_id,
            state=state,
            retry_times=retry_times,
            agent=agent,
            model=model,
            result=result,
        )

    def remove_by_conv_id(self, conv_id: str):
        self.gpts_plan.remove_by_conv_id(conv_id=conv_id)

    def get_by_conv_and_content(self, conv_id: str, content: str) -> Optional[GptsPlan]:
        item = self.gpts_plan.get_by_conv_id_and_content(
            conv_id=conv_id, content=content
        )
        return GptsPlan.from_dict(item.__dict__)


class MetaDbGptsMessageMemory(GptsMessageMemory, ABC):
    def __init__(self):
        self.gpts_message = GptsMessagesDao()

    def append(self, message: GptsMessage):
        self.gpts_message.delete_by_msg_id(message_id=message.message_id)
        self.gpts_message.append(message.to_dict())

    def update(self, message: GptsMessage) -> None:
        self.gpts_message.update_message(message.to_dict())

    def get_by_agent(self, conv_id: str, agent: str) -> Optional[List[GptsMessage]]:
        db_results = self.gpts_message.get_by_agent(conv_id, agent)
        results = []
        db_results = sorted(db_results, key=lambda x: x.rounds)
        for item in db_results:
            results.append(GptsMessage.from_dict(item.__dict__))
        return results

    def get_between_agents(
        self,
        conv_id: str,
        agent1: str,
        agent2: str,
        current_goal: Optional[str] = None,
    ) -> Optional[List[GptsMessage]]:
        db_results = self.gpts_message.get_between_agents(
            conv_id, agent1, agent2, current_goal
        )
        results = []
        db_results = sorted(db_results, key=lambda x: x.rounds)
        for item in db_results:
            results.append(GptsMessage.from_dict(item.__dict__))
        return results

    def get_by_conv_id(self, conv_id: str) -> Optional[List[GptsMessage]]:
        db_results = self.gpts_message.get_by_conv_id(conv_id)

        results = []
        db_results = sorted(db_results, key=lambda x: x.rounds)
        for item in db_results:
            results.append(GptsMessage.from_dict(item.__dict__))
        return results

    def get_by_message_id(self, message_id: str) -> Optional[GptsMessage]:
        message = self.gpts_message.get_by_message_id(message_id)
        return GptsMessage.from_dict(message.__dict__)

    def get_last_message(self, conv_id: str) -> Optional[GptsMessage]:
        db_result = self.gpts_message.get_last_message(conv_id)
        if db_result:
            return GptsMessage.from_dict(db_result.__dict__)
        else:
            return None

    def delete_by_conv_id(self, conv_id: str) -> None:
        self.gpts_message.delete_chat_message(conv_id)
