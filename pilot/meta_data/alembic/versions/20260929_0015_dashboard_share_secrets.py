"""Manage recoverable share credentials in the metadata migration chain.

Existing installations may already have this table from the preview runtime.
Upgrade preserves their ciphertext; downgrade explicitly removes the recovery
copies without changing the separate share grants or their token hashes.
"""

import sqlalchemy as sa
from alembic import op

revision = "20260929_dashboard_share_secrets"
down_revision = "20260926_upstream_trace_link"
branch_labels = None
depends_on = None

TABLE = "dbgpt_dashboard_share_secret"


def upgrade():
    if not sa.inspect(op.get_bind()).has_table(TABLE):
        op.create_table(
            TABLE,
            sa.Column("token_hash", sa.String(64), primary_key=True),
            sa.Column("ciphertext", sa.String(512), nullable=False),
        )


def downgrade():
    if sa.inspect(op.get_bind()).has_table(TABLE):
        op.drop_table(TABLE)
