"""Recognize the deployed v3.8 Dashboard metadata stamp.

Revision ID: 2757edbd890f
Revises: cd2ea32f532b
Create Date: 2026-08-30 01:44:37.823601

The original source was absent from the v9.0 workspace, while deployed local
metadata databases were already stamped with this revision.  The surviving
CPython bytecode in the validated v3.8 workspace confirms that both migration
functions were no-ops and that the parent revision was ``cd2ea32f532b``.
"""

from typing import Sequence, Union

revision: str = "2757edbd890f"
down_revision: Union[str, None] = "cd2ea32f532b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """No schema change; this revision records migration continuity."""


def downgrade() -> None:
    """No schema change; this revision records migration continuity."""
