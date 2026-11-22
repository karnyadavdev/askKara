"""user profile name and avatar

Revision ID: f847c9c9140c
Revises: d58da3b609ab
Create Date: 2026-11-21 07:43:38.905214

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f847c9c9140c'
down_revision: Union[str, Sequence[str], None] = 'd58da3b609ab'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('display_name', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('avatar_key', sa.String(length=255), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('avatar_key')
        batch_op.drop_column('display_name')
