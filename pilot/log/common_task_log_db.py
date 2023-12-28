import uuid
from enum import Enum

from sqlalchemy import Column, Integer, String, DateTime, Text, TIMESTAMP, func, BigInteger

from pilot.base_modules.meta_data.base_dao import BaseDao
from pilot.base_modules.meta_data.meta_data import engine, session, Base
from pilot.configs.config import Config

CFG = Config()


class CommonTaskState(Enum):
    TODO = "TODO"
    FAILED = "FAILED"
    RUNNING = "RUNNING"
    FINISHED = "FINISHED"


class CommonTaskType(Enum):
    ZIP_EMBEDDING_READ = "ZIP_EMBEDDING_READ"
    ZIP_EMBEDDING_EXEC = "ZIP_EMBEDDING_EXEC"
    DELETE_KS_DOC = "DELETE_KS_DOC"
    DELETE_KS = "DELETE_KS"


class CommonTaskLogEntity(Base):
    __tablename__ = "common_task_log"
    id = Column(BigInteger, primary_key=True, autoincrement=True, comment='主键')
    gmt_create = Column(TIMESTAMP, nullable=False, server_default=func.now(), comment='创建时间')
    gmt_modified = Column(TIMESTAMP, nullable=False, server_default=func.now(), onupdate=func.now(), comment='修改时间')
    type = Column(String(100), default=None, comment='任务类型(ZIP_EMBEDDING, CHAT_DATA...)')
    msg = Column(Text, default=None, comment='日志信息')
    state = Column(String(100), default=None, comment='任务状态TODO, RUNNING, FINISHED, FAILED')
    task_uid = Column(String(100), default=None, unique=True, comment='任务id')
    task_param = Column(Text, default=None, comment='任务参数')
    task_result = Column(Text, default=None, comment='任务结果')
    param_idx = Column(String(255), default=None, comment='搜索参数')

    def __repr__(self):
        return f"CommonTaskLogEntity(id={self.id}, type={self.type}, msg='{self.msg}', state='{self.state}', task_uid='{self.task_uid}', task_param='{self.task_param}', task_result='{self.task_result}', param_idx='{self.param_idx}', gmt_create='{self.gmt_create}', gmt_create='{self.gmt_create}', gmt_modified='{self.gmt_modified}')"


class CommonTaskLogDao(BaseDao):
    def __init__(self):
        super().__init__(
            database="dbgpt", orm_base=Base, db_engine=engine, session=session
        )

    def create_simple_log(self, type: str, param_idx: str, msg: str):
        """
          Create simple log.
        """
        session = self.get_session()
        new_common_task = CommonTaskLogEntity(
            type=type,
            msg=msg,
            param_idx=param_idx,
        )
        session.add(new_common_task)
        session.commit()
        session.close()

    def create_common_task_log(self, common_task: CommonTaskLogEntity):
        session = self.get_session()
        task_uid = uuid.uuid4().hex
        new_common_task = CommonTaskLogEntity(
            type=common_task.type,
            msg=common_task.msg,
            state=common_task.state,
            task_uid=task_uid,
            task_param=common_task.task_param,
            task_result=common_task.task_result,
            param_idx=common_task.param_idx,
        )
        session.add(new_common_task)
        session.commit()
        session.close()
        return self.get_by_task_uid(task_uid)

    def get_task_logs(self, query, page=1, page_size=20):
        session = self.get_session()
        print(f"current session:{session}")
        task_logs = session.query(CommonTaskLogEntity)
        if query.id is not None:
            task_logs = task_logs.filter(
                CommonTaskLogEntity.id == query.id
            )
        if query.task_uid is not None:
            task_logs = task_logs.filter(
                CommonTaskLogEntity.task_uid == query.task_uid
            )
        if query.type is not None:
            task_logs = task_logs.filter(
                CommonTaskLogEntity.type == query.type
            )
        if query.state is not None:
            task_logs = task_logs.filter(
                CommonTaskLogEntity.state == query.state
            )
        task_logs = task_logs.order_by(CommonTaskLogEntity.id.desc()).offset((page - 1) * page_size).limit(page_size)

        result = task_logs.all()
        session.close()
        return result

    def get_by_task_uid(self, task_uid: str):
        session = self.get_session()
        task = session.query(CommonTaskLogEntity).filter(CommonTaskLogEntity.task_uid == task_uid).one()
        return task

    def update_task_log(self, task_log: CommonTaskLogEntity):
        """
          update task log.
        """
        try:
            session = self.get_session()
            if len(str(task_log.msg)) < 65535:
                updated = session.merge(task_log)
                session.commit()
                return updated.id
        except Exception as e:
            print(f"update task log error {str(e)}")
        return None

