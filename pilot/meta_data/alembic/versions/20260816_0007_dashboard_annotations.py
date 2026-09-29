"""Persist selection-aware Dashboard annotations and Agent proposals.

Revision ID: 20260816_dashboard_annotations
Revises: 20260814_dashboard_task_assets
Create Date: 2026-08-16
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.mysql import LONGTEXT

revision: str = "20260816_dashboard_annotations"
down_revision: Union[str, Sequence[str], None] = "20260814_dashboard_task_assets"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = "dbgpt_dashboard_annotation"


def _json_text_type():
    return sa.Text().with_variant(LONGTEXT(), "mysql")


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if TABLE in inspector.get_table_names():
        return
    op.create_table(
        TABLE,
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("dashboard_id", sa.String(64), nullable=False),
        sa.Column("actor_id", sa.String(255), nullable=False),
        sa.Column("conversation_id", sa.String(255), nullable=True),
        sa.Column("source_turn_id", sa.String(64), nullable=True),
        sa.Column("base_revision", sa.Integer(), nullable=False),
        sa.Column("target_json", _json_text_type(), nullable=False),
        sa.Column("prompt", _json_text_type(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("proposal_json", _json_text_type(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.Column("gmt_created", sa.DateTime(), nullable=False),
        sa.Column("gmt_modified", sa.DateTime(), nullable=False),
    )
    for name, columns in (
        ("ix_dbgpt_dashboard_annotation_dashboard_id", ["dashboard_id"]),
        ("ix_dbgpt_dashboard_annotation_actor_id", ["actor_id"]),
        ("ix_dbgpt_dashboard_annotation_conversation_id", ["conversation_id"]),
        ("ix_dbgpt_dashboard_annotation_source_turn_id", ["source_turn_id"]),
        ("ix_dbgpt_dashboard_annotation_base_revision", ["base_revision"]),
        ("ix_dbgpt_dashboard_annotation_status", ["status"]),
        ("ix_dbgpt_dashboard_annotation_resolved_at", ["resolved_at"]),
        ("ix_dbgpt_dashboard_annotation_gmt_created", ["gmt_created"]),
    ):
        op.create_index(name, TABLE, columns)


def downgrade() -> None:
    if TABLE in sa.inspect(op.get_bind()).get_table_names():
        op.drop_table(TABLE)
