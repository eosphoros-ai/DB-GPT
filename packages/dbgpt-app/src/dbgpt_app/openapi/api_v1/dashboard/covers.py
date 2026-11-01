"""One private rendered PNG cover per user and dashboard, independent of revisions."""

import base64
import binascii
import struct
from datetime import datetime, timedelta

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Column, DateTime, Integer, String

from dbgpt.storage.metadata import Model

from .models import DashboardConflictError, _json_text_type
from .schemas import DashboardAction


class DashboardCoverEntity(Model):
    __tablename__ = "dbgpt_dashboard_cover"
    owner_id = Column(String(255), primary_key=True)
    dashboard_id = Column(String(64), primary_key=True)
    revision = Column(Integer, nullable=False)
    image = Column(_json_text_type(), nullable=False)
    captured_at = Column(DateTime, nullable=False)


class DashboardCoverRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: int = Field(ge=1)
    image: str = Field(min_length=64, max_length=1600000)


class CoverService:
    def __init__(self, service):
        self.service = service

    def _record(self, dashboard_id, actor):
        record = self.service.get_dashboard(dashboard_id, actor)
        self.service.require_permission(
            dashboard_id, actor, DashboardAction.QUERY, record.schema_payload
        )
        return record

    def read(self, dashboard_id, actor):
        record = self._record(dashboard_id, actor)
        with self.service.dao.session(commit=False) as session:
            row = (
                session.query(DashboardCoverEntity)
                .filter_by(
                    owner_id=self.service._owner(actor), dashboard_id=dashboard_id
                )
                .first()
            )
            if row is None:
                return {"available": False}
            return {
                "available": True,
                "image": row.image,
                "revision": row.revision,
                "captured_at": row.captured_at.isoformat(),
                "stale": row.revision != record.current_revision
                or datetime.now() - row.captured_at > timedelta(hours=24),
            }

    def save(self, dashboard_id, actor, request):
        record = self._record(dashboard_id, actor)
        if record.current_revision != request.expected_revision:
            raise DashboardConflictError("看板已更新，请打开最新版本后重新生成预览")
        prefix = "data:image/png;base64,"
        try:
            if not request.image.startswith(prefix):
                raise ValueError("预览只接受 PNG 图片")
            raw = base64.b64decode(request.image[len(prefix) :], validate=True)
            if raw[:8] != b"\x89PNG\r\n\x1a\n" or raw[12:16] != b"IHDR":
                raise ValueError("预览图片格式无效")
            width, height = struct.unpack(">II", raw[16:24])
            if not (1 <= width <= 1280 and 1 <= height <= 1000):
                raise ValueError("预览图片尺寸超出上限")
        except (binascii.Error, struct.error) as exc:
            raise ValueError("预览图片格式无效") from exc
        with self.service.dao.session() as session:
            owner = self.service._owner(actor)
            row = (
                session.query(DashboardCoverEntity)
                .filter_by(owner_id=owner, dashboard_id=dashboard_id)
                .first()
            )
            if row is None:
                row = DashboardCoverEntity(owner_id=owner, dashboard_id=dashboard_id)
                session.add(row)
            row.revision = request.expected_revision
            row.image = request.image
            row.captured_at = datetime.now()
        return {"saved": True}
