from typing import List, Optional
from dbgpt.agent.memory.gpts_memory import GptsPlansMemory, GptsPlan, GptsMessageMemory, GptsMessage

from ..db.gpts_plans_db import GptsPlansEntity, GptsPlansDao
from ..db.gpts_messages_db import GptsMessagesDao, GptsMessagesEntity


class MetaDbGptsPlansMemory(GptsPlansMemory):

    def __init__(self):
        self.gpts_plan = GptsPlansDao()

    def batch_save(self, plans: list[GptsPlan]):
        self.gpts_plan.batch_save([item.to_dict() for item in plans])

    def get_by_conv_id(self, conv_id: str) -> List[GptsPlan]:
        db_results: List[GptsPlansEntity] = self.gpts_plan.get_by_conv_id(conv_id=conv_id)
        results = []
        for item in db_results:
            results.append(GptsPlan.from_dict(item.__dict__))
        return results

    def get_by_conv_id_and_num(self, conv_id: str, task_nums: List[int]) -> List[GptsPlan]:

        db_results: List[GptsPlansEntity] = self.gpts_plan.get_by_conv_id_and_num(conv_id=conv_id, task_nums=task_nums)
        results = []
        for item in db_results:
            results.append(GptsPlan.from_dict(item.__dict__))
        return results

    def get_todo_plans(self, conv_id: str) -> List[GptsPlan]:
        db_results: List[GptsPlansEntity] = self.gpts_plan.get_todo_plans(
            conv_id=conv_id)
        results = []
        for item in db_results:
            results.append(GptsPlan.from_dict(item.__dict__))
        return results

    def complete_task(self, conv_id: str, task_num: int, result: str):
        self.gpts_plan.complete_task(conv_id=conv_id, task_num=task_num, result=result)

    def update_task(self, conv_id: str, task_num: int, state: str, retry_times: int, agent: str = None, model=None):
        self.gpts_plan.update_task(conv_id=conv_id, task_num=task_num, state=state, retry_times=retry_times,
                                   agent=agent, model=model)

    def remove_by_conv_id(self, conv_id: str):
        self.gpts_plan.remove_by_conv_id(conv_id=conv_id)


class MetaDbGptsMessageMemory(GptsMessageMemory):

    def __init__(self):
        self.gpts_message = GptsMessagesDao()

    def append(self, message: GptsMessage):
        self.gpts_message.append(message.to_dict())

    def get_by_agent(self, agent: str) -> Optional[List[GptsMessage]]:
        db_results = self.gpts_message.get_by_agent(agent)
        results = []
        for item in db_results:
            results.append(GptsMessage.from_dict(item.__dict__))
        return results

    def get_between_agents(self, agent1: str, agent2: str) -> Optional[List[GptsMessage]]:
        db_results = self.gpts_message.get_between_agents(agent1, agent2)
        results = []
        for item in db_results:
            results.append(GptsMessage.from_dict(item.__dict__))
        return results

    def get_by_conv_id(self, conv_id: str) -> Optional[List[GptsMessage]]:

        return super().get_by_conv_id(conv_id)
