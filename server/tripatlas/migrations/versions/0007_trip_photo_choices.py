"""which photos belong to a trip: none, or single ones taken out

Revision ID: 4d7a1e9b3f52
Revises: b8e1f6a2c4d9
Create Date: 2026-10-25 16:30:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '4d7a1e9b3f52'
down_revision: Union[str, Sequence[str], None] = 'b8e1f6a2c4d9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'trip_photo_choices',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tracker_id', sa.Integer(), nullable=False),
        sa.Column('day_key', sa.String(length=10), nullable=False),
        sa.Column('no_photos', sa.Boolean(), nullable=False),
        sa.Column('excluded', sa.JSON(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_by', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['tracker_id'], ['trackers.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['updated_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tracker_id', 'day_key'),
    )


def downgrade() -> None:
    op.drop_table('trip_photo_choices')
