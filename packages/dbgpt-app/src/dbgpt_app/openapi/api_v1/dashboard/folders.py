"""Personal folders organize references without changing dashboard revisions."""

import uuid

from sqlalchemy import Column, String, UniqueConstraint

from dbgpt.storage.metadata import Model

from .models import DashboardNotFoundError
from .schemas import DashboardAction, DashboardOrigin


class DashboardFolderEntity(Model):
    __tablename__ = "dbgpt_dashboard_folder"
    __table_args__ = (
        UniqueConstraint("owner_id", "name", name="uk_dashboard_folder_name"),
    )
    id = Column(String(64), primary_key=True)
    owner_id = Column(String(255), nullable=False, index=True)
    name = Column(String(80), nullable=False)


class DashboardFolderItemEntity(Model):
    __tablename__ = "dbgpt_dashboard_folder_item"
    owner_id = Column(String(255), primary_key=True)
    dashboard_id = Column(String(64), primary_key=True)
    folder_id = Column(String(64), nullable=False, index=True)


class FolderService:
    def __init__(self, service):
        self.service = service
        self.dao = service.dao

    def list(self, actor):
        with self.dao.session(commit=False) as session:
            rows = (
                session.query(DashboardFolderEntity)
                .filter_by(owner_id=actor)
                .order_by(DashboardFolderEntity.name)
                .all()
            )
            folders = [{"id": r.id, "name": r.name} for r in rows]
        # Use the same permission, archive and asset rules as the folder page.
        for folder in folders:
            folder["count"] = self.service.list_dashboard_page(
                actor,
                folder_id=folder["id"],
                exclude_origin=DashboardOrigin.TEMPLATE,
                limit=1,
            ).total
        return folders

    def save(self, actor, name, folder_id=None):
        name = name.strip()
        if not name or len(name) > 80:
            raise ValueError("文件夹名称需要 1–80 个字符")
        with self.dao.session() as session:
            if (
                session.query(DashboardFolderEntity)
                .filter_by(owner_id=actor, name=name)
                .filter(DashboardFolderEntity.id != folder_id)
                .first()
            ):
                raise ValueError("已有同名文件夹")
            if folder_id:
                row = (
                    session.query(DashboardFolderEntity)
                    .filter_by(owner_id=actor, id=folder_id)
                    .first()
                )
                if not row:
                    raise DashboardNotFoundError("文件夹不存在")
                row.name = name
            else:
                row = DashboardFolderEntity(
                    id=uuid.uuid4().hex, owner_id=actor, name=name
                )
                session.add(row)
            session.flush()
            return {"id": row.id, "name": row.name}

    def delete(self, actor, folder_id):
        with self.dao.session() as session:
            session.query(DashboardFolderItemEntity).filter_by(
                owner_id=actor, folder_id=folder_id
            ).delete()
            session.query(DashboardFolderEntity).filter_by(
                owner_id=actor, id=folder_id
            ).delete()
        return {"deleted": True}

    def move(self, actor, dashboard_id, folder_id):
        self.service.require_permission(dashboard_id, actor, DashboardAction.VIEW)
        with self.dao.session() as session:
            if (
                folder_id
                and not session.query(DashboardFolderEntity)
                .filter_by(owner_id=actor, id=folder_id)
                .first()
            ):
                raise DashboardNotFoundError("文件夹不存在")
            session.query(DashboardFolderItemEntity).filter_by(
                owner_id=actor, dashboard_id=dashboard_id
            ).delete()
            if folder_id:
                session.add(
                    DashboardFolderItemEntity(
                        owner_id=actor, dashboard_id=dashboard_id, folder_id=folder_id
                    )
                )
        return {"moved": True}


def folder_scope(query, session, actor, folder_id, dashboard_model):
    if folder_id in ("__main__", "__tests__"):
        from sqlalchemy import func, or_

        title = func.lower(dashboard_model.title)
        testing = or_(
            title.like("uat-%"),
            title.like("uat %"),
            title.like("%-uat-%"),
            title.like("%模板验收%"),
            title.like("%自动验收%"),
            title.like("%验收测试%"),
        )
        return query.filter(testing if folder_id == "__tests__" else ~testing)
    if folder_id is None:
        return query
    ids = session.query(DashboardFolderItemEntity.dashboard_id).filter_by(
        owner_id=actor
    )
    if folder_id != "unfiled":
        ids = ids.filter_by(folder_id=folder_id)
    clause = dashboard_model.id.in_(ids)
    return query.filter(~clause if folder_id == "unfiled" else clause)
