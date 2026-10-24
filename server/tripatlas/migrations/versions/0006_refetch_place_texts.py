"""places: fetch the texts again (children's text no longer falls back to the whole country)

Revision ID: b8e1f6a2c4d9
Revises: 9a4f2c7e1d36
Create Date: 2026-10-25 01:30:00

"""
from typing import Sequence, Union

from alembic import op


revision: str = 'b8e1f6a2c4d9'
down_revision: Union[str, Sequence[str], None] = '9a4f2c7e1d36'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("DELETE FROM places")   # a cache: looked up again the next time a place is shown


def downgrade() -> None:
    pass
