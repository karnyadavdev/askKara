"""conversations

Revision ID: a1b2c3d4e5f6
Revises: eecd341cde0d
Create Date: 2026-10-14 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'eecd341cde0d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'conversations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('conversations', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_conversations_user_id'), ['user_id'], unique=False)

    with op.batch_alter_table('queries', schema=None) as batch_op:
        batch_op.add_column(sa.Column('conversation_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            'fk_queries_conversation_id', 'conversations', ['conversation_id'], ['id'], ondelete='CASCADE'
        )
        batch_op.create_index(batch_op.f('ix_queries_conversation_id'), ['conversation_id'], unique=False)

    conn = op.get_bind()
    rows = conn.execute(
        sa.text("SELECT id, user_id, question, created_at FROM queries ORDER BY id")
    ).fetchall()
    for row in rows:
        title = " ".join((row[2] or "").split())[:60] or "Untitled"
        conn.execute(
            sa.text(
                "INSERT INTO conversations (user_id, title, created_at, updated_at) "
                "VALUES (:user_id, :title, :created_at, :created_at)"
            ),
            {"user_id": row[1], "title": title, "created_at": row[3]},
        )
        conn.execute(
            sa.text("UPDATE queries SET conversation_id = (SELECT MAX(id) FROM conversations) WHERE id = :qid"),
            {"qid": row[0]},
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('queries', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_queries_conversation_id'))
        batch_op.drop_constraint('fk_queries_conversation_id', type_='foreignkey')
        batch_op.drop_column('conversation_id')

    with op.batch_alter_table('conversations', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_conversations_user_id'))

    op.drop_table('conversations')
