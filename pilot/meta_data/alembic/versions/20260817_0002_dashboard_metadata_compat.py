"""Recognize the deployed Dashboard metadata compatibility stamp.

Revision ID: cd2ea32f532b
Revises: f8bd7ecc3d5f
Create Date: 2026-08-17

The deployed local database is stamped with this no-op revision.  Omitting
the revision file makes Alembic reject an otherwise fully migrated database
before DB-GPT can start.
"""

from typing import Sequence, Union

revision: str = "cd2ea32f532b"
down_revision: Union[str, None] = "f8bd7ecc3d5f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """No schema change; this revision records migration continuity."""


def downgrade() -> None:
    """No schema change; this revision records migration continuity."""
