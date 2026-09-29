"""Add revocable and expiring dashboard share tokens.

Revision ID: 20260812_dashboard_v27
Revises: 20260811_dashboard_v24
Create Date: 2026-08-12
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260812_dashboard_v27"
down_revision: Union[str, None] = "20260811_dashboard_v24"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = "dbgpt_dashboard_share"


def upgrade() -> None:
    if TABLE in sa.inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        TABLE,
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("dashboard_id", sa.String(length=64), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("created_by", sa.String(length=255), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column(
            "gmt_created", sa.DateTime(), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash", name="uk_dashboard_share_token"),
    )
    op.create_index("ix_dbgpt_dashboard_share_dashboard_id", TABLE, ["dashboard_id"])
    op.create_index("ix_dbgpt_dashboard_share_revision", TABLE, ["revision"])
    op.create_index("ix_dbgpt_dashboard_share_token_hash", TABLE, ["token_hash"])
    op.create_index("ix_dbgpt_dashboard_share_created_by", TABLE, ["created_by"])
    op.create_index("ix_dbgpt_dashboard_share_expires_at", TABLE, ["expires_at"])
    op.create_index("ix_dbgpt_dashboard_share_revoked_at", TABLE, ["revoked_at"])

    # Existing v1-v2.6 links remain valid and become manageable immediately.
    op.get_bind().execute(
        sa.text(
            """
            INSERT INTO dbgpt_dashboard_share
                (dashboard_id, revision, token_hash, created_by, gmt_created)
            SELECT r.dashboard_id, r.revision, r.share_token_hash,
                   d.owner_id, r.gmt_published
            FROM dbgpt_dashboard_revision AS r
            JOIN dbgpt_dashboard AS d ON d.id = r.dashboard_id
            """
        )
    )


def downgrade() -> None:
    if TABLE in sa.inspect(op.get_bind()).get_table_names():
        op.drop_table(TABLE)
