"""places: fetch again where the article was in another language

Until 0.1.0 a place without an article in the reader's language got the English one. Lookups now prefer the
municipality's or region's article in the reader's language; forgetting these cached places makes them fetched
again the next time they are shown.

Revision ID: 7c2e9d41b5a0
Revises: 3b1d6f0a9c21
Create Date: 2026-10-24 23:10:00

"""
from typing import Sequence, Union

from alembic import op


revision: str = '7c2e9d41b5a0'
down_revision: Union[str, Sequence[str], None] = '3b1d6f0a9c21'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "DELETE FROM places WHERE article_url IS NOT NULL "
        "AND article_url NOT LIKE 'https://' || lang || '.wikipedia.org/%'"
    )


def downgrade() -> None:
    pass   # nothing to restore: the places are fetched again on demand
