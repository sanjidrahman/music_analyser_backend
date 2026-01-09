"""add_file_type_column_to_recordings

Revision ID: 7fb235905587
Revises: 370059d9bf57
Create Date: 2026-01-08 21:16:54.442926

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7fb235905587'
down_revision: Union[str, None] = '370059d9bf57'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add file_type column with default value 'recording'
    op.add_column('recordings', sa.Column('file_type', sa.String(), nullable=False, server_default='recording'))


def downgrade() -> None:
    # Remove file_type column
    op.drop_column('recordings', 'file_type')