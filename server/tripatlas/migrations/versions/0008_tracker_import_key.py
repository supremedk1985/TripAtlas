"""trackers: hide day trips without photos; key for automatic imports

Revision ID: 6c3b8e2a9d17
Revises: 4d7a1e9b3f52
Create Date: 2026-10-25 18:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '6c3b8e2a9d17'
down_revision: Union[str, Sequence[str], None] = '4d7a1e9b3f52'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('trackers') as b:
        b.add_column(sa.Column('hide_empty_day_trips', sa.Boolean(), nullable=False, server_default=sa.false()))
        b.add_column(sa.Column('import_key_hash', sa.String(length=64), nullable=True))
        b.create_unique_constraint('uq_trackers_import_key_hash', ['import_key_hash'])


def downgrade() -> None:
    with op.batch_alter_table('trackers') as b:
        b.drop_constraint('uq_trackers_import_key_hash', type_='unique')
        b.drop_column('import_key_hash')
        b.drop_column('hide_empty_day_trips')
