"""Add private screenshot covers without modifying historical dashboard data."""

from alembic import op
from dbgpt_app.openapi.api_v1.dashboard.covers import DashboardCoverEntity

revision = "20260908_dashboard_covers"
down_revision = "20260907_dashboard_feedback"
branch_labels = None
depends_on = None


def upgrade():
    DashboardCoverEntity.__table__.create(op.get_bind(), checkfirst=True)


def downgrade():
    DashboardCoverEntity.__table__.drop(op.get_bind(), checkfirst=True)
