"""add member_id to action_request

Revision ID: 56c3c6888b23
Revises: 1243680ff21b
Create Date: 2026-08-09 21:39:22.736628

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = '56c3c6888b23'
down_revision: Union[str, Sequence[str], None] = '1243680ff21b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('action_request', schema=None) as batch_op:
        batch_op.add_column(sa.Column('member_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            'fk_action_request_member_id', 'household_member', ['member_id'], ['id']
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('action_request', schema=None) as batch_op:
        batch_op.drop_constraint('fk_action_request_member_id', type_='foreignkey')
        batch_op.drop_column('member_id')
