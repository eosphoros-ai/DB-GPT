"""Add the official observability link to existing chat history databases."""

import sqlalchemy as sa
from alembic import op

revision = "20260926_upstream_trace_link"
down_revision = "20260908_dashboard_covers"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for table, trace_length in (("chat_history_message", 128), ("gpts_messages", 64)):
        if not inspector.has_table(table):
            # Fresh installs create the chat tables from the current ORM models.
            continue
        if "trace_id" not in {column["name"] for column in inspector.get_columns(table)}:
            op.add_column(
                table, sa.Column("trace_id", sa.String(trace_length), nullable=True)
            )
        index = f"ix_{table}_trace_id"
        if index not in {item["name"] for item in sa.inspect(bind).get_indexes(table)}:
            op.create_index(index, table, ["trace_id"])


def downgrade():
    # Retain nullable trace links so a downgrade cannot erase trace history.
    pass
