"""Semantic center models: six-layer semantic stack (L1-L6).

The structured meta DB tables below are the **source of truth**; vector chunks
in the KB managed space ``semantic::<conn_id>`` are a derived, read-only index
rebuilt by :mod:`dbgpt_serve.semantic.publisher`.
"""

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    UniqueConstraint,
)

from dbgpt.storage.metadata import BaseDao, Model


def _dumps(value: Any) -> Optional[str]:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False)


def _loads(text: Optional[str]) -> Any:
    if not text:
        return None
    try:
        return json.loads(text)
    except (TypeError, ValueError):
        return None


class _SemBase(Model):
    """Common columns for all semantic entities."""

    __abstract__ = True

    id = Column(Integer, primary_key=True)
    user_name = Column(String(128))
    sys_code = Column(String(128))
    gmt_created = Column(DateTime, default=datetime.utcnow)
    gmt_modified = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class SemDatasourceEntity(_SemBase):
    """L0: semantic space registration, one row per datasource connection."""

    __tablename__ = "sem_datasource"

    conn_id = Column(String(128), unique=True, nullable=False)
    conn_name = Column(String(256))
    db_type = Column(String(64))
    status = Column(String(32), default="not_activated")
    space_name = Column(String(256))
    embedding_model = Column(String(128))
    chunk_count = Column(Integer, default=0)
    table_count = Column(Integer, default=0)
    last_sync_at = Column(DateTime)
    activated_at = Column(DateTime)
    description = Column(Text)


class SemTableEntity(_SemBase):
    """L1: synced table snapshot."""

    __tablename__ = "sem_table"
    __table_args__ = (UniqueConstraint("ds_id", "table_name", name="uk_sem_table"),)

    ds_id = Column(Integer, index=True, nullable=False)
    table_name = Column(String(256), nullable=False)
    table_comment = Column(Text)
    table_type = Column(String(32), default="table")
    row_count_est = Column(Integer)
    is_whitelisted = Column(Boolean, default=False)
    is_sensitive = Column(Boolean, default=False)
    status = Column(String(32), default="active")
    sync_version = Column(Integer, default=1)
    last_sync_at = Column(DateTime)


class SemColumnEntity(_SemBase):
    """L1: synced column snapshot."""

    __tablename__ = "sem_column"
    __table_args__ = (
        UniqueConstraint("ds_id", "table_id", "column_name", name="uk_sem_column"),
    )

    ds_id = Column(Integer, index=True, nullable=False)
    table_id = Column(Integer, index=True, nullable=False)
    column_name = Column(String(256), nullable=False)
    column_type = Column(String(128))
    column_comment = Column(Text)
    is_pk = Column(Boolean, default=False)
    is_fk = Column(Boolean, default=False)
    is_sensitive = Column(Boolean, default=False)
    is_enum = Column(Boolean, default=False)
    enum_values = Column(Text)
    status = Column(String(32), default="active")
    sync_version = Column(Integer, default=1)
    last_sync_at = Column(DateTime)


class SemEntryEntity(_SemBase):
    """L2: semantic annotation (table/column description, enum, synonyms)."""

    __tablename__ = "sem_entry"

    ds_id = Column(Integer, index=True, nullable=False)
    entry_type = Column(String(32), nullable=False)
    target_id = Column(Integer, index=True)
    entry_name = Column(String(256))
    entry_comment = Column(Text)
    synonyms = Column(Text)
    entry_definition = Column(Text)
    status = Column(String(32), default="draft")
    version = Column(Integer, default=1)
    provenance = Column(String(32), default="llm_draft")
    suite_id = Column(String(128))
    publish_version = Column(Integer)
    last_publish_at = Column(DateTime)


class SemMetricEntity(_SemBase):
    """L3: metric identity; caliber payloads live in SemMetricVersionEntity."""

    __tablename__ = "sem_metric"
    __table_args__ = (UniqueConstraint("ds_id", "metric_name", name="uk_sem_metric"),)

    ds_id = Column(Integer, index=True, nullable=False)
    metric_name = Column(String(256), nullable=False)
    metric_comment = Column(Text)
    metric_type = Column(String(32), default="atomic")
    metric_definition = Column(Text)
    formula = Column(Text)
    base_metrics = Column(Text)
    dimensions = Column(Text)
    status = Column(String(32), default="draft")
    version = Column(Integer, default=0)
    provenance = Column(String(32), default="manual")
    suite_id = Column(String(128))
    publish_version = Column(Integer)
    last_publish_at = Column(DateTime)


class SemMetricVersionEntity(_SemBase):
    """L3: versioned caliber payload (what suites pin and citations reference)."""

    __tablename__ = "sem_metric_version"
    __table_args__ = (
        UniqueConstraint("metric_id", "version", name="uk_sem_metric_version"),
    )

    metric_id = Column(Integer, index=True, nullable=False)
    version = Column(Integer, nullable=False)
    metric_definition = Column(Text)
    formula = Column(Text)
    base_metrics = Column(Text)
    dimensions = Column(Text)
    change_note = Column(Text)
    published_at = Column(DateTime)
    published_by = Column(String(128))


