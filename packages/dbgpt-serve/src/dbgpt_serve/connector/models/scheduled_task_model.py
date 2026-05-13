"""SQLAlchemy model for scheduled connector tasks."""

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text

from dbgpt.storage.metadata import BaseDao, Model

logger = logging.getLogger(__name__)


class ScheduledTaskEntity(Model):
    """SQLAlchemy entity for scheduled connector tasks."""

    __tablename__ = "dbgpt_serve_scheduled_task"

    id = Column(
        Integer, primary_key=True, autoincrement=True, comment="Auto increment id"
    )
    task_id = Column(String(64), unique=True, nullable=False, comment="Task UUID")
    connector_id = Column(
        String(64), nullable=False, index=True, comment="Associated connector UUID"
    )
    task_name = Column(String(256), nullable=False, comment="Task display name")
    description = Column(Text, nullable=True, comment="Task description")
    cron_expression = Column(
        String(128), nullable=False, comment="APScheduler cron expression"
    )
    tool_name = Column(String(256), nullable=False, comment="Tool name to execute")
    tool_args = Column(Text, nullable=True, comment="JSON-serialized tool arguments")
    enabled = Column(
        Boolean, default=True, nullable=False, comment="Whether the task is enabled"
    )
    last_run_time = Column(DateTime, nullable=True, comment="Last execution time")
    last_run_status = Column(
        String(32), nullable=True, comment="Last run status: success/failed/pending"
    )
    last_run_result = Column(
        Text, nullable=True, comment="JSON-serialized last run result summary"
    )
    created_at = Column(DateTime, default=datetime.now, comment="Record creation time")
    updated_at = Column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now,
        comment="Record update time",
    )
    user_name = Column(String(128), index=True, nullable=True, comment="User name")
    sys_code = Column(String(128), index=True, nullable=True, comment="System code")

    def __repr__(self) -> str:
        return (
            f"ScheduledTaskEntity(id={self.id}, task_id='{self.task_id}', "
            f"connector_id='{self.connector_id}', task_name='{self.task_name}', "
            f"enabled={self.enabled}, last_run_status='{self.last_run_status}')"
        )
