"""SQLAlchemy model for dbgpt_serve_scheduled_task."""

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text

from dbgpt.storage.metadata import Model


class ScheduledTaskEntity(Model):
    """Scheduled task definition (chat-replay type)."""

    __tablename__ = "dbgpt_serve_scheduled_task"

    id = Column(
        Integer, primary_key=True, autoincrement=True, comment="Auto increment id"
    )
    task_id = Column(String(64), unique=True, nullable=False, comment="Task UUID")
    task_name = Column(String(256), nullable=False, comment="Task name")
    description = Column(Text, nullable=True, comment="Task description")
    task_type = Column(
        String(32),
        nullable=False,
        default="chat_replay",
        index=True,
        comment="Task type, e.g. chat_replay",
    )
    cron_expression = Column(
        String(128), nullable=False, comment="Cron expression for scheduling"
    )
    payload_json = Column(
        Text, nullable=False, comment="Frozen conversation snapshot JSON"
    )
    enabled = Column(
        Boolean,
        nullable=False,
        default=True,
        comment="Whether the task is enabled",
    )
    created_at = Column(DateTime, default=datetime.now, comment="Record creation time")
    updated_at = Column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now,
        comment="Record update time",
    )
    user_name = Column(String(128), nullable=True, index=True, comment="User name")
    sys_code = Column(String(128), nullable=True, comment="System code")

    def __repr__(self) -> str:
        return (
            f"ScheduledTaskEntity(task_id='{self.task_id}', "
            f"task_name='{self.task_name}', enabled={self.enabled})"
        )