class SemRelationEntity(_SemBase):
    """L4: join graph edge (fk / inferred / manual)."""

    __tablename__ = "sem_relation"

    ds_id = Column(Integer, index=True, nullable=False)
    left_table_id = Column(Integer)
    left_column_id = Column(Integer)
    right_table_id = Column(Integer)
    right_column_id = Column(Integer)
    relation_type = Column(String(32), default="fk")
    join_condition = Column(Text)
    usage_count = Column(Integer, default=0)
    confidence = Column(Float)
    status = Column(String(32), default="active")
    provenance = Column(String(32), default="manual")
    last_used_at = Column(DateTime)


class SemExampleEntity(_SemBase):
    """L5: verified Q->SQL few-shot example."""

    __tablename__ = "sem_example"

    ds_id = Column(Integer, index=True, nullable=False)
    example_name = Column(String(256))
    question = Column(Text)
    sql_text = Column(Text)
    explanation = Column(Text)
    linked_metrics = Column(Text)
    linked_tables = Column(Text)
    use_count = Column(Integer, default=0)
    source = Column(String(32), default="manual")
    src_conv_id = Column(String(128))
    src_example_id = Column(Integer)
    status = Column(String(32), default="draft")
    publish_version = Column(Integer)
    last_publish_at = Column(DateTime)


class SemRuleEntity(_SemBase):
    """L6: guardrail rule (readonly / tenant / soft_delete / whitelist / ...)."""

    __tablename__ = "sem_rule"

    ds_id = Column(Integer, index=True, nullable=False)
    rule_name = Column(String(256))
    rule_type = Column(String(64), nullable=False)
    rule_definition = Column(Text)
    rule_condition = Column(Text)
    rule_action = Column(Text)
    priority = Column(Integer, default=100)
    status = Column(String(32), default="active")
    provenance = Column(String(32), default="manual")


class SemPublishLogEntity(_SemBase):
    """Publish audit trail (chunk ids kept for rollback / delete-by-id)."""

    __tablename__ = "sem_publish_log"

    ds_id = Column(Integer, index=True, nullable=False)
    publish_type = Column(String(32))
    entry_ids = Column(Text)
    chunk_ids = Column(Text)
    version = Column(Integer)
    change_note = Column(Text)
    published_at = Column(DateTime, default=datetime.utcnow)
    published_by = Column(String(128))


class SemDatasourceDao(BaseDao):
    """Dao for semantic space registration."""

    def get(self, ds_id: int) -> Optional[SemDatasourceEntity]:
        session = self.get_raw_session()
        try:
            return (
                session.query(SemDatasourceEntity)
                .filter(SemDatasourceEntity.id == ds_id)
                .first()
            )
        finally:
            session.close()

    def get_by_conn(self, conn_id: str) -> Optional[SemDatasourceEntity]:
        session = self.get_raw_session()
        try:
            return (
                session.query(SemDatasourceEntity)
                .filter(SemDatasourceEntity.conn_id == conn_id)
                .first()
            )
        finally:
            session.close()

    def ensure_space(
        self, conn_id: str, conn_name: str, db_type: str
    ) -> SemDatasourceEntity:
        """Auto-register a semantic space (idempotent, not_activated)."""
        space = self.get_by_conn(conn_id)
        if space:
            return space
        space = SemDatasourceEntity(
            conn_id=conn_id,
            conn_name=conn_name or conn_id,
            db_type=db_type,
            status="not_activated",
            space_name=f"semantic::{conn_id}",
        )
        session = self.get_raw_session()
        session.expire_on_commit = False
        try:
            session.add(space)
            session.commit()
            return space
        finally:
            session.close()

    def list_spaces(self) -> List[SemDatasourceEntity]:
        session = self.get_raw_session()
        try:
            return session.query(SemDatasourceEntity).all()
        finally:
            session.close()


class SemTableDao(BaseDao):
    def list_by_ds(
        self, ds_id: int, status: Optional[str] = None
    ) -> List[SemTableEntity]:
        session = self.get_raw_session()
        try:
            q = session.query(SemTableEntity).filter(SemTableEntity.ds_id == ds_id)
            if status:
                q = q.filter(SemTableEntity.status == status)
            return q.all()
        finally:
            session.close()

    def get_by_name(self, ds_id: int, table_name: str) -> Optional[SemTableEntity]:
        session = self.get_raw_session()
        try:
            return (
                session.query(SemTableEntity)
                .filter(
                    SemTableEntity.ds_id == ds_id,
                    SemTableEntity.table_name == table_name,
                )
                .first()
            )
        finally:
            session.close()


