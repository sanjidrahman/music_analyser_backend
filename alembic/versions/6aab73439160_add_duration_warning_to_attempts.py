"""add_duration_warning_to_attempts

Revision ID: 6aab73439160
Revises: 7fb235905587
Create Date: 2026-01-09 10:41:33.575269

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6aab73439160'
down_revision: Union[str, None] = '7fb235905587'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add duration_warning column as JSONB (stored as JSON in SQLAlchemy)
    op.add_column('attempts', sa.Column('duration_warning', sa.JSON(), nullable=True))


def downgrade() -> None:
    # Remove duration_warning column
    op.drop_column('attempts', 'duration_warning')