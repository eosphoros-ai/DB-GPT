"""Preserve the deployed post-annotation migration stamp.

Revision ID: f8bd7ecc3d5f
Revises: 20260816_dashboard_annotations
Create Date: 2026-08-17

This revision was emitted after the annotation migration without a schema
change.  Keeping it in the repository lets databases created by prior local
Dashboard deliveries remain resolvable by Alembic.
"""

from typing import Sequence, Union

revision: str = "f8bd7ecc3d5f"
down_revision: Union[str, None] = "20260816_dashboard_annotations"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """No schema change; this revision records migration continuity."""


def downgrade() -> None:
    """No schema change; this revision records migration continuity."""