class SemColumnDao(BaseDao):
    def list_by_table(
        self, ds_id: int, table_id: int, status: Optional[str] = None
    ) -> List[SemColumnEntity]:
        session = self.get_raw_session()
        try:
            q = session.query(SemColumnEntity).filter(
                SemColumnEntity.ds_id == ds_id,
                SemColumnEntity.table_id == table_id,
            )
            if status:
                q = q.filter(SemColumnEntity.status == status)
            return q.all()
        finally:
            session.close()

    def get_by_name(
        self, ds_id: int, table_id: int, column_name: str
    ) -> Optional[SemColumnEntity]:
        session = self.get_raw_session()
        try:
            return (
                session.query(SemColumnEntity)
                .filter(
                    SemColumnEntity.ds_id == ds_id,
                    SemColumnEntity.table_id == table_id,
                    SemColumnEntity.column_name == column_name,
                )
                .first()
            )
        finally:
            session.close()


class SemEntryDao(BaseDao):
    def list_by_ds(
        self, ds_id: int, status: Optional[str] = None
    ) -> List[SemEntryEntity]:
        session = self.get_raw_session()
        try:
            q = session.query(SemEntryEntity).filter(SemEntryEntity.ds_id == ds_id)
            if status:
                q = q.filter(SemEntryEntity.status == status)
            return q.all()
        finally:
            session.close()

    def get(self, entry_id: int) -> Optional[SemEntryEntity]:
        session = self.get_raw_session()
        try:
            return (
                session.query(SemEntryEntity)
                .filter(SemEntryEntity.id == entry_id)
                .first()
            )
        finally:
            session.close()

    def mark_stale(self, ds_id: int, entry_type: str, target_ids: List[int]) -> int:
        if not target_ids:
            return 0
        session = self.get_raw_session()
        try:
            n = (
                session.query(SemEntryEntity)
                .filter(
                    SemEntryEntity.ds_id == ds_id,
                    SemEntryEntity.entry_type == entry_type,
                    SemEntryEntity.target_id.in_(target_ids),
                    SemEntryEntity.status.in_(["draft", "published"]),
                )
                .update({"status": "stale"}, synchronize_session=False)
            )
            session.commit()
            return int(n or 0)
        finally:
            session.close()


class SemMetricDao(BaseDao):
    def get(self, metric_id: int) -> Optional[SemMetricEntity]:
        session = self.get_raw_session()
        try:
            return (
                session.query(SemMetricEntity)
                .filter(SemMetricEntity.id == metric_id)
                .first()
            )
        finally:
            session.close()

    def get_by_name(self, ds_id: int, metric_name: str) -> Optional[SemMetricEntity]:
        session = self.get_raw_session()
        try:
            return (
                session.query(SemMetricEntity)
                .filter(
                    SemMetricEntity.ds_id == ds_id,
                    SemMetricEntity.metric_name == metric_name,
                )
                .first()
            )
        finally:
            session.close()

    def list_by_ds(
        self, ds_id: int, status: Optional[str] = None
    ) -> List[SemMetricEntity]:
        session = self.get_raw_session()
        try:
            q = session.query(SemMetricEntity).filter(SemMetricEntity.ds_id == ds_id)
            if status:
                q = q.filter(SemMetricEntity.status == status)
            return q.all()
        finally:
            session.close()


class SemMetricVersionDao(BaseDao):
    def latest(self, metric_id: int) -> Optional[SemMetricVersionEntity]:
        session = self.get_raw_session()
        try:
            return (
                session.query(SemMetricVersionEntity)
                .filter(SemMetricVersionEntity.metric_id == metric_id)
                .order_by(SemMetricVersionEntity.version.desc())
                .first()
            )
        finally:
            session.close()


class SemPublishLogDao(BaseDao):
    def append(self, log: SemPublishLogEntity) -> SemPublishLogEntity:
        session = self.get_raw_session()
        session.expire_on_commit = False
        try:
            session.add(log)
            session.commit()
            return log
        finally:
            session.close()


class SemExampleDao(BaseDao):
    def list_by_ds(
        self, ds_id: int, status: Optional[str] = None
    ) -> List[SemExampleEntity]:
        session = self.get_raw_session()
        try:
            q = session.query(SemExampleEntity).filter(SemExampleEntity.ds_id == ds_id)
            if status:
                q = q.filter(SemExampleEntity.status == status)
            return q.all()
        finally:
            session.close()


class SemRuleDao(BaseDao):
    def list_by_ds(
        self, ds_id: int, status: Optional[str] = None
    ) -> List[SemRuleEntity]:
        session = self.get_raw_session()
        try:
            q = session.query(SemRuleEntity).filter(SemRuleEntity.ds_id == ds_id)
            if status:
                q = q.filter(SemRuleEntity.status == status)
            return q.all()
        finally:
            session.close()


def dump_json(value: Any) -> Optional[str]:
    """Public helper for JSON-text columns."""
    return _dumps(value)


def load_json(text: Optional[str]) -> Any:
    """Public helper for JSON-text columns."""
    return _loads(text)


def filters_to_dict(entity: Any, keys: List[str]) -> Dict[str, Any]:
    """Project an entity to a plain dict (for API/response mapping)."""
    return {k: getattr(entity, k, None) for k in keys}
