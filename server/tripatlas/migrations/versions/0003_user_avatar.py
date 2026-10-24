"""profile pictures

Revision ID: 3b1d6f0a9c21
Revises: ef65734af718
Create Date: 2026-10-24 22:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '3b1d6f0a9c21'
down_revision: Union[str, Sequence[str], None] = 'ef65734af718'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('users') as b:
        b.add_column(sa.Column('avatar', sa.LargeBinary(), nullable=True))
        b.add_column(sa.Column('avatar_updated', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('users') as b:
        b.drop_column('avatar_updated')
        b.drop_column('avatar')
