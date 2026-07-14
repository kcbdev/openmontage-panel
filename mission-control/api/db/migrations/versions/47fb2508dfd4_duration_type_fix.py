"""duration_type_fix

Revision ID: 47fb2508dfd4
Revises: 2a962e619a19
Create Date: 2026-07-14 09:24:00.663405
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '47fb2508dfd4'
down_revision: Union[str, None] = '2a962e619a19'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE projects ALTER COLUMN duration_target_seconds "
        "TYPE INTEGER USING duration_target_seconds::integer"
    )


def downgrade() -> None:
    op.alter_column('projects', 'duration_target_seconds',
               existing_type=sa.Integer(),
               type_=sa.VARCHAR(),
               existing_nullable=True)
