"""Add personal folders and explicitly granted live-data shares.

Historical version pruning is an explicit maintenance operation after backup,
never a destructive side effect of a schema migration.
"""

from alembic import op
from dbgpt_app.openapi.api_v1.dashboard.folders import (
    DashboardFolderEntity,
    DashboardFolderItemEntity,
)
from dbgpt_app.openapi.api_v1.dashboard.live_share import DashboardLiveShareEntity

revision = "20260907_dashboard_feedback"
down_revision = "20260831_dashboard_edit_versions"
branch_labels = None
depends_on = None


def upgrade():
    for model in (
        DashboardFolderEntity,
        DashboardFolderItemEntity,
        DashboardLiveShareEntity,
    ):
        model.__table__.create(op.get_bind(), checkfirst=True)


def downgrade():
    for model in (
        DashboardLiveShareEntity,
        DashboardFolderItemEntity,
        DashboardFolderEntity,
    ):
        model.__table__.drop(op.get_bind(), checkfirst=True)
